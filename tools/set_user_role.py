import argparse
import os
import sys

# Ensure project root (backend/) is importable when running as: python tools/set_user_role.py
BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from app.db.database import SessionLocal  # noqa: E402
from app.db import models  # noqa: E402


ROLES_ORDER = [
    "user",
    "support",
    "curator",
    "moderator",
    "admin",
    "manager",
    "superadmin",
]

ROLE_ALIASES = {
    "menager": "manager",
    "super_admin": "superadmin",
    "super-admin": "superadmin",
    "super": "superadmin",
}


def normalize_role(raw: str) -> str:
    role = (raw or "").strip().lower()
    role = ROLE_ALIASES.get(role, role)
    if role not in ROLES_ORDER:
        raise SystemExit(f"Invalid role '{raw}'. Allowed: {', '.join(ROLES_ORDER)}")
    return role


def main() -> int:
    parser = argparse.ArgumentParser(description="Set TTBoost user role by username")
    parser.add_argument("--username", required=True, help="Username (login)")
    parser.add_argument("--role", required=True, help=f"One of: {', '.join(ROLES_ORDER)}")
    args = parser.parse_args()

    username = (args.username or "").strip()
    if not username:
        raise SystemExit("Username is required")

    role = normalize_role(args.role)

    db = SessionLocal()
    try:
        user = db.query(models.User).filter(models.User.username == username).first()
        if not user:
            raise SystemExit(f"User '{username}' not found")

        old_role = (user.role or "user")
        user.role = role
        db.commit()
        print(f"OK: {username}: {old_role} -> {role}")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
