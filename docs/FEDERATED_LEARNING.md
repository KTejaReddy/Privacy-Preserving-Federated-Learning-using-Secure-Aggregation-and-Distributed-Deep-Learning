# Federated Learning Documentation

## The Engine (`backend/app/federated/`)

### `nn.py` — the trainer

A small, dependency-light **MLP** (`MLP(input_dim, hidden_layers, seed)`) implemented with numpy:

- Forward pass: `Linear → ReLU → … → Linear → Sigmoid`.
- Loss: binary cross-entropy with gradient clipping for stability.
- `train(X, y, epochs, batch_size, lr)` → dict with `weights`, `delta` (new − old, used for federated updates), `loss`, `accuracy`, `training_time_ms`.
- `flatten()` / `load_flattened()` — a **canonical serialization** of all parameters (weights then biases per layer). This is the wire format for global model broadcast. A subtle historical bug here (interleaved vs grouped layout) silently scrambled global weights — the round-trip is now unit-verified.

### `data.py` — realistic synthetic data

The hardest part of a believable FL demo is making the model *actually learn*. The generator:

1. Draws a **shared ground-truth weight vector** `w*` from the job seed.
2. Labels `y = sigmoid(X·w* + noise)` — every client and the evaluation set agree on the same task.
3. Applies per-client **covariate shift** controlled by `distribution`:
   - `iid` — identical feature distribution everywhere.
   - `non_iid` — feature means/rotations shift per client (realistic skew).
   - `pathological` — each client sees a disjoint label class (the hard case).
4. `evaluate(w, X_eval, y_eval)` — accuracy, precision, recall, F1.

### `algorithms.py` — server-side optimizers

| Algorithm | Update rule |
|---|---|
| **FedAvg** | `w ← w + Σ_k (n_k/N)·Δ_k` (sample-weighted average of deltas) |
| **FedProx** | adds proximal term `(μ/2)‖w_k − w‖²` to local loss; server averaging with μ tuning |
| **FedAdam** | `m ← β1·m + (1−β1)·g`; `v ← β2·v + (1−β2)·g²`; `w ← w + lr·m/(√v+ε)` over the aggregate gradient |

Each returns `(new_weights, stats)` with `method` metadata that flows into `AggregationLog`.

### `client_selection.py`

Seeded random fraction of online nodes (excludes `offline`, prefers higher trust). Reproducible given the same seed.

### `engine.py` — orchestration

`run_job(config, nodes, datasets, on_event)`:

1. Build global model, prepare evaluation set.
2. For each round: select clients → for each: local data → local train → delta → **secure aggregation** → optimizer → evaluate.
3. Tracks per-round: `accuracy`, `loss`, `precision/recall/f1`, `communication_bytes`, `aggregation_time_ms`, `privacy_budget_used`, per-client metrics.
4. Returns rounds + final model (weights, feature names, model hash, param count, communication totals, training time).

## Data flow & isolation

```
Global weights ──broadcast──▶ client k
                                 │  private partition (never leaves the node)
                                 ▼
                            local training (local_epochs, lr)
                                 │
                                 ▼
                              Δ_k (delta) ──masked + signed + AES-256-GCM──▶ server
                                                                              │
                                                         verify sigs → cancel masks → sum
                                                                              ▼
                                                              optimizer → next global model
```

Raw data never crosses the network; only deltas (and only encrypted/masked ones) do.

## Reproducibility

- `seed` in the job config seeds: ground truth `w*`, client partitions, evaluation set, client selection, model init.
- Two runs with identical config produce identical curves (secure aggregation uses deterministic HMAC masks).
- The evaluation set is drawn from the *same* task as client data — so convergence reflects true learning, not label leakage or a moving target (another classic demo bug: re-seeding the task per round, which we explicitly avoid).

## Communication accounting

Each round records:
- `upload_bytes = delta.size × 8 + 64` per client (payload + envelope overhead).
- `communication_bytes` per round and `total_communication_bytes` for the job.
- `aggregation_time_ms` (simulated cost proportional to client count).

These feed the Analytics "Communication Cost per Round" chart and the privacy view.

## Hyperparameter guidance

| Parameter | Typical | Notes |
|---|---|---|
| `client_fraction` | 0.6–0.8 | higher = more stable, more communication |
| `local_epochs` | 1–3 | higher local training can slow global convergence |
| `learning_rate` | 0.005–0.02 | FedAdam prefers lower |
| `mu` (FedProx) | 0.05 | only used by `fedprox` |
| `privacy_budget_per_round` | 0.5 | ε accounting, budget 8.0 |
| `noise` | 0.15 | label noise for realism |

## Limitations & next steps

- Data is synthetic (fully reproducible) — swap in `data.py` with real datasets, keeping the same `(X, y)` contract.
- Node computation is simulated server-side; production deployments would push local training to real edge workers via the API contract in `tasks.py`.
- Differential privacy is *accounted* (ε tracking) but not *added* — the reference implementation omits gradient clipping to keep FedAvg math exact. See `docs/SECURE_AGGREGATION.md` for how to add Gaussian noise per round.
