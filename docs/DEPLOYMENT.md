# Deployment Guide

## Option A — Local (zero config)

See the README Quick Start. SQLite + inline task execution; the simulator runs in-process. Ideal for demos, coursework and development.

## Option B — Docker Compose (recommended for showcases)

```bash
cp .env.example .env          # then edit SECRET_KEY
docker compose up --build
```

Services:

| Service | Role | Exposed |
|---|---|---|
| `web` | NGINX serving the SPA + reverse proxy | `:8080` (configurable via `WEB_PORT`) |
| `api` | FastAPI + federated engine | internal `:8000` |
| `worker` | Celery worker (broker = Redis) | — |
| `postgres` | PostgreSQL 16 | internal |
| `redis` | broker / cache | internal |

Everything is behind one NGINX entry point: the SPA, `/api`, `/docs`, `/openapi.json`, `/health`, and the **WebSocket** upgrade path (`/api/v1/monitor/ws`).

## Environment variables

See `.env.example`. Critical ones:

| Variable | Notes |
|---|---|
| `SECRET_KEY` | **must** be a long random string in any non-demo deployment |
| `DATABASE_URL` | default SQLite; compose uses `postgresql+psycopg2://…` |
| `REDIS_URL`, `CELERY_BROKER_URL`, `CELERY_RESULT_BACKEND` | compose wires these to the redis service |
| `CORS_ORIGINS` | comma-separated origins allowed to call the API |
| `ENV=production` | disables demo seeding |
| `ENABLE_HEAVY_DEPS` | set `true` to enable optional torch/tf/shap/xgboost paths |

## Production hardening checklist

- [ ] Generate a strong `SECRET_KEY` (e.g. `openssl rand -hex 32`) and never commit it.
- [ ] Set `ENV=production` (stops demo-data seeding).
- [ ] Front the NGINX service with TLS (the compose setup listens on plain HTTP; terminate TLS at a load balancer / reverse proxy and set `X-Forwarded-Proto`).
- [ ] Back up the PostgreSQL volume (`docker compose exec postgres pg_dump …`).
- [ ] Add monitoring: Prometheus scraping `/metrics` (add a metrics endpoint for your infra) and Grafana dashboards; ship logs to your aggregator.
- [ ] If running multi-worker, ensure `ENABLE_HEAVY_DEPS=false` or provision workers with matching compute.
- [ ] Rotate the AI provider keys via the Admin → AI Integrations UI (stored AES-256 encrypted).

## CI/CD

`.github/workflows/ci.yml` runs on every push/PR:

1. **Backend** — install `requirements-dev.txt`, import check, full API smoke suite (`pytest tests/test_api_smoke.py`).
2. **Frontend** — `npm ci`, `tsc --noEmit`, `npm run build`.

Suggested next steps: build & push images (`docker buildx build --platform linux/amd64 …`) to a registry, then deploy via SSH/docker compose or a Kubernetes manifest (all services are stateless except Postgres/Redis).

## Health checks

- `GET /health` — API liveness (returns `{"status":"ok",…}`).
- Docker healthchecks: postgres (`pg_isready`), redis (`redis-cli ping`), web (`wget /healthz`), api (`curl /health`).
