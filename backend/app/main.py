"""FastAPI application factory and entrypoint (Uvicorn target: app.main:app)."""
from __future__ import annotations

import logging
import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse

from app.api.middleware import RateLimitMiddleware, RequestLoggingMiddleware
from app.api.v1.router import api_router
from app.api.v1.ws import router as ws_router
from app.core.config import get_settings
from app.core.logging import configure_logging

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    logger.info(
        "Starting %s v%s (%s)",
        settings.PROJECT_NAME,
        settings.VERSION,
        settings.ENVIRONMENT,
    )

    if settings.CREATE_TABLES_ON_STARTUP:
        from app.db.session import init_db

        init_db()
        logger.info("Database schema ensured")

    if settings.PRELOAD_MODELS:
        # Warm the models in background threads so startup stays responsive.
        def _warm(loader, name: str) -> None:
            try:
                loader()
                logger.info("%s preloaded", name)
            except Exception as exc:  # noqa: BLE001
                logger.warning("%s preload failed: %s", name, exc)

        from app.services.classifier import zero_shot_classifier
        from app.services.llm import llm_engine

        threading.Thread(target=_warm, args=(llm_engine.load, "LLM"), daemon=True).start()
        threading.Thread(
            target=_warm, args=(zero_shot_classifier.load, "Zero-shot classifier"), daemon=True
        ).start()

    yield
    logger.info("Shutdown complete")


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.LOG_LEVEL)

    docs_kwargs = (
        {"docs_url": None, "redoc_url": None, "openapi_url": None}
        if settings.is_production
        else {}
    )
    app = FastAPI(
        title=settings.PROJECT_NAME,
        version=settings.VERSION,
        description=(
            "Browser-based autonomous customer care: conversational LLM + RAG "
            "+ zero-shot alert classification."
        ),
        lifespan=lifespan,
        **docs_kwargs,
    )

    # Middlewares: the last one added runs first (CORS must wrap everything).
    app.add_middleware(GZipMiddleware, minimum_size=1024)
    app.add_middleware(RateLimitMiddleware)
    app.add_middleware(RequestLoggingMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(api_router, prefix=settings.API_V1_PREFIX)
    app.include_router(ws_router, prefix=settings.API_V1_PREFIX)

    @app.get("/", include_in_schema=False)
    async def root() -> dict:
        return {
            "service": settings.PROJECT_NAME,
            "version": settings.VERSION,
            "api": settings.API_V1_PREFIX,
            "docs": None if settings.is_production else "/docs",
        }

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(
        request: Request, exc: Exception
    ) -> JSONResponse:
        logger.exception("Unhandled error on %s %s", request.method, request.url.path)
        return JSONResponse(status_code=500, content={"detail": "Internal server error"})

    return app


app = create_app()
