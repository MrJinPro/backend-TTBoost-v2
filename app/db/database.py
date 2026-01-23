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

        # Time window fields
        if "starts_at" not in cols:
            conn.exec_driver_sql("ALTER TABLE notifications ADD COLUMN starts_at TIMESTAMP")
        if "ends_at" not in cols:
            conn.exec_driver_sql("ALTER TABLE notifications ADD COLUMN ends_at TIMESTAMP")

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


def _migrate_notifications_postgres():
    if not engine.dialect.name.startswith("postgres"):
        return

    with engine.begin() as conn:
        # Ensure enum types exist (created automatically on new DB, but missing on old schemas).
        for type_name, values in [
            ("notificationtype", ["system", "product", "marketing"]),
            ("notificationlevel", ["info", "warning", "promo"]),
            ("notificationaudience", ["all", "users", "plan", "missing_email"]),
        ]:
            vals_sql = ", ".join([f"'{v}'" for v in values])
            conn.exec_driver_sql(
                f"""
DO $$
BEGIN
    CREATE TYPE {type_name} AS ENUM ({vals_sql});
EXCEPTION
    WHEN duplicate_object THEN NULL;
END $$;
""".strip()
            )

        # Add missing columns.
        conn.exec_driver_sql("ALTER TABLE notifications ADD COLUMN IF NOT EXISTS dedupe_key VARCHAR(256)")
        conn.exec_driver_sql("ALTER TABLE notifications ADD COLUMN IF NOT EXISTS type notificationtype")
        conn.exec_driver_sql("ALTER TABLE notifications ADD COLUMN IF NOT EXISTS targeting JSONB")
        conn.exec_driver_sql("ALTER TABLE notifications ADD COLUMN IF NOT EXISTS in_app_enabled BOOLEAN")
        conn.exec_driver_sql("ALTER TABLE notifications ADD COLUMN IF NOT EXISTS push_enabled BOOLEAN")
        conn.exec_driver_sql("ALTER TABLE notifications ADD COLUMN IF NOT EXISTS created_by_user_id VARCHAR")
        conn.exec_driver_sql("ALTER TABLE notifications ADD COLUMN IF NOT EXISTS starts_at TIMESTAMP")
        conn.exec_driver_sql("ALTER TABLE notifications ADD COLUMN IF NOT EXISTS ends_at TIMESTAMP")

        # Defaults for newly-added nullable columns.
        conn.exec_driver_sql("UPDATE notifications SET in_app_enabled = TRUE WHERE in_app_enabled IS NULL")
        conn.exec_driver_sql("UPDATE notifications SET push_enabled = FALSE WHERE push_enabled IS NULL")
        conn.exec_driver_sql("UPDATE notifications SET type = 'product' WHERE type IS NULL")

        # Unique index for dedupe_key (allows multiple NULLs).
        conn.exec_driver_sql(
            "CREATE UNIQUE INDEX IF NOT EXISTS ux_notifications_dedupe_key ON notifications(dedupe_key)"
        )


def _migrate_push_tokens_postgres():
    if not engine.dialect.name.startswith("postgres"):
        return

    with engine.begin() as conn:
        conn.exec_driver_sql(
            """
            CREATE TABLE IF NOT EXISTS push_device_tokens (
              id VARCHAR PRIMARY KEY,
              user_id VARCHAR NOT NULL,
              platform VARCHAR(32) NOT NULL,
              token VARCHAR(512) NOT NULL,
              enabled BOOLEAN NOT NULL DEFAULT TRUE,
              last_seen_at TIMESTAMP,
              created_at TIMESTAMP NOT NULL,
              updated_at TIMESTAMP NOT NULL,
              CONSTRAINT uq_push_platform_token UNIQUE (platform, token)
            )
            """.strip()
        )
        conn.exec_driver_sql(
            "CREATE INDEX IF NOT EXISTS ix_push_device_tokens_user_id ON push_device_tokens(user_id)"
        )


def _migrate_password_reset_tokens_sqlite():
    if not DATABASE_URL.startswith("sqlite"):
        return
    with engine.begin() as conn:
        conn.exec_driver_sql(
            """
            CREATE TABLE IF NOT EXISTS password_reset_tokens (
              id VARCHAR PRIMARY KEY,
              user_id VARCHAR NOT NULL,
              code_hash VARCHAR(128) NOT NULL,
              expires_at TIMESTAMP NOT NULL,
              used_at TIMESTAMP,
              attempts INTEGER NOT NULL DEFAULT 0,
              request_ip VARCHAR(64),
              user_agent VARCHAR(255),
              created_at TIMESTAMP NOT NULL
            )
            """
        )
        try:
            conn.exec_driver_sql("CREATE INDEX IF NOT EXISTS ix_password_reset_tokens_user_id ON password_reset_tokens(user_id)")
        except Exception:
            pass


def _migrate_password_reset_tokens_postgres():
    if not engine.dialect.name.startswith("postgres"):
        return
    with engine.begin() as conn:
        conn.exec_driver_sql(
            """
            CREATE TABLE IF NOT EXISTS password_reset_tokens (
              id VARCHAR PRIMARY KEY,
              user_id VARCHAR NOT NULL,
              code_hash VARCHAR(128) NOT NULL,
              expires_at TIMESTAMP NOT NULL,
              used_at TIMESTAMP,
              attempts INTEGER NOT NULL DEFAULT 0,
              request_ip VARCHAR(64),
              user_agent VARCHAR(255),
              created_at TIMESTAMP NOT NULL,
              CONSTRAINT fk_password_reset_user_id FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
            """
        )
        conn.exec_driver_sql(
            "CREATE INDEX IF NOT EXISTS ix_password_reset_tokens_user_id ON password_reset_tokens(user_id)"
        )


def _migrate_users_email_unique_sqlite():
    if not DATABASE_URL.startswith("sqlite"):
        return
    with engine.begin() as conn:
        # Case-insensitive unique index for email (allows multiple NULL/empty).
        try:
            conn.exec_driver_sql(
                "CREATE UNIQUE INDEX IF NOT EXISTS ux_users_email_nocase ON users(email COLLATE NOCASE) WHERE email IS NOT NULL AND email <> ''"
            )
        except Exception:
            pass


def _migrate_users_email_unique_postgres():
    if not engine.dialect.name.startswith("postgres"):
        return
    with engine.begin() as conn:
        # Case-insensitive unique index for email.
        # Note: requires no duplicates already present.
        try:
            conn.exec_driver_sql(
                "CREATE UNIQUE INDEX IF NOT EXISTS ux_users_email_lower ON users (lower(email)) WHERE email IS NOT NULL AND email <> ''"
            )
        except Exception:
            # If duplicates exist, index creation will fail; app-level checks still prevent new duplicates.
            pass


# Extend init_db with best-effort Postgres migrations
def init_db():
    from . import models  # noqa: F401 ensure models are imported
    Base.metadata.create_all(bind=engine)
    _migrate_notifications_sqlite()
    _migrate_push_tokens_sqlite()
    _migrate_password_reset_tokens_sqlite()
    _migrate_users_email_unique_sqlite()
    _migrate_notifications_postgres()
    _migrate_push_tokens_postgres()
    _migrate_password_reset_tokens_postgres()
    _migrate_users_email_unique_postgres()
