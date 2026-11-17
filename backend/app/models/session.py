"""Customer support conversation sessions."""
from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin


def _new_uuid() -> str:
    return str(uuid.uuid4())


class ConversationSession(TimestampMixin, Base):
    """One customer support conversation (a browser voice/text call)."""

    __tablename__ = "sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_uuid)
    user_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    customer_name: Mapped[str | None] = mapped_column(String(120))
    channel: Mapped[str] = mapped_column(String(32), default="voice", nullable=False)
    language: Mapped[str] = mapped_column(String(16), default="en-US", nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="active", nullable=False)

    messages: Mapped[list["Message"]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="Message.id",
    )

    # Owning account (joined eagerly — sessions are always shown with their owner).
    user: Mapped["User"] = relationship(lazy="joined")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<ConversationSession id={self.id} status={self.status}>"
