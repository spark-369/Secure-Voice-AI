"""WebSocket endpoint for realtime voice chat (token-authenticated)."""
from __future__ import annotations

import json
import logging

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from fastapi.concurrency import run_in_threadpool
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.core.config import get_settings
from app.models import User
from app.services import auth as auth_service
from app.services.conversation import SessionNotFoundError, process_user_message
from app.utils.text import sanitize_user_text

logger = logging.getLogger(__name__)

router = APIRouter(tags=["ws"])


@router.websocket("/ws/{session_id}")
async def voice_chat(
    websocket: WebSocket, session_id: str, db: Session = Depends(get_db)
) -> None:
    """Realtime duplex chat for voice clients.

    Auth: browsers cannot set headers during the WebSocket handshake, so the
    access token is passed as ``?token=<access_token>``. The socket is denied
    (HTTP 403 at handshake) when the token is missing/invalid, and customers
    may only connect to their own sessions.

    Client → ``{"type": "user_transcript", "text": "..."}``
    Server → ``{"type": "assistant_reply", ...ChatReply fields}`` / ``error``
    """
    settings = get_settings()

    user: User | None = None
    token = websocket.query_params.get("token")
    if token:
        try:
            claims = auth_service.decode_token(token, expected_type="access")
            candidate = db.get(User, int(claims["sub"]))
            if candidate is not None and candidate.is_active:
                user = candidate
        except (auth_service.InvalidTokenError, ValueError):
            user = None
    if user is None:
        # Closing before accept answers the handshake with HTTP 403.
        await websocket.close(code=1008)
        return

    await websocket.accept()
    await websocket.send_json(
        {"type": "ready", "session_id": session_id, "user_id": user.id}
    )
    try:
        while True:
            try:
                data = await websocket.receive_json()
            except json.JSONDecodeError:
                await websocket.send_json({"type": "error", "detail": "Malformed JSON"})
                continue

            if data.get("type") != "user_transcript":
                await websocket.send_json(
                    {"type": "error", "detail": "Unsupported message type"}
                )
                continue

            text = sanitize_user_text(
                str(data.get("text", "")), settings.MAX_MESSAGE_CHARS
            )
            if not text:
                await websocket.send_json({"type": "error", "detail": "Empty transcript"})
                continue

            try:
                result = await run_in_threadpool(
                    process_user_message, db, session_id, text, user
                )
            except SessionNotFoundError:
                await websocket.send_json({"type": "error", "detail": "Unknown session"})
                await websocket.close(code=4404)
                return

            await websocket.send_json({"type": "assistant_reply", **result})
    except WebSocketDisconnect:
        logger.info("WebSocket disconnected (session=%s)", session_id)
    except Exception:  # noqa: BLE001
        logger.exception("WebSocket error (session=%s)", session_id)
        try:
            await websocket.close(code=1011)
        except Exception:  # noqa: BLE001
            pass

