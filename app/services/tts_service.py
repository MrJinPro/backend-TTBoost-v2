import os
import logging
import asyncio
from contextvars import ContextVar
from datetime import datetime, timedelta
from enum import Enum
from typing import Optional, Dict
from gtts import gTTS
import edge_tts
import httpx
try:
    from openai import OpenAI  # type: ignore[import-not-found]
except Exception:
    OpenAI = None

logger = logging.getLogger(__name__)


_tts_meta_var: ContextVar[dict | None] = ContextVar("tts_meta", default=None)


def get_last_tts_meta() -> dict | None:
    """Возвращает метаданные последней генерации TTS в рамках текущего request context."""
    return _tts_meta_var.get()


def _set_tts_meta(meta: dict) -> None:
    try:
        _tts_meta_var.set(meta)
    except Exception:
        pass


def _resolve_media_root() -> str:
    """Папка, где храним медиа-файлы (tts/sounds/avatars).

    В проде nginx обычно раздаёт статику с фиксированного пути (например,
    /opt/ttboost/app/static). Если MEDIA_ROOT не задан, пытаемся подобрать
    существующий путь из нескольких типовых вариантов.
    """
    env = (os.getenv("MEDIA_ROOT") or "").strip()
    if env:
        return env.rstrip("/\\")

    # Типовые варианты прод-деплоя
    candidates = [
        "/opt/ttboost/app/static",
        "/opt/ttboost/static",
    ]

    # Локальный/внутренний путь (в случае, если используем FastAPI /static mount)
    try:
        app_dir = os.path.dirname(os.path.dirname(__file__))  # backend/app
        candidates.append(os.path.join(app_dir, "static"))
    except Exception:
        pass

    for path in candidates:
        if path and os.path.isdir(path):
            return path.rstrip("/\\")

    # Fallback: историческое значение
    return "/opt/ttboost/static"


class TTSEngine(str, Enum):
    """Доступные TTS движки"""
    GTTS = "gtts"
    EDGE = "edge"
    AZURE = "azure"
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
    # Метаданные для диагностики (используется в /tts/generate)
    meta: dict = {
        "requested_voice_id": voice_id,
        "requested_engine": None,
        "used_voice_id": None,
        "used_engine": None,
        "fallback_used": False,
        "primary_error": None,
        "fallback_error": None,
        "ok": False,
    }

    # Находим информацию о голосе
    voice_info = None
    for voices in AVAILABLE_VOICES.values():
        for v in voices:
            if v["id"] == voice_id:
                voice_info = v
                break
        if voice_info:
            break
    
    if voice_info:
        meta["requested_engine"] = voice_info.get("engine")
    else:
        logger.error(f"Голос {voice_id} не найден")
        meta["primary_error"] = f"voice_not_found:{voice_id}"
        _set_tts_meta(meta)
        return ""
    
    engine = voice_info["engine"]
    
    result = ""
    primary_exc: Exception | None = None
    try:
        if engine == "gtts":
            result = await _generate_gtts(text, voice_info, user_id)
        elif engine == "edge":
            # edge_tts (Bing consumer endpoint) часто возвращает 403 на VPS.
            # Если настроен официальный Azure Speech, используем его.
            if _have_azure_speech():
                result = await _generate_azure_speech(text, voice_info, user_id)
                if result:
                    # Для метаданных считаем, что реально использован Azure.
                    engine = TTSEngine.AZURE.value
            if not result:
                result = await _generate_edge(text, voice_info, user_id)
        elif engine == "openai":
            result = await _generate_openai(text, voice_info, user_id)
        elif engine == "eleven":
            result = await _generate_elevenlabs(text, voice_info, user_id)
        else:
            logger.error(f"Неизвестный движок: {engine}")
            result = ""
    except Exception as e:
        primary_exc = e
        logger.exception("Primary TTS engine failed (engine=%s voice_id=%s)", engine, voice_id)
        result = ""

    if result:
        meta["used_voice_id"] = voice_id
        meta["used_engine"] = engine
        meta["ok"] = True
        _set_tts_meta(meta)
        return result

    if primary_exc is not None:
        meta["primary_error"] = str(primary_exc)
    else:
        meta["primary_error"] = f"engine_returned_empty:{engine}"

    # Фолбэк (по умолчанию оставляем, чтобы не ломать текущий UX),
    # но теперь можно увидеть, что он сработал.
    fallback_voice = {"lang": "ru", "engine": "gtts"}
    try:
        logger.warning("TTS engine '%s' failed, falling back to gTTS (ru). voice_id=%s", engine, voice_id)
        result = await _generate_gtts(text, fallback_voice, user_id)
    except Exception as e:
        logger.exception("gTTS fallback failed")
        meta["fallback_error"] = str(e)
        result = ""

    if result:
        meta["used_voice_id"] = "gtts-ru"
        meta["used_engine"] = "gtts"
        meta["fallback_used"] = True
        meta["ok"] = True
        _set_tts_meta(meta)
        return result

    meta["ok"] = False
    _set_tts_meta(meta)
    return ""


async def _generate_gtts(text: str, voice_info: dict, user_id: str = None) -> str:
    """Генерация через Google TTS"""

    media_root = _resolve_media_root()
    

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
    

    media_root = _resolve_media_root()
    

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
        timeout_s = float(os.getenv("EDGE_TTS_TIMEOUT_SECONDS", "35") or "35")
        await asyncio.wait_for(communicate.save(file_path), timeout=timeout_s)
        
        base_url = os.getenv("TTS_BASE_URL", "https://media.ttboost.pro")
        url = f"{base_url.rstrip('/')}/{url_path}/{filename}"
        
        print(f"✅ Edge TTS успешно создан: {file_path}")
        logger.info(f"Edge TTS создан: {file_path}")
        _post_tts_housekeeping(tts_dir, file_path)
        return url
        
    except Exception as e:
        print(f"❌ Edge TTS ошибка: {e}")
        logger.exception("Ошибка Edge TTS")
        return ""


def _have_azure_speech() -> bool:
    return bool((os.getenv("AZURE_SPEECH_KEY") or "").strip()) and bool((os.getenv("AZURE_SPEECH_REGION") or "").strip())


async def _generate_azure_speech(text: str, voice_info: dict, user_id: str = None) -> str:
    """Официальный Microsoft Azure Speech TTS.

    Требует:
      - AZURE_SPEECH_KEY
      - AZURE_SPEECH_REGION (например: westeurope)
    """
    key = (os.getenv("AZURE_SPEECH_KEY") or "").strip()
    region = (os.getenv("AZURE_SPEECH_REGION") or "").strip()
    if not key or not region:
        return ""

    media_root = _resolve_media_root()
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

    voice_name = voice_info.get("id")
    if not voice_name:
        return ""

    # Azure endpoint
    endpoint = f"https://{region}.tts.speech.microsoft.com/cognitiveservices/v1"
    output_format = (os.getenv("AZURE_TTS_OUTPUT_FORMAT") or "audio-16khz-32kbitrate-mono-mp3").strip()

    # Simple SSML
    lang = (voice_info.get("lang") or "ru-RU").strip()
    ssml = (
        f"<speak version='1.0' xml:lang='{lang}'>"
        f"<voice name='{voice_name}'>"
        f"{_escape_xml(text)}"
        f"</voice></speak>"
    )

    headers = {
        "Ocp-Apim-Subscription-Key": key,
        "Content-Type": "application/ssml+xml",
        "X-Microsoft-OutputFormat": output_format,
        "User-Agent": "ttboost-backend",
    }

    timeout_s = float(os.getenv("AZURE_TTS_TIMEOUT_SECONDS", "20") or "20")
    try:
        async with httpx.AsyncClient(timeout=timeout_s) as client:
            resp = await client.post(endpoint, content=ssml.encode("utf-8"), headers=headers)
        if resp.status_code != 200:
            logger.warning("Azure TTS failed: status=%s body=%s", resp.status_code, resp.text[:300])
            return ""
        audio_bytes = resp.content
        if not audio_bytes:
            logger.warning("Azure TTS returned empty audio")
            return ""
        with open(file_path, "wb") as f:
            f.write(audio_bytes)

        base_url = os.getenv("TTS_BASE_URL", "https://media.ttboost.pro")
        url = f"{base_url.rstrip('/')}/{url_path}/{filename}"
        logger.info("Azure TTS created: %s (voice=%s)", file_path, voice_name)
        _post_tts_housekeeping(tts_dir, file_path)
        return url
    except Exception:
        logger.exception("Azure TTS exception")
        return ""


def _escape_xml(text: str) -> str:
    return (
        (text or "")
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&apos;")
    )


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
    media_root = _resolve_media_root()
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

    media_root = _resolve_media_root()
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

    def _contains_cyrillic(s: str) -> bool:
        for ch in s:
            o = ord(ch)
            if 0x0400 <= o <= 0x04FF or 0x0500 <= o <= 0x052F:
                return True
        return False

    def _contains_latin(s: str) -> bool:
        return any(('A' <= ch <= 'Z') or ('a' <= ch <= 'z') for ch in s)

    # Управление языком (опционально):
    # - ELEVENLABS_LANGUAGE_MODE=off (по умолчанию): не передаём language_code, Eleven сам решает.
    # - ELEVENLABS_LANGUAGE_MODE=auto: если есть кириллица -> ru, иначе можно (опц.) принудить en.
    # - ELEVENLABS_LANGUAGE_MODE=force: всегда передаём ELEVENLABS_LANGUAGE_CODE.
    language_mode = (os.getenv("ELEVENLABS_LANGUAGE_MODE") or "off").strip().lower()
    language_code = (os.getenv("ELEVENLABS_LANGUAGE_CODE") or "").strip()

    language_code_to_send = ""
    if language_mode == "force":
        language_code_to_send = language_code
    elif language_mode == "auto":
        if _contains_cyrillic(text):
            language_code_to_send = (os.getenv("ELEVENLABS_LANGUAGE_AUTO_RU") or "ru").strip()
        elif _contains_latin(text):
            # Важно: латиница может быть как английский, так и русская транслитерация.
            # Поэтому EN делаем строго опциональным.
            language_code_to_send = (os.getenv("ELEVENLABS_LANGUAGE_AUTO_EN") or "").strip()

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            if language_code_to_send:
                payload_with_lang = dict(payload)
                payload_with_lang["language_code"] = language_code_to_send
                resp = await client.post(url, headers=headers, json=payload_with_lang)
                # Некоторые аккаунты/эндпоинты могут не принимать language_code.
                # В этом случае делаем один безопасный повтор без параметра.
                if resp.status_code != 200 and resp.status_code in (400, 422) and "language_code" in (resp.text or ""):
                    logger.warning(
                        "ElevenLabs не принял language_code=%s, повтор без него (status=%s)",
                        language_code_to_send,
                        resp.status_code,
                    )
                    resp = await client.post(url, headers=headers, json=payload)
            else:
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


def cleanup_tts_tree(*, media_root: str | None = None) -> None:
    """Удаляет TTS файлы старше TTL во всём дереве tts/.

    Нужен как бэкап-механизм на случай рестартов процесса до срабатывания per-file TTL.
    """

    ttl = _get_retention_seconds()
    root = (media_root or _resolve_media_root()).rstrip("/\\")
    tts_root = os.path.join(root, "tts")
    now = datetime.now()

    def _cleanup_dir(d: str) -> None:
        try:
            for name in os.listdir(d):
                if not name.startswith("tts_"):
                    continue
                full = os.path.join(d, name)
                try:
                    stat = os.stat(full)
                    mtime = datetime.fromtimestamp(stat.st_mtime)
                    if (now - mtime) > timedelta(seconds=ttl):
                        os.remove(full)
                except FileNotFoundError:
                    continue
                except Exception:
                    continue
        except FileNotFoundError:
            return
        except Exception:
            return

    # root tts/
    _cleanup_dir(tts_root)

    # per-user tts/<user_id>/
    try:
        for entry in os.listdir(tts_root):
            sub = os.path.join(tts_root, entry)
            if os.path.isdir(sub):
                _cleanup_dir(sub)
    except FileNotFoundError:
        return
    except Exception:
        return


async def tts_cleanup_loop() -> None:
    """Фоновая цикличная очистка TTS (раз в TTL секунд)."""

    while True:
        try:
            cleanup_tts_tree()
        except Exception:
            pass
        await asyncio.sleep(max(30, _get_retention_seconds()))

