"""
Миграция БД: добавление полей trigger_name и combo_count в таблицу triggers
Удаление поля gift_tts_alongside из user_settings
"""
import logging
from sqlalchemy import text
from app.db.database import SessionLocal

logger = logging.getLogger(__name__)


def migrate_triggers_add_fields():
    """Добавить trigger_name и combo_count в triggers"""
    db = SessionLocal()
    try:
        # Проверяем наличие столбца trigger_name
        result = db.execute(text(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name='triggers' AND column_name='trigger_name'"
        ))
        if not result.fetchone():
            logger.info("Добавляем столбец trigger_name в таблицу triggers...")
            db.execute(text("ALTER TABLE triggers ADD COLUMN trigger_name VARCHAR(100)"))
            db.commit()
            logger.info("✅ Столбец trigger_name добавлен")
        
        # Проверяем наличие столбца combo_count
        result = db.execute(text(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name='triggers' AND column_name='combo_count'"
        ))
        if not result.fetchone():
            logger.info("Добавляем столбец combo_count в таблицу triggers...")
            db.execute(text("ALTER TABLE triggers ADD COLUMN combo_count INTEGER DEFAULT 0 NOT NULL"))
            db.commit()
            logger.info("✅ Столбец combo_count добавлен")
            
    except Exception as e:
        logger.error(f"Ошибка миграции triggers: {e}")
        db.rollback()
    finally:
        db.close()


def migrate_user_settings_remove_gift_tts_alongside():
    """Удалить gift_tts_alongside из user_settings (больше не нужно)"""
    db = SessionLocal()
    try:
        # Проверяем наличие столбца
        result = db.execute(text(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name='user_settings' AND column_name='gift_tts_alongside'"
        ))
        if result.fetchone():
            logger.info("Удаляем столбец gift_tts_alongside из таблицы user_settings...")
            db.execute(text("ALTER TABLE user_settings DROP COLUMN gift_tts_alongside"))
            db.commit()
            logger.info("✅ Столбец gift_tts_alongside удален")
    except Exception as e:
        logger.error(f"Ошибка удаления gift_tts_alongside: {e}")
        db.rollback()
    finally:
        db.close()


def run_migrations():
    """Запуск всех миграций"""
    logger.info("🔧 Запуск миграций БД...")
    migrate_triggers_add_fields()
    migrate_user_settings_remove_gift_tts_alongside()
    logger.info("✅ Миграции завершены")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run_migrations()
