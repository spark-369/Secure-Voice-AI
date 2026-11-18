"""One-off migration adding auth columns/tables to an existing local database.

Safe to run multiple times: PostgreSQL gets proper idempotent in-place ALTERs.
"""
from __future__ import annotations

from sqlalchemy import text

from app.core.config import get_settings
from app.core.logging import configure_logging
from app.db.session import engine, init_db


def main() -> None:
    configure_logging(get_settings().LOG_LEVEL)

    # Creates the new `users` table (and any other missing tables).
    init_db()

    with engine.begin() as connection:
        connection.execute(
            text("ALTER TABLE sessions ADD COLUMN IF NOT EXISTS user_id INTEGER")
        )
        connection.execute(
            text(
                "CREATE INDEX IF NOT EXISTS ix_sessions_user_id ON sessions (user_id)"
            )
        )
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
    print("Auth migration complete: users table + sessions.user_id ready.")


if __name__ == "__main__":
    main()
