"""Communication Monitor: realtime telemetry for nodes, rounds and bandwidth."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Query, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session

from app.api.deps import require_permission, user_org_scope
from app.core.database import SessionLocal, get_db
from app.core.rbac import Permission
from app.models.models import ClientUpdate, FederatedNode, FederatedRound, NodeEvent, TrainingJob, User
from app.ws.manager import manager

router = APIRouter(prefix="/monitor", tags=["monitor"])


@router.get("/overview", response_model=dict)
def monitor_overview(db: Session = Depends(get_db), user: User = Depends(require_permission(Permission.VIEW_MONITOR))):
    nodes = db.query(FederatedNode).all()
    rounds = db.query(FederatedRound).order_by(FederatedRound.id.desc()).limit(30).all()
    active_jobs = db.query(TrainingJob).filter(TrainingJob.status == "running").count()
    return {
        "nodes_online": sum(1 for n in nodes if n.status == "online"),
        "nodes_total": len(nodes),
        "nodes_degraded": sum(1 for n in nodes if n.status == "degraded"),
        "nodes_offline": sum(1 for n in nodes if n.status == "offline"),
        "active_jobs": active_jobs,
        "rounds_completed": db.query(FederatedRound).count(),
        "avg_latency_ms": round(sum(n.latency_ms for n in nodes) / max(len(nodes), 1), 1),
        "total_bandwidth_mbps": round(sum(n.bandwidth_mbps for n in nodes), 1),
        "rounds": [
            {
                "id": r.id, "job_id": r.job_id, "round": r.round_number,
                "status": r.status, "accuracy": r.accuracy, "loss": r.avg_loss,
                "participated": r.participated_count, "communication_bytes": r.communication_bytes,
                "aggregation_time_ms": r.aggregation_time_ms, "finished_at": r.finished_at,
            }
            for r in rounds
        ],
        "node_sync": [
            {
                "id": n.id, "name": n.name, "status": n.status, "latency_ms": n.latency_ms,
                "bandwidth_mbps": n.bandwidth_mbps, "trust_score": n.trust_score,
                "last_heartbeat": n.last_heartbeat, "device_type": n.device_type,
                "mtls": n.mTLS_verified,
            }
            for n in nodes
        ],
    }


@router.get("/timeline", response_model=dict)
def monitor_timeline(limit: int = Query(60), db: Session = Depends(get_db), user: User = Depends(require_permission(Permission.VIEW_MONITOR))):
    since = datetime.now(timezone.utc) - timedelta(hours=24)
    events = (
        db.query(NodeEvent)
        .filter(NodeEvent.created_at >= since)
        .order_by(NodeEvent.created_at.desc())
        .limit(limit)
        .all()
    )
    updates = db.query(ClientUpdate).order_by(ClientUpdate.id.desc()).limit(20).all()
    return {
        "events": [
            {"id": e.id, "node_id": e.node_id, "event_type": e.event_type, "message": e.message,
             "severity": e.severity, "created_at": e.created_at}
            for e in events
        ],
        "updates": [
            {"id": u.id, "round_id": u.round_id, "node_id": u.node_id, "status": u.status,
             "local_accuracy": u.local_accuracy, "local_loss": u.local_loss,
             "training_time_ms": u.training_time_ms, "upload_bytes": u.upload_bytes}
            for u in updates
        ],
    }


@router.websocket("/ws")
async def monitor_ws(ws: WebSocket):
    """Realtime event stream for the Communication Monitor."""
    await manager.connect(ws)
    try:
        await manager.send_personal(
            ws, {"event": "monitor.connected", "data": {"ts": datetime.now(timezone.utc).isoformat()}}
        )
        while True:
            msg = await ws.receive_text()
            # client can request a snapshot
            if msg == "snapshot":
                db = SessionLocal()
                try:
                    nodes = db.query(FederatedNode).all()
                    await manager.send_personal(
                        ws,
                        {
                            "event": "monitor.snapshot",
                            "data": {
                                "nodes": [
                                    {"id": n.id, "name": n.name, "status": n.status,
                                     "latency_ms": n.latency_ms, "bandwidth_mbps": n.bandwidth_mbps}
                                    for n in nodes
                                ]
                            },
                        },
                    )
                finally:
                    db.close()
    except WebSocketDisconnect:
        manager.disconnect(ws)
