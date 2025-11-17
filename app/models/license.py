# Модели для работы с лицензиями и подключениями
from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class License(BaseModel):
    """Лицензия пользователя"""
    license_key: str
    tiktok_username: str  # TikTok username стримера (без @)
    created_at: datetime
    expires_at: datetime
    is_active: bool = True

class StreamConfig(BaseModel):
    """Конфигурация стрима для пользователя"""
    user_id: str
    tiktok_username: str  # TikTok username
    voice_id: str = "ru-RU-SvetlanaNeural"  # ID выбранного голоса для TTS
    tts_enabled: bool = True
    gifts_enabled: bool = True
    likes_enabled: bool = False  # озвучивать ли лайки
