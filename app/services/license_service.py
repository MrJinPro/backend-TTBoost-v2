"""
Сервис для работы с лицензиями и подключениями к стримам
Поддерживает: встроенные демо-ключи, а также реальные ключи из БД (LicenseKey)
"""
import uuid
from typing import Tuple, Optional, Dict
from datetime import datetime, timedelta, timezone
import logging
from sqlalchemy.orm import Session

from app.db.database import SessionLocal
from app.db import models

logger = logging.getLogger(__name__)

# In-memory хранилище для активных сессий (ws_token)
TOKENS: Dict[str, dict] = {}  # ws_token -> user_data


# Демо лицензии для быстрого старта
DEMO_LICENSES = {
    "demo": {
        "tiktok_username": "",  # будет установлен пользователем
    },
    # Реальные тестовые ключи
    "TTBOOST-TEST-2024": {
        "tiktok_username": "",  # пользователь введет сам
    },
    "TTBOOST-PRO-2024": {
        "tiktok_username": "",  # пользователь введет сам
    }
}


def _get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


async def set_user_tiktok(ws_token: str, tiktok_username: str) -> bool:
    """Установить TikTok username для пользователя"""
    if ws_token not in TOKENS:
        return False
    
    # Убираем @ если пользователь ввел
    username = tiktok_username.lstrip("@")
    TOKENS[ws_token]["tiktok_username"] = username
    
    logger.info(f"TikTok username установлен: @{username} для {TOKENS[ws_token]['user_id']}")
    return True


async def set_user_voice(ws_token: str, voice_id: str) -> bool:
    """Установить voice_id для пользователя"""
    if ws_token not in TOKENS:
        return False
    
    TOKENS[ws_token]["voice_id"] = voice_id
    logger.info(f"Voice ID установлен: {voice_id} для {TOKENS[ws_token]['user_id']}")
    return True


async def login_license(license_key: str) -> Tuple[str, str]:
    """Проверить лицензию и вернуть (user_id, ws_token)
    Приоритет:
      1) Демо-ключи (demo / тестовые)
      2) Реальные ключи из БД (license_keys)
      3) Fallback (MVP) — любой ключ длиной >=3
    """
    # Демо режим
    if license_key in DEMO_LICENSES:
        user_id = f"demo_{uuid.uuid4().hex[:8]}"
        ws_token = str(uuid.uuid4())
        TOKENS[ws_token] = {
            "user_id": user_id,
            "license_key": license_key,
            **DEMO_LICENSES[license_key]
        }
        logger.info(f"Demo login: {license_key}")
        return user_id, ws_token

    # БД: проверяем реальный ключ
    try:
        db: Session
        for db in _get_db():
            lk = db.query(models.LicenseKey).filter(models.LicenseKey.key == license_key).first()
            if lk and lk.status == models.LicenseStatus.active:
                if lk.expires_at and datetime.now(timezone.utc) > lk.expires_at:
                    break  # истек
                # Создаем сессию
                user_id = (lk.user_id or f"lic_{uuid.uuid4().hex[:8]}")
                ws_token = str(uuid.uuid4())
                TOKENS[ws_token] = {
                    "user_id": user_id,
                    "license_key": license_key,
                }
                logger.info(f"Login by DB license: {license_key} -> {user_id}")
                return user_id, ws_token
    except Exception as e:
        logger.error(f"DB license lookup error: {e}")

    # Fallback для любого ключа (MVP режим)
    if len(license_key.strip()) >= 3:
        user_id = str(uuid.uuid4())
        ws_token = str(uuid.uuid4())
        TOKENS[ws_token] = {"user_id": user_id, "license_key": license_key}
        return user_id, ws_token

    return "", ""


async def verify_ws_token(token: str) -> Optional[dict]:
    """Проверить токен и вернуть данные пользователя"""
    return TOKENS.get(token)


def get_user_data(user_id: str) -> Optional[dict]:
    """Получить данные пользователя"""
    for data in TOKENS.values():
        if data.get("user_id") == user_id:
            return data
    return None

