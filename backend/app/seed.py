"""Demo data seeder.

Creates a realistic multi-organization federated network with users for every
role, registered nodes, governed datasets, and runs real federated training jobs
through the engine so dashboards show live metrics on first boot.
"""
from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.core.security import generate_rsa_keypair, hash_password
from app.models.models import (
    AIProvider,
    AggregationLog,
    ClientUpdate,
    Dataset,
    FederatedNode,
    FederatedRound,
    ModelVersion,
    Organization,
    PromptTemplate,
    TrainingJob,
    User,
)

log = logging.getLogger("seed")

ORGS = [
    ("MediCore Health Network", "Health & Care", "Switzerland", "GDPR + HIPAA aligned"),
    ("Atlas Financial Group", "Banking & Finance", "Singapore", "MAS + GDPR aligned"),
    ("Nova Research Institute", "Research & Academia", "Germany", "GDPR aligned"),
    ("CityGrid Smart Mobility", "Smart City", "Netherlands", "GDPR aligned"),
    ("SecureEdge Defense Labs", "Defense & Security", "Canada", "ISO 27001 + ITAR"),
]

ROLE_USERS = [
    ("admin@federated.ai", "Aria Vance", "admin", None, "Platform Administrator"),
    ("coordinator@federated.ai", "Marcus Chen", "coordinator", None, "Federated Coordinator"),
    ("orgadmin@medicore.ai", "Elena Rossi", "org_admin", 1, "Head of Data Governance"),
    ("ml@medicore.ai", "Dev Patel", "ml_engineer", 1, "Senior ML Engineer"),
    ("research@nova.ai", "Ingrid Larsen", "research_scientist", 3, "Research Scientist"),
]


def _seed_orgs(db: Session) -> dict:
    org_ids = {}
    for i, (name, industry, country, compliance) in enumerate(ORGS, start=1):
        org = Organization(
            name=name,
            slug=name.lower().replace(" ", "-").replace("&", "and"),
            industry=industry,
            country=country,
            description=f"{name} participates in the federated network with strict data residency controls.",
            status="active",
            compliance_level=compliance,
        )
        db.add(org)
        org_ids[i] = org
    db.commit()
    for i, org in org_ids.items():
        db.refresh(org)
        org_ids[i] = org.id
    return org_ids


def _seed_users(db: Session, org_ids: dict) -> None:
    for email, name, role, org_key, title in ROLE_USERS:
        org_id = org_ids.get(org_key) if org_key else None
        user = User(
            email=email,
            full_name=name,
            password_hash=hash_password("Admin@12345"),
            role=role,
            organization_id=org_id,
            title=title,
        )
        db.add(user)
    db.commit()


def _seed_nodes(db: Session, org_ids: dict) -> None:
    node_specs = [
        (1, "medi-core-h1", "server", 16, "NVIDIA A100", 64, 400, 8),
        (1, "medi-core-h2", "server", 16, "NVIDIA A100", 64, 380, 9),
        (1, "medi-edge-icu", "edge", 8, "None", 32, 250, 14),
        (2, "atlas-trade-a", "server", 32, "NVIDIA H100", 128, 900, 5),
        (2, "atlas-fraud-b", "server", 24, "A10G", 96, 720, 7),
        (2, "atlas-mobile-c", "mobile", 4, "None", 8, 180, 22),
        (3, "nova-lab-cluster", "gpu", 64, "4x A100", 256, 1000, 3),
        (3, "nova-lab-worker", "server", 16, "V100", 64, 420, 11),
        (4, "citygrid-traffic", "edge", 8, "None", 16, 210, 18),
        (4, "citygrid-transit", "edge", 8, "None", 16, 190, 20),
        (5, "secedge-hq", "server", 32, "A100", 128, 850, 4),
        (5, "secedge-field", "server", 16, "None", 48, 300, 16),
    ]
    for org_key, name, dev, cpu, gpu, ram, bw, lat in node_specs:
        kp = generate_rsa_keypair()
        node = FederatedNode(
            organization_id=org_ids[org_key],
            name=name,
            endpoint=f"mtls://{name}.internal:8443",
            status="online",
            device_type=dev,
            cpu_cores=cpu,
            gpu_name=gpu,
            ram_gb=ram,
            bandwidth_mbps=bw,
            latency_ms=lat,
            public_key=kp["public_key"],
            cert_serial=f"MTLS-{name.upper().replace('-','')[:8]}",
            mTLS_verified=True,
            trust_score=0.93,
        )
        db.add(node)
    db.commit()


def _seed_datasets(db: Session, org_ids: dict) -> None:
    specs = [
        (1, "Cardiac Risk Cohort", 8, 4200, 0.32, 0.12),
        (1, "ICU Readmission Signals", 8, 2600, 0.41, 0.15),
        (2, "Transaction Fraud Patterns", 8, 8500, 0.18, 0.10),
        (2, "Credit Default History", 8, 5100, 0.27, 0.13),
        (3, "Scientific Paper Impact", 8, 3800, 0.52, 0.16),
        (4, "Traffic Flow Anomalies", 8, 6400, 0.35, 0.11),
        (5, "Threat Indicator Signals", 8, 2900, 0.22, 0.14),
    ]
    for org_key, name, feats, samples, ratio, noise in specs:
        db.add(
            Dataset(
                organization_id=org_ids[org_key],
                name=name,
                description=f"Synthetic privacy-preserving replica of {name} (raw data remains on-premise).",
                data_type="tabular",
                feature_count=feats,
                sample_count=samples,
                positive_ratio=ratio,
                noise=noise,
                privacy_controls={
                    "fingerprint": f"fp-{name[:6].lower()}-{samples}",
                    "raw_data_exposure": False,
                    "synthetic_replica": True,
                    "pii_detected": False,
                    "encryption": "AES-256 at rest",
                    "retention_days": 365,
                },
                status="validated",
            )
        )
    db.commit()


def _run_demo_jobs(db: Session, org_ids: dict) -> None:
    """Run real federated training through the engine and persist results."""
    from app.federated.engine import FederatedEngine

    users = {u.role: u.id for u in db.query(User).all()}
    nodes = db.query(FederatedNode).all()

    job_defs = [
        {
            "name": "Global Fraud Risk Model",
            "description": "Federated fraud detection across banking + smart city + defense partners.",
            "algorithm": "fedavg", "rounds": 8, "fraction": 0.7, "lr": 0.01,
            "epochs": 2, "mu": 0.0, "secure": True, "distribution": "non_iid",
            "org": org_ids[2],
        },
        {
            "name": "Healthcare Readmission Predictor",
            "description": "Secure aggregation demo across healthcare organizations.",
            "algorithm": "fedprox", "rounds": 8, "fraction": 0.6, "lr": 0.02,
            "epochs": 2, "mu": 0.05, "secure": True, "distribution": "non_iid",
            "org": org_ids[1],
        },
        {
            "name": "Federated IoT Anomaly Detector",
            "description": "FedAdam experiment on smart city + research data.",
            "algorithm": "fedadam", "rounds": 6, "fraction": 0.5, "lr": 0.005,
            "epochs": 2, "mu": 0.0, "secure": True, "distribution": "iid",
            "org": org_ids[4],
        },
    ]

    for idx, spec in enumerate(job_defs):
        job = TrainingJob(
            name=spec["name"],
            description=spec["description"],
            status="completed",
            algorithm=spec["algorithm"],
            hidden_layers=[16, 8],
            total_rounds=spec["rounds"],
            client_fraction=spec["fraction"],
            learning_rate=spec["lr"],
            batch_size=32,
            local_epochs=spec["epochs"],
            mu=spec["mu"],
            server_momentum=0.9,
            secure_aggregation=spec["secure"],
            privacy_budget_per_round=0.5,
            use_encryption=True,
            dataset_ids=[],
            created_by=users.get("ml_engineer") or users.get("admin"),
            organization_id=spec["org"],
            metrics_json={
                "data_distribution": spec["distribution"],
                "local_samples": 700,
                "noise": 0.15,
                "input_dim": 8,
                "seed": 42 + idx,
            },
        )
        db.add(job)
        db.commit()
        db.refresh(job)

        node_dicts = [{"id": n.id, "name": n.name, "status": "online", "trust_score": n.trust_score} for n in nodes]
        engine = FederatedEngine()
        result = engine.run_job(
            {
                "algorithm": job.algorithm,
                "total_rounds": job.total_rounds,
                "client_fraction": job.client_fraction,
                "learning_rate": job.learning_rate,
                "batch_size": job.batch_size,
                "local_epochs": job.local_epochs,
                "mu": job.mu,
                "server_momentum": job.server_momentum,
                "secure_aggregation": job.secure_aggregation,
                "privacy_budget_per_round": 0.5,
                "hidden_layers": [16, 8],
                "input_dim": 8,
                "seed": 42 + idx,
                "local_samples": 700,
                "data_distribution": spec["distribution"],
                "noise": 0.15,
            },
            node_dicts,
            [],
        )
        from app.models.models import utcnow

        version = None
        for r in result["rounds"]:
            round_rec = FederatedRound(
                job_id=job.id, round_number=r["round"], status="completed",
                selected_client_ids=[c["node_id"] for c in []],
                participated_count=r["participated"],
                avg_loss=r["loss"], accuracy=r["accuracy"], precision=r["precision"],
                recall=r["recall"], f1=r["f1"],
                communication_bytes=r["communication_bytes"],
                aggregation_time_ms=r["aggregation_time_ms"],
                client_metrics=r["client_metrics"],
                privacy_budget_used=r["privacy_budget_used"],
                started_at=utcnow(), finished_at=utcnow(),
            )
            db.add(round_rec)
            db.flush()
            for cid, cmeta in r["client_metrics"].items():
                db.add(
                    ClientUpdate(
                        round_id=round_rec.id, node_id=int(cid), status="aggregated",
                        local_accuracy=cmeta.get("accuracy"), local_loss=cmeta.get("loss"),
                        training_time_ms=cmeta.get("training_time_ms", 0),
                        upload_bytes=int(r["communication_bytes"] / max(r["participated"], 1)),
                        contribution_score=round(float(cmeta.get("accuracy", 0)), 4),
                    )
                )
            db.add(
                AggregationLog(
                    round_id=round_rec.id, method=r["agg"].get("method", "masked_sum"),
                    client_count=r["participated"],
                    masked_upload_count=r["participated"] if r["agg"].get("encrypted") else 0,
                    masks_cancelled=bool(r["agg"].get("math_ok")),
                    signature_verified=True, integrity_hash=f"sha256-{job.id}-{r['round']}",
                    privacy_budget_consumed=r["privacy_budget_used"], details=r["agg"],
                )
            )
            job.current_round = r["round"]
        final = result["rounds"][-1] if result["rounds"] else {}
        version = ModelVersion(
            job_id=job.id, version=1, status="deployed" if idx == 0 else "approved",
            accuracy=final.get("accuracy"), loss=final.get("loss"),
            precision=final.get("precision"), recall=final.get("recall"), f1=final.get("f1"),
            metrics_json={
                "rounds": result["rounds"],
                "algorithm": result["algorithm"],
                "total_communication_bytes": result["total_communication_bytes"],
                "total_training_time_ms": result["total_training_time_ms"],
                "param_count": result["param_count"],
                "feature_names": result["feature_names"],
                "model_hash": result["model_hash"],
                "weights": [],
            },
            created_by=users.get("coordinator") or users.get("admin"),
        )
        db.add(version)
        job.status = "completed"
        job.metrics_json = {
            **job.metrics_json,
            "final_accuracy": final.get("accuracy"),
            "final_f1": final.get("f1"),
            "total_communication_bytes": result["total_communication_bytes"],
            "total_training_time_ms": result["total_training_time_ms"],
            "algorithm": result["algorithm"],
        }
        db.commit()


def _seed_ai(db: Session) -> None:
    from app.core.security import encrypt_secret, mask_key

    provider = AIProvider(
        name="OpenAI (Bring-Your-Own-Key)",
        provider_type="openai",
        base_url="https://api.openai.com/v1",
        api_key_encrypted="",
        key_mask="",
        models=["gpt-4o", "gpt-4o-mini"],
        temperature_default=0.3,
        status="configured",
    )
    db.add(provider)
    db.add(
        PromptTemplate(
            name="Training Summary",
            system_prompt="Summarize the latest federated training run from the platform context.",
            user_prompt="Write a concise executive summary of the training results.",
            temperature=0.2,
            variables=["job", "accuracy"],
        )
    )
    db.commit()


def seed_demo_data() -> None:
    db: Session = SessionLocal()
    try:
        if db.query(User).count() > 0:
            return
        org_ids = _seed_orgs(db)
        _seed_users(db, org_ids)
        _seed_nodes(db, org_ids)
        _seed_datasets(db, org_ids)
        try:
            _run_demo_jobs(db, org_ids)
        except Exception as exc:  # noqa: BLE001
            log.warning("Demo job seeding failed (non-fatal): %s", exc)
        _seed_ai(db)
        log.info("Demo data seeded.")
    finally:
        db.close()


if __name__ == "__main__":
    seed_demo_data()
    print("Seeded.")
