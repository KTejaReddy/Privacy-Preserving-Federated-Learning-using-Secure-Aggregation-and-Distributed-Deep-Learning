"""Admin Panel: user administration, feature flags, system settings."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_client_ip, require_permission
from app.core.audit import write_audit
from app.core.database import get_db
from app.core.rbac import ALL_ROLES, Permission, role_label
from app.core.security import hash_password
from app.models.models import FeatureFlag, Organization, Setting, User
from app.schemas.schemas import (
    FeatureFlagUpdate,
    MessageOut,
    RegisterRequest,
    SettingUpdate,
    UserOut,
)

router = APIRouter(prefix="/admin", tags=["admin"])

admin = require_permission(Permission.MANAGE_PLATFORM)


def _user_out(u: User, db: Session) -> UserOut:
    out = UserOut.model_validate(u)
    org = db.get(Organization, u.organization_id) if u.organization_id else None
    out.organization_name = org.name if org else None
    return out


@router.get("/users", response_model=list[UserOut])
def list_users(db: Session = Depends(get_db), user: User = Depends(admin)):
    return [_user_out(u, db) for u in db.query(User).order_by(User.created_at.desc()).all()]


@router.post("/users", response_model=UserOut)
def create_user(body: RegisterRequest, ip: str = Depends(get_client_ip), db: Session = Depends(get_db), user: User = Depends(admin)):
    if body.role not in ALL_ROLES:
        raise HTTPException(status_code=400, detail="Invalid role")
    if db.query(User).filter(User.email == body.email.lower()).first():
        raise HTTPException(status_code=409, detail="Email already exists")
    u = User(
        email=body.email.lower(), full_name=body.full_name,
        password_hash=hash_password(body.password), role=body.role,
        organization_id=body.organization_id, title=body.title,
    )
    db.add(u)
    db.commit()
    db.refresh(u)
    write_audit(db, action="admin.user.create", entity_type="user", entity_id=u.id,
                actor_id=user.id, actor_email=user.email, ip=ip,
                details={"role": u.role})
    return _user_out(u, db)


@router.put("/users/{user_id}", response_model=UserOut)
def update_user(user_id: int, body: dict, ip: str = Depends(get_client_ip), db: Session = Depends(get_db), user: User = Depends(admin)):
    u = db.get(User, user_id)
    if u is None:
        raise HTTPException(status_code=404, detail="User not found")
    for field in ("full_name", "role", "title", "organization_id", "is_active", "mfa_enabled"):
        if field in body:
            setattr(u, field, body[field])
    if "password" in body and body["password"]:
        u.password_hash = hash_password(body["password"])
    db.commit()
    db.refresh(u)
    write_audit(db, action="admin.user.update", entity_type="user", entity_id=user_id,
                actor_id=user.id, actor_email=user.email, ip=ip,
                details={k: body.get(k) for k in ("role", "is_active") if k in body})
    return _user_out(u, db)


@router.delete("/users/{user_id}", response_model=MessageOut)
def delete_user(user_id: int, ip: str = Depends(get_client_ip), db: Session = Depends(get_db), user: User = Depends(admin)):
    u = db.get(User, user_id)
    if u is None:
        raise HTTPException(status_code=404, detail="User not found")
    if u.id == user.id:
        raise HTTPException(status_code=400, detail="Cannot delete yourself")
    db.delete(u)
    db.commit()
    write_audit(db, action="admin.user.delete", entity_type="user", entity_id=user_id,
                actor_id=user.id, actor_email=user.email, severity="warning", ip=ip)
    return MessageOut(message="User deleted")


@router.get("/roles", response_model=list[dict])
def roles_list(db: Session = Depends(get_db), user: User = Depends(admin)):
    return [{"role": r, "label": role_label(r)} for r in ALL_ROLES]


@router.get("/feature-flags", response_model=list[dict])
def feature_flags(db: Session = Depends(get_db), user: User = Depends(admin)):
    from app.core.config import settings

    rows = []
    for key, enabled in settings.feature_flag_map.items():
        flag = db.get(FeatureFlag, key)
        rows.append(
            {
                "key": key,
                "enabled": flag.enabled if flag else enabled,
                "description": flag.description if flag else f"Feature flag: {key}",
            }
        )
    return rows


@router.put("/feature-flags/{key}", response_model=dict)
def update_flag(key: str, body: FeatureFlagUpdate, ip: str = Depends(get_client_ip), db: Session = Depends(get_db), user: User = Depends(admin)):
    flag = db.get(FeatureFlag, key)
    if flag is None:
        flag = FeatureFlag(key=key, enabled=body.enabled, description=body.description)
        db.add(flag)
    else:
        flag.enabled = body.enabled
        if body.description:
            flag.description = body.description
    db.commit()
    write_audit(db, action="admin.feature_flag", entity_type="feature_flag", entity_id=key,
                actor_id=user.id, actor_email=user.email, ip=ip,
                details={"enabled": body.enabled})
    return {"key": key, "enabled": body.enabled}


@router.get("/settings", response_model=list[dict])
def list_settings(db: Session = Depends(get_db), user: User = Depends(admin)):
    return [{"key": s.key, "value": s.value} for s in db.query(Setting).order_by(Setting.key).all()]


@router.put("/settings/{key}", response_model=dict)
def update_setting(key: str, body: SettingUpdate, ip: str = Depends(get_client_ip), db: Session = Depends(get_db), user: User = Depends(admin)):
    setting = db.get(Setting, key)
    if setting is None:
        setting = Setting(key=key, value=body.value)
        db.add(setting)
    else:
        setting.value = body.value
    db.commit()
    write_audit(db, action="admin.setting.update", entity_type="setting", entity_id=key,
                actor_id=user.id, actor_email=user.email, ip=ip)
    return {"key": key, "value": body.value}


@router.get("/system", response_model=dict)
def system_info(db: Session = Depends(get_db), user: User = Depends(admin)):
    import platform

    from app.core.config import settings

    import numpy as np

    return {
        "app": settings.APP_NAME,
        "environment": settings.ENV,
        "python": platform.python_version(),
        "numpy": np.__version__,
        "database": "sqlite" if settings.DATABASE_URL.startswith("sqlite") else "postgresql",
        "users": db.query(User).count(),
        "orgs": db.query(Organization).count(),
        "workers": "celery" if __import__("app.workers.celery_app", fromlist=["USE_CELERY"]).USE_CELERY else "thread-pool",
        "uptime_ok": True,
    }
