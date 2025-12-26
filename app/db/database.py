import os
import json
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base


DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./ttboost.db")

# For SQLite need check_same_thread=False
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(DATABASE_URL, echo=False, future=True, connect_args=connect_args)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)

Base = declarative_base()


def _sqlite_table_columns(conn, table_name: str) -> set[str]:
    rows = conn.exec_driver_sql(f"PRAGMA table_info({table_name})").fetchall()
    # PRAGMA table_info: cid, name, type, notnull, dflt_value, pk
    return {str(r[1]) for r in rows}


def _migrate_notifications_sqlite():
    # Minimal, idempotent migration for SQLite (no Alembic in this repo).
    if not DATABASE_URL.startswith("sqlite"):
        return

    with engine.begin() as conn:
        # Table may not exist on first run.
        try:
            cols = _sqlite_table_columns(conn, "notifications")
        except Exception:
            return

        if not cols:
            return

        # Add new columns if missing.
        if "dedupe_key" not in cols:
            conn.exec_driver_sql("ALTER TABLE notifications ADD COLUMN dedupe_key VARCHAR(256)")
        if "type" not in cols:
            conn.exec_driver_sql("ALTER TABLE notifications ADD COLUMN type VARCHAR(32)")
        if "targeting" not in cols:
            conn.exec_driver_sql("ALTER TABLE notifications ADD COLUMN targeting TEXT")
        if "in_app_enabled" not in cols:
            conn.exec_driver_sql("ALTER TABLE notifications ADD COLUMN in_app_enabled BOOLEAN")
        if "push_enabled" not in cols:
            conn.exec_driver_sql("ALTER TABLE notifications ADD COLUMN push_enabled BOOLEAN")
        if "created_by_user_id" not in cols:
            conn.exec_driver_sql("ALTER TABLE notifications ADD COLUMN created_by_user_id VARCHAR")

        # Unique index for dedupe_key (SQLite allows multiple NULLs).
        try:
            conn.exec_driver_sql("CREATE UNIQUE INDEX IF NOT EXISTS ux_notifications_dedupe_key ON notifications(dedupe_key)")
        except Exception:
            pass

        # Backfill defaults for existing rows.
        rows = conn.exec_driver_sql(
            "SELECT id, audience, audience_value, level, type, targeting, in_app_enabled, push_enabled FROM notifications"
        ).fetchall()

        for (nid, audience, audience_value, level, ntype, targeting, in_app_enabled, push_enabled) in rows:
            # type
            if not ntype:
                a = (audience or "all").strip().lower()
                lvl = (level or "info").strip().lower()
                inferred_type = "marketing" if (lvl == "promo" or a == "missing_email") else "product"
                conn.exec_driver_sql(
                    "UPDATE notifications SET type = ? WHERE id = ? AND (type IS NULL OR type = '')",
                    (inferred_type, nid),
                )

            # in_app_enabled / push_enabled
            if in_app_enabled is None:
                conn.exec_driver_sql(
                    "UPDATE notifications SET in_app_enabled = 1 WHERE id = ? AND in_app_enabled IS NULL",
                    (nid,),
                )
            if push_enabled is None:
                conn.exec_driver_sql(
                    "UPDATE notifications SET push_enabled = 0 WHERE id = ? AND push_enabled IS NULL",
                    (nid,),
                )

            # targeting JSON (stored as TEXT in SQLite)
            if not targeting:
                a = (audience or "all").strip().lower()
                raw = (audience_value or "").strip()

                tgt: dict = {}
                if a == "all":
                    tgt = {"all_users": True}
                elif a == "missing_email":
                    tgt = {"all_users": True, "missing_email": True}
                elif a == "plan":
                    plans = [
                        p.strip().lower()
                        for p in raw.replace(";", ",").split(",")
                        if p and p.strip()
                    ]
                    tgt = {"all_users": True, "plans": plans}
                elif a == "users":
                    # Legacy audience uses notification_targets table.
                    tgt = {"users": True}
                else:
                    tgt = {"all_users": True}

                conn.exec_driver_sql(
                    "UPDATE notifications SET targeting = ? WHERE id = ? AND (targeting IS NULL OR targeting = '')",
                    (json.dumps(tgt, ensure_ascii=False), nid),
                )


def _migrate_push_tokens_sqlite():
    if not DATABASE_URL.startswith("sqlite"):
        return

    with engine.begin() as conn:
        # Create table if not exists
        conn.exec_driver_sql(
            """
            CREATE TABLE IF NOT EXISTS push_device_tokens (
              id VARCHAR PRIMARY KEY,
              user_id VARCHAR NOT NULL,
              platform VARCHAR(32) NOT NULL,
              token VARCHAR(512) NOT NULL,
              enabled BOOLEAN NOT NULL DEFAULT 1,
              last_seen_at TIMESTAMP,
              created_at TIMESTAMP NOT NULL,
              updated_at TIMESTAMP NOT NULL,
              CONSTRAINT uq_push_platform_token UNIQUE (platform, token)
            )
            """
        )
        try:
            conn.exec_driver_sql("CREATE INDEX IF NOT EXISTS ix_push_device_tokens_user_id ON push_device_tokens(user_id)")
        except Exception:
            pass

def init_db():
    from . import models  # noqa: F401 ensure models are imported
    Base.metadata.create_all(bind=engine)
    _migrate_notifications_sqlite()
    _migrate_push_tokens_sqlite()
