"""Executive Dashboard: aggregate KPIs + activity feed for the home page."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import require_permission, user_org_scope
from app.core.database import get_db
from app.core.rbac import Permission
from app.models.models import (
    AuditLog,
    FederatedNode,
    FederatedRound,
    ModelVersion,
    Organization,
    TrainingJob,
    User,
)

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("", response_model=dict)
def dashboard(user: User = Depends(require_permission(Permission.VIEW_ANALYTICS)), db: Session = Depends(get_db)):
    scoped = user_org_scope(user, db)
    if user.role in ("admin", "coordinator"):
        orgs = db.query(Organization).all()
        nodes = db.query(FederatedNode).all()
        jobs = db.query(TrainingJob).all()
        versions = db.query(ModelVersion).all()
    else:
        orgs = db.query(Organization).filter(Organization.id.in_(scoped)).all()
        nodes = db.query(FederatedNode).filter(FederatedNode.organization_id.in_(scoped)).all()
        jobs = db.query(TrainingJob).filter(TrainingJob.organization_id.in_(scoped)).all()
        versions = db.query(ModelVersion).all()

    rounds = db.query(FederatedRound).all()
    completed_jobs = [j for j in jobs if j.status == "completed"]
    running = [j for j in jobs if j.status in ("running", "approved")]

    # time series of round accuracy (last 24 rounds)
    ordered = sorted(rounds, key=lambda r: r.round_number)
    acc_series = [{"round": r.round_number, "accuracy": r.accuracy, "loss": r.avg_loss} for r in ordered[-24:]]

    # node health distribution
    health = {"online": 0, "degraded": 0, "offline": 0, "unknown": 0}
    for n in nodes:
        health[n.status] = health.get(n.status, 0) + 1

    # activity feed from audit
    since = datetime.now(timezone.utc) - timedelta(hours=24)
    feed = (
        db.query(AuditLog)
        .filter(AuditLog.created_at >= since)
        .order_by(AuditLog.id.desc())
        .limit(10)
        .all()
    )

    from app.models.models import Dataset

    dataset_total = db.query(Dataset).filter(Dataset.organization_id.in_(scoped)).count() if user.role not in ("admin", "coordinator") else db.query(Dataset).count()
    return {
        "kpis": {
            "organizations": len(orgs),
            "nodes": len(nodes),
            "nodes_online": health["online"],
            "datasets": dataset_total,
            "jobs": len(jobs),
            "running_jobs": len(running),
            "completed_jobs": len(completed_jobs),
            "rounds": len(rounds),
            "model_versions": len(versions),
            "deployed_models": sum(1 for v in versions if v.status == "deployed"),
            "avg_accuracy": round(sum(r.accuracy or 0 for r in rounds) / max(len(rounds), 1), 4),
            "avg_f1": round(sum(r.f1 or 0 for r in rounds) / max(len(rounds), 1), 4),
            "privacy_budget_used": round(sum(r.privacy_budget_used for r in rounds), 4),
        },
        "accuracy_series": acc_series,
        "node_health": health,
        "jobs_by_status": {
            s: sum(1 for j in jobs if j.status == s)
            for s in ("draft", "approved", "running", "completed", "failed", "paused", "cancelled")
        },
        "activity_feed": [
            {"action": a.action, "actor": a.actor_email, "severity": a.severity, "created_at": a.created_at}
            for a in feed
        ],
        "recent_jobs": [
            {"id": j.id, "name": j.name, "status": j.status, "algorithm": j.algorithm,
             "accuracy": j.metrics_json.get("final_accuracy"), "created_at": j.created_at}
            for j in sorted(jobs, key=lambda j: j.created_at, reverse=True)[:6]
        ],
        "top_nodes": sorted(
            [
                {"id": n.id, "name": n.name, "status": n.status, "trust_score": n.trust_score,
                 "latency_ms": n.latency_ms}
                for n in nodes
            ],
            key=lambda n: n["trust_score"],
            reverse=True,
        )[:6],
    }
