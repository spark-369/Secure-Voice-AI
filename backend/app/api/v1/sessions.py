"""Session lifecycle endpoints (authentication + ownership scoping)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db, pagination_params
from app.models import ConversationSession, User
from app.schemas.session import SessionCreate, SessionDetail, SessionOut, SessionUpdateIn
from app.services.conversation import (
    close_session,
    create_session,
    delete_session,
    get_session_scoped,
    list_sessions,
    update_session,
)

router = APIRouter(tags=["sessions"])


def _to_out(session: ConversationSession) -> SessionOut:
    out = SessionOut.model_validate(session)
    out.message_count = len(session.messages)
    return out


@router.post("", response_model=SessionOut, status_code=201)
def start_session(
    payload: SessionCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SessionOut:
    """Start a new support session owned by the authenticated user."""
    session = create_session(
        db,
        user=current_user,
        customer_name=payload.customer_name,
        channel=payload.channel,
        language=payload.language,
    )
    return _to_out(session)


@router.get("", response_model=list[SessionOut])
def index(
    params: dict = Depends(pagination_params),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[SessionOut]:
    """List sessions — customers see their own, agents/admins see all."""
    sessions = list_sessions(db, user=current_user, **params)
    return [_to_out(session) for session in sessions]


@router.get("/{session_id}", response_model=SessionDetail)
def show(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SessionDetail:
    """Fetch one session including its full transcript (ownership-aware)."""
    session = get_session_scoped(db, session_id, current_user)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    detail = SessionDetail.model_validate(session)
    detail.message_count = len(session.messages)
    return detail


@router.patch("/{session_id}", response_model=SessionOut)
def update(
    session_id: str,
    payload: SessionUpdateIn,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SessionOut:
    """Partial update (owner or staff): name / channel / language / status."""
    session = update_session(
        db,
        session_id,
        current_user,
        customer_name=payload.customer_name,
        channel=payload.channel,
        language=payload.language,
        status=payload.status,
    )
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return _to_out(session)


@router.post("/{session_id}/close", response_model=SessionOut)
def close(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SessionOut:
    """Mark a session as closed (owner or staff only)."""
    session = close_session(db, session_id, current_user)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return _to_out(session)


@router.delete("/{session_id}", status_code=204)
def delete(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    """Delete a session and its transcript (owner or admin)."""
    if not delete_session(db, session_id, current_user):
        raise HTTPException(status_code=404, detail="Session not found")
    return Response(status_code=204)


