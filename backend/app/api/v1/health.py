"""Liveness and readiness endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.core.config import get_settings
from app.services.cache import redis_cache
from app.services.rag import knowledge_index

router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> dict:
    """Liveness probe (no dependency checks — always cheap)."""
    settings = get_settings()
    return {
        "status": "ok",
        "service": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "environment": settings.ENVIRONMENT,
    }


@router.get("/health/ready")
async def ready(db: Session = Depends(get_db)) -> JSONResponse:
    """Readiness probe: PostgreSQL, Redis and the vector store."""
    components: dict[str, str] = {}

    try:
        db.execute(text("SELECT 1"))
        components["postgres"] = "up"
    except Exception as exc:  # noqa: BLE001
        components["postgres"] = f"down ({exc.__class__.__name__})"

    components["redis"] = "up" if redis_cache.ping() else "down"
    components["vector_store"] = "up" if knowledge_index.is_available() else "down"

    healthy = all(value == "up" for value in components.values())
    return JSONResponse(
        status_code=200 if healthy else 503,
        content={"status": "ready" if healthy else "degraded", "components": components},
    )
