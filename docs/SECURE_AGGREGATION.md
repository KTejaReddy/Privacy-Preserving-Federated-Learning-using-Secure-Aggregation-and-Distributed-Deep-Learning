# Secure Aggregation Documentation

Secure aggregation lets the server learn the **sum** of client updates without learning any individual update. This is the Bonawitz et al. (2017, IEEE S&P) construction, implemented in `backend/app/federated/secure_aggregation.py`.

## Protocol

### 1. Pairwise mask agreement
For an ordered pair of clients `(i, j)`, a shared secret is derived from the platform master secret and both client IDs:

```
mask_key(i,j) = HMAC-SHA256(master_secret, f"{i}:{j}:round")
mask(i,j)     = digest_stream(mask_key, param_count)   # deterministic pseudo-random vector
```

`digest_stream` expands the 32-byte key into a pseudo-random float vector of exactly `param_count` values via a SHA-256 counter chain — this is why the mask math is exact and reproducible, and why a block-size mismatch bug (historic) broke aggregation for non-multiples of 32.

### 2. Client-side masking
Each client `i` adds its outgoing masks and subtracts incoming ones:

```
masked_delta_i = delta_i + Σ_{j<i} mask(j,i) − Σ_{j>i} mask(i,j)
```

### 3. Signature + encryption
- **Integrity:** each masked delta is signed with the client's RSA-SHA256 private key.
- **Confidentiality:** the signed payload is encrypted with **AES-256-GCM** using a per-client key.

### 4. Server unmask + sum
The server verifies every signature, decrypts, and sums the masked deltas:

```
Σ_i masked_delta_i = Σ_i delta_i + Σ_{i<j} mask(i,j) − Σ_{i<j} mask(i,j) = Σ_i delta_i
```

Pairwise masks cancel **exactly** — the server only learns the aggregate.

### 5. Integrity verification
`math_ok = ‖Σ masked − Σ true‖ < 1e-6`, checked against the true deltas in the demonstration path. Every run appends an `AggregationLog` (masks cancelled, signatures verified, ε consumed) and an audit record.

## Crypto primitives

| Primitive | Use |
|---|---|
| HMAC-SHA256 | pairwise mask key derivation |
| SHA-256 | mask expansion (counter-chain digest stream) |
| RSA-2048 / SHA-256 | per-client signing + verification |
| AES-256-GCM | payload encryption at rest & in transit (simulated) |
| JWT (HS256) | API auth, not model updates |

All key material originates from `app.core.security` (`generate_rsa_keypair`, `aes_gcm_encrypt/decrypt`) and the `MASK_KEY_BYTES`/`RSA_KEY_BITS` settings.

## The demonstration endpoint

`POST /api/v1/coordinator/secure-aggregation/demo` runs the *entire* protocol live on fresh engine output:

1. Builds `N` client deltas from real local training.
2. Generates a fresh RSA identity per client.
3. Runs the full mask → sign → encrypt → verify → unmask → sum pipeline.
4. Returns `mask_pairs` (`N·(N−1)` directed pairs), `verified_signatures`, `math_ok`, the privacy ε consumed, and the full **protocol log** — rendered step-by-step in the Secure Aggregation page.

This is the academic-demonstration centerpiece: the math is real, the code path is the same one used by live training jobs.

## Privacy budget (ε accounting)

- `MAX_PRIVACY_BUDGET = 8.0` (configurable).
- Each round consumes `privacy_budget_per_round` ε.
- Analytics surfaces `budget_used`, `budget_remaining`, `utilization_pct`, `rounds_with_masking`.
- The system **tracks** but does not enforce a hard stop (enforcement is a policy decision per deployment).

> To add true differential privacy, clip each delta to norm `C` and add Gaussian noise `𝒩(0, σ²·C²)` with σ from the Gaussian mechanism for the target (ε, δ). The current build deliberately keeps FedAvg math exact for teaching clarity.

## Threat model

| Adversary capability | Outcome |
|---|---|
| Server is curious | Cannot see individual updates — only the masked aggregate |
| Eavesdropper on the wire | Sees only AES-256-GCM ciphertext |
| Client submits forged update | Rejected — RSA signature verification fails |
| Attacker mutates a stored update | Detected — `math_ok` / integrity verification fails |
| Attacker edits the audit log | Detected — SHA-256 hash chain breaks |

## Files

- `backend/app/federated/secure_aggregation.py` — masks, digest stream, aggregate, demo flow, JSON-safe serialization.
- `backend/app/api/routers/coordinator.py` — live demo endpoint + aggregation log query.
- `backend/app/core/security.py` — RSA + AES-GCM primitives.
- `backend/app/core/crypto.py` — legacy/utility crypto helpers.
