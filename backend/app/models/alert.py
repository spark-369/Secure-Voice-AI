"""Operational alerts raised from LLM classification of user messages."""
from __future__ import annotations

from typing import Any

from sqlalchemy import JSON, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin


class Alert(TimestampMixin, Base):
    """A classified risk/issue that the human support team must triage."""

    __tablename__ = "alerts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("sessions.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    message_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("messages.id", ondelete="SET NULL")
    )
    category: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    severity: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    scores: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    summary: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(
        String(16), default="open", index=True, nullable=False
    )  # open | acknowledged | resolved
    provider: Mapped[str] = mapped_column(String(32), default="ollama", nullable=False)

    # Many-to-one navigation to the owning conversation (and its customer).
    session: Mapped["ConversationSession"] = relationship(lazy="select")

    @property
    def customer_id(self) -> int | None:
        return self.session.user_id if self.session is not None else None

    @property
    def customer_email(self) -> str | None:
        if self.session is not None and self.session.user is not None:
            return self.session.user.email
        return None

    @property
    def customer_name(self) -> str | None:
        if self.session is not None and self.session.user is not None:
            return self.session.user.full_name
        return None

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Alert id={self.id} category={self.category} severity={self.severity}>"
