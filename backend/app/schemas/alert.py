"""Alert schemas."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.user import CustomerSummary


class AlertOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    session_id: str
    message_id: int | None = None
    customer_id: int | None = None
    customer_email: str | None = None
    customer_name: str | None = None
    customer: CustomerSummary | None = None
    session_created_at: datetime | None = None
    category: str
    severity: float
    confidence: float
    scores: dict[str, Any] = Field(default_factory=dict)
    summary: str | None = None
    status: str
    provider: str = "ollama"
    created_at: datetime


class AlertCreateIn(BaseModel):
    """Manually raise an alert on a session (staff-created ticket)."""

    session_id: str
    category: str = Field(min_length=1, max_length=64)
    severity: float = Field(ge=0.0, le=1.0)
    summary: str | None = Field(default=None, max_length=2000)


class AlertUpdate(BaseModel):
    """Partial triage update — at least one field must be provided."""

    status: Literal["open", "acknowledged", "resolved"] | None = None
    category: str | None = Field(default=None, min_length=1, max_length=64)
    severity: float | None = Field(default=None, ge=0.0, le=1.0)
    summary: str | None = Field(default=None, max_length=2000)


class AlertSummaryOut(BaseModel):
    """Aggregated counters powering the agent dashboard cards."""

    total_alerts: int = 0
    open_alerts: int = 0
    acknowledged_alerts: int = 0
    resolved_alerts: int = 0
    high_severity_open: int = 0
    total_sessions: int = 0
    total_messages: int = 0
