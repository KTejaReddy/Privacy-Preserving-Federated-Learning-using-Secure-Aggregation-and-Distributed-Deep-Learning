# Testing Guide

## Strategy

| Layer | Tool | Coverage |
|---|---|---|
| API smoke tests | pytest + FastAPI TestClient | auth, RBAC, all module reads, aggregation math, audit chain, full job lifecycle |
| Type safety | `tsc --noEmit` | entire frontend |
| Build | `vite build` | production bundle |
| Engine math | ad-hoc scripts (`python -c` / REPL) | gradient checks, round-trip serialization, convergence curves |
| CI | GitHub Actions | backend suite + frontend typecheck/build on every push/PR |

## Running the suite

```bash
cd backend && python -m pytest tests/ -v
cd frontend && npx tsc --noEmit && npm run build
```

## Backend suite (`backend/tests/test_api_smoke.py`)

Isolated environment: a temp SQLite file, `ENV=test`, demo data seeded through the real seeder (organizations, users, nodes, datasets, three fully-trained jobs).

| Test | Verifies |
|---|---|
| `test_health` | `/health` liveness |
| `test_auth_flow` | register → `/auth/me` returns user, role label, permission list |
| `test_rbac_enforcement` | org_admin is **denied** `admin:view` endpoints (403) while still able to read datasets |
| `test_module_read_endpoints` | ~30 read endpoints across every module return 200 |
| `test_secure_aggregation_demo` | mask pairs = N·(N−1), all signatures verified, `math_ok` true |
| `test_audit_chain_integrity` | `/audit/verify` reports an intact chain |
| `test_training_job_lifecycle` | create → coordinator approve → start → **completes with all rounds** → model version exists |

The lifecycle test is the most valuable regression guard: it exercises the engine, secure aggregation, persistence, the async task path, and version creation in one flow.

## Historical bugs these tests guard against

- Weight serialization mismatch between `flatten()` and `load_flattened()` (silently scrambled global weights — accuracy stuck at ~0.49).
- Ground-truth task re-seeded per round (clients chased a moving target — no convergence).
- Pairwise mask block-size bug when `param_count % 32 != 0`.
- Unmasked/untyped `request` params being parsed as query params (FastAPI 422s).
- Audited actions missing from the chain serializer (verify/write now share one canonical payload).
- Frontend: TanStack Query rejecting query functions with extra parameters; `Stat` rejecting `unknown` values.

## Adding tests

- **New endpoint** → add a row to `test_module_read_endpoints` and, for mutating paths, a focused test with the right role.
- **New engine behavior** → extend the lifecycle test or add a standalone pytest that calls `FederatedEngine().run_job` with a tiny config and asserts monotone-ish convergence.
- **Frontend** → keep `tsc --noEmit` green; the build failing on the CI catches broken imports and invalid JSX.

## Manual QA checklist

- [ ] Login with each of the 5 demo roles — sidebar & permissions differ.
- [ ] Run a secure aggregation demo (N=2…8) — mask pairs & verification scale correctly.
- [ ] Start a job as coordinator → rounds stream in the Communication Monitor (WebSocket live).
- [ ] Deploy a model version → Inference Playground returns prediction + SHAP explanation.
- [ ] Audit Center → *Verify chain integrity* reports intact.
- [ ] Federated Lab → run a benchmark + an experiment with a failure rate; check History.
- [ ] Frontend `npm run build` passes with no chunk warnings.
