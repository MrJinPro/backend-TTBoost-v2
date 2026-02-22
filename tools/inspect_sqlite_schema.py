"""Inspect SQLite DB schema (tables + columns).

Usage:
  py tools/inspect_sqlite_schema.py --db ttboost.db

Prints a human-readable list to stdout.
"""

from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default="ttboost.db", help="Path to SQLite .db file")
    args = parser.parse_args()

    db_path = Path(args.db)
    if not db_path.is_file():
        raise SystemExit(f"DB file not found: {db_path}")

    conn = sqlite3.connect(str(db_path))
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT name FROM sqlite_master "
            "WHERE type='table' AND name NOT LIKE 'sqlite_%' "
            "ORDER BY name"
        )
        tables = [r[0] for r in cur.fetchall()]

        print(f"{len(tables)} tables")
        for table in tables:
            cur.execute(f"PRAGMA table_info({table})")
            cols = [r[1] for r in cur.fetchall()]
            print(f"{table}: {', '.join(cols)}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
