"""Shared FastAPI dependencies: DB session, authentication and RBAC."""
from __future__ import annotations

from collections.abc import Generator, Callable

from fastapi import Depends, HTTPException, Query, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models import User
from app.services import auth as auth_service

# Kept in sync with the auth router mount point (main.py adds /api/v1).
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/token")


def get_db() -> Generator[Session, None, None]:
    """Request-scoped database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    """Validate the bearer token and load the active user it belongs to."""
    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = auth_service.decode_token(token, expected_type="access")
    except auth_service.InvalidTokenError:
        raise credentials_error from None

    user = db.get(User, int(payload["sub"]))
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User no longer exists",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Account is deactivated"
        )
    return user


def require_roles(*roles: str) -> Callable[..., User]:
    """Dependency factory enforcing role-based access (403 otherwise)."""

    def dependency(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"This action requires one of the roles: {', '.join(roles)}",
            )
        return user

    return dependency


# Prebuilt guards used across the routers.
require_agent = require_roles("agent", "admin")
require_admin = require_roles("admin")


def pagination_params(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> dict:
    """Reusable limit/offset query parameters."""
    return {"limit": limit, "offset": offset}

