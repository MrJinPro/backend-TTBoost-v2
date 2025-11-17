"""
Универсальный TTS сервис с поддержкой нескольких движков
Поддерживает: gTTS (Google), Edge-TTS (Microsoft)
"""
import os
from gtts import gTTS
import edge_tts
import logging
from datetime import datetime
import asyncio
from enum import Enum

logger = logging.getLogger(__name__)


class TTSEngine(str, Enum):
    """Доступные TTS движки"""
    GTTS = "gtts"  # Google TTS
    EDGE = "edge"  # Microsoft Edge TTS


# Список доступных голосов для каждого движка
AVAILABLE_VOICES = {
    "gtts": [
        {"id": "gtts-ru", "name": "Google Русский (женский)", "lang": "ru", "engine": "gtts"},
        {"id": "gtts-ru-slow", "name": "Google Русский медленный (женский)", "lang": "ru", "engine": "gtts", "slow": True},
        {"id": "gtts-en", "name": "Google English (female)", "lang": "en", "engine": "gtts"},
    ],
    "edge": [
        {"id": "ru-RU-SvetlanaNeural", "name": "Microsoft Svetlana (женский, нейронный)", "lang": "ru-RU", "engine": "edge"},
        {"id": "ru-RU-DariyaNeural", "name": "Microsoft Dariya (женский, нейронный)", "lang": "ru-RU", "engine": "edge"},
        {"id": "ru-RU-DmitryNeural", "name": "Microsoft Dmitry (мужской, нейронный)", "lang": "ru-RU", "engine": "edge"},
        {"id": "en-US-JennyNeural", "name": "Microsoft Jenny (female, neural)", "lang": "en-US", "engine": "edge"},
    ]
}


def get_all_voices():
    """Получить список всех доступных голосов"""
    all_voices = []
    for engine_voices in AVAILABLE_VOICES.values():
        all_voices.extend(engine_voices)
    return all_voices


async def generate_tts(text: str, voice_id: str = "gtts-ru") -> str:
    """
    Генерирует TTS и возвращает URL
    
    Args:
        text: Текст для озвучки
        voice_id: ID голоса из списка AVAILABLE_VOICES
        
    Returns:
        URL до аудиофайла
    """
    # Находим информацию о голосе
    voice_info = None
    for voices in AVAILABLE_VOICES.values():
        for v in voices:
            if v["id"] == voice_id:
                voice_info = v
                break
        if voice_info:
            break
    
    if not voice_info:
        logger.error(f"Голос {voice_id} не найден")
        return ""
    
    engine = voice_info["engine"]
    
    result = ""
    if engine == "gtts":
        result = await _generate_gtts(text, voice_info)
    elif engine == "edge":
        result = await _generate_edge(text, voice_info)
    else:
        logger.error(f"Неизвестный движок: {engine}")
        result = ""

    # Фолбэк: если выбратьный движок не сгенерировал звук, пытаемся через gTTS (ru)
    if not result:
        try:
            logger.warning(f"TTS движок '{engine}' не вернул результат, пробуем gTTS (ru)")
            result = await _generate_gtts(text, {"lang": "ru", "engine": "gtts"})
        except Exception as e:
            logger.error(f"Фолбэк gTTS не удался: {e}")
            result = ""
    return result


async def _generate_gtts(text: str, voice_info: dict) -> str:
    """Генерация через Google TTS"""
    base_dir = os.path.dirname(os.path.dirname(__file__))
    static_tts = os.path.join(base_dir, "static", "tts")
    os.makedirs(static_tts, exist_ok=True)

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')
    filename = f"tts_{timestamp}.mp3"
    file_path = os.path.join(static_tts, filename)

    try:
        def _generate():
            lang = voice_info.get("lang", "ru")
            slow = voice_info.get("slow", False)
            tts = gTTS(text=text, lang=lang, slow=slow)
            tts.save(file_path)
        
        await asyncio.to_thread(_generate)
        
        base_url = os.getenv("TTS_BASE_URL") or os.getenv("SERVER_HOST") or "http://localhost:8000"
        url = f"{base_url.rstrip('/')}/static/tts/{filename}"
        
        logger.info(f"Google TTS создан: {filename}")
        return url
        
    except Exception as e:
        logger.error(f"Ошибка Google TTS: {e}")
        return ""


async def _generate_edge(text: str, voice_info: dict) -> str:
    """Генерация через Microsoft Edge TTS"""
    base_dir = os.path.dirname(os.path.dirname(__file__))
    static_tts = os.path.join(base_dir, "static", "tts")
    os.makedirs(static_tts, exist_ok=True)

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')
    filename = f"tts_{timestamp}.mp3"
    file_path = os.path.join(static_tts, filename)

    try:
        voice = voice_info["id"]
        communicate = edge_tts.Communicate(text, voice)
        await communicate.save(file_path)
        
        base_url = os.getenv("TTS_BASE_URL") or os.getenv("SERVER_HOST") or "http://localhost:8000"
        url = f"{base_url.rstrip('/')}/static/tts/{filename}"
        
        logger.info(f"Edge TTS создан: {filename}")
        return url
        
    except Exception as e:
        logger.error(f"Ошибка Edge TTS: {e}")
        return ""

