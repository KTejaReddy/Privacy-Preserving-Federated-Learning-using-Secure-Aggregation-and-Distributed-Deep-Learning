# Federated AI Platform

**Privacy-Preserving Federated Learning using Secure Aggregation and Distributed Deep Learning**

An enterprise-grade, research-quality platform where organizations train a shared global model **without ever sharing raw data**. Local training happens on each organization's own nodes; only encrypted, masked model updates travel to a central **Secure Aggregation Engine**, which combines them into a global model.

> Built for healthcare networks, banks, government agencies, universities, research labs, insurance, manufacturing, smart cities and defense — and as a complete Final Year B.Tech Computer Science & Machine Learning project.

---

## ✨ Highlights

| Capability | What you get |
|---|---|
| 🔐 **Secure Aggregation** | Bonawitz-style masked aggregation: pairwise HMAC-SHA256 masks, RSA-SHA256 signatures, AES-256-GCM encryption. The server never sees an individual client update. |
| 🧠 **Federated Engine** | Real distributed training: **FedAvg**, **FedProx**, **FedAdam**, client selection, local epochs, privacy budgets, communication accounting. |
| 🗂 **Model Registry** | Versioning, approval workflow, deploy & rollback, real inference with SHAP explanations. |
| 🔍 **Explainable AI** | Kernel-SHAP local explanations, permutation importance, fairness & bias analysis, confidence scores. |
| 📡 **Realtime Monitor** | WebSocket live feed of node health, synchronization, bandwidth, latency and round completion. |
| 🤖 **AI Integrations** | Bring-Your-Own-Key providers (OpenAI, Claude, Gemini, Groq, DeepSeek, OpenRouter, Mistral, Ollama, Azure…), Prompt Studio, encrypted key storage, inference logs. |
| 🧪 **Federated Lab** | Interactive sandbox: benchmark algorithms, simulate node failures, compare data distributions. |
| 🏛 **RBAC** | Five enterprise roles with different dashboards, sidebars and permissions. |
| 🧾 **Audit & Compliance** | Immutable SHA-256 hash-chained audit log with tamper verification. |
| 🐳 **Production-ready** | Docker Compose (Postgres + Redis + API + Celery + NGINX), GitHub Actions CI, health checks, feature flags. |

---

## 🏗 Architecture

```
                    ┌─────────────────────────────────────────────┐
                    │              Web UI (React/Vite)            │
                    │      NGINX  ·  dark enterprise theme        │
                    └──────────────────┬──────────────────────────┘
                                       │ /api  (REST + WebSocket)
                    ┌──────────────────▼──────────────────────────┐
                    │              FastAPI (Python)               │
                    │  Auth · RBAC · Audit · Rate-limit · Events  │
                    ├──────────────┬───────────────┬──────────────┤
                    │ Federated    │ Secure        │ XAI + AI     │
                    │ Engine       │ Aggregation   │ Integrations │
                    │ FedAvg/Prox/ │ masks+sigs    │ SHAP · BYOK  │
                    │ Adam         │ +AES-256-GCM  │ providers    │
                    └──────┬───────┴───────┬───────┴──────┬───────┘
                           │               │              │
                    ┌──────▼──────┐ ┌──────▼──────┐ ┌─────▼──────┐
                    │  PostgreSQL │ │    Redis    │ │   Celery   │
                    │  (or SQLite)│ │ broker+sim  │ │  workers   │
                    └─────────────┘ └─────────────┘ └────────────┘
```

### Federated round lifecycle

1. **Client selection** — each round samples a random fraction of online, mTLS-verified nodes.
2. **Broadcast** — the global weights are distributed to selected clients.
3. **Local training** — every client trains on its private data partition (local epochs, no raw data leaves the node).
4. **Masked upload** — deltas are pair-wise masked, RSA-SHA256 signed and AES-256-GCM encrypted.
5. **Secure aggregation** — the server verifies signatures, cancels masks (they sum to zero), applies the configured optimizer (FedAvg / FedProx / FedAdam) and evaluates.

### Repository layout

```
backend/            FastAPI application, federated engine, XAI, AI gateway
  app/
    core/           config · database · security · rbac · audit · events · crypto · ratelimit
    models/         SQLAlchemy ORM models
    schemas/        Pydantic request/response contracts
    federated/      nn (trainer) · data · algorithms · client_selection · secure_aggregation · engine
    explainability/ kernel-SHAP explanations · importance · fairness
    ai/             Bring-Your-Own-Key provider gateway
    api/routers/    21 module routers
    workers/        Celery tasks + inline fallback + node simulator
    ws/             WebSocket broadcast manager
    seed.py         realistic demo data (orgs, nodes, datasets, trained jobs)
    tests/          API smoke test suite (pytest + TestClient)
frontend/           React 18 + Vite + TypeScript + Tailwind (dark enterprise theme)
  src/pages/        one page per module, live API wiring via TanStack Query
  src/lib/          typed API client · WebSocket hook · formatters
docker-compose.yml  full stack (postgres · redis · api · worker · web)
.github/workflows/  CI: backend API tests + frontend typecheck/build
docs/               architecture, developer, trainer, student, deployment & API docs
```

---

## 🚀 Quick Start

### Local development (zero external services)

```bash
# 1. Backend
cd backend
python -m venv .venv && source .venv/Scripts/activate   # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
uvicorn app.main:app --reload --port 8000
# Demo data is seeded automatically on first boot (SQLite by default)

# 2. Frontend
cd ../frontend
npm install
npm run dev            # http://localhost:5173
```

Open **http://localhost:5173** — API docs at **http://localhost:8000/docs**.

### Demo accounts (password for all: `Admin@12345`)

| Role | Email | Scope |
|---|---|---|
| Platform Admin | `admin@federated.ai` | Full platform control |
| Federated Coordinator | `coordinator@federated.ai` | Rounds, orgs & approvals |
| Organization Admin | `orgadmin@medicore.ai` | Local datasets & training |
| ML Engineer | `ml@medicore.ai` | Models, eval & explainability |
| Research Scientist | `research@nova.ai` | Federated Lab & experiments |

### Docker (production-style stack)

```bash
docker compose up --build
# Web UI   → http://localhost:8080
# API docs → http://localhost:8080/docs
```

---

## 🧪 Testing

```bash
cd backend && python -m pytest tests/ -v
```

The suite covers auth, RBAC enforcement, every module read endpoint, the secure aggregation demo (mask pairs, signatures, math verification), audit-chain integrity, and a **full training-job lifecycle** (create → approve → run → complete → model version).

## 📚 Documentation

- [Architecture Guide](docs/ARCHITECTURE.md)
- [Developer Guide](docs/DEVELOPER.md)
- [Trainer Guide](docs/TRAINER_GUIDE.md)
- [Student Guide](docs/STUDENT_GUIDE.md)
- [Deployment Guide](docs/DEPLOYMENT.md)
- [API Reference](docs/API.md)
- [Database Schema](docs/DATABASE.md)
- [Federated Learning Notes](docs/FEDERATED_LEARNING.md)
- [Secure Aggregation Notes](docs/SECURE_AGGREGATION.md)
- [Testing Guide](docs/TESTING.md)
- [Release Notes](docs/RELEASE_NOTES.md)
- [Project Report](docs/PROJECT_REPORT.md)

---

## 🔒 Security model

- **JWT** access/refresh tokens, bcrypt password hashing.
- **RBAC** permission matrix across 5 roles (see `backend/app/core/rbac.py`).
- **AES-256** encryption of AI provider API keys at rest (only admin-accessible, masked in UI).
- **Secure aggregation** masks individual updates; **SHA-256 hash-chained audit log** detects tampering.
- **Rate limiting** (token bucket per IP), input validation via Pydantic, simulated **mTLS** for node identities.
- Zero-trust principle: raw data never leaves participating organizations.

## 🧰 Tech stack

**Frontend:** React · TypeScript · Vite · TailwindCSS · Framer Motion · React Router · TanStack Query · Recharts · Lucide

**Backend:** FastAPI · SQLAlchemy · Pydantic v2 · PostgreSQL/SQLite · Redis · Celery · WebSockets · numpy · scikit-learn · cryptography · PyJWT

**Ops:** Docker · Docker Compose · NGINX · GitHub Actions · health checks · feature flags

---

Built as a Final Year B.Tech Computer Science & Machine Learning project — production-ready architecture with academic-grade transparency. See the [Project Report](docs/PROJECT_REPORT.md) for the full academic write-up.
