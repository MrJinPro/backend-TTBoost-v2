"""
Миграция: добавление колонки tiktok_username в таблицу users
"""
import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "ttboost.db")

def migrate():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        # Проверяем существует ли колонка
        cursor.execute("PRAGMA table_info(users)")
        columns = [row[1] for row in cursor.fetchall()]
        
        if 'tiktok_username' not in columns:
            print("Добавление колонки tiktok_username...")
            cursor.execute("ALTER TABLE users ADD COLUMN tiktok_username VARCHAR(64)")
            conn.commit()
            print("✓ Колонка tiktok_username добавлена успешно")
        else:
            print("✓ Колонка tiktok_username уже существует")
        
        # Показываем структуру таблицы
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
