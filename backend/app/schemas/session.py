"""Session and message schemas."""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class SessionCreate(BaseModel):
    customer_name: str | None = Field(default=None, max_length=120)
    channel: str = Field(default="voice", max_length=32)
    language: str = Field(default="en-US", max_length=16)


class SessionUpdateIn(BaseModel):
    """Partial session update (owner or staff)."""

    customer_name: str | None = Field(default=None, max_length=120)
    channel: str | None = Field(default=None, max_length=32)
    language: str | None = Field(default=None, max_length=16)
    status: Literal["active", "closed"] | None = None


class MessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    session_id: str
    role: str
    content: str
    created_at: datetime
    latency_ms: int | None = None
    model: str | None = None


class SessionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    customer_name: str | None = None
    channel: str
    language: str
    status: str
    created_at: datetime
    message_count: int = 0


class SessionDetail(SessionOut):
    """A session including its full message transcript."""

    messages: list[MessageOut] = Field(default_factory=list)
