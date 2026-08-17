# Student Guide — Learning the Concepts

This project is designed to teach **federated learning**, **secure aggregation** and **distributed deep learning** through a real, working system. Here is a map from textbook concept → where to see it live.

## 1. What is federated learning?

Instead of collecting data into one place, **the model travels to the data**. Each organization trains on its own data and only shares *model updates*.

**See it:** *Training Center* → start a job and open the detail view. Watch clients train locally each round while the global model improves.

## 2. Non-IID data (the core research problem)

Real clients rarely have identically distributed data. If one hospital mostly sees sick patients and another mostly healthy ones, their updates pull the model in different directions.

**See it:** *Federated Lab → Benchmark Studio*. Run the benchmark on **IID** vs **Non-IID** vs **Pathological** data. Pathological (each client holds a disjoint label class) is the hardest case — the curves make the difference visible.

## 3. FedAvg / FedProx / FedAdam

- **FedAvg** — average the deltas, weighted by sample count.
- **FedProx** — adds a proximal penalty `(μ/2)‖w − w_global‖²` to local objectives, keeping local models near the global one. Better under drift.
- **FedAdam** — the server applies Adam to the aggregate gradient: adaptive per-coordinate steps. Often the fastest to converge, but can be unstable early.

**See it:** the Lab benchmark plots all three on identical data. In the code: `backend/app/federated/algorithms.py`.

## 4. Secure aggregation (Bonawitz et al., 2017)

The server must learn the **sum** of client updates without learning **any individual update**. Idea: every pair of clients shares a secret mask. Each client adds its outgoing masks and subtracts incoming ones. When the server sums the masked vectors, the masks cancel to zero — it only sees the true aggregate. Combined with RSA signatures (integrity) and AES-256-GCM (confidentiality), no single update is ever revealed.

**See it:** *Secure Aggregation* page → *Run secure aggregation* → read the protocol log. In the code: `backend/app/federated/secure_aggregation.py` (note how masks cancel exactly — `_pair_mask` derives a per-pair HMAC key).

## 5. Client selection & stragglers

Each round only a **fraction** of clients participate (saves communication). Real systems drop nodes; the server aggregates whatever arrives.

**See it:** *Federated Lab → Run Experiment* → set a **fail rate** and watch the curve degrade. The *Communication Monitor* shows nodes going offline in real time.

## 6. Privacy budgets (differential privacy accounting)

Even with secure aggregation, repeated updates leak information. The platform tracks cumulative **ε (epsilon)** consumed per round against a budget.

**See it:** *Analytics* → Privacy Budget card; *Secure Aggregation* shows ε per run.

## 7. Explainable AI

SHAP values attribute a prediction to its features — positive SHAP pushes toward class 1, negative toward class 0, and they sum to the prediction minus a base rate.

**See it:** *Explainable AI* → Local Explanation (per-sample SHAP), Global Importance (permutation importance), Fairness & Bias (demographic parity, equalized odds, disparate impact).

## 8. Auditing & compliance

An immutable **hash chain** links every audit record: `hash_i = SHA256(hash_{i-1} | payload_i)`. Changing any past record breaks every subsequent hash.

**See it:** *Audit Center* → *Verify chain integrity*. In the code: `backend/app/core/audit.py` (write + verify share one canonical serializer).

## 9. MLOps: versioning, evaluation, deployment

Every completed job creates a model **version** with metrics. Versions flow `pending → approved → deployed`, can be rolled back, and the deployed one serves live inference with explanations.

**See it:** *Global Model Registry*, *Model Evaluation* (accuracy history, comparison, confusion matrix), *Analytics* (drift across versions).

## Suggested exploration path

1. Run a **Benchmark** in the Federated Lab (10 minutes, no setup).
2. Start a **FedProx** job and watch rounds stream on the monitor.
3. Run a **secure aggregation** handshake and read the log.
4. Deploy the resulting model and use the **Inference Playground** + SHAP explanation.
5. Verify the **audit chain**, then review the **Privacy Budget**.
6. Open the code and trace `engine.run_job` → `algorithms.py` → `secure_aggregation.py`.

## Reproducibility

All data is **synthetic and seeded** (`seed` in job config), so experiments are reproducible. The ground-truth task derives from the job seed and is shared across clients and the evaluation set — the model genuinely learns the task.
