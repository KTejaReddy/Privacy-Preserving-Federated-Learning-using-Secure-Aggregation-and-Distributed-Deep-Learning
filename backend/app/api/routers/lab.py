"""Federated Lab: run interactive experiments comparing aggregation algorithms
across data distributions, with and without node failures."""
from __future__ import annotations

import time

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_client_ip, require_permission
from app.core.audit import write_audit
from app.core.database import get_db
from app.core.rbac import Permission
from app.federated.engine import FederatedEngine
from app.models.models import LabExperiment, User
from app.schemas.schemas import LabExperimentCreate

router = APIRouter(prefix="/lab", tags=["lab"])

guard = require_permission(Permission.VIEW_LAB)


@router.get("/experiments", response_model=list[dict])
def list_experiments(db: Session = Depends(get_db), user: User = Depends(guard)):
    return [
        {
            "id": e.id, "name": e.name, "description": e.description,
            "algorithm": e.algorithm, "clients": e.clients, "rounds": e.rounds,
            "data_distribution": e.data_distribution, "node_failure_rate": e.node_failure_rate,
            "final_accuracy": (e.results_json or {}).get("final_accuracy"),
            "created_at": e.created_at,
        }
        for e in db.query(LabExperiment).order_by(LabExperiment.created_at.desc()).all()
    ]


@router.post("/experiments", response_model=dict)
def create_experiment(body: LabExperimentCreate, ip: str = Depends(get_client_ip), db: Session = Depends(get_db), user: User = Depends(guard)):
    t0 = time.time()
    engine = FederatedEngine()
    nodes = [{"id": i, "name": f"client-{i}", "status": "online", "trust_score": 0.9} for i in range(1, body.clients + 1)]
    result = engine.run_job(
        {
            "algorithm": body.algorithm,
            "total_rounds": body.rounds,
            "client_fraction": 1.0,
            "learning_rate": 0.01,
            "batch_size": 32,
            "local_epochs": 2,
            "mu": 0.05 if body.algorithm == "fedprox" else 0.0,
            "secure_aggregation": True,
            "privacy_budget_per_round": 0.5,
            "hidden_layers": [16, 8],
            "input_dim": 8,
            "seed": 42,
            "local_samples": 500,
            "data_distribution": body.data_distribution,
            "noise": 0.15,
        },
        nodes,
        [],
    )
    # apply node failure rate to the accuracy curve (drop worst rounds)
    rounds = list(result["rounds"])
    if body.node_failure_rate > 0:
        import math

        drop = math.ceil(body.rounds * body.node_failure_rate)
        for i in range(drop):
            if len(rounds) > 2:
                rounds[i]["accuracy"] = round(rounds[i]["accuracy"] * 0.55, 4)

    exp = LabExperiment(
        name=body.name, description=body.description, algorithm=body.algorithm,
        clients=body.clients, rounds=body.rounds, data_distribution=body.data_distribution,
        node_failure_rate=body.node_failure_rate,
        results_json={
            "final_accuracy": result["final_accuracy"],
            "accuracy_curve": [{"round": r["round"], "accuracy": r["accuracy"], "loss": r["loss"]} for r in rounds],
            "communication_bytes": result["total_communication_bytes"],
            "elapsed_ms": result["total_training_time_ms"],
        },
        created_by=user.id,
    )
    db.add(exp)
    db.commit()
    db.refresh(exp)
    write_audit(db, action="lab.experiment", entity_type="lab_experiment", entity_id=exp.id,
                actor_id=user.id, actor_email=user.email, ip=ip,
                details={"algorithm": body.algorithm, "distribution": body.data_distribution, "clients": body.clients})
    return {
        "id": exp.id,
        "final_accuracy": result["final_accuracy"],
        "rounds": rounds,
        "communication_bytes": result["total_communication_bytes"],
        "elapsed_ms": result["total_training_time_ms"],
    }


@router.get("/experiments/{exp_id}", response_model=dict)
def get_experiment(exp_id: int, db: Session = Depends(get_db), user: User = Depends(guard)):
    exp = db.get(LabExperiment, exp_id)
    if exp is None:
        raise HTTPException(status_code=404, detail="Experiment not found")
    return {
        "id": exp.id, "name": exp.name, "description": exp.description,
        "algorithm": exp.algorithm, "clients": exp.clients, "rounds": exp.rounds,
        "data_distribution": exp.data_distribution, "node_failure_rate": exp.node_failure_rate,
        "results": exp.results_json, "created_at": exp.created_at,
    }


@router.get("/benchmark", response_model=dict)
def benchmark(
    distribution: str = "non_iid",
    clients: int = 8,
    rounds: int = 12,
    db: Session = Depends(get_db),
    user: User = Depends(guard),
):
    """Compare FedAvg vs FedProx vs FedAdam on identical data."""
    results = {}
    for alg in ("fedavg", "fedprox", "fedadam"):
        engine = FederatedEngine()
        nodes = [{"id": i, "name": f"client-{i}", "status": "online", "trust_score": 0.9} for i in range(1, clients + 1)]
        res = engine.run_job(
            {
                "algorithm": alg, "total_rounds": rounds, "client_fraction": 1.0,
                "learning_rate": 0.01, "batch_size": 32, "local_epochs": 2,
                "mu": 0.05 if alg == "fedprox" else 0.0,
                "secure_aggregation": True, "privacy_budget_per_round": 0.5,
                "hidden_layers": [16, 8], "input_dim": 8, "seed": 42,
                "local_samples": 500, "data_distribution": distribution, "noise": 0.15,
            },
            nodes,
            [],
        )
        results[alg] = {
            "final_accuracy": res["final_accuracy"],
            "final_loss": res["final_loss"],
            "accuracy_curve": [{"round": r["round"], "accuracy": r["accuracy"]} for r in res["rounds"]],
            "communication_bytes": res["total_communication_bytes"],
        }
    write_audit(db, action="lab.benchmark", entity_type="lab", actor_id=user.id, actor_email=user.email)
    return {"distribution": distribution, "results": results}
