# Модели для настроек пользователя
from pydantic import BaseModel


class UserSettings(BaseModel):
    """Настройки пользователя"""
    tiktok_username: str = ""  # TikTok username для подключения
    tts_enabled: bool = True
    gifts_enabled: bool = True
    likes_enabled: bool = False
    tts_lang: str = "ru"
    tts_tld: str = "com"  # Google TTS accent (com = female)
