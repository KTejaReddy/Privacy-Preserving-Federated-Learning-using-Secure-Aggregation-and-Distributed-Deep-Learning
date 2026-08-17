"""Organization Manager: CRUD for participating organizations."""
from __future__ import annotations

import re

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.deps import get_client_ip, get_current_user, require_permission, user_org_scope
from app.core.audit import write_audit
from app.core.database import get_db
from app.core.rbac import Permission
from app.models.models import Dataset, FederatedNode, Organization, User
from app.schemas.schemas import (
    MessageOut,
    OrganizationCreate,
    OrganizationOut,
    OrganizationUpdate,
)

router = APIRouter(prefix="/organizations", tags=["organizations"])


def _org_out(org: Organization, db: Session) -> OrganizationOut:
    out = OrganizationOut.model_validate(org)
    out.node_count = db.query(func.count(FederatedNode.id)).filter(FederatedNode.organization_id == org.id).scalar() or 0
    out.dataset_count = db.query(func.count(Dataset.id)).filter(Dataset.organization_id == org.id).scalar() or 0
    out.user_count = db.query(func.count(User.id)).filter(User.organization_id == org.id).scalar() or 0
    return out


@router.get("", response_model=list[OrganizationOut])
def list_organizations(
    q: str = Query("", description="filter by name"),
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(Permission.VIEW_ORGS)),
):
    scoped = user_org_scope(user, db)
    query = db.query(Organization)
    if user.role not in ("admin", "coordinator"):
        query = query.filter(Organization.id.in_(scoped))
    if q:
        query = query.filter(Organization.name.ilike(f"%{q}%"))
    return [_org_out(o, db) for o in query.order_by(Organization.name).all()]


@router.get("/stats", response_model=dict)
def organization_stats(db: Session = Depends(get_db), user: User = Depends(require_permission(Permission.VIEW_ORGS))):
    scoped = user_org_scope(user, db)
    orgs = db.query(Organization).filter(Organization.id.in_(scoped)).all()
    industries: dict = {}
    for o in orgs:
        industries[o.industry or "Other"] = industries.get(o.industry or "Other", 0) + 1
    total_nodes = sum(_org_out(o, db).node_count for o in orgs)
    total_datasets = sum(_org_out(o, db).dataset_count for o in orgs)
    return {
        "total": len(orgs),
        "by_industry": industries,
        "total_nodes": total_nodes,
        "total_datasets": total_datasets,
        "active": sum(1 for o in orgs if o.status == "active"),
        "total_samples": sum(d.sample_count for o in orgs for d in o.datasets),
    }


@router.get("/{org_id}", response_model=OrganizationOut)
def get_organization(org_id: int, db: Session = Depends(get_db), user: User = Depends(require_permission(Permission.VIEW_ORGS))):
    org = db.get(Organization, org_id)
    if org is None:
        raise HTTPException(status_code=404, detail="Organization not found")
    if user.role not in ("admin", "coordinator") and user.organization_id != org_id:
        raise HTTPException(status_code=403, detail="Not permitted")
    return _org_out(org, db)


@router.post("", response_model=OrganizationOut)
def create_organization(
    body: OrganizationCreate,
    ip: str = Depends(get_client_ip),
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(Permission.MANAGE_ORGS)),
):
    slug = re.sub(r"[^a-z0-9]+", "-", body.name.lower()).strip("-")
    if db.query(Organization).filter(Organization.slug == slug).first():
        slug = f"{slug}-{user.id}"
    org = Organization(
        name=body.name,
        slug=slug,
        industry=body.industry,
        country=body.country,
        description=body.description,
        compliance_level=body.compliance_level,
        data_guardian_enabled=body.data_guardian_enabled,
    )
    db.add(org)
    db.commit()
    db.refresh(org)
    write_audit(db, action="org.create", entity_type="organization", entity_id=org.id,
                actor_id=user.id, actor_email=user.email,
                ip=ip)
    return _org_out(org, db)


@router.put("/{org_id}", response_model=OrganizationOut)
def update_organization(
    org_id: int,
    body: OrganizationUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(Permission.MANAGE_ORGS)),
):
    org = db.get(Organization, org_id)
    if org is None:
        raise HTTPException(status_code=404, detail="Organization not found")
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(org, field, value)
    db.commit()
    db.refresh(org)
    write_audit(db, action="org.update", entity_type="organization", entity_id=org.id,
                actor_id=user.id, actor_email=user.email, details=body.model_dump(exclude_unset=True))
    return _org_out(org, db)


@router.delete("/{org_id}", response_model=MessageOut)
def delete_organization(org_id: int, db: Session = Depends(get_db), user: User = Depends(require_permission(Permission.MANAGE_ORGS))):
    org = db.get(Organization, org_id)
    if org is None:
        raise HTTPException(status_code=404, detail="Organization not found")
    db.delete(org)
    db.commit()
    write_audit(db, action="org.delete", entity_type="organization", entity_id=org_id,
                actor_id=user.id, actor_email=user.email, severity="warning")
    return MessageOut(message="Organization deleted")
