# Trainer Guide

This guide explains how to operate the platform as a **Federated Coordinator** or **Organization Admin** — creating, approving and running federated training.

## Roles at a glance

| Role | Can do |
|---|---|
| Platform Admin | Everything |
| Federated Coordinator | Approve jobs, manage rounds & organizations |
| Organization Admin | Register datasets & nodes, launch local training, view local analytics |
| ML Engineer | Create training jobs, evaluate models, explainability, tune hyperparameters |
| Research Scientist | Federated Lab, experiments, read-only datasets |

## Workflow: training a global model

### 1. Register an organization & nodes
**Organizations** → *Create organization* (name, industry, compliance level).
**Federated Nodes** → *Register Node* (organization, device type, compute). On registration the node receives an RSA identity and a simulated mTLS certificate.

### 2. Register datasets
**Dataset Registry** → *Register Dataset*. Raw data never leaves the organization — the platform derives a **Data Guardian** SHA-256 fingerprint and a synthetic schema. Nothing is uploaded.

### 3. Create a training job
**Training Center** → *New Training Job*. Key settings:

| Setting | Meaning | Recommendation |
|---|---|---|
| Algorithm | `fedavg` / `fedprox` / `fedadam` | FedProx for non-IID data |
| Rounds | number of federated rounds | 8–20 for a demo |
| Client fraction | fraction of online nodes selected per round | 0.6–0.8 |
| Local epochs | training epochs on each node | 1–3 |
| Learning rate | optimizer step | 0.005–0.02 |
| Secure aggregation | always on in this build | keep on |
| Privacy budget ε/round | ε consumed per round | 0.5 |

### 4. Approve & run
- **Federated Coordinator** sees the job in the approval queue → **Approve**.
- Back in **Training Center**, press **Start**. Rounds stream live; the detail view shows accuracy/loss per round, client participation, communication bytes and ε consumed.

### 5. Register, deploy & monitor the model
- Completed jobs produce a **Model Version** in the **Global Model Registry** (`pending`).
- Approve → **Deploy**. The deployed version serves real **inference** in the registry's Inference Playground.
- **Model Evaluation** compares versions; **Explainable AI** explains predictions with SHAP.

## Running a live secure-aggregation demonstration

**Secure Aggregation** → move the client slider → **Run secure aggregation**. You'll see the full protocol log: pairwise mask agreement → client masking → signature + AES-256-GCM → server unmask & sum → integrity verification.

## Using the Federated Lab (Research Scientists)

**Federated Lab** is an interactive sandbox:

- **Benchmark Studio** — compare FedAvg vs FedProx vs FedAdam on identical data across IID / Non-IID / Pathological distributions.
- **Run Experiment** — configure clients, rounds, and a **node failure rate** to see how resilience degrades (simulated stragglers).
- **History** — every experiment is stored with its full accuracy curve.
- **Learn** — concept cards explaining secure aggregation, optimizer differences, and why non-IID data is the hard case.

## Tips for a compelling demo

1. Start with the **Benchmark Studio** (FedAdam typically wins the accuracy race on non-IID).
2. Create a job with **FedProx** + non-IID data and watch it converge round-by-round on the monitor.
3. Use the **AI Assistant** (see AI Integrations) to summarize results — connect your own API key first.
4. Show the **Audit Center** → *Verify chain integrity* to demonstrate tamper-evident logging.
