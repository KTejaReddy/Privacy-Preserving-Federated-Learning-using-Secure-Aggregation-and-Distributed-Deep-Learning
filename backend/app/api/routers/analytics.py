"""Analytics: aggregated metrics across jobs, rounds, nodes and time."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.deps import require_permission
from app.core.database import get_db
from app.core.rbac import Permission
from app.models.models import ClientUpdate, FederatedRound, ModelVersion, TrainingJob, User

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/overview", response_model=dict)
def analytics_overview(db: Session = Depends(get_db), user: User = Depends(require_permission(Permission.VIEW_ANALYTICS))):
    rounds = db.query(FederatedRound).order_by(FederatedRound.round_number).all()
    versions = db.query(ModelVersion).all()
    jobs = db.query(TrainingJob).all()

    acc_history = [{"round": r.round_number, "accuracy": r.accuracy, "loss": r.avg_loss, "f1": r.f1} for r in rounds]
    comm_per_round = [{"round": r.round_number, "communication_bytes": r.communication_bytes, "aggregation_time_ms": r.aggregation_time_ms} for r in rounds]

    # node contribution: how often selected + avg local accuracy
    node_stats: dict = {}
    for u in db.query(ClientUpdate).all():
        s = node_stats.setdefault(u.node_id, {"rounds": 0, "accuracy_sum": 0.0, "time_sum": 0})
        s["rounds"] += 1
        s["accuracy_sum"] += u.local_accuracy or 0
        s["time_sum"] += u.training_time_ms
    node_contribution = [
        {
            "node_id": nid,
            "rounds": v["rounds"],
            "avg_local_accuracy": round(v["accuracy_sum"] / max(v["rounds"], 1), 4),
            "total_training_time_ms": v["time_sum"],
        }
        for nid, v in node_stats.items()
    ]
    node_contribution.sort(key=lambda x: x["rounds"], reverse=True)

    # model drift: |accuracy change| across versions of each job
    drift = []
    for v in versions:
        drift.append({"version": v.version, "job_id": v.job_id, "accuracy": v.accuracy, "f1": v.f1})

    total_comm = sum(r.communication_bytes for r in rounds)
    total_time = sum(r.aggregation_time_ms for r in rounds)
    best_round = max(rounds, key=lambda r: r.accuracy or 0, default=None)
    best_round_d = (
        {
            "round": best_round.round_number,
            "accuracy": best_round.accuracy,
            "f1": best_round.f1,
            "loss": best_round.avg_loss,
            "participated": best_round.participated_count,
            "job_id": best_round.job_id,
        }
        if best_round
        else None
    )
    return {
        "total_rounds": len(rounds),
        "total_communication_bytes": total_comm,
        "total_aggregation_time_ms": total_time,
        "avg_accuracy": round(sum(r.accuracy or 0 for r in rounds) / max(len(rounds), 1), 4),
        "avg_f1": round(sum(r.f1 or 0 for r in rounds) / max(len(rounds), 1), 4),
        "best_round": best_round_d,
        "accuracy_history": acc_history,
        "communication_history": comm_per_round,
        "node_contribution": node_contribution,
        "model_drift": drift,
        "privacy_budget_used_total": round(sum(r.privacy_budget_used for r in rounds), 4),
        "jobs_by_algorithm": {alg: sum(1 for j in jobs if j.algorithm == alg) for alg in ("fedavg", "fedprox", "fedadam")},
        "versions_by_status": {s: sum(1 for v in versions if v.status == s) for s in ("pending", "approved", "deployed", "archived", "rejected")},
    }


@router.get("/privacy", response_model=dict)
def privacy_metrics(db: Session = Depends(get_db), user: User = Depends(require_permission(Permission.VIEW_ANALYTICS))):
    rounds = db.query(FederatedRound).all()
    from app.core.config import settings

    budget_total = settings.MAX_PRIVACY_BUDGET
    used = round(sum(r.privacy_budget_used for r in rounds), 4)
    return {
        "budget_total": budget_total,
        "budget_used": used,
        "budget_remaining": round(budget_total - used, 4),
        "utilization_pct": round(used / budget_total * 100, 1),
        "rounds_with_masking": sum(1 for r in rounds if r.privacy_budget_used > 0),
        "max_per_round": max((r.privacy_budget_used for r in rounds), default=0),
    }
