"""Alert CRUD + dashboard summary (role checks are enforced in the router layer)."""
from __future__ import annotations

from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import Alert, ConversationSession, Message


def create_alert(
    db: Session,
    *,
    session_id: str,
    category: str,
    severity: float,
    summary: str | None = None,
    confidence: float = 1.0,
    provider: str = "manual",
) -> Alert:
    """Insert an alert row (system classification or staff-created ticket)."""
    alert = Alert(
        session_id=session_id,
        category=category,
        severity=severity,
        confidence=confidence,
        scores={},
        summary=summary,
        status="open",
        provider=provider,
    )
    db.add(alert)
    db.commit()
    db.refresh(alert)
    return alert


def update_alert(db: Session, alert: Alert, changes: dict[str, Any]) -> Alert:
    """Apply a schema-validated partial-update dict."""
    for field in ("status", "category", "severity", "summary"):
        if field in changes and changes[field] is not None:
            setattr(alert, field, changes[field])
    db.commit()
    db.refresh(alert)
    return alert


def delete_alert(db: Session, alert: Alert) -> None:
    db.delete(alert)
    db.commit()


def alert_summary(db: Session) -> dict:
    """Aggregated counters for the agent dashboard."""
    settings = get_settings()

    def _count(query) -> int:
        return int(query.scalar() or 0)

    return {
        "total_alerts": _count(db.query(func.count(Alert.id))),
        "open_alerts": _count(
            db.query(func.count(Alert.id)).filter(Alert.status == "open")
        ),
        "acknowledged_alerts": _count(
            db.query(func.count(Alert.id)).filter(Alert.status == "acknowledged")
        ),
        "resolved_alerts": _count(
            db.query(func.count(Alert.id)).filter(Alert.status == "resolved")
        ),
        "high_severity_open": _count(
            db.query(func.count(Alert.id)).filter(
                Alert.status != "resolved",
                Alert.severity >= settings.ALERT_HIGH_SEVERITY,
            )
        ),
        "total_sessions": _count(db.query(func.count(ConversationSession.id))),
        "total_messages": _count(db.query(func.count(Message.id))),
    }
