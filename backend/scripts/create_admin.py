"""Create or promote an admin user.

Usage (from ``backend/`` with the virtualenv active):
    python -m scripts.create_admin --email admin@example.com --password 'S3curePass!1'
"""
from __future__ import annotations

import argparse
import getpass


def main() -> None:
    parser = argparse.ArgumentParser(description="Create or promote an admin user.")
    parser.add_argument("--email", required=True, help="Admin email address")
    parser.add_argument(
        "--password",
        default=None,
        help="Plaintext password (prompted if omitted; min 8 chars)",
    )
    parser.add_argument("--name", default=None, help="Optional full name")
    args = parser.parse_args()

    password = args.password or getpass.getpass("Password for the admin account: ")
    if len(password) < 8:
        raise SystemExit("Password must be at least 8 characters.")

    from app.core.config import get_settings
    from app.core.logging import configure_logging
    from app.db.session import SessionLocal, init_db
    from app.models import User
    from app.services import auth as auth_service

    configure_logging(get_settings().LOG_LEVEL)
    init_db()

    email = args.email.lower().strip()
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == email).first()
        if user is None:
            user = User(
                email=email,
                hashed_password=auth_service.hash_password(password),
                full_name=args.name,
                role="admin",
            )
            db.add(user)
            action = "created"
        else:
            user.role = "admin"
            if args.name:
                user.full_name = args.name
            action = "promoted"
        db.commit()
        print(f"Admin user {action}: {email}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
