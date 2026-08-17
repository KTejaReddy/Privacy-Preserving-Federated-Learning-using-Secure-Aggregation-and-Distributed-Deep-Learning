# Developer Guide

## Prerequisites

- Python 3.12+
- Node.js 20+
- (optional) Docker for the full stack

## Setup

```bash
# backend
cd backend
python -m venv .venv
source .venv/Scripts/activate        # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt  # includes pytest

# frontend
cd ../frontend
npm install
```

## Running

```bash
# terminal 1 — API (seeds demo data on first boot, serves docs at /docs)
cd backend && uvicorn app.main:app --reload --port 8000

# terminal 2 — web app
cd frontend && npm run dev           # http://localhost:5173
```

The Vite dev server proxies `/api` and `/health` (including WebSocket upgrades) to `http://127.0.0.1:8000`.

## Where things live

```
backend/app/
  core/            cross-cutting: config, security, rbac, audit, events, crypto, ratelimit
  models/          SQLAlchemy models (single file: models.py)
  schemas/         Pydantic contracts (single file: schemas.py)
  federated/       the research core — trainer, data, algorithms, secure aggregation
  explainability/  XAI engine
  ai/              BYOK provider gateway
  api/routers/     one router per module (auth, orgs, nodes, datasets, training, ...)
  workers/         task queue + simulator
  ws/              websocket fan-out
  seed.py          demo seeder (idempotent)
  tests/           pytest suite
frontend/src/
  lib/api.ts       typed API client — ADD new endpoints here
  pages/           one page per module
  ui.tsx           design-system components
  charts.tsx       chart wrappers
  layout.tsx       shell + RBAC-filtered sidebar
  auth.tsx         auth context / guards
```

## Conventions

- **Routers are thin.** Query → validate via Pydantic → call domain logic → audit → return schema.
- **Never import routers from models.** Depend on `app.core.database.get_db`.
- **Add endpoints to `frontend/src/lib/api.ts`** with a typed return so pages stay type-safe.
- **RBAC:** every router declares `Depends(require_permission(Permission.X))` at the endpoint level; new permissions go in `rbac.py` with entries in `ROLE_PERMISSIONS`.
- **Audit:** write an audit record for any mutating action (`write_audit(db, action=..., ...)`).
- **Colors/styles:** use the Tailwind tokens from `tailwind.config.js` (`brand`, `ink`, `mint`, `warn`, `danger`); reuse `Card/Stat/Badge/Button` instead of ad-hoc markup.

## Adding a new module (checklist)

1. Model in `backend/app/models/models.py` (if persistent).
2. Schema in `backend/app/schemas/schemas.py`.
3. Router in `backend/app/api/routers/<name>.py`, then register in `main.py`.
4. Add read endpoints to the smoke test in `tests/test_api_smoke.py`.
5. Frontend: API methods in `lib/api.ts`, page in `pages/`, route + sidebar entry in `App.tsx` / `layout.tsx`.
6. Run: `python -m pytest tests/ -v`, `npx tsc --noEmit`, `npm run build`.

## Testing

```bash
cd backend && python -m pytest tests/ -v
cd frontend && npx tsc --noEmit && npm run build
```

## Useful commands

```bash
# reset demo data
cd backend && rm -f federated_platform.db

# run the federated engine standalone (no API)
cd backend && python -c "
from app.federated.engine import FederatedEngine
nodes = [{'id': i, 'name': f'c{i}', 'status': 'online', 'trust_score': 0.9} for i in range(1, 5)]
r = FederatedEngine().run_job({'algorithm': 'fedavg', 'total_rounds': 3, 'client_fraction': 1.0, 'learning_rate': 0.01, 'batch_size': 32, 'local_epochs': 2, 'mu': 0.0, 'secure_aggregation': True, 'privacy_budget_per_round': 0.5, 'hidden_layers': [16, 8], 'input_dim': 8, 'seed': 42, 'local_samples': 400, 'data_distribution': 'non_iid', 'noise': 0.15}, nodes, [])
print('final accuracy:', r['final_accuracy'])
"
```

## Troubleshooting

- **Port 8000 in use on Windows:** `netstat -ano | grep :8000` then `taskkill //F //PID <pid>`.
- **Frontend type errors after adding an API method:** check the query function signature — TanStack Query rejects queryFns with extra params; wrap them (`() => api.list()`).
- **Audit "tampering" on an old DB:** records written by an earlier build may use a different serializer — delete the DB and let it re-seed (`rm -f backend/federated_platform.db`).
