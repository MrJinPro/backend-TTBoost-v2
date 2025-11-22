from fastapi import APIRouter, WebSocket, WebSocketDisconnect, status
from app.services.license_service import verify_ws_token, get_user_data
from app.services.event_dispatcher import dispatcher
from app.services.tts_service import generate_tts
from app.services.tiktok_service import tiktok_service
from app.services.profile_service import get_or_create_profile, get_gift_sound, get_viewer_sound
from app.services.triggers_service import find_applicable_trigger
from TikTokLive.client.errors import SignatureRateLimitError, SignAPIError, PremiumEndpointError
import asyncio
import json
import logging
import re
import os

logger = logging.getLogger(__name__)
router = APIRouter()


@router.websocket("/ws/{ws_token}")
async def ws_endpoint(websocket: WebSocket, ws_token: str):
    """WebSocket для получения событий TikTok Live стрима"""
    user_data = await verify_ws_token(ws_token)
    if not user_data:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    user_id = user_data.get("user_id")
    await dispatcher.register(websocket)
    
    # Запускаем подключение к TikTok Live если есть username
    stream_task = None
    tiktok_username = user_data.get("tiktok_username", "")
    voice_id = user_data.get("voice_id", "ru-RU-SvetlanaNeural")  # Получаем voice_id
    
    logger.info(f"WebSocket подключен: user_id={user_id}, tiktok_username='{tiktok_username}', voice_id={voice_id}")
    
    def _remove_emojis(s: str) -> str:
        """Удаляет эмодзи и вариационные селекторы из строки."""
        try:
            emoji_pattern = re.compile(
                """
                [\U0001F600-\U0001F64F]  # emoticons
                |[\U0001F300-\U0001F5FF]  # symbols & pictographs
                |[\U0001F680-\U0001F6FF]  # transport & map symbols
                |[\U0001F1E6-\U0001F1FF]  # flags
                |[\U00002702-\U000027B0]  # dingbats
                |[\U000024C2-\U0001F251]  # enclosed characters
                |[\U0001F900-\U0001F9FF]  # supplemental symbols
                |[\U0001FA70-\U0001FAFF]  # symbols extended-A
                |[\u2600-\u26FF]          # misc symbols
                |[\u2700-\u27BF]          # dingbats (BMP)
                |\uFE0F                   # variation selector
                """,
                flags=re.UNICODE | re.VERBOSE,
            )
            return emoji_pattern.sub("", s)
        except Exception:
            return s

    def _first_mention(s: str) -> str:
        m = re.search(r"@(\w[\w\.]*)", s)
        return f"@{m.group(1)}" if m else ""

    def _safe_format(template: str, **kwargs) -> str:
        class _D(dict):
            def __missing__(self, key):
                return "{" + key + "}"
        return template.format_map(_D(**kwargs))

    def _base_url() -> str:
        """Базовый URL для формирования абсолютных ссылок на статику."""
        return (os.getenv("TTS_BASE_URL") or os.getenv("SERVER_HOST") or "http://localhost:8000").rstrip("/")

    def _abs_url(path_or_url: str) -> str:
        """Возвращает абсолютный URL: если пришел относительный путь '/static/...', дополняем базовым хостом."""
        if not path_or_url:
            return path_or_url
        if path_or_url.startswith("http://") or path_or_url.startswith("https://"):
            return path_or_url
        if path_or_url.startswith("/"):
            return f"{_base_url()}{path_or_url}"
        # иначе оставляем как есть
        return path_or_url

    # Множество пользователей, которые уже отправили первое сообщение за текущий стрим
    first_message_seen = set()

    # Callback для обработки комментариев TikTok
    async def on_comment(user: str, text: str):
        """Обработка комментария из TikTok Live"""
        try:
            # 1) Проверяем триггер для чата (event_type='chat')
            trig = await find_applicable_trigger(
                user_id,
                event_type="chat",
                condition_key="message_contains",
                condition_value=text,
            )
            sanitized_text = _remove_emojis(text)
            sanitized_user = _remove_emojis(user)
            mention = _first_mention(text)
            tts_url = None
            if trig and trig.action:
                # Требование: для комментариев только TTS — play_sound игнорируем
                if trig.action.type == "tts" and trig.action.text_template:
                    # Формируем фразу из шаблона
                    phrase = _safe_format(trig.action.text_template, user=sanitized_user, message=sanitized_text, mention=mention)
                    tts_url = await generate_tts(phrase, voice_id)
                    logger.info(f"Chat trigger(tts) для '{text[:20]}...' → шаблон")
            if not tts_url:
                # Обычный режим TTS только текста сообщения
                tts_url = await generate_tts(sanitized_text, voice_id)
            
            # Отправляем клиенту
            payload = {
                "type": "chat",
                "user": user,
                "message": text,
                "tts_url": tts_url,
            }
            await websocket.send_text(json.dumps(payload, ensure_ascii=False))
            logger.info(f"TikTok комментарий: {user}: {text[:30]}...")

            # Триггер: первое сообщение зрителя за текущий стрим
            if user not in first_message_seen:
                first_message_seen.add(user)
                try:
                    trig = await find_applicable_trigger(user_id, event_type="viewer_first_message", condition_key="username", condition_value=user)
                    if trig and trig.enabled and trig.action and trig.action.type == "play_sound" and trig.action.sound_file:
                        sound_url = f"/static/sounds/{user_id}/{trig.action.sound_file}"
                        await websocket.send_text(json.dumps({
                            "type": "viewer_first_message",
                            "user": user,
                            "sound_url": _abs_url(sound_url),
                        }, ensure_ascii=False))
                        logger.info(f"Первое сообщение от {user}: сработал триггер звук {sound_url}")
                except Exception as e:
                    logger.error(f"Ошибка обработки триггера первого сообщения: {e}")
        except Exception as e:
            logger.error(f"Ошибка отправки комментария: {e}")
    
    # Callback для подарков
    async def on_gift(user: str, gift_id: str, gift_name: str, count: int, diamonds: int):
        """Обработка подарка - использует кастомный звук если настроен"""
        try:
            sound_url: str

            # 1) Сначала проверяем триггеры
            trig = await find_applicable_trigger(user_id, event_type="gift", condition_key="gift_name", condition_value=gift_name)
            if trig and trig.enabled and trig.action and trig.action.type == "play_sound" and trig.action.sound_file:
                sound_url = f"/static/sounds/{user_id}/{trig.action.sound_file}"
                logger.info(f"Триггер сработал для подарка {gift_name}: {sound_url}")
            else:
                # 2) Затем проверяем старое сопоставление профиля
                gift_sound = await get_gift_sound(user_id, gift_name)
                if gift_sound and gift_sound.enabled:
                    sound_url = f"/static/sounds/{user_id}/{gift_sound.sound_file}"
                    logger.info(f"Кастомный звук для подарка {gift_name}: {sound_url}")
                else:
                    # 3) Fallback: TTS
                    sound_text = f"{_remove_emojis(user)} отправил подарок {_remove_emojis(gift_name)}, количество {count}"
                    sound_url = await generate_tts(sound_text, voice_id)
            
            payload = {
                "type": "gift",
                "gift_name": gift_name,
                "count": count,
                "sound_url": _abs_url(sound_url),
                "user": user,
                "diamonds": diamonds,
                "gift_id": gift_id,
            }
            await websocket.send_text(json.dumps(payload, ensure_ascii=False))
            logger.info(f"TikTok подарок: {user} {gift_name} x{count}")
        except Exception as e:
            logger.error(f"Ошибка отправки подарка: {e}")
    
    # Callback для лайков (опционально)
    async def on_like(user: str, count: int):
        """Обработка лайков"""
        try:
            payload = {
                "type": "like",
                "user": user,
                "count": count,
            }
            await websocket.send_text(json.dumps(payload, ensure_ascii=False))
            logger.info(f"TikTok лайки: {user} x{count}")
        except Exception as e:
            logger.error(f"Ошибка отправки лайков: {e}")
    
    # Callback для входа зрителей
    async def on_join(user: str):
        """Обработка входа зрителя - проигрывает кастомный звук если настроен"""
        try:
            sound_url = None

            # 1) Проверяем триггер на вход зрителя
            trig = await find_applicable_trigger(user_id, event_type="viewer_join", condition_key="username", condition_value=user)
            if trig and trig.enabled and trig.action and trig.action.type == "play_sound" and trig.action.sound_file:
                sound_url = f"/static/sounds/{user_id}/{trig.action.sound_file}"
                logger.info(f"Триггер на вход зрителя {user}: {sound_url}")
            else:
                # 2) Проверяем старое сопоставление VIP-звуков
                viewer_sound = await get_viewer_sound(user_id, user)
                if viewer_sound and viewer_sound.enabled:
                    sound_url = f"/static/sounds/{user_id}/{viewer_sound.sound_file}"
                    logger.info(f"VIP зритель присоединился: {user} (звук: {sound_url})")

            if sound_url:
                payload = {"type": "viewer_join", "user": user, "sound_url": _abs_url(sound_url)}
                await websocket.send_text(json.dumps(payload, ensure_ascii=False))
        except Exception as e:
            logger.error(f"Ошибка отправки события зрителя: {e}")

    # Callback для подписки (follow)
    async def on_follow(user: str):
        try:
            trig = await find_applicable_trigger(user_id, event_type="follow", condition_key="username", condition_value=user)
            sound_url = None
            if trig and trig.enabled and trig.action and trig.action.type == "play_sound" and trig.action.sound_file:
                sound_url = f"/static/sounds/{user_id}/{trig.action.sound_file}"
            payload = {"type": "follow", "user": user}
            if sound_url:
                payload["sound_url"] = _abs_url(sound_url)
            await websocket.send_text(json.dumps(payload, ensure_ascii=False))
            logger.info(f"Подписка: {user}")
        except Exception as e:
            logger.error(f"Ошибка обработки follow: {e}")

    # Callback для супер-подписки (subscribe)
    async def on_subscribe(user: str):
        try:
            trig = await find_applicable_trigger(user_id, event_type="subscribe", condition_key="username", condition_value=user)
            sound_url = None
            if trig and trig.enabled and trig.action and trig.action.type == "play_sound" and trig.action.sound_file:
                sound_url = f"/static/sounds/{user_id}/{trig.action.sound_file}"
            payload = {"type": "subscribe", "user": user}
            if sound_url:
                payload["sound_url"] = _abs_url(sound_url)
            await websocket.send_text(json.dumps(payload, ensure_ascii=False))
            logger.info(f"Супер-подписка: {user}")
        except Exception as e:
            logger.error(f"Ошибка обработки subscribe: {e}")

    async def on_share(user: str):
        try:
            payload = {"type": "share", "user": user}
            await websocket.send_text(json.dumps(payload, ensure_ascii=False))
            logger.info(f"Share: {user}")
        except Exception as e:
            logger.error(f"Ошибка обработки share: {e}")

    async def on_viewer(current: int, total: int):
        try:
            await websocket.send_text(json.dumps({"type": "viewer", "current": current, "total": total}, ensure_ascii=False))
        except Exception as e:
            logger.error(f"Ошибка отправки viewer метрик: {e}")
    
    try:
        # Подключаемся к TikTok Live если есть username
        if tiktok_username and tiktok_username.strip():
            logger.info(f"🔴 Подключение к TikTok Live: @{tiktok_username}")
            try:
                await tiktok_service.start_client(
                    user_id=user_id,
                    tiktok_username=tiktok_username,
                    on_comment_callback=on_comment,
                    on_gift_callback=on_gift,
                    on_like_callback=on_like,
                    on_join_callback=on_join,
                    on_follow_callback=on_follow,
                    on_subscribe_callback=on_subscribe,
                    on_share_callback=on_share,
                    on_viewer_callback=on_viewer,
                )
                logger.info(f"✅ TikTok Live клиент запущен для @{tiktok_username}")
            except SignatureRateLimitError as e:
                # Rate limit от TikTok API
                logger.error(f"❌ Rate limit от TikTok API: {e}")
                logger.info(
                    "💡 Подсказка: Установите SIGN_SERVER_URL в .env для собственного Sign Server или используйте EulerStream API: https://www.eulerstream.com/pricing"
                )
                
                # Отправляем ошибку пользователю
                await websocket.send_text(json.dumps({
                    "type": "error",
                    "message": "❌ Достигнут лимит подключений TikTok API",
                    "details": "Подождите или настройте свой Sign Server (переменная SIGN_SERVER_URL в .env) либо используйте EulerStream API."
                }, ensure_ascii=False))
                
                # Закрываем соединение
                await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
                return
            except PremiumEndpointError as e:
                logger.error(f"❌ Подпись отклонена (PremiumEndpointError): {e}")
                await websocket.send_text(json.dumps({
                    "type": "error",
                    "message": "❌ Доступ к премиум эндпоинту подписи запрещён",
                    "details": "Проверьте права вашего ключа EulerStream или тариф."
                }, ensure_ascii=False))
                await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
                return
            except SignAPIError as e:
                logger.error(f"❌ Ошибка Sign API: {e}")
                await websocket.send_text(json.dumps({
                    "type": "error",
                    "message": "❌ Ошибка Sign API",
                    "details": str(e)
                }, ensure_ascii=False))
                await websocket.close(code=status.WS_1011_INTERNAL_ERROR)
                return
            except Exception as e:
                logger.error(f"❌ Ошибка подключения к TikTok Live: {e}")
                await websocket.send_text(json.dumps({
                    "type": "error",
                    "message": f"❌ Ошибка подключения к TikTok Live",
                    "details": str(e)
                }, ensure_ascii=False))
                await websocket.close(code=status.WS_1011_INTERNAL_ERROR)
                return
        else:
            logger.warning(f"⚠️ TikTok username не указан для user_id={user_id}")
            await websocket.send_text(json.dumps({
                "type": "error",
                "message": "⚠️ Необходимо указать TikTok username",
                "details": "Перейдите в настройки и укажите ваш TikTok username"
            }, ensure_ascii=False))
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return
        
        # Ждём сообщений от клиента (для обнаружения отключения)
        while True:
            try:
                await websocket.receive_text()
            except RuntimeError:
                await asyncio.sleep(0.1)
                
    except WebSocketDisconnect:
        logger.info(f"WebSocket отключен: {user_id}")
    finally:
        # Останавливаем TikTok клиент
        if tiktok_service.is_running(user_id):
            await tiktok_service.stop_client(user_id)
            
        await dispatcher.unregister(websocket)
