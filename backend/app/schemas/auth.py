"""Authentication schemas (register / login / tokens)."""
from __future__ import annotations

from pydantic import BaseModel, Field


class RegisterIn(BaseModel):
    email: str = Field(min_length=5, max_length=255)
    password: str = Field(min_length=8, max_length=128)
    full_name: str | None = Field(default=None, max_length=120)


class LoginIn(BaseModel):
    email: str
    password: str


class RefreshIn(BaseModel):
    refresh_token: str


class TokenPair(BaseModel):
    """Access + refresh token bundle returned by the login endpoints."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    role: str
    expires_in: int = Field(description="Access-token lifetime in seconds")


class ProfileUpdateIn(BaseModel):
    """Self-service profile update; password change re-verifies credentials."""

    full_name: str | None = Field(default=None, max_length=120)
    current_password: str | None = None
    password: str | None = Field(default=None, min_length=8, max_length=128)
