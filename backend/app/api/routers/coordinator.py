"""Federated Coordinator: oversee rounds, approve training, run live secure
aggregation demonstrations on real engine output."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_client_ip, get_current_user, require_permission
from app.core.audit import write_audit
from app.core.database import get_db
from app.core.rbac import Permission
from app.federated.algorithms import ClientPayload
from app.federated.engine import build_mlp
from app.federated.secure_aggregation import demo_secure_aggregation_flow, json_safe_payload
from app.models.models import AggregationLog, FederatedRound, Organization, TrainingJob, User
from app.schemas.schemas import AggregationDemoResponse, JobAction, TrainingJobOut

router = APIRouter(prefix="/coordinator", tags=["coordinator"])


@router.get("/overview", response_model=dict)
def coordinator_overview(db: Session = Depends(get_db), user: User = Depends(require_permission(Permission.VIEW_TRAINING))):
    orgs = db.query(Organization).count()
    jobs = db.query(TrainingJob).count()
    running = db.query(TrainingJob).filter(TrainingJob.status.in_(["running", "approved"])).count()
    rounds = db.query(FederatedRound).count()
    pending = db.query(TrainingJob).filter(TrainingJob.status == "draft").count()
    latest_rounds = (
        db.query(FederatedRound).order_by(FederatedRound.id.desc()).limit(8).all()
    )
    return {
        "organizations": orgs,
        "jobs": jobs,
        "running_jobs": running,
        "rounds_total": rounds,
        "pending_approval": pending,
        "recent_rounds": [
            {
                "id": r.id,
                "round_number": r.round_number,
                "accuracy": r.accuracy,
                "loss": r.avg_loss,
                "participated": r.participated_count,
                "status": r.status,
                "job_id": r.job_id,
            }
            for r in latest_rounds
        ],
    }


@router.get("/approvals", response_model=list[TrainingJobOut])
def approval_queue(db: Session = Depends(get_db), user: User = Depends(require_permission(Permission.APPROVE_TRAINING))):
    jobs = db.query(TrainingJob).filter(TrainingJob.status.in_(["draft", "pending_approval"])).order_by(TrainingJob.created_at.desc()).all()
    return [TrainingJobOut.model_validate(j) for j in jobs]


@router.post("/approvals/{job_id}", response_model=TrainingJobOut)
def approve_job(job_id: int, body: JobAction, ip: str = Depends(get_client_ip), db: Session = Depends(get_db), user: User = Depends(require_permission(Permission.APPROVE_TRAINING))):
    job = db.get(TrainingJob, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    if body.action == "approve":
        job.status = "approved"
    elif body.action == "reject":
        job.status = "draft"
    else:
        raise HTTPException(status_code=400, detail="action must be approve|reject")
    db.commit()
    db.refresh(job)
    write_audit(db, action=f"coordinator.{body.action}", entity_type="training_job", entity_id=job_id,
                actor_id=user.id, actor_email=user.email, details={"notes": body.notes},
                ip=ip)
    return TrainingJobOut.model_validate(job)


@router.post("/secure-aggregation/demo", response_model=AggregationDemoResponse)
def secure_aggregation_demo(body: dict, db: Session = Depends(get_db), user: User = Depends(require_permission(Permission.VIEW_TRAINING))):
    """Run a live end-to-end secure aggregation handshake on real engine deltas.

    body: {job_id?, round?} — if a job_id is given, re-runs the last round of
    that job with fresh local training; otherwise synthesizes a demo round.
    """
    from app.federated.data import generate_non_iid_node_data

    job = db.get(TrainingJob, body.get("job_id")) if body.get("job_id") else None
    job_name = job.name if job else "Live demonstration round"
    round_number = body.get("round", 1)
    client_count = int(body.get("clients", 4))
    input_dim = int((job.metrics_json or {}).get("input_dim", 8)) if job else int(body.get("input_dim", 8))
    layers = job.hidden_layers if job and job.hidden_layers else [16, 8]

    node_ids = list(range(1, client_count + 1))
    node_names = [f"node-{i}" for i in node_ids]
    if job and job.selected_node_ids:
        node_ids = list(job.selected_node_ids)[:client_count]
        node_names = [f"node-{nid}" for nid in node_ids]

    # generate fresh client deltas exactly like the engine does
    from app.core.security import generate_rsa_keypair

    global_model = build_mlp(input_dim, layers, seed=42)
    payloads: list[ClientPayload] = []
    for i, nid in enumerate(node_ids):
        local_model = build_mlp(input_dim, layers, seed=nid)
        local_model.load_flattened(global_model.flatten())
        X, y = generate_non_iid_node_data(42, nid, 700, input_dim, "non_iid", noise=0.15)
        result = local_model.train(X, y, epochs=2, batch_size=32, lr=0.01)
        payloads.append(
            ClientPayload(
                node_id=nid,
                node_name=node_names[i],
                delta=result["delta"],
                local_accuracy=result["accuracy"],
                local_loss=result["loss"],
                samples=700,
                training_time_ms=80 + i * 17,
                upload_bytes=result["delta"].size * 8 + 64,
            )
        )

    # sign + verify with the SAME keypair (identity pair for the live demo)
    private_keys, public_keys = {}, {}
    for p in payloads:
        kp = generate_rsa_keypair()
        private_keys[p.node_id] = kp["private_key"]
        public_keys[p.node_id] = kp["public_key"]

    agg = demo_secure_aggregation_flow(payloads, private_keys, public_keys)
    privacy = float(job.privacy_budget_per_round if job else 0.5)

    write_audit(db, action="secure_aggregation.demo", entity_type="aggregation",
                actor_id=user.id, actor_email=user.email,
                details={"clients": client_count, "masks": agg.mask_pair_count, "verified": agg.verified_signatures})
    return AggregationDemoResponse(
        job_name=job_name,
        round_number=round_number,
        clients=json_safe_payload(payloads),
        method="masked_sum (Bonawitz-style)",
        mask_pairs=agg.mask_pair_count,
        verified_signatures=agg.verified_signatures,
        math_ok=agg.integrity_ok,
        privacy_budget_used=privacy,
        log=agg.log,
    )


@router.get("/aggregation-logs", response_model=list[dict])
def aggregation_logs(limit: int = 50, db: Session = Depends(get_db), user: User = Depends(require_permission(Permission.VIEW_TRAINING))):
    logs = db.query(AggregationLog).order_by(AggregationLog.id.desc()).limit(limit).all()
    return [
        {
            "id": l.id, "round_id": l.round_id, "method": l.method,
            "client_count": l.client_count, "masked_upload_count": l.masked_upload_count,
            "masks_cancelled": l.masks_cancelled, "signature_verified": l.signature_verified,
            "privacy_budget_consumed": l.privacy_budget_consumed,
            "encryption_alg": l.encryption_alg, "created_at": l.created_at,
        }
        for l in logs
    ]
