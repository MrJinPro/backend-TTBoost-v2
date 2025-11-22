"""
Модели для профиля пользователя и персонализации
"""
from pydantic import BaseModel
from typing import Dict, Optional
from datetime import datetime


class GiftSound(BaseModel):
    """Настройка звука для конкретного подарка"""
    gift_name: str  # Название подарка TikTok (Rose, Heart, Galaxy и т.д.)
    sound_file: str  # Имя файла звука (хранится в static/sounds/{user_id}/)
    enabled: bool = True


class ViewerSound(BaseModel):
    """Настройка звука при входе определённого зрителя"""
    viewer_username: str  # TikTok username зрителя (без @)
    sound_file: str  # Имя файла звука
    enabled: bool = True


class UserProfile(BaseModel):
    """Профиль пользователя с персональными настройками"""
    user_id: str
    
    # TikTok настройки
    tiktok_username: str = ""
    
    # TTS настройки
    voice_id: str = "ru-RU-SvetlanaNeural"
    tts_enabled: bool = True
    tts_volume: float = 1.0  # 0.0 - 1.0
    
    # Подарки
    gifts_enabled: bool = True
    gifts_volume: float = 1.0
    gift_sounds: Dict[str, GiftSound] = {}  # gift_name -> GiftSound
    # Воспроизводить ли озвучку (TTS) вместе с триггер/кастомным звуком подарка
    gift_tts_alongside: bool = False  # если True: и звук триггера, и голосовое описание; если False: только звук/фолбэк
    
    # Зрители
    viewer_sounds: Dict[str, ViewerSound] = {}  # viewer_username -> ViewerSound
    
    # Метаданные
    created_at: datetime
    updated_at: datetime


class UploadSoundRequest(BaseModel):
    """Запрос на загрузку звукового файла"""
    ws_token: str
    sound_name: str  # Уникальное имя файла


class UploadSoundResponse(BaseModel):
    """Ответ после загрузки звука"""
    status: str = "ok"
    sound_file: str  # Имя сохранённого файла
    sound_url: str  # URL для доступа к файлу


class SetGiftSoundRequest(BaseModel):
    """Привязать звук к подарку"""
    ws_token: str
    gift_name: str
    sound_file: str
    enabled: bool = True


class SetViewerSoundRequest(BaseModel):
    """Привязать звук к зрителю"""
    ws_token: str
    viewer_username: str
    sound_file: str
    enabled: bool = True


class ProfileResponse(BaseModel):
    """Ответ с данными профиля"""
    status: str = "ok"
    profile: UserProfile
