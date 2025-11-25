import json
import logging
import os
import re
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, status, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.database import SessionLocal
from app.db import models
from .auth_v2 import get_current_user
from app.services.security import decode_token
from app.services.tts_service import generate_tts
from app.services.tiktok_service import tiktok_service

logger = logging.getLogger(__name__)
router = APIRouter()


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
    await websocket.accept()
    first_message_seen = set()

    def get_current_settings():
        """Получить актуальные настройки пользователя (голос + флаги)."""
        settings = db.query(models.UserSettings).filter(models.UserSettings.user_id == user.id).first()
        # дефолты если нет записей
        return {
            "voice_id": (settings.voice_id if settings and settings.voice_id else "gtts-ru"),
            "tts_enabled": (settings.tts_enabled if settings else True),
            "gift_sounds_enabled": (settings.gift_sounds_enabled if settings else True),
            "gift_tts_alongside": (settings.gift_tts_alongside if settings else False),
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
            trig_v = (
                db.query(models.Trigger)
                .filter(models.Trigger.user_id == user.id, models.Trigger.event_type == "viewer_first_message", models.Trigger.enabled == True)
                .all()
            )
            for t in trig_v:
                if t.condition_key == "username" and t.condition_value and t.condition_value == u:
                    fn = t.action_params.get("sound_filename") if t.action_params else None
                    if fn:
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
        voice_id = s["voice_id"]
        # trigger by gift_id
        trig = (
            db.query(models.Trigger)
            .filter(models.Trigger.user_id == user.id, models.Trigger.event_type == "gift", models.Trigger.enabled == True)
            .order_by(models.Trigger.priority.desc())
            .all()
        )
        sound_url = None
        tts_url = None
        for t in trig:
            # Проверяем по gift_id
            if t.condition_key == "gift_id" and t.condition_value and t.condition_value == gift_id:
                fn = t.action_params.get("sound_filename") if t.action_params else None
                if fn:
                    if s["gift_sounds_enabled"]:
                        sound_url = _abs_url(f"/static/sounds/{user.id}/{fn}")
                    try:
                        t.executed_count += 1
                        db.add(t)
                        db.commit()
                    except Exception:
                        logger.warning("Не удалось обновить executed_count для триггера %s", t.id)
                    break
                # Поддержка TTS действия для подарка по gift_id
                if t.action == models.TriggerAction.tts and t.action_params and s["tts_enabled"]:
                    template = t.action_params.get("text_template") or "{user} отправил {gift_name} x{count}"
                    phrase = template.replace("{user}", _remove_emojis(u)).replace("{gift_name}", _remove_emojis(gift_name)).replace("{count}", str(count))
                    try:
                        tts_url = await generate_tts(phrase, voice_id, user_id=str(user.id))
                        t.executed_count += 1
                        db.add(t)
                        db.commit()
                    except Exception:
                        logger.warning("Не удалось обновить executed_count для TTS gift триггера %s", t.id)
                    # Не break здесь — позволим более приоритетному звуку (если есть) тоже установиться
            # Проверяем по gift_name
            if t.condition_key == "gift_name" and t.condition_value and t.condition_value.lower() == gift_name.lower():
                fn = t.action_params.get("sound_filename") if t.action_params else None
                if fn:
                    if s["gift_sounds_enabled"]:
                        sound_url = _abs_url(f"/static/sounds/{user.id}/{fn}")
                    try:
                        t.executed_count += 1
                        db.add(t)
                        db.commit()
                    except Exception:
                        logger.warning("Не удалось обновить executed_count для триггера %s", t.id)
                    break
                # Поддержка TTS действия для подарка по gift_name
                if t.action == models.TriggerAction.tts and t.action_params and s["tts_enabled"]:
                    template = t.action_params.get("text_template") or "{user} отправил {gift_name} x{count}"
                    phrase = template.replace("{user}", _remove_emojis(u)).replace("{gift_name}", _remove_emojis(gift_name)).replace("{count}", str(count))
                    try:
                        tts_url = await generate_tts(phrase, voice_id, user_id=str(user.id))
                        t.executed_count += 1
                        db.add(t)
                        db.commit()
                    except Exception:
                        logger.warning("Не удалось обновить executed_count для TTS gift триггера %s", t.id)
                    # Не break — позволяем найти звук тоже
        # Генерация TTS для подарка, если включено
        if s["tts_enabled"]:
            phrase = f"{_remove_emojis(u)} отправил подарок {_remove_emojis(gift_name)}, количество {count}"
            # если нет пользовательского звука или включено одновременное воспроизведение
            if (not sound_url or s["gift_tts_alongside"]) and not tts_url:
                # Только если ещё не сгенерировано через TTS-триггер
                tts_url = await generate_tts(phrase, voice_id, user_id=str(user.id))
        payload = {"type": "gift", "user": u, "gift_id": gift_id, "gift_name": gift_name, "count": count, "diamonds": diamonds}
        if sound_url:
            payload["sound_url"] = sound_url
        if tts_url:
            payload["tts_url"] = tts_url
        await websocket.send_text(json.dumps(payload, ensure_ascii=False))

    async def on_like(u: str, count: int):
        await websocket.send_text(json.dumps({"type": "like", "user": u, "count": count}, ensure_ascii=False))

    async def on_join(u: str):
        trig = (
            db.query(models.Trigger)
            .filter(models.Trigger.user_id == user.id, models.Trigger.event_type == "viewer_join", models.Trigger.enabled == True)
            .all()
        )
        for t in trig:
            if t.condition_key == "username" and t.condition_value == u:
                fn = t.action_params.get("sound_filename") if t.action_params else None
                if fn:
                    await websocket.send_text(json.dumps({"type": "viewer_join", "user": u, "sound_url": _abs_url(f"/static/sounds/{user.id}/{fn}")}, ensure_ascii=False))
                    try:
                        t.executed_count += 1
                        db.add(t)
                        db.commit()
                    except Exception:
                        logger.warning("Не удалось обновить executed_count для триггера %s", t.id)
                break

    async def on_follow(u: str):
        await websocket.send_text(json.dumps({"type": "follow", "user": u}, ensure_ascii=False))

    async def on_subscribe(u: str):
        await websocket.send_text(json.dumps({"type": "subscribe", "user": u}, ensure_ascii=False))

    async def on_share(u: str):
        await websocket.send_text(json.dumps({"type": "share", "user": u}, ensure_ascii=False))

    async def on_viewer(current: int, total: int):
        await websocket.send_text(json.dumps({"type": "viewer", "current": current, "total": total}, ensure_ascii=False))

    # run tiktok client
    try:
        # Используем tiktok_username если задан, иначе username
        target_username = user.tiktok_username if user.tiktok_username else user.username
        if not target_username:
            await websocket.send_text(json.dumps({
                "type": "error",
                "message": "TikTok username не указан. Укажите его в настройках."
            }, ensure_ascii=False))
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return
        
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
        )
        # Отправляем подтверждение успешного подключения
        await websocket.send_text(json.dumps({
            "type": "status",
            "message": f"Подключено к TikTok Live @{target_username}",
            "connected": True
        }, ensure_ascii=False))
        
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    except Exception as e:
        # Отправляем ошибку перед закрытием
        error_msg = str(e)
        try:
            await websocket.send_text(json.dumps({
                "type": "error",
                "message": f"Ошибка подключения к TikTok Live: {error_msg}"
            }, ensure_ascii=False))
        except:
            pass
    finally:
        if tiktok_service.is_running(user.id):
            await tiktok_service.stop_client(user.id)
