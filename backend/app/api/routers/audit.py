"""Audit Center: search/query the immutable audit log and verify chain integrity."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import require_permission
from app.core.audit import verify_chain
from app.core.database import get_db
from app.core.rbac import Permission
from app.models.models import AuditLog, User

router = APIRouter(prefix="/audit", tags=["audit"])


@router.get("/logs", response_model=dict)
def audit_logs(
    limit: int = Query(100, le=500),
    offset: int = Query(0),
    action: str | None = Query(None),
    severity: str | None = Query(None),
    actor: str | None = Query(None),
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(Permission.VIEW_AUDIT)),
):
    query = db.query(AuditLog)
    if action:
        query = query.filter(AuditLog.action.contains(action))
    if severity:
        query = query.filter(AuditLog.severity == severity)
    if actor:
        query = query.filter(AuditLog.actor_email.contains(actor))
    total = query.count()
    records = query.order_by(AuditLog.id.desc()).offset(offset).limit(limit).all()
    return {
        "total": total,
        "records": [
            {
                "id": a.id, "actor_email": a.actor_email, "action": a.action,
                "entity_type": a.entity_type, "entity_id": a.entity_id,
                "details": a.details, "ip": a.ip, "severity": a.severity,
                "chain_hash": a.chain_hash, "created_at": a.created_at,
            }
            for a in records
        ],
    }


@router.get("/verify", response_model=dict)
def verify(db: Session = Depends(get_db), user: User = Depends(require_permission(Permission.VIEW_AUDIT))):
    ok, message = verify_chain(db)
    return {"ok": ok, "message": message}


@router.get("/summary", response_model=dict)
def audit_summary(db: Session = Depends(get_db), user: User = Depends(require_permission(Permission.VIEW_AUDIT))):
    records = db.query(AuditLog).all()
    actions: dict = {}
    severities: dict = {}
    for r in records:
        actions[r.action] = actions.get(r.action, 0) + 1
        severities[r.severity] = severities.get(r.severity, 0) + 1
    return {
        "total": len(records),
        "by_action": dict(sorted(actions.items(), key=lambda kv: kv[1], reverse=True)[:12]),
        "by_severity": severities,
        "warnings": sum(1 for r in records if r.severity in ("warning", "critical")),
    }
