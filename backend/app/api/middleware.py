"""ASGI middlewares: request logging/tracing and Redis-backed rate limiting."""
from __future__ import annotations

import logging
import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from app.core.config import get_settings
from app.services.cache import redis_cache

logger = logging.getLogger(__name__)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Attach an X-Request-ID and emit one structured line per request."""

    async def dispatch(self, request: Request, call_next):
        request_id = uuid.uuid4().hex[:12]
        started = time.perf_counter()
        response = await call_next(request)
        duration_ms = (time.perf_counter() - started) * 1000
        logger.info(
            "%s %s -> %s (%.1f ms) request_id=%s",
            request.method,
            request.url.path,
            response.status_code,
            duration_ms,
            request_id,
        )
        response.headers["X-Request-ID"] = request_id
        return response


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Fixed-window per-IP limiter backed by Redis; fails open when Redis is down."""

    async def dispatch(self, request: Request, call_next):
        settings = get_settings()
        path = request.url.path
        if path.startswith("/api") and not path.startswith(
            f"{settings.API_V1_PREFIX}/health"
        ):
            identifier = request.client.host if request.client else "anonymous"
            bucket = int(time.time() // 60)
            key = f"ratelimit:{identifier}:{bucket}"
            count = redis_cache.incr_with_expiry(key, window_seconds=90)
            if count is not None and count > settings.RATE_LIMIT_PER_MINUTE:
                return JSONResponse(
                    {"detail": "Rate limit exceeded. Please slow down."},
                    status_code=429,
                    headers={"Retry-After": "60"},
                )
        return await call_next(request)
