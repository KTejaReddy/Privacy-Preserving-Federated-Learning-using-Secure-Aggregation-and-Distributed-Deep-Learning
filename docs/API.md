# API Reference

Base path: `/api/v1` · Interactive docs at `/docs` (OpenAPI/Swagger).

**Authentication:** `Authorization: Bearer <access_token>` for all protected endpoints. Tokens from `POST /auth/login` or `POST /auth/register`.

## Auth

| Method | Path | Description |
|---|---|---|
| POST | `/auth/register` | Create account (roles: `admin`, `coordinator`, `org_admin`, `ml_engineer`, `research_scientist`) |
| POST | `/auth/login` | `{email, password}` → `{access_token, refresh_token, user}` |
| POST | `/auth/refresh` | Rotate access token from a refresh token |
| GET | `/auth/me` | Current user + `permissions` (RBAC) + `role_label` + `feature_flags` |
| POST | `/auth/logout` | Log out (audited) |

## Dashboard & Organizations

| Method | Path | Description |
|---|---|---|
| GET | `/dashboard` | Executive KPIs: orgs, nodes online, datasets, jobs, rounds, privacy budget, model versions, activity feed |
| GET | `/organizations` | List (search `?q=`) |
| POST | `/organizations` | Create |
| PUT | `/organizations/{id}` | Update |
| DELETE | `/organizations/{id}` | Remove (RBAC: `orgs:manage`) |
| GET | `/organizations/stats` | Totals + industry breakdown |

## Nodes & Datasets

| Method | Path | Description |
|---|---|---|
| GET/POST | `/nodes` | List / register node (mTLS cert simulated on register) |
| GET | `/nodes/health` | Online/degraded/offline counts, avg latency, mTLS |
| GET | `/nodes/{id}/events` · `/nodes/{id}/handshake` | Node event history / identity handshake |
| GET/POST/DELETE | `/datasets` · `/datasets/{id}` | Dataset registry (metadata only — no raw data) |
| GET | `/datasets/summary` | Total samples by industry |
| GET | `/datasets/schema/{features}` | Derived feature names |

## Training & Coordinator

| Method | Path | Description |
|---|---|---|
| GET/POST | `/training` | List / create training job |
| GET | `/training/stats` | Status + algorithm breakdown |
| GET | `/training/{id}` · `/training/{id}/rounds` | Job detail / per-round metrics |
| POST | `/training/{id}/action` | `start` / `pause` / `resume` / `cancel` |
| GET | `/coordinator/overview` | Round + approval KPIs |
| GET | `/coordinator/approvals` | Queue of jobs awaiting sign-off |
| POST | `/coordinator/approvals/{id}` | `{action: approve|reject}` |
| POST | `/coordinator/secure-aggregation/demo` | Live masked-aggregation handshake: `{clients, job_id?, round?}` → mask pairs, verified signatures, math check, protocol log |
| GET | `/coordinator/aggregation-logs` | Audit of every aggregation |

## Models, Evaluation, XAI

| Method | Path | Description |
|---|---|---|
| GET | `/models` | Model versions (`?job_id=`) |
| GET | `/models/stats` | Deployed/pending counts, best model |
| POST | `/models/{id}/approve|deploy|rollback|archive` | Version workflow (RBAC `models:deploy`) |
| POST | `/models/infer` | `{features, version_id?}` → prediction, probability, confidence, SHAP explanation |
| GET | `/evaluation` | Aggregate metrics across versions |
| GET | `/evaluation/compare?version_ids=1,2` | Per-version accuracy/P/R/F1 + best |
| GET | `/evaluation/confusion/{version_id}` | Reconstructed confusion matrix |
| GET | `/xai/explain?version_id=&sample_index=` | Kernel-SHAP explanation |
| GET | `/xai/importance?version_id=` | Permutation importance |
| GET | `/xai/fairness?version_id=&sensitive_feature=` | Demographic parity, equalized odds, disparate impact |
| GET | `/xai/bias-report` | Bias audit across versions |

## Monitor, Analytics, Reports, Audit

| Method | Path | Description |
|---|---|---|
| GET | `/monitor/overview` | Node sync grid + round summary |
| GET | `/monitor/timeline` | Recent node events |
| **WS** | `/monitor/ws` | **Realtime feed** — events: `round.complete`, `node.training`, `job.completed`, `job.failed`, `monitor.tick`, `federated.*` |
| GET | `/analytics/overview` | Accuracy/loss history, communication cost, node contribution, model drift, jobs by algorithm |
| GET | `/analytics/privacy` | ε budget accounting |
| GET | `/reports/types` · `/reports/generate?report_type=` | Report catalog / generation |
| GET | `/audit/logs` | Searchable audit log (`?action=&severity=&actor=&limit=`) |
| GET | `/audit/verify` | Hash-chain tamper verification |
| GET | `/audit/summary` | Counts by action/severity |

## AI Integrations (Bring Your Own Key)

| Method | Path | Description |
|---|---|---|
| GET | `/ai/specs` | Provider capability matrix |
| GET/POST/PUT/DELETE | `/ai/providers` · `/ai/providers/{id}` | Manage providers (keys AES-256 encrypted, masked in responses) |
| GET | `/ai/providers/available` | Fresh provider specs for the form |
| POST | `/ai/providers/{id}/test` | Live connectivity + latency check |
| POST | `/ai/chat` | `{provider_id, messages, model, temperature}` → LLM response (recorded to inference log) |
| GET/POST/DELETE | `/ai/prompts` | Prompt Studio templates |
| GET | `/ai/inference-logs` | Usage history (admin) |

## Lab, Admin, Settings

| Method | Path | Description |
|---|---|---|
| GET/POST | `/lab/experiments` | List / create experiment (`{name, algorithm, clients, rounds, data_distribution, node_failure_rate}`) |
| GET | `/lab/experiments/{id}` | Full results + accuracy curve |
| GET | `/lab/benchmark?distribution=&clients=&rounds=` | FedAvg vs FedProx vs FedAdam on identical data |
| GET/POST/PUT/DELETE | `/admin/users` · `/admin/users/{id}` | User management (admin only) |
| GET | `/admin/roles` | Role catalog |
| GET/PUT | `/admin/feature-flags` · `/admin/feature-flags/{key}` | Feature flags |
| GET/PUT | `/admin/settings` · `/admin/settings/{key}` | Platform settings |
| GET | `/admin/system` | System info |
| GET/PUT | `/settings/profile` | Own profile |
| POST | `/settings/change-password` | Password rotation |

## WebSocket feed

```
ws://<host>/api/v1/monitor/ws
```

Frames are JSON `{event, data}`. The frontend uses this for the Communication Monitor and to invalidate React Query caches, so dashboards stream live.
