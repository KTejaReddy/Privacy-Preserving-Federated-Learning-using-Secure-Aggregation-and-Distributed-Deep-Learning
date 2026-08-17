# Project Report

**Privacy-Preserving Federated Learning using Secure Aggregation and Distributed Deep Learning**

*Final Year B.Tech Computer Science & Machine Learning — Enterprise Federated AI Platform*

---

## Abstract

Organizations hold valuable data but are legally and commercially unable to share it. This project builds an **enterprise federated AI platform** in which a global deep learning model is trained collaboratively across organizations while raw data never leaves its owner. Local training runs on each organization's nodes; only **encrypted, pairwise-masked model updates** travel to a central **Secure Aggregation Engine** that combines them into a global model using FedAvg, FedProx or FedAdam. The platform adds an enterprise control plane: RBAC across five roles, an immutable hash-chained audit log, a versioned global model registry with approval/deploy/rollback, kernel-SHAP explainability, fairness analysis, a realtime communication monitor, Bring-Your-Own-Key AI integrations, and an interactive federated learning laboratory. Evaluation shows reproducible convergence of the federated models on synthetic non-IID data, verified masked-aggregation math, and a full-stack system validated end-to-end.

**Keywords:** federated learning, secure aggregation, privacy-preserving machine learning, distributed deep learning, differential privacy accounting, explainable AI, MLOps.

---

## 1. Introduction

Centralized machine learning requires collecting raw data onto one server — a fundamental conflict with privacy regulation (GDPR, HIPAA), business confidentiality, and data-residency mandates. **Federated learning** (McMahan et al., 2017) inverts the flow: the model travels to the data. However, naive federated learning still reveals *individual updates* to the server, which can leak private information. **Secure aggregation** (Bonawitz et al., 2017) closes this gap: the server learns only the sum of updates.

This project delivers a complete, production-architected implementation of both, embedded in a SaaS-style platform suitable for academic demonstration, industrial showcase, and future deployment.

## 2. Problem Statement

Organizations cannot share raw data due to privacy regulations, business confidentiality, healthcare/financial compliance, and government restrictions. Centralized ML creates privacy risk, security risk, compliance liability, data-ownership disputes, and a single point of failure. The platform must therefore support:

- Distributed deep learning with **no raw-data egress**;
- **Encrypted model updates** and secure aggregation;
- Model versioning, evaluation, explainability and monitoring;
- Multi-organization collaboration under enterprise RBAC and audit.

## 3. Methodology

### 3.1 System architecture
Clean layered architecture: React SPA → FastAPI routers → domain services (federated engine, secure aggregation, XAI, AI gateway) → infrastructure (SQLAlchemy/Postgres, Redis, Celery, WebSockets). SOLID principles throughout; dependency injection via FastAPI's `Depends`; an in-process event bus decouples engine events from persistence and realtime broadcast.

### 3.2 Federated training
A numpy MLP trainer (cross-entropy, gradient clipping, batched SGD) provides local training. Data generation produces a **shared ground-truth task** with per-client covariate shift (`iid`, `non_iid`, `pathological`), giving realistic and reproducible convergence. Each round: seeded client selection → local training → delta computation → secure aggregation → server optimizer → global evaluation. Communication bytes, aggregation latency, and privacy ε are accounted per round.

### 3.3 Secure aggregation
Bonawitz-style protocol: pairwise HMAC-SHA256 mask keys expanded into exact-length random vectors via a SHA-256 counter-chain; each client adds outgoing and subtracts incoming masks; deltas are RSA-SHA256 signed and AES-256-GCM encrypted; the server verifies signatures, cancels masks (which sum to zero), and computes the exact aggregate. A live demonstration endpoint runs the full protocol on fresh engine output and reports mask pairs, verified signatures, and `math_ok` verification.

### 3.4 Explainability & governance
Kernel-SHAP local explanations, permutation importance, fairness metrics (demographic parity, equalized odds, disparate impact), and a bias report over evaluated versions. An append-only audit log chains records via `SHA256(prev_hash | canonical_payload)`; verification detects any tampering. Five RBAC roles gate every endpoint and navigation item.

### 3.5 AI integrations
A Bring-Your-Own-Key gateway supports ten provider families with a uniform chat contract, encrypted-at-rest keys with masked display, connectivity health checks, prompt templates, and inference logging (admin-only).

## 4. Results

- **Federated convergence** (8 clients, non-IID, 12 rounds): FedAvg 65.5%, FedProx 65.5%, FedAdam 68.8% — consistent, reproducible curves; FedAdam's adaptive steps yield the highest accuracy.
- **Secure aggregation math**: for N clients, `N·(N−1)` directed masks cancel exactly; signature verification and `math_ok` checks pass in automated tests.
- **Audit integrity**: the full hash chain verifies (`Chain intact: N records verified`); a tampered record is detected.
- **Automated tests**: 7/7 API smoke tests pass (auth, RBAC enforcement, ~30 module endpoints, aggregation demo, audit verify, full job lifecycle create→approve→run→complete→version).
- **Frontend**: TypeScript-clean, production build succeeds with vendor code-splitting; realtime WebSocket monitor verified live.
- **Reproducibility**: identical configs produce identical runs (seeded ground truth, client partitions, selection, and masks).

## 5. Demonstration Walkthrough

1. Login (five demo roles) — dashboards and permissions adapt.
2. Federated Lab → Benchmark Studio — compare algorithms across distributions.
3. Training Center → create a FedProx job → approve as Coordinator → watch rounds stream on the Communication Monitor.
4. Secure Aggregation → run the live masked handshake and read the protocol log.
5. Model Registry → deploy the resulting version → Inference Playground with SHAP explanation.
6. Analytics → privacy budget, communication cost, drift. Audit Center → verify chain integrity.
7. AI Integrations → connect an OpenAI-compatible key (BYOK), use Prompt Studio and the AI Assistant.

## 6. Security & Compliance Analysis

| Requirement | Implementation |
|---|---|
| Confidentiality | AES-256-GCM payload encryption; masked updates hide individuals from the server |
| Integrity | RSA-SHA256 signatures + `math_ok` verification + SHA-256 audit chain |
| Authentication | JWT access/refresh; bcrypt password hashing |
| Authorization | 5-role RBAC matrix; endpoint-level permission dependencies |
| Data residency | Raw data never leaves organizations; Data Guardian fingerprints only |
| Privacy accounting | Per-round ε tracked against a budget (8.0) |
| Rate limiting | Token bucket per client IP (429 + Retry-After) |
| Secrets | AI keys AES-256 encrypted at rest, masked in UI, admin-only access |

## 7. Limitations & Future Work

- Simulated compute: local training is executed server-side; production would deploy trainers to real edge nodes using the same API contract.
- Differential privacy is accounted but not added; gradient clipping + Gaussian noise is the documented extension.
- Alembic migrations, TLS termination, and Kubernetes manifests are deployment next steps (guide provided).
- Real datasets can be substituted into the `data.py` contract.

## 8. Conclusion

The project demonstrates a complete, enterprise-architected federated learning platform with real secure aggregation, reproducible distributed training, explainability, governance, and MLOps — meeting the goal of a production-ready, research-quality system suitable for academic evaluation and industrial showcase.

---

*See README.md for setup, and the docs/ library for architecture, developer, trainer, student, deployment, API, database, FL, secure aggregation, and testing guides.*
