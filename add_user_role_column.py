"""Миграция: добавление колонки role в таблицу users.

Роль хранится как строка:
- user (default)
- support
- curator
- moderator
- admin
- manager
- superadmin

SQLite: ALTER TABLE users ADD COLUMN role VARCHAR(32) NOT NULL DEFAULT 'user'
"""

import os
import sqlite3

DB_PATH = os.path.join(os.path.dirname(__file__), "ttboost.db")


def migrate() -> None:
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        cursor.execute("PRAGMA table_info(users)")
        columns = [row[1] for row in cursor.fetchall()]

        if "role" not in columns:
            print("Добавление колонки role...")
            cursor.execute("ALTER TABLE users ADD COLUMN role VARCHAR(32) NOT NULL DEFAULT 'user'")
            conn.commit()
            print("✓ Колонка role добавлена успешно")
        else:
            print("✓ Колонка role уже существует")

        cursor.execute("PRAGMA table_info(users)")
        print("\nТекущая структура таблицы users:")
        for row in cursor.fetchall():
            print(f"  {row[1]}: {row[2]} (nullable={row[3]==0})")

    except Exception as e:
        print(f"✗ Ошибка миграции: {e}")
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    migrate()
