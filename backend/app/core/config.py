"""Application configuration loaded from environment variables / `.env`."""
from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Central, typed settings (12-factor style). All values can be overridden via env."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=True,
    )

    # --- Application ------------------------------------------------------
    PROJECT_NAME: str = "SecureVoice AI"
    VERSION: str = "1.0.0"
    ENVIRONMENT: str = "development"  # development | production
    DEBUG: bool = False
    API_V1_PREFIX: str = "/api/v1"
    LOG_LEVEL: str = "INFO"

    # --- Database (PostgreSQL + SQLAlchemy) -------------------------------
    DATABASE_URL: str = (
        "postgresql+psycopg2://securevoice:securevoice@localhost:5432/securevoice"
    )
    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 20
    DB_ECHO: bool = False
    CREATE_TABLES_ON_STARTUP: bool = True

    # --- Redis (cache + rate limiting) -------------------------------------
    REDIS_URL: str = "redis://localhost:6379/0"
    CACHE_TTL_SECONDS: int = 300
    RATE_LIMIT_PER_MINUTE: int = 60

    # --- Celery -------------------------------------------------------------
    CELERY_BROKER_URL: str = "redis://localhost:6379/1"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/2"

    # --- AI inference (local Ollama server: chat + embeddings) --------------
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_TIMEOUT: int = 300  # seconds; small models can be slow on CPU
    LLM_MODEL_NAME: str = "hf.co/Qwen/Qwen2.5-0.5B-Instruct-GGUF:Q4_K_M"
    EMBEDDING_MODEL_NAME: str = "hf.co/Qwen/Qwen3-Embedding-0.6B-GGUF:Q8_0"
    LLM_MAX_NEW_TOKENS: int = 220  # mapped to num_predict in Ollama options
    LLM_TEMPERATURE: float = 0.7
    PRELOAD_MODELS: bool = False
    HISTORY_WINDOW: int = 8  # chat turns kept in the LLM prompt

    # --- RAG (Ollama embeddings + PostgreSQL chunk table) ----------------------
    RAG_CHUNK_SIZE: int = 700
    RAG_CHUNK_OVERLAP: int = 120
    RAG_TOP_K: int = 4
    RAG_MAX_DISTANCE: float = 1.2  # cosine distance cutoff for relevance

    # --- Alerting ---------------------------------------------------------------
    ALERT_HIGH_SEVERITY: float = 0.75

    # --- Authentication / Authorization (JWT + RBAC) ---------------------------
    JWT_SECRET_KEY: str = "change-me-in-production"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # --- Input limits ------------------------------------------------------------
    MAX_MESSAGE_CHARS: int = 2000
    CORS_ORIGINS: list[str] = [
        "http://localhost:5173",
        "http://localhost",
        "http://127.0.0.1",
    ]

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT.lower() == "production"


@lru_cache
def get_settings() -> Settings:
    """Return the cached singleton settings instance."""
    return Settings()
