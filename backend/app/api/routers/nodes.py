"""Federated Node Manager: register, monitor and manage participating nodes."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import get_client_ip, get_current_user, require_permission, user_org_scope
from app.core.audit import write_audit
from app.core.crypto import random_seed_bytes
from app.core.database import get_db
from app.core.rbac import Permission
from app.core.security import generate_rsa_keypair
from app.models.models import FederatedNode, NodeEvent, Organization
from app.schemas.schemas import MessageOut, NodeCreate, NodeOut, NodeUpdate

router = APIRouter(prefix="/nodes", tags=["nodes"])


def _node_out(node: FederatedNode, db: Session) -> NodeOut:
    out = NodeOut.model_validate(node)
    org = db.get(Organization, node.organization_id)
    out.organization_name = org.name if org else None
    return out


@router.get("", response_model=list[NodeOut])
def list_nodes(
    org_id: int | None = Query(None),
    status: str | None = Query(None),
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(Permission.VIEW_NODES)),
):
    scoped = user_org_scope(user, db)
    query = db.query(FederatedNode)
    if user.role not in ("admin", "coordinator"):
        query = query.filter(FederatedNode.organization_id.in_(scoped))
    if org_id:
        query = query.filter(FederatedNode.organization_id == org_id)
    if status:
        query = query.filter(FederatedNode.status == status)
    return [_node_out(n, db) for n in query.order_by(FederatedNode.name).all()]


@router.get("/health", response_model=dict)
def node_health(db: Session = Depends(get_db), user: User = Depends(require_permission(Permission.VIEW_NODES))):
    scoped = user_org_scope(user, db)
    query = db.query(FederatedNode)
    if user.role not in ("admin", "coordinator"):
        query = query.filter(FederatedNode.organization_id.in_(scoped))
    nodes = query.all()
    return {
        "total": len(nodes),
        "online": sum(1 for n in nodes if n.status == "online"),
        "degraded": sum(1 for n in nodes if n.status == "degraded"),
        "offline": sum(1 for n in nodes if n.status == "offline"),
        "avg_latency_ms": round(sum(n.latency_ms for n in nodes) / max(len(nodes), 1), 1),
        "avg_bandwidth_mbps": round(sum(n.bandwidth_mbps for n in nodes) / max(len(nodes), 1), 1),
        "mtls_verified": sum(1 for n in nodes if n.mTLS_verified),
        "total_trust": round(sum(n.trust_score for n in nodes) / max(len(nodes), 1), 4),
    }


@router.post("", response_model=NodeOut)
def create_node(
    body: NodeCreate,
    ip: str = Depends(get_client_ip),
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(Permission.MANAGE_NODES)),
):
    org = db.get(Organization, body.organization_id)
    if org is None:
        raise HTTPException(status_code=404, detail="Organization not found")
    if user.role not in ("admin", "coordinator") and user.organization_id != body.organization_id:
        raise HTTPException(status_code=403, detail="Cannot register nodes for other organizations")

    keypair = generate_rsa_keypair()
    node = FederatedNode(
        organization_id=body.organization_id,
        name=body.name,
        endpoint=body.endpoint,
        device_type=body.device_type,
        cpu_cores=body.cpu_cores,
        gpu_name=body.gpu_name,
        ram_gb=body.ram_gb,
        bandwidth_mbps=body.bandwidth_mbps,
        latency_ms=body.latency_ms,
        status="unknown",
        public_key=keypair["public_key"],
        cert_serial=f"MTLS-{random_seed_bytes(6).hex().upper()}",
        mTLS_verified=True,  # simulated mutual-TLS handshake on registration
    )
    db.add(node)
    db.commit()
    db.refresh(node)
    write_audit(db, action="node.register", entity_type="node", entity_id=node.id,
                actor_id=user.id, actor_email=user.email,
                details={"name": node.name, "mtls": node.mTLS_verified},
                ip=ip)
    return _node_out(node, db)


@router.get("/{node_id}", response_model=NodeOut)
def get_node(node_id: int, db: Session = Depends(get_db), user: User = Depends(require_permission(Permission.VIEW_NODES))):
    node = db.get(FederatedNode, node_id)
    if node is None:
        raise HTTPException(status_code=404, detail="Node not found")
    if user.role not in ("admin", "coordinator") and user.organization_id != node.organization_id:
        raise HTTPException(status_code=403, detail="Not permitted")
    return _node_out(node, db)


@router.put("/{node_id}", response_model=NodeOut)
def update_node(node_id: int, body: NodeUpdate, db: Session = Depends(get_db), user: User = Depends(require_permission(Permission.MANAGE_NODES))):
    node = db.get(FederatedNode, node_id)
    if node is None:
        raise HTTPException(status_code=404, detail="Node not found")
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(node, field, value)
    db.commit()
    db.refresh(node)
    write_audit(db, action="node.update", entity_type="node", entity_id=node_id,
                actor_id=user.id, actor_email=user.email, details=body.model_dump(exclude_unset=True))
    return _node_out(node, db)


@router.delete("/{node_id}", response_model=MessageOut)
def delete_node(node_id: int, db: Session = Depends(get_db), user: User = Depends(require_permission(Permission.MANAGE_NODES))):
    node = db.get(FederatedNode, node_id)
    if node is None:
        raise HTTPException(status_code=404, detail="Node not found")
    db.delete(node)
    db.commit()
    write_audit(db, action="node.delete", entity_type="node", entity_id=node_id,
                actor_id=user.id, actor_email=user.email, severity="warning")
    return MessageOut(message="Node removed")


@router.get("/{node_id}/events", response_model=list[dict])
def node_events(node_id: int, limit: int = Query(50), db: Session = Depends(get_db), user: User = Depends(require_permission(Permission.VIEW_NODES))):
    events = (
        db.query(NodeEvent)
        .filter(NodeEvent.node_id == node_id)
        .order_by(NodeEvent.created_at.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "id": e.id, "event_type": e.event_type, "message": e.message,
            "severity": e.severity, "created_at": e.created_at,
        }
        for e in events
    ]


@router.get("/{node_id}/handshake", response_model=dict)
def node_handshake(node_id: int, db: Session = Depends(get_db), user: User = Depends(require_permission(Permission.VIEW_NODES))):
    """Simulated mutual-TLS handshake inspection."""
    node = db.get(FederatedNode, node_id)
    if node is None:
        raise HTTPException(status_code=404, detail="Node not found")
    return {
        "node_id": node.id,
        "cert_serial": node.cert_serial,
        "mtls_verified": node.mTLS_verified,
        "public_key_algorithm": "RSA-2048",
        "cipher_suite": "TLS_AES_256_GCM_SHA384",
        "handshake_status": "established" if node.mTLS_verified else "pending",
        "trust_score": node.trust_score,
    }
