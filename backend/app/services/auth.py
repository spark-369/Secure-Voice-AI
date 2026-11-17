"""Password hashing (bcrypt) and JWT issuing/verification (PyJWT).

Tokens carry ``sub`` (user id), ``role`` (for fast RBAC context), ``type``
(``access`` | ``refresh``), ``iat`` and ``exp``. Verification is strict:
signature, expiry and token type are all enforced.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

import bcrypt
import jwt

from app.core.config import get_settings


class InvalidTokenError(Exception):
    """Raised when a token is missing, malformed, expired or of the wrong type."""


def hash_password(password: str) -> str:
    """Hash a plaintext password with bcrypt (salt auto-generated)."""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, hashed: str) -> bool:
    """Constant-time password check; returns False for malformed hashes too."""
    try:
        return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))
    except ValueError:
        return False


def _create_token(
    *, user_id: int, role: str, token_type: str, lifetime: timedelta
) -> str:
    settings = get_settings()
    now = datetime.now(timezone.utc)
    payload: dict[str, Any] = {
        "sub": str(user_id),
        "role": role,
        "type": token_type,
        "iat": now,
        "exp": now + lifetime,
        "jti": uuid.uuid4().hex,
    }
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def create_access_token(*, user_id: int, role: str) -> str:
    settings = get_settings()
    return _create_token(
        user_id=user_id,
        role=role,
        token_type="access",
        lifetime=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
    )


def create_refresh_token(*, user_id: int, role: str) -> str:
    settings = get_settings()
    return _create_token(
        user_id=user_id,
        role=role,
        token_type="refresh",
        lifetime=timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
    )


def decode_token(token: str, expected_type: str = "access") -> dict[str, Any]:
    """Verify signature/expiry/type and return the claims dict."""
    settings = get_settings()
    try:
        payload = jwt.decode(
            token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM]
        )
    except jwt.ExpiredSignatureError as exc:
        raise InvalidTokenError("Token has expired") from exc
    except jwt.InvalidTokenError as exc:
        raise InvalidTokenError("Token is invalid") from exc
    if payload.get("type") != expected_type:
        raise InvalidTokenError(f"Expected a {expected_type} token")
    if not payload.get("sub"):
        raise InvalidTokenError("Token has no subject")
    return payload


def access_token_lifetime_seconds() -> int:
    """Expose the configured access-token TTL (for login responses)."""
    return int(get_settings().ACCESS_TOKEN_EXPIRE_MINUTES * 60)
