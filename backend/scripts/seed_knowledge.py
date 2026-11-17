"""Seed the knowledge base with the bundled starter documents — RBAC-gated.

The operation reuses the same authorization boundary as the API: the caller
must authenticate with valid credentials **and** hold an active ``admin``
role. Anything else is refused, so the knowledge base can never be modified
outside the RBAC rules.

Usage (from ``backend/`` with the virtualenv active):
    python -m scripts.seed_knowledge --email admin@example.com
    # password is prompted (hidden); or pass --password for scripts/CI
"""
from __future__ import annotations

import argparse
import getpass
import json
import sys
from pathlib import Path

SEED_PATH = Path(__file__).resolve().parents[1] / "app" / "data" / "knowledge_seed.json"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Seed the RAG knowledge base (requires an active admin account)."
    )
    parser.add_argument("--email", required=True, help="Admin email address")
    parser.add_argument(
        "--password", default=None, help="Admin password (prompted if omitted)"
    )
    args = parser.parse_args()

    from app.core.config import get_settings
    from app.core.logging import configure_logging
    from app.db.session import SessionLocal, init_db
    from app.models import User
    from app.services import auth as auth_service
    from app.tasks.tasks import _ingest_documents_impl

    configure_logging(get_settings().LOG_LEVEL)
    init_db()

    password = args.password or getpass.getpass("Admin password: ")

    # ---- RBAC check: identical rules to the API's admin-only endpoints ----
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == args.email.lower().strip()).first()
        if user is None or not auth_service.verify_password(password, user.hashed_password):
            print("Authentication failed: incorrect email or password.", file=sys.stderr)
            raise SystemExit(1)
        if not user.is_active or user.role != "admin":
            print(
                "Authorization failed: seeding the knowledge base requires an active "
                "admin account.",
                file=sys.stderr,
            )
            raise SystemExit(1)

        if not SEED_PATH.exists():
            raise SystemExit(f"Seed file not found: {SEED_PATH}")

        documents = json.loads(SEED_PATH.read_text(encoding="utf-8"))
        result = _ingest_documents_impl(documents)
        print(
            f"Admin '{user.email}' ingested {result['ingested']} knowledge document(s)."
        )
    finally:
        db.close()


if __name__ == "__main__":
    main()
