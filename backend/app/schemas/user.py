"""User account schemas."""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

RoleName = Literal["customer", "agent", "admin"]


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    full_name: str | None = None
    role: str
    is_active: bool
    created_at: datetime


class UserCreateIn(BaseModel):
    """Admin-created accounts (can be any role, e.g. onboarding an agent)."""

    email: str = Field(min_length=5, max_length=255)
    password: str = Field(min_length=8, max_length=128)
    full_name: str | None = Field(default=None, max_length=120)
    role: RoleName = "customer"


class UserUpdateIn(BaseModel):
    """Partial profile/role updates performed by an admin."""

    full_name: str | None = Field(default=None, max_length=120)
    role: RoleName | None = None
    is_active: bool | None = None
    password: str | None = Field(default=None, min_length=8, max_length=128)


class CustomerSummary(BaseModel):
    """Every valid (non-sensitive) customer field + engagement stats.

    Attached to staff-facing views (e.g. the alert queue) so agents see the
    full customer context. Never contains credentials.
    """

    id: int
    email: str
    full_name: str | None = None
    role: str
    is_active: bool
    member_since: datetime
    total_sessions: int = 0
    total_messages: int = 0
    total_alerts: int = 0
    last_activity: datetime | None = None
