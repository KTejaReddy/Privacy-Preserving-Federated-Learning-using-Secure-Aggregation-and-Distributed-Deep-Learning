"""Settings: current user's profile, password change and preferences."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_client_ip, get_current_user
from app.core.audit import write_audit
from app.core.database import get_db
from app.core.security import hash_password, verify_password
from app.models.models import User
from app.schemas.schemas import MessageOut, UserOut

router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("/profile", response_model=UserOut)
def profile(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    out = UserOut.model_validate(user)
    if user.organization_id:
        from app.models.models import Organization

        org = db.get(Organization, user.organization_id)
        out.organization_name = org.name if org else None
    return out


@router.put("/profile", response_model=UserOut)
def update_profile(body: dict, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    for field in ("full_name", "title"):
        if field in body:
            setattr(user, field, body[field])
    db.commit()
    db.refresh(user)
    return UserOut.model_validate(user)


@router.post("/change-password", response_model=MessageOut)
def change_password(body: dict, ip: str = Depends(get_client_ip), user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    current = body.get("current_password", "")
    new = body.get("new_password", "")
    if not verify_password(current, user.password_hash):
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    if len(new) < 8:
        raise HTTPException(status_code=400, detail="New password must be at least 8 characters")
    user.password_hash = hash_password(new)
    db.commit()
    write_audit(db, action="settings.password_change", entity_type="user", entity_id=user.id,
                actor_id=user.id, actor_email=user.email, ip=ip)
    return MessageOut(message="Password updated")


@router.get("/preferences", response_model=dict)
def preferences(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return {"theme": "dark", "notifications": True, "realtime": True, "default_page": "dashboard"}
