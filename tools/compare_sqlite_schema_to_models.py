"""Compare a SQLite DB schema to SQLAlchemy models (Base.metadata).

Usage:
  py tools/compare_sqlite_schema_to_models.py --db ttboost.db

Assumes it is executed from repo root or backend/.
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path


def load_sqlite_schema(db_path: Path) -> dict[str, set[str]]:
    conn = sqlite3.connect(str(db_path))
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT name FROM sqlite_master "
            "WHERE type='table' AND name NOT LIKE 'sqlite_%' "
            "ORDER BY name"
        )
        tables = [r[0] for r in cur.fetchall()]

        schema: dict[str, set[str]] = {}
        for table in tables:
            cur.execute(f"PRAGMA table_info({table})")
            cols = {r[1] for r in cur.fetchall()}
            schema[table] = cols
        return schema
    finally:
        conn.close()


def load_expected_schema_from_models() -> dict[str, set[str]]:
    # Make sure `backend/` is importable
    if "backend" not in sys.path[0:1]:
        sys.path.insert(0, "backend")

    from app.db.database import Base  # noqa
    import app.db.models  # noqa: F401

    expected: dict[str, set[str]] = {}
    for table_name, table in Base.metadata.tables.items():
        expected[table_name] = {c.name for c in table.columns}
    return expected


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default="ttboost.db", help="Path to SQLite .db file")
    args = parser.parse_args()

    db_path = Path(args.db)
    if not db_path.is_file():
        raise SystemExit(f"DB file not found: {db_path}")

    actual = load_sqlite_schema(db_path)
    expected = load_expected_schema_from_models()

    actual_tables = set(actual)
    expected_tables = set(expected)

    missing_tables = sorted(expected_tables - actual_tables)
    extra_tables = sorted(actual_tables - expected_tables)

    print(f"DB: {db_path}")
    print(f"Actual tables: {len(actual_tables)}")
    print(f"Expected tables (models): {len(expected_tables)}")

    if missing_tables:
        print("\nMISSING TABLES (in DB, but required by models):")
        for t in missing_tables:
            print("-", t)

    if extra_tables:
        print("\nEXTRA TABLES (in DB, not present in models):")
        for t in extra_tables:
            print("-", t)

    print("\nCOLUMN DIFFS:")
    common = sorted(actual_tables & expected_tables)
    any_diff = False
    for t in common:
        missing_cols = sorted(expected[t] - actual[t])
        extra_cols = sorted(actual[t] - expected[t])
        if missing_cols or extra_cols:
            any_diff = True
            print(f"\n[{t}]")
            if missing_cols:
                print("  missing:", ", ".join(missing_cols))
            if extra_cols:
                print("  extra:", ", ".join(extra_cols))

    if not any_diff:
        print("(no column diffs)")


if __name__ == "__main__":
    main()
