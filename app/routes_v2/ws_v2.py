import json
import logging
import os
import re
import time
import asyncio
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, status, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.database import SessionLocal
from app.db import models
from .auth_v2 import get_current_user
from app.services.security import decode_token
from app.services.tts_service import generate_tts, AVAILABLE_VOICES
from app.services.tiktok_service import tiktok_service
from app.services.gift_sounds import get_global_gift_sound_path
from app.services.plans import resolve_tariff, normalize_platform

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
    # platform can come from query (?platform=mobile) or header
    platform_raw = websocket.headers.get("X-Client-Platform")
    raw_q = websocket.scope.get("query_string", b"").decode()
    if raw_q:
        for part in raw_q.split("&"):
            k, _, v = part.partition("=")
            if k == "platform" and v:
                platform_raw = v
                break
    platform = normalize_platform(platform_raw)
    tariff, _lic = resolve_tariff(db, user.id)

    await websocket.accept()
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
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return
    first_message_seen = set()  # Отслеживание зрителей, которые уже писали в чат в этой сессии
    seen_viewers = set()  # Отслеживание зрителей, которых уже «видели» в этой сессии (join или first_message)
    _cooldown = {}  # (scope, trigger_id, username_or_star) -> last_time_monotonic

    def _cooldown_allows(trigger_id: int, seconds: float | int | None, username: str | None = None) -> bool:
        if not seconds:
            return True
        try:
            seconds_f = float(seconds)
        except Exception:
            return True
        if seconds_f <= 0:
            return True
        now = time.monotonic()
        key = ("global", int(trigger_id), username or "*")
        last = _cooldown.get(key)
        if last is not None and (now - float(last)) < seconds_f:
            return False
        _cooldown[key] = now
        return True

    def _matches_always(t: models.Trigger) -> bool:
        if not t.condition_key or t.condition_key == "always":
            if not t.condition_value:
                return True
            v = str(t.condition_value).strip().lower()
            return v in ("true", "1", "yes", "*")
        return False

    def get_current_settings():
        """Получить актуальные настройки пользователя (голос + флаги)."""
        settings = db.query(models.UserSettings).filter(models.UserSettings.user_id == user.id).first()
        voice_id = (settings.voice_id if settings and settings.voice_id else "gtts-ru")

        # NovaFree: only allow gtts voices
        engine = None
        for voices in AVAILABLE_VOICES.values():
            for v in voices:
                if v.get("id") == voice_id:
                    engine = v.get("engine")
                    break
            if engine:
                break
        if engine and engine not in tariff.allowed_tts_engines:
            voice_id = "gtts-ru"

        # дефолты если нет записей
        return {
            "voice_id": voice_id,
            "tts_enabled": (settings.tts_enabled if settings else True),
            "gift_sounds_enabled": (settings.gift_sounds_enabled if settings else True),
            "viewer_sounds_enabled": (settings.viewer_sounds_enabled if settings and hasattr(settings, 'viewer_sounds_enabled') else True),
        }

    async def on_comment(u: str, text: str):
        s = get_current_settings()
        voice_id = s["voice_id"]
        sanitized_text = _remove_emojis(text)
        # find trigger
        trig = (
            db.query(models.Trigger)
            .filter(models.Trigger.user_id == user.id,
                    models.Trigger.event_type == "chat",
                    models.Trigger.enabled == True)
            .order_by(models.Trigger.priority.desc())
            .all()
        )
        tts_url = None
        for t in trig:
            if t.condition_key == "message_contains" and t.condition_value and t.condition_value.lower() in text.lower():
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
        if not tts_url and s["tts_enabled"]:
            tts_url = await generate_tts(sanitized_text, voice_id, user_id=str(user.id))
        # если tts выключен — отправим без tts_url
        payload = {"type": "chat", "user": u, "message": text}
        if tts_url:
            payload["tts_url"] = tts_url
        await websocket.send_text(json.dumps(payload, ensure_ascii=False))

        if u not in first_message_seen:
            first_message_seen.add(u)
            # JoinEvent от TikTok может отсутствовать: используем первое сообщение как «первое появление» зрителя.
            # Важно: не дублируем, если join уже был обработан.
            if u not in seen_viewers:
                if WS_DEBUG:
                    logger.debug("First message from '%s' -> treat as viewer_join (first seen in session)", u)
                await on_join(u)
            
            # Также проверяем viewer_first_message триггеры
            trig_v = (
                db.query(models.Trigger)
                .filter(models.Trigger.user_id == user.id, models.Trigger.event_type == "viewer_first_message", models.Trigger.enabled == True)
                .order_by(models.Trigger.priority.desc())
                .all()
            )
            for t in trig_v:
                matched = False
                if _matches_always(t):
                    matched = True
                elif t.condition_key == "username" and t.condition_value:
                    matched = (t.condition_value == u)

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
        if WS_DEBUG:
            logger.debug("on_gift: user=%s gift_id=%s gift_name=%s count=%s diamonds=%s", u, gift_id, gift_name, count, diamonds)
        # Ищем триггер для подарка (только звуковые файлы, НЕ TTS!)
        trig = (
            db.query(models.Trigger)
            .filter(models.Trigger.user_id == user.id, models.Trigger.event_type == "gift", models.Trigger.enabled == True)
            .order_by(models.Trigger.priority.desc())
            .all()
        )
        if WS_DEBUG:
            logger.debug("on_gift: triggers=%d", len(trig))
        sound_url = None
        for t in trig:
            if WS_DEBUG:
                logger.debug(
                    "on_gift: check trigger=%s key=%s val=%r enabled=%s", t.id, t.condition_key, t.condition_value, t.enabled
                )
            
            # Проверяем по gift_id (строгое сравнение строк)
            if t.condition_key == "gift_id" and t.condition_value:
                # Приводим оба значения к строке для сравнения
                if str(t.condition_value) == str(gift_id):
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
                        logger.debug("on_gift: no match gift_id trigger=%s %r != %r", t.id, t.condition_value, gift_id)
                    
            # Проверяем по gift_name (регистронезависимое сравнение)
            elif t.condition_key == "gift_name" and t.condition_value:
                if t.condition_value.lower() == gift_name.lower():
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
                        logger.debug("on_gift: no match gift_name trigger=%s %r != %r", t.id, t.condition_value, gift_name)

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
        if WS_DEBUG:
            logger.debug("on_gift: send payload=%s", payload)
        await websocket.send_text(json.dumps(payload, ensure_ascii=False))

    async def on_like(u: str, count: int):
        await websocket.send_text(json.dumps({"type": "like", "user": u, "count": count}, ensure_ascii=False))

    async def on_join(u: str):
        # Игнорируем повторные входы — считаем только первый раз «увидели» за сессию
        if u in seen_viewers:
            if WS_DEBUG:
                logger.debug("on_join: user %s already seen in session, skip", u)
            return

        seen_viewers.add(u)
        if WS_DEBUG:
            logger.debug("on_join: first time in session user=%s", u)
        
        s = get_current_settings()
        sound_url = None
        
        # Проверяем триггеры для добавления звука (опционально)
        trig = (
            db.query(models.Trigger)
            .filter(models.Trigger.user_id == user.id, models.Trigger.event_type == "viewer_join", models.Trigger.enabled == True)
            .order_by(models.Trigger.priority.desc())
            .all()
        )
        if WS_DEBUG:
            logger.debug("on_join: triggers=%d", len(trig))
        
        for t in trig:
            if WS_DEBUG:
                logger.debug("on_join: check trigger=%s key=%s val=%r", t.id, t.condition_key, t.condition_value)
            
            matched = False
            if _matches_always(t):
                matched = True
            elif t.condition_key == "username" and t.condition_value:
                matched = (t.condition_value == u)

            if matched:
                fn = t.action_params.get("sound_filename") if t.action_params else None
                if fn and s["viewer_sounds_enabled"] and _cooldown_allows(t.id, (t.action_params or {}).get("cooldown_seconds")):
                    sound_url = _abs_url(f"/static/sounds/{user.id}/{fn}")
                    if WS_DEBUG:
                        logger.debug("on_join: matched trigger=%s sound=%s", t.id, fn)
                    try:
                        t.executed_count += 1
                        db.add(t)
                        db.commit()
                    except Exception:
                        logger.warning("Не удалось обновить executed_count для триггера %s", t.id)
                break
        
        # ВСЕГДА отправляем событие на фронтенд (для отображения в UI)
        payload = {"type": "viewer_join", "user": u}
        if sound_url:
            payload["sound_url"] = sound_url
        
        if WS_DEBUG:
            logger.debug("on_join: send payload=%s", payload)
        await websocket.send_text(json.dumps(payload, ensure_ascii=False))

    async def on_follow(u: str):
        s = get_current_settings()
        sound_url = None

        trig = (
            db.query(models.Trigger)
            .filter(models.Trigger.user_id == user.id, models.Trigger.event_type == "follow", models.Trigger.enabled == True)
            .order_by(models.Trigger.priority.desc())
            .all()
        )
        for t in trig:
            matched = False
            if not t.condition_key or t.condition_key == "always":
                if not t.condition_value or str(t.condition_value).lower() in ("true", "1", "yes", "*"):
                    matched = True
            elif t.condition_key == "username" and t.condition_value:
                matched = (t.condition_value == u)

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

        trig = (
            db.query(models.Trigger)
            .filter(models.Trigger.user_id == user.id, models.Trigger.event_type == "subscribe", models.Trigger.enabled == True)
            .order_by(models.Trigger.priority.desc())
            .all()
        )
        for t in trig:
            matched = False
            if not t.condition_key or t.condition_key == "always":
                if not t.condition_value or str(t.condition_value).lower() in ("true", "1", "yes", "*"):
                    matched = True
            elif t.condition_key == "username" and t.condition_value:
                matched = (t.condition_value == u)

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

        async def _on_tiktok_connect(username: str):
            await _safe_send({
                "type": "status",
                "message": f"Подключено к TikTok Live @{username}",
                "connected": True,
                "tiktok_username": username,
            })

        async def _on_tiktok_disconnect(username: str):
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

        # Backwards compatibility: optional autostart on WS connect (disabled by default)
        ws_autostart = str(os.getenv("TT_WS_AUTOSTART", "0")).strip().lower() in ("1", "true", "yes", "on")
        if ws_autostart and (user.tiktok_username or user.username):
            target_username = (user.tiktok_username or user.username).strip().lstrip("@").lower()
            if target_username:
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
