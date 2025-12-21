"""One-time DB migration helper: add ban-related columns to `users`.

Run on server where DATABASE_URL is configured (or edit below).
This script is idempotent.

Example (Linux):
  python3 add_user_ban_columns.py

Example (Windows PowerShell):
  py add_user_ban_columns.py
"""

from __future__ import annotations

import os

from sqlalchemy import text

from app.db.database import SessionLocal


def main() -> None:
    db = SessionLocal()
    try:
        # Postgres: add columns if missing.
        db.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS is_banned boolean NOT NULL DEFAULT false"))
        db.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS banned_at timestamp"))
        db.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS banned_reason varchar(255)"))
        db.commit()
        print("OK: users ban columns ensured")
    finally:
        db.close()


if __name__ == "__main__":
    # Ensure app can import even if run from repo root
    # Expected usage: run from backend/ folder.
    if os.getcwd().endswith("\\backend") or os.getcwd().endswith("/backend"):
        main()
    else:
        main()
