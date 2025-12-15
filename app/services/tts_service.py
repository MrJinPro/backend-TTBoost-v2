import os
import logging
import asyncio
from datetime import datetime, timedelta
from enum import Enum
from typing import Optional, Dict
from gtts import gTTS
import edge_tts
import httpx
try:
    from openai import OpenAI
except Exception:
    OpenAI = None

logger = logging.getLogger(__name__)


class TTSEngine(str, Enum):
    """Доступные TTS движки"""
    GTTS = "gtts"
    EDGE = "edge"
    OPENAI = "openai"
    ELEVEN = "eleven"



AVAILABLE_VOICES: Dict[str, list[dict]] = {
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
    ],
    "openai": [
        {"id": "openai-alloy", "name": "OpenAI Alloy", "voice": "alloy", "engine": "openai"},
        {"id": "openai-coral", "name": "OpenAI Coral", "voice": "coral", "engine": "openai"},
        {"id": "openai-verse", "name": "OpenAI Verse", "voice": "verse", "engine": "openai"},
    ],
    # Премиальный TTS ElevenLabs.
    # Пользователь выбирает один из voice_id ниже, а сервер использует соответствующий Eleven voice UUID.
    # Важно: сохраняем id "eleven-premium-main" (уже используется в настройках), но переименовываем его в Nova.
    "eleven": [
        # Основной (уже использовался ранее)
        {"id": "eleven-premium-main", "name": "Nova", "engine": "eleven", "voice_id": "LHi3adMlU7AICv8Yxpmm"},

        # Женские
        {"id": "eleven-mariana", "name": "Мариана", "engine": "eleven", "voice_id": "ETBmMkYUh8i2exSl2h3P"},
        {"id": "eleven-veronika", "name": "Вероника", "engine": "eleven", "voice_id": "OowtKaZH9N7iuGbsd00l"},
        {"id": "eleven-viktoriya", "name": "Виктория", "engine": "eleven", "voice_id": "gelrownZgbRhxH6LI78J"},
        {"id": "eleven-ekaterina", "name": "Екатерина", "engine": "eleven", "voice_id": "GN4wbsbejSnGSa1AzjH5"},
        {"id": "eleven-mariya", "name": "Мария", "engine": "eleven", "voice_id": "EDpEYNf6XIeKYRzYcx4I"},

        # Мужские
        {"id": "eleven-artem", "name": "Артём", "engine": "eleven", "voice_id": "blxHPCXhpXOsc7mCKk0P"},
        {"id": "eleven-mayson", "name": "Мыйсон", "engine": "eleven", "voice_id": "huXlXYhtMIZkTYxM93t6"},
        {"id": "eleven-artur", "name": "Артур", "engine": "eleven", "voice_id": "vpUqfpCIn34tjFW4KHjt"},
        {"id": "eleven-mark", "name": "Марк", "engine": "eleven", "voice_id": "ZHIn0jcgR6VIvVAXkwWV"},
        {"id": "eleven-egor", "name": "Егор", "engine": "eleven", "voice_id": "BHMDqCKgYeHHupc0I8VD"},
    ],
}


def get_all_voices():
    """Получить список всех доступных голосов.
    Если отсутствует OPENAI_API_KEY или SDK — openai голоса помечаем флагом unavailable.
    """
    all_voices = []
    have_openai = OpenAI is not None and os.getenv("OPENAI_API_KEY")
    have_eleven = bool(os.getenv("ELEVENLABS_API_KEY"))
    for engine, engine_voices in AVAILABLE_VOICES.items():
        for v in engine_voices:
            v_copy = dict(v)
            if engine == "openai" and not have_openai:
                v_copy["unavailable"] = True
            if engine == "eleven" and not have_eleven:
                v_copy["unavailable"] = True
            all_voices.append(v_copy)
    return all_voices


async def generate_tts(text: str, voice_id: str = "gtts-ru", user_id: str = None) -> str:
    """
    Генерирует TTS и возвращает URL
    
    Args:
        text: Текст для озвучки
        voice_id: ID голоса из списка AVAILABLE_VOICES
        user_id: ID пользователя для разделения файлов
        
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
        result = await _generate_gtts(text, voice_info, user_id)
    elif engine == "edge":
        result = await _generate_edge(text, voice_info, user_id)
    elif engine == "openai":
        result = await _generate_openai(text, voice_info, user_id)
    elif engine == "eleven":
        result = await _generate_elevenlabs(text, voice_info, user_id)
    else:
        logger.error(f"Неизвестный движок: {engine}")
        result = ""


    if not result:
        try:
            logger.warning(f"TTS движок '{engine}' не вернул результат, пробуем gTTS (ru)")
            result = await _generate_gtts(text, {"lang": "ru", "engine": "gtts"}, user_id)
        except Exception as e:
            logger.error(f"Фолбэк gTTS не удался: {e}")
            result = ""
    return result


async def _generate_gtts(text: str, voice_info: dict, user_id: str = None) -> str:
    """Генерация через Google TTS"""

    media_root = os.getenv("MEDIA_ROOT", "/opt/ttboost/static")
    

    if user_id:
        tts_dir = os.path.join(media_root, "tts", user_id)
        url_path = f"static/tts/{user_id}"
    else:
        tts_dir = os.path.join(media_root, "tts")
        url_path = "static/tts"
    
    os.makedirs(tts_dir, exist_ok=True)

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')
    filename = f"tts_{timestamp}.mp3"
    file_path = os.path.join(tts_dir, filename)

    try:
        def _generate():
            lang = voice_info.get("lang", "ru")
            slow = voice_info.get("slow", False)
            tts = gTTS(text=text, lang=lang, slow=slow)
            tts.save(file_path)
        
        await asyncio.to_thread(_generate)
        
        base_url = os.getenv("TTS_BASE_URL", "https://media.ttboost.pro")
        url = f"{base_url.rstrip('/')}/{url_path}/{filename}"
        
        logger.info(f"Google TTS создан: {file_path}")
        _post_tts_housekeeping(tts_dir, file_path)
        return url
        
    except Exception as e:
        logger.error(f"Ошибка Google TTS: {e}")
        return ""


async def _generate_edge(text: str, voice_info: dict, user_id: str = None) -> str:
    """Генерация через Microsoft Edge TTS"""
    print(f"🎙️ Attempting Edge TTS with voice: {voice_info['id']}")
    

    media_root = os.getenv("MEDIA_ROOT", "/opt/ttboost/static")
    

    if user_id:
        tts_dir = os.path.join(media_root, "tts", user_id)
        url_path = f"static/tts/{user_id}"
    else:
        tts_dir = os.path.join(media_root, "tts")
        url_path = "static/tts"
    
    os.makedirs(tts_dir, exist_ok=True)

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')
    filename = f"tts_{timestamp}.mp3"
    file_path = os.path.join(tts_dir, filename)

    try:
        voice = voice_info["id"]
        communicate = edge_tts.Communicate(text, voice)
        await communicate.save(file_path)
        
        base_url = os.getenv("TTS_BASE_URL", "https://media.ttboost.pro")
        url = f"{base_url.rstrip('/')}/{url_path}/{filename}"
        
        print(f"✅ Edge TTS успешно создан: {file_path}")
        logger.info(f"Edge TTS создан: {file_path}")
        _post_tts_housekeeping(tts_dir, file_path)
        return url
        
    except Exception as e:
        print(f"❌ Edge TTS ошибка: {e}")
        logger.error(f"Ошибка Edge TTS: {e}")
        return ""


async def _generate_openai(text: str, voice_info: dict, user_id: str = None) -> str:
    """Генерация через OpenAI TTS (модель *_tts). Возвращает URL или пустую строку."""
    if OpenAI is None:
        logger.warning("OpenAI SDK не установлен - openai tts недоступен")
        return ""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        logger.warning("OPENAI_API_KEY не задан - openai tts пропущен")
        return ""
    model = os.getenv("OPENAI_TTS_MODEL", "gpt-4o-mini-tts")
    voice = voice_info.get("voice", "alloy")

    # Директория
    media_root = os.getenv("MEDIA_ROOT", "/opt/ttboost/static")
    if user_id:
        tts_dir = os.path.join(media_root, "tts", user_id)
        url_path = f"static/tts/{user_id}"
    else:
        tts_dir = os.path.join(media_root, "tts")
        url_path = "static/tts"
    os.makedirs(tts_dir, exist_ok=True)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')
    filename = f"tts_{timestamp}.mp3"
    file_path = os.path.join(tts_dir, filename)

    try:
        client = OpenAI(api_key=api_key)
        resp = await asyncio.to_thread(
            lambda: client.audio.speech.create(
                model=model,
                voice=voice,
                input=text,
            )
        )
        audio_bytes = resp.read() if hasattr(resp, 'read') else getattr(resp, 'audio', None)
        if not audio_bytes:
            logger.error("OpenAI TTS не вернул аудио")
            return ""
        with open(file_path, "wb") as f:
            f.write(audio_bytes)
        base_url = os.getenv("TTS_BASE_URL", "https://media.ttboost.pro")
        url = f"{base_url.rstrip('/')}/{url_path}/{filename}"
        logger.info(f"OpenAI TTS создан: {file_path} (voice={voice}, model={model})")
        _post_tts_housekeeping(tts_dir, file_path)
        return url
    except Exception as e:
        logger.error(f"Ошибка OpenAI TTS: {e}")
        return ""


async def _generate_elevenlabs(text: str, voice_info: dict, user_id: str = None) -> str:
    """Генерация через ElevenLabs TTS.

    Требует переменных окружения:
      - ELEVENLABS_API_KEY  – секретный API ключ
      - ELEVENLABS_VOICE_ID – ID выбранного premium-голоса (uuid из ElevenLabs)
      - ELEVENLABS_TTS_MODEL (опц.) – модель, по умолчанию eleven_multilingual_v2
    """
    api_key = os.getenv("ELEVENLABS_API_KEY")
    if not api_key:
        logger.warning("ELEVENLABS_API_KEY не задан – ElevenLabs TTS недоступен")
        return ""

    voice_id = voice_info.get("voice_id") or os.getenv("ELEVENLABS_VOICE_ID")
    if not voice_id:
        logger.warning("ELEVENLABS_VOICE_ID не задан – неизвестно, какой голос использовать")
        return ""

    model_id = os.getenv("ELEVENLABS_TTS_MODEL", "eleven_multilingual_v2")
    base_api = os.getenv("ELEVENLABS_API_BASE", "https://api.elevenlabs.io")
    url = f"{base_api.rstrip('/')}/v1/text-to-speech/{voice_id}"

    media_root = os.getenv("MEDIA_ROOT", "/opt/ttboost/static")
    if user_id:
        tts_dir = os.path.join(media_root, "tts", user_id)
        url_path = f"static/tts/{user_id}"
    else:
        tts_dir = os.path.join(media_root, "tts")
        url_path = "static/tts"
    os.makedirs(tts_dir, exist_ok=True)

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')
    filename = f"tts_{timestamp}.mp3"
    file_path = os.path.join(tts_dir, filename)

    headers = {
        "xi-api-key": api_key,
        "Accept": "audio/mpeg",
        "Content-Type": "application/json",
    }
    payload = {
        "text": text,
        "model_id": model_id,
        "voice_settings": {
            "stability": float(os.getenv("ELEVENLABS_VOICE_STABILITY", "0.5")),
            "similarity_boost": float(os.getenv("ELEVENLABS_VOICE_SIMILARITY", "0.75")),
        },
    }

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(url, headers=headers, json=payload)
        if resp.status_code != 200:
            logger.error(
                "Ошибка ElevenLabs TTS: %s %s", resp.status_code, resp.text[:200]
            )
            return ""

        with open(file_path, "wb") as f:
            f.write(resp.content)

        base_url = os.getenv("TTS_BASE_URL", "https://media.ttboost.pro")
        public_url = f"{base_url.rstrip('/')}/{url_path}/{filename}"
        logger.info(
            "ElevenLabs TTS создан: %s (voice_id=%s, model=%s)",
            file_path,
            voice_id,
            model_id,
        )
        _post_tts_housekeeping(tts_dir, file_path)
        return public_url
    except Exception as e:
        logger.error(f"Ошибка ElevenLabs TTS: {e}")
        return ""


def _get_retention_seconds() -> int:
    """TTL (сек) для TTS файлов. По заданию: 5 минут (300с), можно переопределить env TTS_RETENTION_SECONDS."""
    try:
        return int(os.getenv("TTS_RETENTION_SECONDS", "300"))
    except ValueError:
        return 300


def _post_tts_housekeeping(tts_dir: str, file_path: str) -> None:
    ttl = _get_retention_seconds()
    try:
        asyncio.get_running_loop().create_task(_delete_file_later(file_path, ttl))
    except RuntimeError:
        pass
    _cleanup_old_files(tts_dir, ttl)


async def _delete_file_later(file_path: str, ttl: int):
    await asyncio.sleep(ttl)
    try:
        if os.path.exists(file_path):
            os.remove(file_path)
            logger.debug(f"TTS файл удалён по TTL: {file_path}")
    except Exception:
        logger.debug(f"Не удалось удалить TTS файл: {file_path}")


def _cleanup_old_files(tts_dir: str, ttl: int):
    now = datetime.now()
    try:
        for name in os.listdir(tts_dir):
            if not name.startswith("tts_"):
                continue
            full = os.path.join(tts_dir, name)
            try:
                stat = os.stat(full)
                mtime = datetime.fromtimestamp(stat.st_mtime)
                if (now - mtime) > timedelta(seconds=ttl):
                    os.remove(full)
                    logger.debug(f"Удалён просроченный TTS файл: {full}")
            except FileNotFoundError:
                continue
            except Exception:
                logger.debug(f"Ошибка при очистке файла: {full}")
    except FileNotFoundError:
        return

