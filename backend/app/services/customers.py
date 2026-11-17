"""Customer profile enrichment: everything valid about a customer, in one place."""
from __future__ import annotations

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import Alert, ConversationSession, Message, User


def customer_summary_map(db: Session, user_ids: list[int]) -> dict[int, dict]:
    """Build per-customer profiles (account fields + engagement stats).

    Returns ``{user_id: {...}}`` containing every non-sensitive account field
    plus aggregate counters. Runs in a fixed number of grouped queries no
    matter how many ids are passed (no N+1).
    """
    ids = list({uid for uid in user_ids if uid is not None})
    if not ids:
        return {}

    users = db.query(User).filter(User.id.in_(ids)).all()

    def _grouped(query) -> dict:
        return {key: value for key, value in query.all()}

    session_counts = _grouped(
        db.query(ConversationSession.user_id, func.count(ConversationSession.id))
        .filter(ConversationSession.user_id.in_(ids))
        .group_by(ConversationSession.user_id)
    )
    message_counts = _grouped(
        db.query(ConversationSession.user_id, func.count(Message.id))
        .join(Message, Message.session_id == ConversationSession.id)
        .filter(ConversationSession.user_id.in_(ids))
        .group_by(ConversationSession.user_id)
    )
    alert_counts = _grouped(
        db.query(ConversationSession.user_id, func.count(Alert.id))
        .join(Alert, Alert.session_id == ConversationSession.id)
        .filter(ConversationSession.user_id.in_(ids))
        .group_by(ConversationSession.user_id)
    )
    last_session = _grouped(
        db.query(ConversationSession.user_id, func.max(ConversationSession.created_at))
        .filter(ConversationSession.user_id.in_(ids))
        .group_by(ConversationSession.user_id)
    )
    last_message = _grouped(
        db.query(ConversationSession.user_id, func.max(Message.created_at))
        .join(Message, Message.session_id == ConversationSession.id)
        .filter(ConversationSession.user_id.in_(ids))
        .group_by(ConversationSession.user_id)
    )

    summaries: dict[int, dict] = {}
    for user in users:
        last_activity = max(
            (ts for ts in (last_session.get(user.id), last_message.get(user.id)) if ts),
            default=None,
        )
        summaries[user.id] = {
            "id": user.id,
            "email": user.email,
            "full_name": user.full_name,
            "role": user.role,
            "is_active": user.is_active,
            "member_since": user.created_at,
            "total_sessions": session_counts.get(user.id, 0),
            "total_messages": message_counts.get(user.id, 0),
            "total_alerts": alert_counts.get(user.id, 0),
            "last_activity": last_activity,
        }
    return summaries
