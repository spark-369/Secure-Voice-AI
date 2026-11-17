"""Business logic for the autonomous conversation pipeline.

Flow: persist user turn → retrieve RAG context → generate with Qwen →
persist assistant turn → enqueue Celery classification for alerting.
"""
from __future__ import annotations

import logging
import time

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import ConversationSession, Message, User
from app.services.llm import llm_engine
from app.services.rag import knowledge_index
from app.utils.text import (
    FALLBACK_REPLY,
    build_chat_messages,
    format_context_block,
    sanitize_user_text,
)

logger = logging.getLogger(__name__)


class SessionNotFoundError(LookupError):
    """Raised when a session id does not exist."""


def create_session(
    db: Session,
    *,
    user: User | None = None,
    customer_name: str | None = None,
    channel: str = "voice",
    language: str = "en-US",
) -> ConversationSession:
    session = ConversationSession(
        customer_name=customer_name,
        channel=channel,
        language=language,
        user_id=user.id if user else None,
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


def get_session(db: Session, session_id: str) -> ConversationSession | None:
    return db.get(ConversationSession, session_id)


def get_session_scoped(
    db: Session, session_id: str, user: User
) -> ConversationSession | None:
    """Ownership-aware fetch: customers may only reach their own sessions."""
    session = get_session(db, session_id)
    if session is None:
        return None
    if user.role == "customer" and session.user_id != user.id:
        return None
    return session


def list_sessions(
    db: Session, *, user: User, limit: int = 20, offset: int = 0
) -> list[ConversationSession]:
    """Customers see their own sessions; agents/admins see everything."""
    query = db.query(ConversationSession)
    if user.role == "customer":
        query = query.filter(ConversationSession.user_id == user.id)
    return (
        query.order_by(ConversationSession.created_at.desc())
        .limit(limit)
        .offset(offset)
        .all()
    )


def close_session(
    db: Session, session_id: str, user: User
) -> ConversationSession | None:
    session = get_session_scoped(db, session_id, user)
    if session is None:
        return None
    session.status = "closed"
    db.commit()
    db.refresh(session)
    return session


def update_session(
    db: Session,
    session_id: str,
    user: User,
    *,
    customer_name: str | None = None,
    channel: str | None = None,
    language: str | None = None,
    status: str | None = None,
) -> ConversationSession | None:
    """Partial update (owner or staff; scope violations surface as 404 upstream)."""
    session = get_session_scoped(db, session_id, user)
    if session is None:
        return None
    if customer_name is not None:
        session.customer_name = customer_name
    if channel is not None:
        session.channel = channel
    if language is not None:
        session.language = language
    if status is not None:
        session.status = status
    db.commit()
    db.refresh(session)
    return session


def delete_session(db: Session, session_id: str, user: User) -> bool:
    """Delete a session (owner or admin). Messages cascade; alerts via FK."""
    session = get_session_scoped(db, session_id, user)
    if session is None:
        return False
    if session.user_id != user.id and user.role != "admin":
        return False
    db.delete(session)
    db.commit()
    return True


def _recent_history(db: Session, session_id: str, window: int) -> list[dict[str, str]]:
    """Last ``window`` turns (chronological) *before* the new user message."""
    rows = (
        db.query(Message)
        .filter(Message.session_id == session_id)
        .order_by(Message.id.desc())
        .limit(window)
        .all()
    )
    rows.reverse()
    return [{"role": row.role, "content": row.content} for row in rows]


def process_user_message(
    db: Session, session_id: str, text: str, user: User
) -> dict:
    """Run the full autonomous pipeline for one customer utterance."""
    settings = get_settings()
    session = get_session_scoped(db, session_id, user)
    if session is None:
        raise SessionNotFoundError(session_id)

    clean_text = sanitize_user_text(text, settings.MAX_MESSAGE_CHARS)
    if not clean_text:
        raise ValueError("Message text is empty after sanitisation")

    # History is captured *before* the new user turn is persisted.
    history = _recent_history(db, session_id, settings.HISTORY_WINDOW)

    user_message = Message(session_id=session_id, role="user", content=clean_text)
    db.add(user_message)
    db.commit()
    db.refresh(user_message)

    hits = knowledge_index.query(clean_text)
    context_block = format_context_block(hits)
    chat_messages = build_chat_messages(
        history=history, user_text=clean_text, context_block=context_block
    )

    started = time.perf_counter()
    model_name = settings.LLM_MODEL_NAME
    try:
        reply = llm_engine.generate(chat_messages) or FALLBACK_REPLY
    except Exception as exc:  # noqa: BLE001 - never break the conversation
        logger.exception("LLM generation failed (%s); using fallback reply", exc)
        reply = FALLBACK_REPLY
        model_name = "fallback"
    latency_ms = int((time.perf_counter() - started) * 1000)

    assistant_message = Message(
        session_id=session_id,
        role="assistant",
        content=reply,
        latency_ms=latency_ms,
        model=model_name,
    )
    db.add(assistant_message)
    db.commit()
    db.refresh(assistant_message)

    alert_pending = _enqueue_classification(user_message.id, session_id, clean_text)

    sources = [
        {
            "document_id": hit.get("document_id", 0),
            "title": hit.get("title", ""),
            "source": hit.get("source", ""),
            "chunk_index": hit.get("chunk_index", 0),
            "distance": hit.get("distance", 0.0),
            "snippet": (hit.get("text", "") or "")[:180],
        }
        for hit in hits
    ]

    return {
        "session_id": session_id,
        "reply": reply,
        "user_message_id": user_message.id,
        "assistant_message_id": assistant_message.id,
        "latency_ms": latency_ms,
        "model": model_name,
        "sources": sources,
        "alert_pending": alert_pending,
    }


def _enqueue_classification(message_id: int, session_id: str, text: str) -> bool:
    """Queue zero-shot classification on the Celery worker."""
    try:
        from app.tasks.tasks import classify_and_alert

        async_result = classify_and_alert.delay(message_id, session_id, text)
        logger.info("Queued alert classification task=%s", getattr(async_result, "id", "?"))
        return True
    except Exception as exc:  # noqa: BLE001 - broker down must not break chat
        logger.warning(
            "Could not enqueue classification task (%s); alert skipped for this message",
            exc,
        )
        return False




