"""Aggregated v1 API router."""
from __future__ import annotations

from fastapi import APIRouter

from app.api.v1 import alerts, auth, chat, health, knowledge, sessions, users

api_router = APIRouter()
api_router.include_router(auth.router, prefix="/auth")
api_router.include_router(users.router, prefix="/users")
api_router.include_router(health.router)
api_router.include_router(sessions.router, prefix="/sessions")
api_router.include_router(chat.router)
api_router.include_router(alerts.router, prefix="/alerts")
api_router.include_router(knowledge.router)


