"""User management endpoints (admin only)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.api.deps import get_db, pagination_params, require_admin
from app.models import User
from app.schemas.user import UserCreateIn, UserOut, UserUpdateIn
from app.services import auth as auth_service

router = APIRouter(tags=["users"])


def _ensure_unique_email(db: Session, email: str) -> str:
    email = email.lower().strip()
    if db.query(User).filter(User.email == email).first() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists",
        )
    return email


@router.get("", response_model=list[UserOut])
def index(
    params: dict = Depends(pagination_params),
    _admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> list[User]:
    """List accounts (newest first)."""
    return (
        db.query(User)
        .order_by(User.created_at.desc())
        .limit(params["limit"])
        .offset(params["offset"])
        .all()
    )


@router.post("", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def create(
    payload: UserCreateIn,
    _admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> User:
    """Create an account with any role (e.g. onboarding an agent)."""
    user = User(
        email=_ensure_unique_email(db, payload.email),
        hashed_password=auth_service.hash_password(payload.password),
        full_name=payload.full_name,
        role=payload.role,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.patch("/{user_id}", response_model=UserOut)
def update(
    user_id: int,
    payload: UserUpdateIn,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> User:
    """Change role / activation / profile / password (admins cannot lock out self)."""
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    if user.id == admin.id and (
        payload.role is not None and payload.role != "admin" or payload.is_active is False
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Admins cannot demote or deactivate their own account",
        )

    if payload.role is not None:
        user.role = payload.role
    if payload.is_active is not None:
        user.is_active = payload.is_active
    if payload.full_name is not None:
        user.full_name = payload.full_name
    if payload.password is not None:
        user.hashed_password = auth_service.hash_password(payload.password)
    db.commit()
    db.refresh(user)
    return user


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete(
    user_id: int,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> Response:
    """Delete an account (admins cannot delete themselves)."""
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    if user.id == admin.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Admins cannot delete their own account",
        )
    db.delete(user)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
