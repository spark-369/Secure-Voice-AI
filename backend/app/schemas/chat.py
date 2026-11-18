"""Chat request/response schemas."""
from __future__ import annotations

from pydantic import BaseModel, Field


class ChatMessageIn(BaseModel):
    """A user transcript coming from browser STT (or typed input)."""

    text: str = Field(min_length=1, max_length=2000, description="Customer utterance")
    session_id: str | None = Field(
        default=None,
        description="Existing session id; omit to automatically start a new session",
    )


class KnowledgeSource(BaseModel):
    """One retrieved knowledge-base chunk attached to a reply."""

    document_id: int
    title: str
    source: str = ""
    chunk_index: int = 0
    distance: float
    snippet: str = ""


class ChatReply(BaseModel):
    """The autonomous agent's answer plus operational metadata."""

    session_id: str
    reply: str
    user_message_id: int
    assistant_message_id: int
    latency_ms: int
    model: str
    sources: list[KnowledgeSource] = Field(default_factory=list)
    alert_pending: bool = Field(
        default=False,
        description="True when alert classification was queued with Celery",
    )
