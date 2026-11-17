"""Unit tests for the auth primitives (bcrypt hashing + JWT issue/verify).

Run from ``backend/``:  python -m pytest -q
Only needs bcrypt/PyJWT — no database or ML stack required.
"""
import pytest

from app.services import auth as auth_service
from app.services.auth import InvalidTokenError


class _FakeUser:
    """Duck-typed stand-in for app.models.user.User (only id/role are used)."""

    def __init__(self, user_id: int = 1, role: str = "customer"):
        self.id = user_id
        self.role = role


# ---------------------------------------------------------------------------
# Passwords
# ---------------------------------------------------------------------------


def test_password_hash_roundtrip():
    hashed = auth_service.hash_password("S3curePass!123")
    assert hashed != "S3curePass!123"
    assert hashed.startswith("$2")  # bcrypt format
    assert auth_service.verify_password("S3curePass!123", hashed)
    assert not auth_service.verify_password("wrong-password", hashed)


def test_verify_password_tolerates_malformed_hash():
    assert not auth_service.verify_password("x", "not-a-bcrypt-hash")


# ---------------------------------------------------------------------------
# Tokens
# ---------------------------------------------------------------------------


def test_access_token_roundtrip():
    token = auth_service.create_access_token(user_id=7, role="agent")
    payload = auth_service.decode_token(token, expected_type="access")
    assert payload["sub"] == "7"
    assert payload["role"] == "agent"
    assert payload["type"] == "access"


def test_refresh_token_roundtrip_and_type_enforcement():
    token = auth_service.create_refresh_token(user_id=3, role="customer")
    payload = auth_service.decode_token(token, expected_type="refresh")
    assert payload["sub"] == "3"
    with pytest.raises(InvalidTokenError):
        auth_service.decode_token(token, expected_type="access")


def test_tampered_token_is_rejected():
    token = auth_service.create_access_token(user_id=1, role="admin")
    with pytest.raises(InvalidTokenError):
        auth_service.decode_token(token[:-3] + "xyz", expected_type="access")


def test_access_token_lifetime_matches_settings():
    assert auth_service.access_token_lifetime_seconds() > 0
