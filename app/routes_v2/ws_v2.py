import json
import logging
import os
import re
import time
import asyncio
from datetime import datetime
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, status, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.database import SessionLocal
from app.db import models
from .auth_v2 import get_current_user
from app.services.security import decode_token
from app.services.tts_service import generate_tts, get_voice_by_id
from app.services.tiktok_service import tiktok_service
from app.services.gift_sounds import get_global_gift_sound_path
from app.services.plans import TARIFF_FREE, resolve_tariff, normalize_platform
from app.services.limits import FREE_MAX_TRIGGERS
from app.services.gift_stats_service import record_gift_and_update_stats
from app.services.admin_state import STATE as ADMIN_STATE


ACTIVE_WS_CONNECTIONS = 0

try:
    # В новых версиях TikTokLive есть отдельное исключение, дающее понятный текст
    from TikTokLive.client.errors import UserNotFoundError  # type: ignore
except Exception:  # pragma: no cover
    # Фолбэк, если используем стараую версию библиотеки без этого класса
    class UserNotFoundError(Exception):  # type: ignore
        pass

try:
    from TikTokLive.client.errors import WebcastBlocked200Error  # type: ignore
except Exception:  # pragma: no cover
    WebcastBlocked200Error = None  # type: ignore

logger = logging.getLogger(__name__)
router = APIRouter()

WS_DEBUG = str(os.getenv("WS_DEBUG", "")).strip() in ("1", "true", "yes", "on")


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _remove_emojis(s: str) -> str:
    try:
        emoji_pattern = re.compile(
            """
            [\U0001F600-\U0001F64F]|[\U0001F300-\U0001F5FF]|[\U0001F680-\U0001F6FF]|[\U0001F1E6-\U0001F1FF]|[\U00002702-\U000027B0]|[\U000024C2-\U0001F251]|[\U0001F900-\U0001F9FF]|[\U0001FA70-\U0001FAFF]|[\u2600-\u26FF]|[\u2700-\u27BF]|\uFE0F
            """,
            flags=re.UNICODE | re.VERBOSE,
        )
        return emoji_pattern.sub("", s)
    except Exception:
        return s


def _abs_url(path_or_url: str) -> str:
    base = (os.getenv("MEDIA_BASE_URL") or os.getenv("TTS_BASE_URL") or os.getenv("SERVER_HOST") or "http://localhost:8000").rstrip("/")
    if not path_or_url:
        return path_or_url
    if path_or_url.startswith("http://") or path_or_url.startswith("https://"):
        return path_or_url
    if path_or_url.startswith("/"):
        return f"{base}{path_or_url}"
    return path_or_url


@router.websocket("/ws")
async def ws_endpoint(websocket: WebSocket, db: Session = Depends(get_db), authorization: str | None = None):
    global ACTIVE_WS_CONNECTIONS
    # Попытка извлечь токен из заголовка Authorization, если нет — из query ?token=...
    token = None
    auth_header = websocket.headers.get("Authorization")
    if auth_header and auth_header.lower().startswith("bearer "):
        token = auth_header.split(" ", 1)[1]
    else:
        # query string: b'token=...'
        raw_q = websocket.scope.get("query_string", b"").decode()
        if raw_q:
            for part in raw_q.split("&"):
                k, _, v = part.partition("=")
                if k == "token" and v:
                    token = v
                    break
    if not token:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return
    sub = decode_token(token)
    if not sub:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return
    user = db.get(models.User, sub)
    if not user:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return
    # Client hints can come from query (?platform=mobile&os=android&device=...) or headers.
    platform_raw = websocket.headers.get("X-Client-Platform")
    client_os_raw = websocket.headers.get("X-Client-OS")
    client_device_raw = websocket.headers.get("X-Client-Device")
    raw_q = websocket.scope.get("query_string", b"").decode()
    if raw_q:
        for part in raw_q.split("&"):
            k, _, v = part.partition("=")
            if k == "platform" and v:
                platform_raw = v
                break
        for part in raw_q.split("&"):
            k, _, v = part.partition("=")
            if k == "os" and v and not client_os_raw:
                client_os_raw = v
            if k == "device" and v and not client_device_raw:
                client_device_raw = v
    platform = normalize_platform(platform_raw)
    tariff, _lic = resolve_tariff(db, user.id)

    if ADMIN_STATE.maintenance_mode or ADMIN_STATE.disable_new_connections:
        try:
            await websocket.accept()
            await websocket.send_text(
                json.dumps(
                    {
                        "type": "status",
                        "connected": False,
                        "message": "Сервис на обслуживании. Подключения временно отключены.",
                    },
                    ensure_ascii=False,
                )
            )
        except Exception:
            pass
        finally:
            await websocket.close(code=status.WS_1013_TRY_AGAIN_LATER)
        return

    if platform not in tariff.allowed_platforms:
        try:
            await websocket.send_text(
                json.dumps(
                    {
                        "type": "status",
                        "connected": False,
                        "message": f"Тариф '{tariff.name}' не позволяет использовать платформу '{platform}'.",
                    },
                    ensure_ascii=False,
                )
            )
        finally:
            try:
                await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            except Exception:
                pass
        return

    await websocket.accept()
    try:
        ACTIVE_WS_CONNECTIONS += 1
    except Exception:
        pass
    first_message_seen = set()  # Отслеживание зрителей, которые уже писали в чат в этой сессии
    seen_viewers = set()  # Отслеживание зрителей, которых уже «видели» в этой сессии (join или first_message)
    _cooldown = {}  # (scope, trigger_id, username_or_star) -> last_time_monotonic
    active_tiktok_username: str | None = None
    active_stream_session_id: str | None = None
    _last_ws_touch_at = 0.0
    last_chat_at = time.monotonic()
    last_silence_emit_at = 0.0
    greeted_in_silence: set[str] = set()
    recent_silence_phrases: list[str] = []
    donor_diamonds_total: dict[str, int] = {}
    _allowed_trigger_ids_cache: set[str] | None = None
    _allowed_trigger_ids_cache_at: float = 0.0

    def _cooldown_allows(trigger_id: str, seconds: float | int | None, username: str | None = None) -> bool:
        if not seconds:
            return True
        try:
            seconds_f = float(seconds)
        except Exception:
            return True
        if seconds_f <= 0:
            return True
        now = time.monotonic()
        key = ("global", str(trigger_id), username or "*")
        last = _cooldown.get(key)
        if last is not None and (now - float(last)) < seconds_f:
            return False
        _cooldown[key] = now
        return True

    def _matches_always(t: models.Trigger) -> bool:
        condition_key = str(t.condition_key or "").strip().lower()
        if not condition_key or condition_key == "always":
            if not t.condition_value:
                return True
            v = str(t.condition_value).strip().lower()
            return v in ("true", "1", "yes", "*")
        return False

    def _trigger_condition_key(t: models.Trigger) -> str:
        return str(t.condition_key or "").strip().lower()

    def _trigger_condition_value(t: models.Trigger) -> str:
        return str(t.condition_value or "").strip()

    def _get_allowed_trigger_ids() -> set[str] | None:
        nonlocal _allowed_trigger_ids_cache, _allowed_trigger_ids_cache_at
        if tariff.id != TARIFF_FREE.id:
            return None
        now = time.monotonic()
        if _allowed_trigger_ids_cache is not None and (now - _allowed_trigger_ids_cache_at) < 5.0:
            return _allowed_trigger_ids_cache
        rows = (
            db.query(models.Trigger.id)
            .filter(models.Trigger.user_id == user.id)
            .order_by(models.Trigger.priority.desc(), models.Trigger.created_at.asc())
            .limit(FREE_MAX_TRIGGERS)
            .all()
        )
        _allowed_trigger_ids_cache = {str(r[0]) for r in rows}
        _allowed_trigger_ids_cache_at = now
        return _allowed_trigger_ids_cache

    def get_current_settings():
        """Получить актуальные настройки пользователя (голос + флаги)."""
        settings = db.query(models.UserSettings).filter(models.UserSettings.user_id == user.id).first()
        voice_id = (settings.voice_id if settings and settings.voice_id else "gtts-ru")

        # NovaFree: only allow gtts voices
        voice = get_voice_by_id(voice_id)
        engine = voice.get("engine") if voice else None
        if engine and engine not in tariff.allowed_tts_engines:
            voice_id = "gtts-ru"

        # дефолты если нет записей
        silence_enabled = bool(getattr(settings, "silence_enabled", False)) if settings else False
        silence_minutes = int(getattr(settings, "silence_minutes", 5) or 5) if settings else 5
        if silence_minutes < 1:
            silence_minutes = 1
        if silence_minutes > 60:
            silence_minutes = 60

        # premium gate: silence requires eleven
        if "eleven" not in tariff.allowed_tts_engines:
            silence_enabled = False

        chat_tts_mode = str(getattr(settings, "chat_tts_mode", "all") or "all") if settings else "all"
        chat_tts_mode = chat_tts_mode.strip().lower()
        if chat_tts_mode not in ("all", "prefix", "donor"):
            chat_tts_mode = "all"

        chat_tts_prefixes = str(getattr(settings, "chat_tts_prefixes", ".") or ".") if settings else "."
        chat_tts_prefixes = "".join([c for c in chat_tts_prefixes if not c.isspace()])[:8] or "."

        try:
            chat_tts_min_diamonds = int(getattr(settings, "chat_tts_min_diamonds", 0) or 0) if settings else 0
        except Exception:
            chat_tts_min_diamonds = 0
        if chat_tts_min_diamonds < 0:
            chat_tts_min_diamonds = 0

        return {
            "voice_id": voice_id,
            "tts_enabled": (settings.tts_enabled if settings else True),
            "gift_sounds_enabled": (settings.gift_sounds_enabled if settings else True),
            "viewer_sounds_enabled": (settings.viewer_sounds_enabled if settings and hasattr(settings, 'viewer_sounds_enabled') else True),
            "silence_enabled": silence_enabled,
            "silence_minutes": silence_minutes,
            "chat_tts_mode": chat_tts_mode,
            "chat_tts_prefixes": chat_tts_prefixes,
            "chat_tts_min_diamonds": chat_tts_min_diamonds,
        }

    def _chat_tts_should_speak(user_login: str, message: str) -> tuple[bool, str]:
        """Returns (should_speak, sanitized_text_for_tts)."""
        s = get_current_settings()
        if not s.get("tts_enabled"):
            return (False, "")

        mode = str(s.get("chat_tts_mode") or "all")
        if mode == "all":
            return (True, message)

        u_key = _norm_tiktok_login(user_login)

        if mode == "donor":
            min_d = int(s.get("chat_tts_min_diamonds") or 0)
            if min_d <= 0:
                min_d = 1
            have = int(donor_diamonds_total.get(u_key, 0) or 0)
            if have >= min_d:
                return (True, message)
            return (False, "")

        if mode == "prefix":
            prefixes = str(s.get("chat_tts_prefixes") or ".")
            prefixes_set = set(prefixes)
            trimmed = (message or "").lstrip()
            if not trimmed:
                return (False, "")
            if trimmed[0] not in prefixes_set:
                return (False, "")
            without = trimmed[1:].lstrip()
            if not without:
                return (False, "")
            return (True, without)

        return (True, message)

    def _silence_is_active() -> tuple[bool, int]:
        s = get_current_settings()
        if not s.get("silence_enabled"):
            return (False, int(s.get("silence_minutes") or 5))
        minutes = int(s.get("silence_minutes") or 5)
        now = time.monotonic()
        return ((now - float(last_chat_at)) >= float(minutes) * 60.0, minutes)

    def _choose_silence_phrase() -> str:
        pool = [
            "Ребята, не стесняйтесь — пишите в чат, я тут!",
            "Как настроение? Напишите в чат пару слов 🙂",
            "Если вы новенький — привет! Как вас зовут?",
            "Что сейчас делаем: апаемся или фармим?",
            "Оцените от 1 до 10, как идёт стрим.",
            "Какая музыка вам больше заходит на стриме?",
            "Кто откуда смотрит? Город в чат!",
            "Пока тихо — давайте вопрос-ответ: задавайте вопросы.",
            "Кто впервые на канале — ставьте плюсик в чат.",
            "Какой контент хотите дальше: лайв, гайды или разборы?",
            "Напишите, что сегодня у вас было самым классным событием.",
            "Проверка связи: чат живой?",
            "Какой ваш любимый момент на стримах?",
            "Давайте актив — любой смайлик в чат.",
            "Кто уже подписан — спасибо! Кто нет — загляните, если нравится.",
            "Какой у вас сегодня уровень энергии — высокий или на минималках?",
            "С каким настроем вы зашли на стрим?",
            "Если есть идея для следующей темы — напишите.",
            "Окей, чат на паузе. Я подожду… но вы пишите!",
            "Кто тут главный по активности? Давайте оживим чат.",
        ]
        # avoid repeating last few
        recent = set(recent_silence_phrases[-5:])
        candidates = [p for p in pool if p not in recent]
        if not candidates:
            candidates = pool
        return candidates[int(time.monotonic() * 1000) % len(candidates)]

    async def _emit_silence_message(extra_text: str | None = None):
        nonlocal last_chat_at, last_silence_emit_at
        # rate limit: at most once per 60s
        now = time.monotonic()
        if last_silence_emit_at and (now - float(last_silence_emit_at)) < 60.0:
            return

        s = get_current_settings()
        if not s.get("silence_enabled"):
            return
        if not active_tiktok_username or not tiktok_service.is_running(user.id):
            return

        voice_id = "eleven-premium-main"
        phrase = (extra_text or _choose_silence_phrase()).strip()
        if not phrase:
            return

        tts_url = ""
        try:
            tts_url = await generate_tts(phrase, voice_id, user_id=str(user.id))
        except Exception as e:
            logger.warning("Silence TTS failed: %s", e)
            return

        payload = {"type": "chat", "user": "Nova", "message": phrase}
        if tts_url:
            payload["tts_url"] = tts_url
        await _safe_send(payload)
        last_silence_emit_at = now
        last_chat_at = now
        recent_silence_phrases.append(phrase)

    async def on_comment(u: str, text: str):
        nonlocal last_chat_at
        last_chat_at = time.monotonic()
        s = get_current_settings()
        voice_id = s["voice_id"]
        sanitized_text = _remove_emojis(text)
        # find trigger
        allowed_ids = _get_allowed_trigger_ids()
        q = (
            db.query(models.Trigger)
            .filter(
                models.Trigger.user_id == user.id,
                models.Trigger.event_type == "chat",
                models.Trigger.enabled == True,
            )
            .order_by(models.Trigger.priority.desc(), models.Trigger.created_at.asc())
        )
        if allowed_ids is not None:
            q = q.filter(models.Trigger.id.in_(allowed_ids))
        trig = q.all()
        tts_url = None
        for t in trig:
            condition_key = _trigger_condition_key(t)
            condition_value = _trigger_condition_value(t)
            if condition_key == "message_contains" and condition_value and condition_value.lower() in text.lower():
                if t.action == models.TriggerAction.tts and t.action_params:
                    if not _cooldown_allows(t.id, (t.action_params or {}).get("cooldown_seconds"), username=u):
                        continue
                    template = t.action_params.get("text_template") or "{message}"
                    phrase = template.replace("{user}", _remove_emojis(u)).replace("{message}", sanitized_text)
                    tts_url = await generate_tts(phrase, voice_id, user_id=str(user.id))
                    try:
                        t.executed_count += 1
                        db.add(t)
                        db.commit()
                    except Exception:
                        logger.warning("Не удалось обновить executed_count для триггера %s", t.id)
                    break
        if not tts_url:
            should_speak, tts_text = _chat_tts_should_speak(u, sanitized_text)
            if should_speak:
                tts_url = await generate_tts(tts_text, voice_id, user_id=str(user.id))
        # если tts выключен — отправим без tts_url
        payload = {"type": "chat", "user": u, "message": text}
        if tts_url:
            payload["tts_url"] = tts_url
        await websocket.send_text(json.dumps(payload, ensure_ascii=False))

        # Для устойчивости (регистры, '@') используем нормализованный ключ
        u_key = _norm_tiktok_login(u)
        if u_key and u_key not in first_message_seen:
            first_message_seen.add(u_key)
            # JoinEvent от TikTok может отсутствовать: используем первое сообщение как «первое появление» зрителя.
            # Важно: не дублируем, если join уже был обработан.
            if u_key not in seen_viewers:
                if WS_DEBUG:
                    logger.debug("First message from '%s' -> treat as viewer_join (first seen in session)", u)
                await on_join(u)
            
            # Также проверяем viewer_first_message триггеры
            allowed_ids = _get_allowed_trigger_ids()
            qv = (
                db.query(models.Trigger)
                .filter(
                    models.Trigger.user_id == user.id,
                    models.Trigger.event_type == "viewer_first_message",
                    models.Trigger.enabled == True,
                )
                .order_by(models.Trigger.priority.desc(), models.Trigger.created_at.asc())
            )
            if allowed_ids is not None:
                qv = qv.filter(models.Trigger.id.in_(allowed_ids))
            trig_v = qv.all()
            for t in trig_v:
                matched = False
                if _matches_always(t):
                    matched = True
                elif _trigger_condition_key(t) == "username" and _trigger_condition_value(t):
                    cv = _norm_tiktok_login(_trigger_condition_value(t))
                    matched = bool(cv) and (cv == u_key)

                if matched:
                    fn = t.action_params.get("sound_filename") if t.action_params else None
                    if fn and _cooldown_allows(t.id, (t.action_params or {}).get("cooldown_seconds"), username=u):
                        await websocket.send_text(json.dumps({"type": "viewer_first_message", "user": u, "sound_url": _abs_url(f"/static/sounds/{user.id}/{fn}")}, ensure_ascii=False))
                        try:
                            t.executed_count += 1
                            db.add(t)
                            db.commit()
                        except Exception:
                            logger.warning("Не удалось обновить executed_count для триггера %s", t.id)
                    break

    async def on_gift(u: str, gift_id: str, gift_name: str, count: int, diamonds: int = 0):
        s = get_current_settings()
        # JoinEvent от TikTok может отсутствовать. Если впервые видим зрителя по подарку — трактуем как viewer_join.
        u_key = _norm_tiktok_login(u)
        if u_key and u_key not in seen_viewers:
            await on_join(u)

        # Track donors for chat TTS filtering (session-only)
        try:
            if u_key:
                d = int(diamonds or 0)
                c = int(count or 0)
                if c <= 0:
                    c = 1
                delta = d * c
                if delta > 0:
                    donor_diamonds_total[u_key] = int(donor_diamonds_total.get(u_key, 0) or 0) + int(delta)
        except Exception:
            pass
        if WS_DEBUG:
            logger.debug("on_gift: user=%s gift_id=%s gift_name=%s count=%s diamonds=%s", u, gift_id, gift_name, count, diamonds)
        # Ищем триггер для подарка (только звуковые файлы, НЕ TTS!)
        allowed_ids = _get_allowed_trigger_ids()
        q = (
            db.query(models.Trigger)
            .filter(
                models.Trigger.user_id == user.id,
                models.Trigger.event_type == "gift",
                models.Trigger.enabled == True,
            )
            .order_by(models.Trigger.priority.desc(), models.Trigger.created_at.asc())
        )
        if allowed_ids is not None:
            q = q.filter(models.Trigger.id.in_(allowed_ids))
        trig = q.all()
        if WS_DEBUG:
            logger.debug("on_gift: triggers=%d", len(trig))
        sound_url = None
        for t in trig:
            if WS_DEBUG:
                logger.debug(
                    "on_gift: check trigger=%s key=%s val=%r enabled=%s", t.id, t.condition_key, t.condition_value, t.enabled
                )
            
            # Проверяем по gift_id (строгое сравнение строк)
            condition_key = _trigger_condition_key(t)
            condition_value = _trigger_condition_value(t)

            if condition_key == "gift_id" and condition_value:
                # Приводим оба значения к строке для сравнения
                if str(condition_value) == str(gift_id):
                    # combo_count: 0 = любое количество, иначе требуем count >= combo_count
                    if getattr(t, "combo_count", 0) and int(count) < int(t.combo_count):
                        continue
                    fn = t.action_params.get("sound_filename") if t.action_params else None
                    if fn and s["gift_sounds_enabled"] and _cooldown_allows(t.id, (t.action_params or {}).get("cooldown_seconds")):
                        sound_url = _abs_url(f"/static/sounds/{user.id}/{fn}")
                        if WS_DEBUG:
                            logger.debug("on_gift: matched by gift_id trigger=%s sound=%s", t.id, fn)
                        try:
                            t.executed_count += 1
                            db.add(t)
                            db.commit()
                        except Exception:
                            logger.warning("Не удалось обновить executed_count для триггера %s", t.id)
                        break
                else:
                    if WS_DEBUG:
                        logger.debug("on_gift: no match gift_id trigger=%s %r != %r", t.id, condition_value, gift_id)

            # Проверяем по gift_name (регистронезависимое сравнение)
            elif condition_key == "gift_name" and condition_value:
                if condition_value.lower() == gift_name.lower():
                    if getattr(t, "combo_count", 0) and int(count) < int(t.combo_count):
                        continue
                    fn = t.action_params.get("sound_filename") if t.action_params else None
                    if fn and s["gift_sounds_enabled"] and _cooldown_allows(t.id, (t.action_params or {}).get("cooldown_seconds")):
                        sound_url = _abs_url(f"/static/sounds/{user.id}/{fn}")
                        if WS_DEBUG:
                            logger.debug("on_gift: matched by gift_name trigger=%s sound=%s", t.id, fn)
                        try:
                            t.executed_count += 1
                            db.add(t)
                            db.commit()
                        except Exception:
                            logger.warning("Не удалось обновить executed_count для триггера %s", t.id)
                        break
                else:
                    if WS_DEBUG:
                        logger.debug("on_gift: no match gift_name trigger=%s %r != %r", t.id, condition_value, gift_name)

        # Фолбэк: если нет пользовательского триггера — используем глобальный звук подарка
        if not sound_url and s["gift_sounds_enabled"]:
            try:
                global_sound = get_global_gift_sound_path(int(gift_id))
            except Exception:
                global_sound = None
            if global_sound:
                sound_url = _abs_url(global_sound)
        # Отправляем событие подарка (только с sound_url если триггер есть)
        payload = {"type": "gift", "user": u, "gift_id": gift_id, "gift_name": gift_name, "count": count, "diamonds": diamonds}
        if sound_url:
            payload["sound_url"] = sound_url

        # Сохраняем подарок и инкрементируем агрегаты (UTC)
        try:
            record_gift_and_update_stats(
                db,
                streamer_id=str(user.id),
                streamer_tiktok_username=active_tiktok_username,
                donor_username=u,
                gift_id=gift_id,
                gift_name=gift_name,
                gift_count=int(count or 0),
                gift_coins=int(diamonds or 0),
            )
        except Exception:
            # record_gift_and_update_stats сам логирует/rollback'ает, но держим WS стабильным
            pass
        if WS_DEBUG:
            logger.debug("on_gift: send payload=%s", payload)
        await websocket.send_text(json.dumps(payload, ensure_ascii=False))

    async def on_like(u: str, count: int):
        # JoinEvent от TikTok может отсутствовать. Если впервые видим зрителя по лайку — трактуем как viewer_join.
        u_key = _norm_tiktok_login(u)
        if u_key and u_key not in seen_viewers:
            await on_join(u)
        await websocket.send_text(json.dumps({"type": "like", "user": u, "count": count}, ensure_ascii=False))

    def _norm_tiktok_login(s: str | None) -> str:
        return (s or "").strip().lstrip("@").lower()

    async def on_join(viewer):
        # viewer может быть str (старый формат) или dict {username, nickname}
        login_raw = None
        nickname_raw = None
        if isinstance(viewer, dict):
            login_raw = viewer.get("username") or viewer.get("unique_id") or viewer.get("user")
            nickname_raw = viewer.get("nickname") or viewer.get("display_name")
        else:
            login_raw = str(viewer) if viewer is not None else None

        login_norm = _norm_tiktok_login(login_raw)
        nick_norm = _norm_tiktok_login(nickname_raw)
        viewer_key = login_norm or nick_norm
        if not viewer_key:
            return

        # Для TTS/логов нужен читабельный юзер заранее
        display_user = (login_raw or nickname_raw or viewer_key)

        first_time = viewer_key not in seen_viewers
        if first_time:
            seen_viewers.add(viewer_key)

        if WS_DEBUG:
            logger.debug(
                "on_join: login=%s nickname=%s key=%s first_time=%s",
                login_norm,
                nick_norm,
                viewer_key,
                first_time,
            )
        
        s = get_current_settings()
        sound_url = None
        tts_url = None
        
        # Проверяем триггеры для добавления звука (опционально)
        allowed_ids = _get_allowed_trigger_ids()
        q = (
            db.query(models.Trigger)
            .filter(
                models.Trigger.user_id == user.id,
                models.Trigger.event_type == "viewer_join",
                models.Trigger.enabled == True,
            )
            .order_by(models.Trigger.priority.desc(), models.Trigger.created_at.asc())
        )
        if allowed_ids is not None:
            q = q.filter(models.Trigger.id.in_(allowed_ids))
        trig = q.all()
        if WS_DEBUG:
            logger.debug("on_join: triggers=%d", len(trig))
        
        autoplay_sound: bool | None = None
        for t in trig:
            if WS_DEBUG:
                logger.debug("on_join: check trigger=%s key=%s val=%r", t.id, t.condition_key, t.condition_value)

            ap = t.action_params or {}
            once_per_stream = ap.get("once_per_stream", True)
            # Если триггер настроен на "только 1 раз за стрим" — не срабатываем на повторные join этого же зрителя.
            if once_per_stream and not first_time:
                continue
            
            matched = False
            if _matches_always(t):
                matched = True
            elif _trigger_condition_key(t) == "username" and _trigger_condition_value(t):
                cv = _trigger_condition_value(t).strip().lstrip("@").lower()
                matched = (cv == login_norm) or (not login_norm and cv == nick_norm) or (nick_norm and cv == nick_norm)

            if matched:
                # play_sound
                if t.action == models.TriggerAction.play_sound:
                    fn = ap.get("sound_filename")
                    autoplay_sound = ap.get("autoplay_sound", True)
                    if fn and s["viewer_sounds_enabled"] and _cooldown_allows(t.id, (t.action_params or {}).get("cooldown_seconds"), username=viewer_key):
                        sound_url = _abs_url(f"/static/sounds/{user.id}/{fn}")
                        if WS_DEBUG:
                            logger.debug("on_join: matched trigger=%s sound=%s", t.id, fn)
                        try:
                            t.executed_count += 1
                            db.add(t)
                            db.commit()
                        except Exception:
                            logger.warning("Не удалось обновить executed_count для триггера %s", t.id)

                # tts
                elif t.action == models.TriggerAction.tts:
                    if not _cooldown_allows(t.id, (t.action_params or {}).get("cooldown_seconds"), username=viewer_key):
                        break
                    template = (ap.get("text_template") or "{user}").strip() or "{user}"
                    phrase = (
                        template
                        .replace("{user}", _remove_emojis(display_user))
                        .replace("{username}", _remove_emojis(login_raw or ""))
                        .replace("{nickname}", _remove_emojis(nickname_raw or ""))
                    )
                    voice_id = s["voice_id"]
                    tts_url = await generate_tts(phrase, voice_id, user_id=str(user.id))
                    if WS_DEBUG:
                        logger.debug("on_join: matched tts trigger=%s", t.id)
                    try:
                        t.executed_count += 1
                        db.add(t)
                        db.commit()
                    except Exception:
                        logger.warning("Не удалось обновить executed_count для триггера %s", t.id)
                break
        
        # ВСЕГДА отправляем событие на фронтенд (для отображения в UI)
        # Для UI отдаём читабельные значения, но сохраняем и нормализованное поле
        payload = {
            "type": "viewer_join",
            "user": display_user,
            "username": login_raw or None,
            "nickname": nickname_raw or None,
            "user_norm": viewer_key,
        }
        if sound_url:
            payload["sound_url"] = sound_url
            if autoplay_sound is False:
                payload["autoplay_sound"] = False
        if tts_url:
            payload["tts_url"] = tts_url
        
        if WS_DEBUG:
            logger.debug("on_join: send payload=%s", payload)
        await websocket.send_text(json.dumps(payload, ensure_ascii=False))

        # Silence mode: greet new viewers if chat is already silent
        try:
            silent, _m = _silence_is_active()
        except Exception:
            silent = False
        if silent and viewer_key not in greeted_in_silence:
            greeted_in_silence.add(viewer_key)
            greet_name = (login_raw or nickname_raw or "")
            greet_name = str(greet_name).strip()
            if greet_name.startswith("@"):  # avoid double @ in speech
                greet_name = greet_name[1:]
            if greet_name:
                await _emit_silence_message(f"Привет, {greet_name}! Рад видеть тебя на стриме. Напиши в чат, как дела?")
            else:
                await _emit_silence_message("Привет! Рад видеть тебя на стриме. Напиши в чат, как дела?")

    async def on_follow(u: str):
        s = get_current_settings()
        sound_url = None
        u_norm = _norm_tiktok_login(u)

        allowed_ids = _get_allowed_trigger_ids()
        q = (
            db.query(models.Trigger)
            .filter(
                models.Trigger.user_id == user.id,
                models.Trigger.event_type == "follow",
                models.Trigger.enabled == True,
            )
            .order_by(models.Trigger.priority.desc(), models.Trigger.created_at.asc())
        )
        if allowed_ids is not None:
            q = q.filter(models.Trigger.id.in_(allowed_ids))
        trig = q.all()
        for t in trig:
            matched = False
            if not t.condition_key or t.condition_key == "always":
                if not t.condition_value or str(t.condition_value).lower() in ("true", "1", "yes", "*"):
                    matched = True
            elif _trigger_condition_key(t) == "username" and _trigger_condition_value(t):
                matched = (_norm_tiktok_login(_trigger_condition_value(t)) == u_norm)

            if matched:
                fn = t.action_params.get("sound_filename") if t.action_params else None
                if fn and s["viewer_sounds_enabled"] and _cooldown_allows(t.id, (t.action_params or {}).get("cooldown_seconds")):
                    sound_url = _abs_url(f"/static/sounds/{user.id}/{fn}")
                    try:
                        t.executed_count += 1
                        db.add(t)
                        db.commit()
                    except Exception:
                        logger.warning("Не удалось обновить executed_count для триггера %s", t.id)
                break

        payload = {"type": "follow", "user": u}
        if sound_url:
            payload["sound_url"] = sound_url
        await websocket.send_text(json.dumps(payload, ensure_ascii=False))

    async def on_subscribe(u: str):
        s = get_current_settings()
        sound_url = None
        u_norm = _norm_tiktok_login(u)

        allowed_ids = _get_allowed_trigger_ids()
        q = (
            db.query(models.Trigger)
            .filter(
                models.Trigger.user_id == user.id,
                models.Trigger.event_type == "subscribe",
                models.Trigger.enabled == True,
            )
            .order_by(models.Trigger.priority.desc(), models.Trigger.created_at.asc())
        )
        if allowed_ids is not None:
            q = q.filter(models.Trigger.id.in_(allowed_ids))
        trig = q.all()
        for t in trig:
            matched = False
            if not t.condition_key or t.condition_key == "always":
                if not t.condition_value or str(t.condition_value).lower() in ("true", "1", "yes", "*"):
                    matched = True
            elif _trigger_condition_key(t) == "username" and _trigger_condition_value(t):
                matched = (_norm_tiktok_login(_trigger_condition_value(t)) == u_norm)

            if matched:
                fn = t.action_params.get("sound_filename") if t.action_params else None
                if fn and s["viewer_sounds_enabled"] and _cooldown_allows(t.id, (t.action_params or {}).get("cooldown_seconds")):
                    sound_url = _abs_url(f"/static/sounds/{user.id}/{fn}")
                    try:
                        t.executed_count += 1
                        db.add(t)
                        db.commit()
                    except Exception:
                        logger.warning("Не удалось обновить executed_count для триггера %s", t.id)
                break

        payload = {"type": "subscribe", "user": u}
        if sound_url:
            payload["sound_url"] = sound_url
        await websocket.send_text(json.dumps(payload, ensure_ascii=False))

    async def on_share(u: str):
        await websocket.send_text(json.dumps({"type": "share", "user": u}, ensure_ascii=False))

    async def on_viewer(current: int, total: int):
        if WS_DEBUG:
            logger.debug("on_viewer: current=%s total=%s", current, total)
        await websocket.send_text(json.dumps({"type": "viewer", "current": current, "total": total}, ensure_ascii=False))

    # WS control loop
    try:
        async def _safe_send(payload: dict):
            try:
                await websocket.send_text(json.dumps(payload, ensure_ascii=False))
            except Exception:
                return

        async def _silence_monitor():
            while True:
                await asyncio.sleep(5)
                silent, _minutes = _silence_is_active()
                if not silent:
                    continue
                await _emit_silence_message()

        async def _on_tiktok_connect(username: str):
            nonlocal active_tiktok_username
            active_tiktok_username = username

            # Persist LIVE session (best-effort).
            try:
                nonlocal active_stream_session_id
                ss = models.StreamSession(
                    user_id=user.id,
                    tiktok_username=username,
                    started_at=datetime.utcnow(),
                    status="running",
                )
                db.add(ss)
                db.flush()
                active_stream_session_id = getattr(ss, "id", None)
                db.commit()
            except Exception:
                try:
                    db.rollback()
                except Exception:
                    pass
            await _safe_send({
                "type": "status",
                "message": f"Подключено к TikTok Live @{username}",
                "connected": True,
                "tiktok_username": username,
            })

        async def _on_tiktok_disconnect(username: str):
            nonlocal active_tiktok_username
            if active_tiktok_username == username:
                active_tiktok_username = None

            # Close LIVE session (best-effort).
            try:
                nonlocal active_stream_session_id
                if active_stream_session_id:
                    ss = db.get(models.StreamSession, active_stream_session_id)
                    if ss and getattr(ss, "ended_at", None) is None:
                        ss.ended_at = datetime.utcnow()
                        ss.status = "ended"
                        db.add(ss)
                        db.commit()
                active_stream_session_id = None
            except Exception:
                try:
                    db.rollback()
                except Exception:
                    pass
            auto_reconnect = str(os.getenv("TT_AUTO_RECONNECT", "1")).strip().lower() in ("1", "true", "yes", "on")
            await _safe_send({
                "type": "status",
                "message": f"TikTok Live отключен @{username}" + (" — переподключаемся…" if auto_reconnect else ""),
                "connected": False,
                "tiktok_username": username,
            })

        # Initial status
        await _safe_send({
            "type": "status",
            "connected": tiktok_service.is_running(user.id),
            "message": "WS подключен. Подключение к LIVE выполняется по команде.",
            "tiktok_username": (user.tiktok_username or None),
        })

        # Touch last_ws_at once on WS connect (+ best-effort client hints).
        try:
            user.last_ws_at = datetime.utcnow()
            try:
                user.last_client_platform = platform
            except Exception:
                pass
            try:
                os_hint = (client_os_raw or "").strip()[:32] or None
                if os_hint:
                    user.last_client_os = os_hint
            except Exception:
                pass
            try:
                dev = (client_device_raw or "").strip()
                if dev:
                    user.last_device = dev[:255]
            except Exception:
                pass
            db.add(user)
            db.commit()
        except Exception:
            try:
                db.rollback()
            except Exception:
                pass

        silence_task: asyncio.Task | None = asyncio.create_task(_silence_monitor())
        try:
            if 'silence_task' in locals() and silence_task is not None:
                silence_task.cancel()
        except Exception:
            pass

        # Backwards compatibility: optional autostart on WS connect (disabled by default)
        ws_autostart = str(os.getenv("TT_WS_AUTOSTART", "0")).strip().lower() in ("1", "true", "yes", "on")
        if ws_autostart and (user.tiktok_username or user.username):
            target_username = (user.tiktok_username or user.username).strip().lstrip("@").lower()
            if target_username:
                active_tiktok_username = target_username
                await _safe_send({
                    "type": "status",
                    "message": f"Подключаемся к TikTok Live @{target_username}…",
                    "connected": False,
                    "tiktok_username": target_username,
                })
                await tiktok_service.start_client(
                    user_id=user.id,
                    tiktok_username=target_username,
                    on_comment_callback=on_comment,
                    on_gift_callback=on_gift,
                    on_like_callback=on_like,
                    on_join_callback=on_join,
                    on_follow_callback=on_follow,
                    on_subscribe_callback=on_subscribe,
                    on_share_callback=on_share,
                    on_viewer_callback=on_viewer,
                    on_connect_callback=_on_tiktok_connect,
                    on_disconnect_callback=_on_tiktok_disconnect,
                )

        while True:
            raw = await websocket.receive_text()

            # Throttled heartbeat write (best-effort).
            try:
                now_m = time.monotonic()
                if (now_m - _last_ws_touch_at) >= 15.0:
                    _last_ws_touch_at = now_m
                    user.last_ws_at = datetime.utcnow()
                    db.add(user)
                    db.commit()
            except Exception:
                try:
                    db.rollback()
                except Exception:
                    pass
            try:
                data = json.loads(raw) if raw else {}
            except Exception:
                continue

            if not isinstance(data, dict):
                continue

            action = str(data.get("action") or "").strip().lower()

            if action == "connect_tiktok":
                username = str(data.get("username") or "").strip().lstrip("@").lower()
                if not username:
                    await _safe_send({"type": "error", "message": "Username is required"})
                    continue

                # remember for stats resolution (most recent TikTok account)
                try:
                    row = (
                        db.query(models.UserTikTokAccount)
                        .filter(models.UserTikTokAccount.user_id == user.id)
                        .filter(models.UserTikTokAccount.username == username)
                        .first()
                    )
                    if not row:
                        row = models.UserTikTokAccount(user_id=user.id, username=username, last_used_at=datetime.utcnow())
                        db.add(row)
                    else:
                        row.last_used_at = datetime.utcnow()
                        db.add(row)
                    db.commit()
                except Exception:
                    db.rollback()

                active_tiktok_username = username

                # Stop previous session if any
                if tiktok_service.is_running(user.id):
                    try:
                        await tiktok_service.stop_client(user.id)
                    except Exception:
                        pass

                await _safe_send({
                    "type": "status",
                    "message": f"Подключаемся к TikTok Live @{username}…",
                    "connected": False,
                    "tiktok_username": username,
                })

                try:
                    await tiktok_service.start_client(
                        user_id=user.id,
                        tiktok_username=username,
                        on_comment_callback=on_comment,
                        on_gift_callback=on_gift,
                        on_like_callback=on_like,
                        on_join_callback=on_join,
                        on_follow_callback=on_follow,
                        on_subscribe_callback=on_subscribe,
                        on_share_callback=on_share,
                        on_viewer_callback=on_viewer,
                        on_connect_callback=_on_tiktok_connect,
                        on_disconnect_callback=_on_tiktok_disconnect,
                    )
                except UserNotFoundError:
                    await _safe_send({
                        "type": "error",
                        "message": (
                            "TikTok пользователь не найден. "
                            "Проверьте, что ник указан без '@', и что стрим запущен."
                        ) + (f" (username: @{username})" if username else ""),
                    })
                except Exception as e:
                    if WebcastBlocked200Error is not None and isinstance(e, WebcastBlocked200Error):
                        await _safe_send({
                            "type": "error",
                            "message": (
                                "TikTok заблокировал WebSocket (DEVICE_BLOCKED). "
                                "На VPS/датацентровом IP это бывает очень часто. "
                                "Решение: используйте residential proxy (TIKTOK_PROXY) и/или авторизованные cookies (TIKTOK_COOKIES)."
                            ),
                        })
                    else:
                        await _safe_send({
                            "type": "error",
                            "message": f"Ошибка подключения к TikTok Live: {e}",
                        })

            elif action == "disconnect_tiktok":
                if tiktok_service.is_running(user.id):
                    try:
                        await tiktok_service.stop_client(user.id)
                    except Exception:
                        pass
                active_tiktok_username = None

                # Close session if disconnect callback did not fire.
                try:
                    if active_stream_session_id:
                        ss = db.get(models.StreamSession, active_stream_session_id)
                        if ss and getattr(ss, "ended_at", None) is None:
                            ss.ended_at = datetime.utcnow()
                            ss.status = "ended"
                            db.add(ss)
                            db.commit()
                    active_stream_session_id = None
                except Exception:
                    try:
                        db.rollback()
                    except Exception:
                        pass
                await _safe_send({
                    "type": "status",
                    "message": "Отключено от TikTok Live",
                    "connected": False,
                })
    except WebSocketDisconnect:
        # Клиент сам отключился — ничего не отправляем
        pass
    except UserNotFoundError:
        # Особый случай: TikTokLive не нашёл пользователя/стрим
        try:
            await websocket.send_text(json.dumps({
                "type": "error",
                "message": (
                    "TikTok пользователь не найден. "
                    "Проверьте, что ник указан без '@', и что стрим запущен."
                ) + (f" (username: @{target_username})" if 'target_username' in locals() and target_username else "")
            }, ensure_ascii=False))
        except Exception:
            pass
    except Exception as e:
        # DEVICE_BLOCKED и подобные блокировки лучше объяснять явно
        if WebcastBlocked200Error is not None and isinstance(e, WebcastBlocked200Error):
            try:
                await websocket.send_text(json.dumps({
                    "type": "error",
                    "message": (
                        "TikTok заблокировал WebSocket (DEVICE_BLOCKED). "
                        "На VPS/датацентровом IP это бывает очень часто. "
                        "Решение: используйте residential proxy (TIKTOK_PROXY) и/или авторизованные cookies (TIKTOK_COOKIES)."
                    )
                }, ensure_ascii=False))
            except Exception:
                pass
        else:
            # Отправляем любую другую ошибку перед закрытием
            error_msg = str(e)
            try:
                await websocket.send_text(json.dumps({
                    "type": "error",
                    "message": f"Ошибка подключения к TikTok Live: {error_msg}"
                }, ensure_ascii=False))
            except Exception:
                pass
    finally:
        if tiktok_service.is_running(user.id):
            await tiktok_service.stop_client(user.id)

        try:
            ACTIVE_WS_CONNECTIONS = max(0, int(ACTIVE_WS_CONNECTIONS) - 1)
        except Exception:
            pass


# ====== REST API ENDPOINTS ======

from pydantic import BaseModel

class ConnectTikTokRequest(BaseModel):
    username: str

class DisconnectTikTokRequest(BaseModel):
    pass  # Простое отключение без параметров


@router.post("/tiktok/connect")
async def connect_tiktok(request: ConnectTikTokRequest, user=Depends(get_current_user), db: Session = Depends(get_db)):
    """
    REST API для подключения к TikTok Live
    """
    username = request.username.strip().lstrip('@')
    if not username:
        raise HTTPException(400, detail="Username is required")
    
    # Тариф проверяем через текущую модель тарифов (как в WS):
    # ограничения по TikTok подключению сейчас не вводим, чтобы не ломать мобильный поток.
    resolve_tariff(db, user.id)
    
    # Если уже подключен - отключаем сначала
    if tiktok_service.is_running(user.id):
        await tiktok_service.stop_client(user.id)
    
    try:
        logger.info(f"REST: Подключение пользователя {user.id} к TikTok Live @{username}")
        
        # Запускаем TikTok клиент
        await tiktok_service.start_client(
            user_id=user.id,
            tiktok_username=username,
            db=db,
            on_connect_callback=None,  # Для REST API не используем callbacks
            on_disconnect_callback=None,
            auto_reconnect=True
        )
        
        # Небольшая пауза для инициализации
        await asyncio.sleep(1)
        
        # Проверяем статус подключения
        if tiktok_service.is_running(user.id):
            logger.info(f"REST: Успешно подключен к TikTok Live @{username}")
            return {"success": True, "message": f"Подключено к @{username}"}
        else:
            logger.warning(f"REST: Не удалось подключиться к TikTok Live @{username}")
            return {"success": False, "message": f"Не удалось подключиться к @{username}"}
            
    except UserNotFoundError:
        logger.error(f"REST: Пользователь TikTok не найден: @{username}")
        raise HTTPException(404, detail=f"TikTok пользователь @{username} не найден")
    except Exception as e:
        logger.error(f"REST: Ошибка подключения к TikTok @{username}: {e}")
        raise HTTPException(500, detail=f"Ошибка подключения: {str(e)}")


@router.post("/tiktok/disconnect")
async def disconnect_tiktok(request: DisconnectTikTokRequest, user=Depends(get_current_user)):
    """
    REST API для отключения от TikTok Live
    """
    try:
        if tiktok_service.is_running(user.id):
            await tiktok_service.stop_client(user.id)
            logger.info(f"REST: Пользователь {user.id} отключен от TikTok Live")
            return {"success": True, "message": "Отключено от TikTok Live"}
        else:
            return {"success": False, "message": "TikTok Live не подключен"}
    except Exception as e:
        logger.error(f"REST: Ошибка отключения от TikTok для пользователя {user.id}: {e}")
        raise HTTPException(500, detail=f"Ошибка отключения: {str(e)}")


@router.get("/tiktok/status")
async def get_tiktok_status(user=Depends(get_current_user)):
    """
    REST API для получения статуса подключения к TikTok Live
    """
    is_connected = tiktok_service.is_running(user.id)
    return {
        "connected": is_connected,
        "message": "Подключено к TikTok Live" if is_connected else "Не подключено к TikTok Live"
    }
