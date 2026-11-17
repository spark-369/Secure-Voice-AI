"""Conversational chat endpoint (REST, authenticated)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from fastapi.concurrency import run_in_threadpool
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models import User
from app.schemas.chat import ChatMessageIn, ChatReply
from app.services.conversation import (
    SessionNotFoundError,
    create_session,
    process_user_message,
)

router = APIRouter(tags=["chat"])


@router.post("/chat/message", response_model=ChatReply)
async def send_message(
    payload: ChatMessageIn,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ChatReply:
    """Send one customer utterance; receive the autonomous agent's reply.

    The heavy LLM generation runs in the threadpool so the event loop stays
    responsive; alert classification happens asynchronously via Celery.
    Requires authentication — customers can only continue their own sessions.
    """
    if payload.session_id:
        session_id = payload.session_id
    else:
        session_id = create_session(db, user=current_user).id
    try:
        result = await run_in_threadpool(
            process_user_message, db, session_id, payload.text, current_user
        )
    except SessionNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail="Session not found. Omit session_id to start a new one.",
        ) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return ChatReply(**result)

