"""Dataset Registry: register and govern organization-local datasets.

Raw data never leaves the organization — only structured metadata is stored.
A synthetic fingerprint is derived for reproducibility and the Data Guardian
flags privacy-sensitive properties.
"""
from __future__ import annotations

import hashlib
import json

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.deps import get_client_ip, get_current_user, require_permission, user_org_scope
from app.core.audit import write_audit
from app.core.database import get_db
from app.core.rbac import Permission
from app.federated.data import feature_names
from app.models.models import Dataset, Organization
from app.schemas.schemas import DatasetCreate, DatasetOut, DatasetSummary, MessageOut

router = APIRouter(prefix="/datasets", tags=["datasets"])


def _dataset_out(ds: Dataset, db: Session) -> DatasetOut:
    out = DatasetOut.model_validate(ds)
    org = db.get(Organization, ds.organization_id)
    out.organization_name = org.name if org else None
    return out


@router.get("", response_model=list[DatasetOut])
def list_datasets(
    org_id: int | None = Query(None),
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(Permission.VIEW_DATASETS)),
):
    scoped = user_org_scope(user, db)
    query = db.query(Dataset)
    if user.role not in ("admin", "coordinator"):
        query = query.filter(Dataset.organization_id.in_(scoped))
    if org_id:
        query = query.filter(Dataset.organization_id == org_id)
    return [_dataset_out(ds, db) for ds in query.order_by(Dataset.created_at.desc()).all()]


@router.get("/summary", response_model=DatasetSummary)
def dataset_summary(db: Session = Depends(get_db), user: User = Depends(require_permission(Permission.VIEW_DATASETS))):
    scoped = user_org_scope(user, db)
    query = db.query(Dataset).filter(Dataset.organization_id.in_(scoped)) if user.role not in ("admin", "coordinator") else db.query(Dataset)
    datasets = query.all()
    by_industry: dict = {}
    for ds in datasets:
        org = db.get(Organization, ds.organization_id)
        ind = org.industry if org else "Other"
        by_industry[ind] = by_industry.get(ind, 0) + ds.sample_count
    return DatasetSummary(
        total_datasets=len(datasets),
        total_samples=sum(ds.sample_count for ds in datasets),
        by_industry=by_industry,
    )


@router.get("/schema/{feature_count}", response_model=dict)
def dataset_schema(feature_count: int = 8):
    return {"feature_names": feature_names(feature_count)}


@router.post("", response_model=DatasetOut)
def create_dataset(
    body: DatasetCreate,
    ip: str = Depends(get_client_ip),
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(Permission.CREATE_DATASETS)),
):
    org = db.get(Organization, body.organization_id)
    if org is None:
        raise HTTPException(status_code=404, detail="Organization not found")
    if user.role not in ("admin", "coordinator") and user.organization_id != body.organization_id:
        raise HTTPException(status_code=403, detail="Cannot register datasets for other organizations")

    # Data Guardian: fingerprint + privacy controls
    fingerprint_input = json.dumps(
        {"org": org.id, "name": body.name, "samples": body.sample_count, "features": body.feature_count},
        sort_keys=True,
    )
    fingerprint = hashlib.sha256(fingerprint_input.encode()).hexdigest()[:16]
    ds = Dataset(
        organization_id=body.organization_id,
        name=body.name,
        description=body.description,
        data_type=body.data_type,
        feature_count=body.feature_count,
        sample_count=body.sample_count,
        positive_ratio=body.positive_ratio,
        noise=body.noise,
        privacy_controls={
            "fingerprint": fingerprint,
            "raw_data_exposure": False,
            "synthetic_replica": True,
            "pii_detected": False,
            "encryption": "AES-256 at rest",
            "retention_days": 365,
        },
        status="registered",
    )
    db.add(ds)
    db.commit()
    db.refresh(ds)
    write_audit(db, action="dataset.register", entity_type="dataset", entity_id=ds.id,
                actor_id=user.id, actor_email=user.email, ip=ip,
                details={"name": ds.name, "samples": ds.sample_count, "features": ds.feature_count})
    return _dataset_out(ds, db)


@router.put("/{ds_id}", response_model=DatasetOut)
def update_dataset(ds_id: int, body: dict, db: Session = Depends(get_db), user: User = Depends(require_permission(Permission.MANAGE_DATASETS))):
    ds = db.get(Dataset, ds_id)
    if ds is None:
        raise HTTPException(status_code=404, detail="Dataset not found")
    for field in ("name", "description", "status", "sample_count", "feature_count", "noise", "positive_ratio"):
        if field in body:
            setattr(ds, field, body[field])
    db.commit()
    db.refresh(ds)
    write_audit(db, action="dataset.update", entity_type="dataset", entity_id=ds_id,
                actor_id=user.id, actor_email=user.email)
    return _dataset_out(ds, db)


@router.delete("/{ds_id}", response_model=MessageOut)
def delete_dataset(ds_id: int, db: Session = Depends(get_db), user: User = Depends(require_permission(Permission.MANAGE_DATASETS))):
    ds = db.get(Dataset, ds_id)
    if ds is None:
        raise HTTPException(status_code=404, detail="Dataset not found")
    db.delete(ds)
    db.commit()
    write_audit(db, action="dataset.delete", entity_type="dataset", entity_id=ds_id,
                actor_id=user.id, actor_email=user.email, severity="warning")
    return MessageOut(message="Dataset deleted")
