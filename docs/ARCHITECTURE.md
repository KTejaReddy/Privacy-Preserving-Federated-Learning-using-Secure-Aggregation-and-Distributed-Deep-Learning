# Architecture Guide

## 1. System Overview

The platform is a **client-server federated learning control plane**:

- **Control plane (this repo)** — FastAPI service that orchestrates federated rounds, stores metadata, serves the web UI, and runs the secure aggregation math. It never receives raw training data.
- **Participating nodes** — registered compute endpoints (simulated in this build) that hold organization data, receive global weights, train locally, and return masked updates.
- **Web UI** — React SPA that talks to the control plane over REST + WebSocket.

## 2. Clean Architecture Layers

```
┌──────────────────────────────────────────────────────────┐
│  Presentation  → React pages (feature modules)           │
├──────────────────────────────────────────────────────────┤
│  API layer     → FastAPI routers (thin, HTTP concerns)   │
│                  deps.py: auth, RBAC, IP, DB dependencies│
├──────────────────────────────────────────────────────────┤
│  Service/Domain → federated engine, secure aggregation,  │
│                   XAI, AI gateway, audit, events          │
├──────────────────────────────────────────────────────────┤
│  Infrastructure → SQLAlchemy (Postgres/SQLite), Redis,   │
│                   Celery, WebSockets                     │
└──────────────────────────────────────────────────────────┘
```

**Dependency rule:** routers depend on the domain layer, never the other way. The domain layer is framework-agnostic (pure Python + numpy).

## 3. Key Modules

| Module | Path | Responsibility |
|---|---|---|
| Config | `app/core/config.py` | pydantic-settings, env-driven |
| Database | `app/core/database.py` | engine, session, `init_db` |
| Security | `app/core/security.py` | JWT, bcrypt, AES-GCM, RSA, key masking |
| RBAC | `app/core/rbac.py` | role → permission matrix |
| Audit | `app/core/audit.py` | append-only hash-chained log |
| Events | `app/core/events.py` | in-process event bus |
| Federated | `app/federated/` | `nn.py` trainer, `data.py` generators, `algorithms.py` optimizers, `client_selection.py`, `secure_aggregation.py`, `engine.py` orchestrator |
| XAI | `app/explainability/xai.py` | SHAP, importance, fairness, bias |
| AI gateway | `app/ai/providers.py` | BYOK provider registry + chat |
| Workers | `app/workers/` | Celery tasks, inline fallback, node simulator |
| WS | `app/ws/manager.py` | realtime broadcast |

## 4. The Federated Engine (`app/federated/engine.py`)

`FederatedEngine.run_job(config, nodes, datasets, on_event)` executes an entire training run:

1. Builds the global MLP from `hidden_layers`/`input_dim`.
2. For each round:
   - `client_selection.select_clients(...)` — random fraction of online nodes (seeded, reproducible).
   - Per client: generate a private non-IID partition → train locally → compute delta.
   - `secure_aggregation.secure_aggregate(...)` — mask, sign, encrypt, aggregate.
   - Apply optimizer (`fedavg` / `fedprox` / `fedadam`) to produce the next global model.
   - Evaluate on a shared held-out set; record metrics, communication bytes, ε consumed.
3. Returns per-round records + final model metadata.

**Reproducibility:** the ground-truth task is derived from the job seed (shared across clients and evaluation) so FedAvg can actually converge — a classic failure mode in toy FL demos.

## 5. Event Bus & Realtime

- `app/core/events.py` is a synchronous pub/sub bus.
- The worker publishes `round.complete`, `job.completed`, `monitor.tick`, etc.
- `app/ws/manager.py` fans events out to connected WebSocket clients (`/api/v1/monitor/ws`).
- The frontend `useRealtime` hook subscribes and invalidates React Query caches — so dashboards update without polling.

## 6. Security Architecture

- **Authentication** — JWT (HS256) access tokens + refresh tokens; passwords bcrypt-hashed.
- **Authorization** — `require_permission(Permission.X)` dependency reads the permission matrix.
- **Secrets** — AI API keys encrypted with AES-256-GCM (`encrypt_secret`), shown masked (`sk-…abcd`).
- **Audit** — every sensitive action appends a record whose `chain_hash = SHA256(prev_hash | canonical_payload)`. `verify_chain` recomputes and compares.
- **Rate limiting** — token bucket per client IP (429 with `Retry-After`).

## 7. Data Flow for One Federated Round

```
Coordinator ──▶ select clients ──▶ broadcast global weights
                                      │
            ┌─────────────────────────┼─────────────────────────┐
            ▼                         ▼                         ▼
        client A                 client B                 client C
        (local data)             (local data)             (local data)
            │ local train           │ local train           │ local train
            ▼                         ▼                         ▼
        mask + sign + AES         mask + sign + AES         mask + sign + AES
            └──────────────┬──────────┴────────────┬──────────┘
                           ▼                       ▼
                     server verifies sigs     cancels pairwise masks
                                    │
                                    ▼
                          optimizer (FedAvg/Prox/Adam)
                                    │
                                    ▼
                        evaluate → new global model
```

## 8. Frontend Architecture

- `src/lib/api.ts` — typed API client (throws on non-2xx, injects JWT).
- `src/auth.tsx` — `AuthProvider`, `RequireAuth`, `RequirePerm`, permission-aware navigation.
- `src/layout.tsx` — sidebar filtered by the user's permissions; section grouping.
- `src/ui.tsx` — design system (Card, Stat, Badge, Button, Modal, Tabs, Toasts).
- `src/charts.tsx` — reusable Recharts wrappers (curves, areas, bars, donuts).
- `src/pages/` — one page per module, data via TanStack Query, mutations invalidate caches.

## 9. Concurrency & Workers

- Celery is supported but optional: `USE_CELERY` is derived from env. Without a broker, `tasks.py` provides a **decorator fallback** so the same code path runs inline/threaded — zero-config local runs, real queues in production.
- The node simulator (`simulate_node_activity`) runs as a daemon thread in the API process, updating heartbeats and publishing monitor events.
