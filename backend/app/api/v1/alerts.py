"""Alert CRUD + triage endpoints (agent/admin; deletes are admin-only)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session, joinedload

from app.api.deps import get_db, require_agent, require_admin
from app.models import Alert, ConversationSession, User
from app.schemas.alert import AlertCreateIn, AlertOut, AlertSummaryOut, AlertUpdate
from app.services.alerts import alert_summary, create_alert, delete_alert, update_alert
from app.services.customers import customer_summary_map

router = APIRouter(tags=["alerts"])


def _serialize(db: Session, alerts: list[Alert]) -> list[AlertOut]:
    """Convert ORM alerts to AlertOut, enriching full customer profiles."""
    user_ids = [alert.customer_id for alert in alerts if alert.customer_id is not None]
    summaries = customer_summary_map(db, user_ids)
    result: list[AlertOut] = []
    for alert in alerts:
        item = AlertOut.model_validate(alert)
        item.session_created_at = alert.session.created_at if alert.session else None
        if alert.customer_id is not None:
            item.customer = summaries.get(alert.customer_id)
        result.append(item)
    return result


@router.get("/summary", response_model=AlertSummaryOut)
def summary(
    _agent: User = Depends(require_agent),
    db: Session = Depends(get_db),
) -> AlertSummaryOut:
    """Aggregated counters (declared before ``/{alert_id}`` to avoid path clashes)."""
    return AlertSummaryOut(**alert_summary(db))


@router.post("", response_model=AlertOut, status_code=201)
def create(
    payload: AlertCreateIn,
    _agent: User = Depends(require_agent),
    db: Session = Depends(get_db),
) -> Alert:
    """Manually raise an alert on an existing session (staff-created ticket)."""
    if db.get(ConversationSession, payload.session_id) is None:
        raise HTTPException(status_code=404, detail="Session not found")
    alert = create_alert(
        db,
        session_id=payload.session_id,
        category=payload.category,
        severity=payload.severity,
        summary=payload.summary,
    )
    return _serialize(db, [alert])[0]


@router.get("", response_model=list[AlertOut])
def index(
    status: str | None = Query(default=None, pattern="^(open|acknowledged|resolved)$"),
    session_id: str | None = Query(default=None),
    min_severity: float | None = Query(default=None, ge=0.0, le=1.0),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    _agent: User = Depends(require_agent),
    db: Session = Depends(get_db),
) -> list[Alert]:
    """List alerts with optional filters (newest first), incl. customer info."""
    query = db.query(Alert).options(
        joinedload(Alert.session).joinedload(ConversationSession.user)
    )
    if status:
        query = query.filter(Alert.status == status)
    if session_id:
        query = query.filter(Alert.session_id == session_id)
    if min_severity is not None:
        query = query.filter(Alert.severity >= min_severity)
    rows = query.order_by(Alert.created_at.desc()).limit(limit).offset(offset).all()
    return _serialize(db, rows)


@router.patch("/{alert_id}", response_model=AlertOut)
def update(
    alert_id: int,
    payload: AlertUpdate,
    _agent: User = Depends(require_agent),
    db: Session = Depends(get_db),
) -> Alert:
    """Triage update: status and/or category / severity / summary."""
    alert = db.get(Alert, alert_id)
    if alert is None:
        raise HTTPException(status_code=404, detail="Alert not found")
    changes = payload.model_dump(exclude_unset=True)
    if not changes:
        raise HTTPException(status_code=422, detail="No fields to update")
    alert = update_alert(db, alert, changes)
    return _serialize(db, [alert])[0]


@router.delete("/{alert_id}", status_code=204)
def delete(
    alert_id: int,
    _admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> Response:
    """Permanently delete an alert record (admin only)."""
    alert = db.get(Alert, alert_id)
    if alert is None:
        raise HTTPException(status_code=404, detail="Alert not found")
    delete_alert(db, alert)
    return Response(status_code=204)


