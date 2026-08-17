# Release Notes

## v1.0.0 — Initial Release

**Privacy-Preserving Federated Learning using Secure Aggregation and Distributed Deep Learning**

### New in this release

**Core platform**
- FastAPI backend with 21 module routers, Pydantic v2 contracts, SQLAlchemy 2.0 (SQLite or PostgreSQL).
- JWT auth (access + refresh), bcrypt passwords, 5-role RBAC permission matrix.
- Immutable SHA-256 hash-chained audit log with tamper verification.
- Rate limiting (token bucket), simulated mTLS node identities, AES-256-GCM secrets.
- In-process event bus + WebSocket fan-out for realtime dashboards.

**Federated engine**
- FedAvg, FedProx and FedAdam server optimizers with real, reproducible convergence.
- Seeded non-IID / IID / pathological data generation sharing one ground-truth task.
- Client selection, local epochs, communication & aggregation-time accounting, per-round privacy ε.
- Bonawitz-style secure aggregation: pairwise HMAC masks, RSA-SHA256 signatures, AES-256-GCM encryption, exact mask cancellation, `math_ok` verification.

**Model lifecycle**
- Global Model Registry with versioning, approval → deploy → rollback workflow.
- Live inference API with probability, confidence and kernel-SHAP explanations.
- Evaluation center (accuracy history, version comparison, confusion matrix) and analytics (drift, node contribution, communication cost).

**Explainability**
- Kernel-SHAP local explanations, permutation importance, fairness metrics (demographic parity, equalized odds, disparate impact), bias report.

**AI integrations**
- Bring-Your-Own-Key gateway: OpenAI, Claude, Gemini, Groq, DeepSeek, OpenRouter, Mistral, Ollama, Azure OpenAI, OpenAI-compatible.
- Provider health checks, encrypted key storage with masking, Prompt Studio, inference logs.

**Frontend**
- Enterprise dark theme (Azure ML / Databricks / Grafana-inspired), 22 pages, RBAC-filtered sidebar.
- Realtime Communication Monitor over WebSocket; Analytics charts; interactive Federated Lab (benchmark studio, failure simulation, experiment history, concept cards).

**Operations**
- Docker Compose stack (Postgres + Redis + API + Celery worker + NGINX) with health checks.
- GitHub Actions CI (backend API tests + frontend typecheck/build).
- Optional Celery with inline fallback decorator — zero-config local runs, real queues in production.
- Full documentation library (12 guides) + project report.

### Fixes during development
- Weight round-trip serialization (flatten/load mismatch) — global weights were scrambled.
- Moving-target ground truth per round — replaced with a single shared task seed.
- Mask digest block-size bug for non-multiple-of-32 parameter counts.
- Untyped `request` params parsed as query params (FastAPI 422s) — replaced with an `ip` dependency.
- Audit chain canonical serializer shared between write & verify paths.
- Inference + XAI static-method bugs, analytics ORM → dict conversion.
- Frontend: TanStack Query function signatures, `Stat` unknown values, WebSocket dev proxy, audit query-string separator.

### Known limitations
- Training computation is simulated server-side (no real edge deployment yet); node behavior is driven by a simulator.
- Differential privacy is **accounted** (ε tracking) but not **added** — gradient clipping/Gaussian noise are documented as an extension.
- Database migrations via Alembic are not yet generated (schema created on boot).
- Not audited for production-grade TLS/hardening — see Deployment Guide checklist.

### Demo accounts
All passwords `Admin@12345` — `admin@federated.ai`, `coordinator@federated.ai`, `orgadmin@medicore.ai`, `ml@medicore.ai`, `research@nova.ai`.
