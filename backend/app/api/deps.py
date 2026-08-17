"""Shared FastAPI dependencies: authentication + RBAC permission guards."""
from __future__ import annotations

from typing import Optional

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.rbac import Permission, has_permission, role_label
from app.core.security import decode_token
from app.models.models import User

bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    try:
        payload = decode_token(credentials.credentials)
        user_id = int(payload.get("sub", "0"))
    except Exception:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token") from None
    user = db.get(User, user_id)
    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User inactive or missing")
    return user


def require_permission(permission: Permission):
    """Dependency factory enforcing a permission on the current user."""

    def checker(user: User = Depends(get_current_user)) -> User:
        if not has_permission(user.role, permission):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
        return user

    return checker


def current_user(request: Request, db: Session = Depends(get_db)) -> User:
    """FastAPI dependency alias so endpoints can inject the raw user."""
    return get_current_user(request, db=db)


def client_ip(request: Request) -> str:
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else ""


def get_client_ip(request: Request) -> str:
    """FastAPI dependency returning the client IP (works in every endpoint)."""
    return client_ip(request)


def user_org_scope(user: User, db: Session, view_orgs_perm: bool = False):
    """Return the set of organization ids a user may operate on.

    Platform roles (admin/coordinator) may see all; org-bound roles see only
    their own organization.
    """
    if user.role in ("admin", "coordinator"):
        from app.models.models import Organization

        return [o.id for o in db.query(Organization).all()]
    if user.organization_id:
        return [user.organization_id]
    return []
