"""Authentication endpoints: register, login (JSON + OAuth2 form), refresh, me."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.core.config import get_settings
from app.models import User
from app.schemas.auth import LoginIn, ProfileUpdateIn, RefreshIn, RegisterIn, TokenPair
from app.schemas.user import UserOut
from app.services import auth as auth_service

router = APIRouter(tags=["auth"])


def _token_pair(user: User) -> TokenPair:
    """Issue a fresh access/refresh pair for a verified user."""
    return TokenPair(
        access_token=auth_service.create_access_token(user_id=user.id, role=user.role),
        refresh_token=auth_service.create_refresh_token(user_id=user.id, role=user.role),
        role=user.role,
        expires_in=auth_service.access_token_lifetime_seconds(),
    )


def _authenticate(db: Session, email: str | None, password: str | None) -> User:
    user = db.query(User).filter(User.email == (email or "").lower().strip()).first()
    if user is None or not auth_service.verify_password(
        password or "", user.hashed_password
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Account is deactivated"
        )
    return user


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterIn, db: Session = Depends(get_db)) -> User:
    """Open registration: always creates a ``customer`` role account."""
    email = payload.email.lower().strip()
    if db.query(User).filter(User.email == email).first() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists",
        )
    user = User(
        email=email,
        hashed_password=auth_service.hash_password(payload.password),
        full_name=payload.full_name,
        role="customer",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.post("/login", response_model=TokenPair)
def login(payload: LoginIn, db: Session = Depends(get_db)) -> TokenPair:
    """JSON login used by the frontend."""
    user = _authenticate(db, payload.email, payload.password)
    return _token_pair(user)


@router.post("/token", response_model=TokenPair)
def oauth2_token(
    form: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
) -> TokenPair:
    """OAuth2 password flow (``username`` = email) — powers Swagger's Authorize."""
    user = _authenticate(db, form.username, form.password)
    return _token_pair(user)


@router.post("/refresh", response_model=TokenPair)
def refresh(payload: RefreshIn, db: Session = Depends(get_db)) -> TokenPair:
    """Exchange a valid refresh token for a brand-new token pair."""
    try:
        decoded = auth_service.decode_token(payload.refresh_token, expected_type="refresh")
    except auth_service.InvalidTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)
        ) from None
    user = db.get(User, int(decoded["sub"]))
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Account unavailable"
        )
    return _token_pair(user)


@router.get("/me", response_model=UserOut)
def me(current_user: User = Depends(get_current_user)) -> User:
    """Profile of the authenticated user."""
    return current_user


@router.patch("/me", response_model=UserOut)
def update_me(
    payload: ProfileUpdateIn,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> User:
    """Self-service profile update (password change re-verifies credentials)."""
    if payload.password is not None:
        if not payload.current_password or not auth_service.verify_password(
            payload.current_password, current_user.hashed_password
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Current password is incorrect",
            )
        current_user.hashed_password = auth_service.hash_password(payload.password)
    if payload.full_name is not None:
        current_user.full_name = payload.full_name
    db.commit()
    db.refresh(current_user)
    return current_user
