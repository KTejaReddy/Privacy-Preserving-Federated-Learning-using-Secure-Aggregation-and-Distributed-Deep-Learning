"""Training Center: create, run, monitor and manage federated training jobs."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import get_client_ip, get_current_user, require_permission, user_org_scope
from app.core.audit import write_audit
from app.core.database import get_db
from app.core.rbac import Permission
from app.models.models import FederatedRound, Organization, TrainingJob, User
from app.schemas.schemas import JobAction, MessageOut, RoundOut, TrainingJobCreate, TrainingJobOut
from app.workers.tasks import execute_training_job

router = APIRouter(prefix="/training", tags=["training"])


def _job_out(job: TrainingJob) -> TrainingJobOut:
    return TrainingJobOut.model_validate(job)


@router.get("", response_model=list[TrainingJobOut])
def list_jobs(
    status: str | None = Query(None),
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(Permission.VIEW_TRAINING)),
):
    query = db.query(TrainingJob)
    if user.role not in ("admin", "coordinator"):
        query = query.filter(TrainingJob.organization_id == user.organization_id) if user.organization_id else query.filter(TrainingJob.organization_id.is_(None))
    if status:
        query = query.filter(TrainingJob.status == status)
    return [_job_out(j) for j in query.order_by(TrainingJob.created_at.desc()).all()]


@router.get("/stats", response_model=dict)
def training_stats(db: Session = Depends(get_db), user: User = Depends(require_permission(Permission.VIEW_TRAINING))):
    query = db.query(TrainingJob)
    if user.role not in ("admin", "coordinator"):
        query = query.filter(TrainingJob.organization_id == user.organization_id) if user.organization_id else query.filter(TrainingJob.organization_id.is_(None))
    jobs = query.all()
    completed = [j for j in jobs if j.status == "completed"]
    return {
        "total": len(jobs),
        "running": sum(1 for j in jobs if j.status in ("running", "approved")),
        "completed": len(completed),
        "failed": sum(1 for j in jobs if j.status == "failed"),
        "total_rounds_executed": sum(j.current_round for j in jobs),
        "avg_accuracy": round(sum(j.metrics_json.get("final_accuracy", 0) for j in completed) / max(len(completed), 1), 4),
    }


@router.post("", response_model=TrainingJobOut)
def create_job(
    body: TrainingJobCreate,
    ip: str = Depends(get_client_ip),
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(Permission.CREATE_TRAINING)),
):
    if body.dataset_ids and user.role not in ("admin", "coordinator"):
        from app.models.models import Dataset

        ds = db.query(Dataset).filter(Dataset.id.in_(body.dataset_ids)).all()
        if any(d.organization_id != user.organization_id for d in ds):
            raise HTTPException(status_code=403, detail="Cannot use datasets from other organizations")

    org_id = body.organization_id or user.organization_id
    job = TrainingJob(
        name=body.name,
        description=body.description,
        status="draft",
        algorithm=body.algorithm,
        model_architecture=body.model_architecture,
        hidden_layers=body.hidden_layers,
        total_rounds=body.total_rounds,
        client_fraction=body.client_fraction,
        learning_rate=body.learning_rate,
        batch_size=body.batch_size,
        local_epochs=body.local_epochs,
        mu=body.mu,
        server_momentum=body.server_momentum,
        secure_aggregation=body.secure_aggregation,
        privacy_budget_per_round=body.privacy_budget_per_round,
        use_encryption=body.use_encryption,
        dataset_ids=body.dataset_ids,
        selected_node_ids=body.selected_node_ids,
        created_by=user.id,
        organization_id=org_id,
        metrics_json={
            "data_distribution": body.data_distribution,
            "local_samples": body.local_samples,
            "noise": body.noise,
            "input_dim": body.input_dim,
            "seed": body.seed,
        },
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    write_audit(db, action="training.create", entity_type="training_job", entity_id=job.id,
                actor_id=user.id, actor_email=user.email, ip=ip,
                details={"algorithm": job.algorithm, "rounds": job.total_rounds})
    return _job_out(job)


@router.get("/{job_id}", response_model=TrainingJobOut)
def get_job(job_id: int, db: Session = Depends(get_db), user: User = Depends(require_permission(Permission.VIEW_TRAINING))):
    job = db.get(TrainingJob, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    if user.role not in ("admin", "coordinator") and job.organization_id != user.organization_id:
        raise HTTPException(status_code=403, detail="Not permitted")
    return _job_out(job)


@router.get("/{job_id}/rounds", response_model=list[RoundOut])
def job_rounds(job_id: int, db: Session = Depends(get_db), user: User = Depends(require_permission(Permission.VIEW_TRAINING))):
    job = db.get(TrainingJob, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    rounds = (
        db.query(FederatedRound)
        .filter(FederatedRound.job_id == job_id)
        .order_by(FederatedRound.round_number)
        .all()
    )
    return [RoundOut.model_validate(r) for r in rounds]


@router.post("/{job_id}/action", response_model=TrainingJobOut)
def job_action(
    job_id: int,
    body: JobAction,
    ip: str = Depends(get_client_ip),
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(Permission.RUN_TRAINING)),
):
    job = db.get(TrainingJob, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")

    action = body.action
    if action == "start":
        if job.status in ("running",):
            raise HTTPException(status_code=400, detail="Job already running")
        job.status = "approved"
        db.commit()
        # execute asynchronously (Celery if configured, else thread pool)
        execute_training_job.delay(job_id) if hasattr(execute_training_job, "delay") else _run_inline(job_id)
        write_audit(db, action="training.start", entity_type="training_job", entity_id=job_id,
                    actor_id=user.id, actor_email=user.email, ip=ip)
    elif action == "pause":
        job.status = "paused"
        db.commit()
    elif action == "resume":
        if job.status != "paused":
            raise HTTPException(status_code=400, detail="Job not paused")
        job.status = "running"
        db.commit()
    elif action == "cancel":
        job.status = "cancelled"
        db.commit()
    elif action == "approve":
        job.status = "approved"
        write_audit(db, action="training.approve", entity_type="training_job", entity_id=job_id,
                    actor_id=user.id, actor_email=user.email, details={"notes": body.notes})
        db.commit()
    elif action == "reject":
        job.status = "draft"
        write_audit(db, action="training.reject", entity_type="training_job", entity_id=job_id,
                    actor_id=user.id, actor_email=user.email, details={"notes": body.notes})
        db.commit()
    else:
        raise HTTPException(status_code=400, detail="Unknown action")
    db.refresh(job)
    return _job_out(job)


@router.delete("/{job_id}", response_model=MessageOut)
def delete_job(job_id: int, db: Session = Depends(get_db), user: User = Depends(require_permission(Permission.MANAGE_TRAINING))):
    job = db.get(TrainingJob, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    db.delete(job)
    db.commit()
    write_audit(db, action="training.delete", entity_type="training_job", entity_id=job_id,
                actor_id=user.id, actor_email=user.email, severity="warning")
    return MessageOut(message="Job deleted")


def _run_inline(job_id: int) -> None:
    import threading

    threading.Thread(target=execute_training_job, args=(job_id,), daemon=True).start()
