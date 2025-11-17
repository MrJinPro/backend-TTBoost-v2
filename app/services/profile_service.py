"""
Сервис для управления профилями пользователей
"""
from app.models.profile import UserProfile, GiftSound, ViewerSound
from datetime import datetime, timezone
from typing import Dict, Optional
import logging

logger = logging.getLogger(__name__)

# In-memory хранилище профилей (в продакшене использовать БД)
PROFILES: Dict[str, UserProfile] = {}


async def get_or_create_profile(user_id: str) -> UserProfile:
    """Получить или создать профиль пользователя"""
    if user_id not in PROFILES:
        now = datetime.now(timezone.utc)
        PROFILES[user_id] = UserProfile(
            user_id=user_id,
            created_at=now,
            updated_at=now,
        )
        logger.info(f"Создан новый профиль для {user_id}")
    return PROFILES[user_id]


async def update_profile(user_id: str, **kwargs) -> UserProfile:
    """Обновить профиль пользователя"""
    profile = await get_or_create_profile(user_id)
    
    for key, value in kwargs.items():
        if hasattr(profile, key):
            setattr(profile, key, value)
    
    profile.updated_at = datetime.now(timezone.utc)
    logger.info(f"Профиль обновлён для {user_id}: {list(kwargs.keys())}")
    return profile


async def set_gift_sound(user_id: str, gift_name: str, sound_file: str, enabled: bool = True) -> bool:
    """Установить звук для подарка"""
    profile = await get_or_create_profile(user_id)
    
    profile.gift_sounds[gift_name] = GiftSound(
        gift_name=gift_name,
        sound_file=sound_file,
        enabled=enabled,
    )
    profile.updated_at = datetime.now(timezone.utc)
    
    logger.info(f"Звук для подарка '{gift_name}' установлен: {sound_file}")
    return True


async def remove_gift_sound(user_id: str, gift_name: str) -> bool:
    """Удалить звук для подарка"""
    profile = await get_or_create_profile(user_id)
    
    if gift_name in profile.gift_sounds:
        del profile.gift_sounds[gift_name]
        profile.updated_at = datetime.now(timezone.utc)
        logger.info(f"Звук для подарка '{gift_name}' удалён")
        return True
    return False


async def get_gift_sound(user_id: str, gift_name: str) -> Optional[GiftSound]:
    """Получить настройки звука для подарка"""
    profile = await get_or_create_profile(user_id)
    return profile.gift_sounds.get(gift_name)


async def set_viewer_sound(user_id: str, viewer_username: str, sound_file: str, enabled: bool = True) -> bool:
    """Установить звук для зрителя"""
    profile = await get_or_create_profile(user_id)
    
    # Убираем @ если есть
    username = viewer_username.lstrip("@")
    
    profile.viewer_sounds[username] = ViewerSound(
        viewer_username=username,
        sound_file=sound_file,
        enabled=enabled,
    )
    profile.updated_at = datetime.now(timezone.utc)
    
    logger.info(f"Звук для зрителя '@{username}' установлен: {sound_file}")
    return True


async def remove_viewer_sound(user_id: str, viewer_username: str) -> bool:
    """Удалить звук для зрителя"""
    profile = await get_or_create_profile(user_id)
    username = viewer_username.lstrip("@")
    
    if username in profile.viewer_sounds:
        del profile.viewer_sounds[username]
        profile.updated_at = datetime.now(timezone.utc)
        logger.info(f"Звук для зрителя '@{username}' удалён")
        return True
    return False


async def get_viewer_sound(user_id: str, viewer_username: str) -> Optional[ViewerSound]:
    """Получить настройки звука для зрителя"""
    profile = await get_or_create_profile(user_id)
    username = viewer_username.lstrip("@")
    return profile.viewer_sounds.get(username)


async def list_user_sounds(user_id: str) -> dict:
    """Получить список всех звуков пользователя"""
    profile = await get_or_create_profile(user_id)
    return {
        "gift_sounds": list(profile.gift_sounds.values()),
        "viewer_sounds": list(profile.viewer_sounds.values()),
    }
