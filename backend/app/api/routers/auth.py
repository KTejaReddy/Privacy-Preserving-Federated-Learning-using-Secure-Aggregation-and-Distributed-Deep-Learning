"""Authentication: register, login, refresh, and current-user profile."""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.api.deps import client_ip, get_current_user
from app.core.audit import write_audit
from app.core.config import settings
from app.core.database import get_db
from app.core.rbac import ALL_ROLES, role_label
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.models.models import Organization, User
from app.schemas.schemas import (
    LoginRequest,
    MeOut,
    MessageOut,
    RefreshRequest,
    RegisterRequest,
    TokenResponse,
    UserOut,
)

router = APIRouter(prefix="/auth", tags=["auth"])


def _user_out(user: User, db: Session) -> UserOut:
    out = UserOut.model_validate(user)
    org = db.get(Organization, user.organization_id) if user.organization_id else None
    out.organization_name = org.name if org else None
    return out


@router.post("/register", response_model=TokenResponse)
def register(body: RegisterRequest, request: Request, db: Session = Depends(get_db)):
    if body.role not in ALL_ROLES:
        raise HTTPException(status_code=400, detail="Invalid role")
    exists = db.query(User).filter(User.email == body.email.lower()).first()
    if exists:
        raise HTTPException(status_code=409, detail="Email already registered")
    user = User(
        email=body.email.lower(),
        full_name=body.full_name,
        password_hash=hash_password(body.password),
        role=body.role,
        organization_id=body.organization_id,
        title=body.title,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    write_audit(db, action="auth.register", entity_type="user", entity_id=user.id,
                actor_id=user.id, actor_email=user.email, ip=client_ip(request))
    return TokenResponse(
        access_token=create_access_token(str(user.id), {"role": user.role}),
        refresh_token=create_refresh_token(str(user.id)),
        user=_user_out(user, db),
    )


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest, request: Request, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == body.email.lower()).first()
    if user is None or not verify_password(body.password, user.password_hash):
        write_audit(db, action="auth.login_failed", entity_type="user",
                    actor_email=body.email, ip=client_ip(request), severity="warning")
        raise HTTPException(status_code=401, detail="Invalid credentials")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account disabled")
    user.last_login = datetime.now(timezone.utc)
    db.commit()
    write_audit(db, action="auth.login", entity_type="user", entity_id=user.id,
                actor_id=user.id, actor_email=user.email, ip=client_ip(request))
    return TokenResponse(
        access_token=create_access_token(str(user.id), {"role": user.role}),
        refresh_token=create_refresh_token(str(user.id)),
        user=_user_out(user, db),
    )


@router.post("/refresh", response_model=TokenResponse)
def refresh(body: RefreshRequest, db: Session = Depends(get_db)):
    try:
        payload = decode_token(body.refresh_token)
        user = db.get(User, int(payload["sub"]))
        if user is None or not user.is_active:
            raise HTTPException(status_code=401, detail="Invalid refresh token")
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid refresh token") from None
    return TokenResponse(
        access_token=create_access_token(str(user.id), {"role": user.role}),
        refresh_token=create_refresh_token(str(user.id)),
        user=_user_out(user, db),
    )


@router.get("/me", response_model=MeOut)
def me(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    from app.core.rbac import role_permissions

    flags = settings.feature_flag_map
    return MeOut(
        user=_user_out(user, db),
        permissions=sorted(role_permissions(user.role)),
        role_label=role_label(user.role),
        feature_flags=flags,
    )


@router.post("/logout", response_model=MessageOut)
def logout(request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    write_audit(db, action="auth.logout", entity_type="user", entity_id=user.id,
                actor_id=user.id, actor_email=user.email, ip=client_ip(request))
    return MessageOut(message="Logged out")
