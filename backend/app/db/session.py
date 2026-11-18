"""Engine and session factory for the local PostgreSQL database."""
from __future__ import annotations

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker

from app.core.config import get_settings
from app.db.base import Base

settings = get_settings()

engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,
    echo=settings.DB_ECHO,
    future=True,
    pool_size=settings.DB_POOL_SIZE,
    max_overflow=settings.DB_MAX_OVERFLOW,
)

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
    expire_on_commit=False,
    future=True,
)


def get_db():
    """FastAPI dependency yielding a request-scoped session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """Create all tables, then apply lightweight dev-time column patches.

    ``create_all`` only creates *missing* tables — it never alters existing
    ones. For local development we bridge that gap with idempotent, inspected
    ALTERs so later schema additions (e.g. auth columns) apply automatically
    on startup. Production deployments should use Alembic migrations instead.
    """
    import app.models  # noqa: F401  (registers every model on the metadata)

    Base.metadata.create_all(bind=engine)
    _patch_sessions_user_id()


def _patch_sessions_user_id() -> None:
    """Add ``sessions.user_id`` to databases created before auth existed."""
    inspector = inspect(engine)
    if "sessions" not in inspector.get_table_names():
        return
    columns = {column["name"] for column in inspector.get_columns("sessions")}
    if "user_id" in columns:
        return

    with engine.begin() as connection:
        connection.execute(text("ALTER TABLE sessions ADD COLUMN user_id INTEGER"))
        connection.execute(
            text("CREATE INDEX IF NOT EXISTS ix_sessions_user_id ON sessions (user_id)")
        )
        # Attach the FK constraint idempotently (PostgreSQL-only project).
        connection.execute(
            text(
                """
                DO $$
                BEGIN
                    IF NOT EXISTS (
                        SELECT 1 FROM pg_constraint
                        WHERE conname = 'fk_sessions_user_id_users'
                    ) THEN
                        ALTER TABLE sessions
                            ADD CONSTRAINT fk_sessions_user_id_users
                            FOREIGN KEY (user_id) REFERENCES users (id)
                            ON DELETE SET NULL;
                    END IF;
                END $$;
                """
            )
        )

