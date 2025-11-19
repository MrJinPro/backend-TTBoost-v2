"""
Сервис для подключения к TikTok Live стримам
Использует библиотеку TikTokLive для получения событий в реальном времени
"""
from TikTokLive import TikTokLiveClient
from TikTokLive.events import (
    CommentEvent, 
    GiftEvent, 
    LikeEvent, 
    ConnectEvent, 
    DisconnectEvent,
    JoinEvent  # Событие когда зритель заходит в стрим
)
try:
    from TikTokLive.events import FollowEvent  # type: ignore
except Exception:  # pragma: no cover
    FollowEvent = None
try:
    from TikTokLive.events import SubscribeEvent  # type: ignore
except Exception:  # pragma: no cover
    SubscribeEvent = None
import logging
import os
from TikTokLive.client.web.web_settings import WebDefaults
import asyncio
from typing import Dict, Callable, Optional
from datetime import datetime
from TikTokLive.client.errors import SignAPIError, SignatureRateLimitError

logger = logging.getLogger(__name__)


class TikTokService:
    """Сервис для управления подключениями к TikTok Live"""
    
    def __init__(self):
        self._clients: Dict[str, TikTokLiveClient] = {}
        self._callbacks: Dict[str, dict] = {}
        self._connection_times: Dict[str, datetime] = {}  # Время подключения для фильтрации старых событий
        # Настройки подписи (EulerStream / кастомный sign server)
        # Поддерживаются переменные окружения:
        #  - SIGN_API_KEY: API ключ EulerStream
        #  - SIGN_API_URL: Базовый URL sign-сервера (по умолчанию https://tiktok.eulerstream.com)
        #  - SIGN_SERVER_URL (устаревш.): URL самописного /sign — используйте SIGN_API_URL вместо
        self._sign_api_key: Optional[str] = os.getenv("SIGN_API_KEY")
        self._sign_api_url: Optional[str] = os.getenv("SIGN_API_URL")
        # Для обратной совместимости: если задан SIGN_SERVER_URL, используем его как SIGN_API_URL
        if not self._sign_api_url:
            legacy = os.getenv("SIGN_SERVER_URL")
            if legacy:
                self._sign_api_url = legacy
    
    async def start_client(
        self, 
        user_id: str, 
        tiktok_username: str,
        on_comment_callback: Optional[Callable] = None,
        on_gift_callback: Optional[Callable] = None,
        on_like_callback: Optional[Callable] = None,
        on_join_callback: Optional[Callable] = None,
        on_follow_callback: Optional[Callable] = None,
        on_subscribe_callback: Optional[Callable] = None,
    ):
        """
        Запускает клиент TikTok Live для указанного пользователя
        
        Args:
            user_id: ID пользователя в системе
            tiktok_username: TikTok username стримера (без @)
            on_comment_callback: callback для комментариев (user, text)
            on_gift_callback: callback для подарков (user, gift_name, count, diamonds)
            on_like_callback: callback для лайков (user, count)
            on_join_callback: callback для входа зрителей (user)
        """
        if user_id in self._clients:
            logger.warning(f"TikTok клиент уже запущен для {user_id}")
            return
        
        try:
            # Применяем настройки подписи к глобальным WebDefaults перед созданием клиента
            if self._sign_api_key:
                WebDefaults.tiktok_sign_api_key = self._sign_api_key
                os.environ.setdefault("SIGN_API_KEY", self._sign_api_key)
                logger.info(
                    f"EulerStream SIGN_API_KEY установлен (***{self._sign_api_key[-6:]}), будет использоваться для подписи"
                )
            if self._sign_api_url:
                WebDefaults.tiktok_sign_url = self._sign_api_url
                os.environ.setdefault("SIGN_API_URL", self._sign_api_url)
                logger.info(f"Sign server base URL: {self._sign_api_url}")

            # Создаем клиент для конкретного стримера (без несуществующих kwargs)
            client: TikTokLiveClient = TikTokLiveClient(unique_id=f"@{tiktok_username}")
            
            # Сохраняем время подключения для фильтрации старых событий
            connection_time = datetime.now()
            self._connection_times[user_id] = connection_time
            
            # Сохраняем callbacks
            self._callbacks[user_id] = {
                "comment": on_comment_callback,
                "gift": on_gift_callback,
                "like": on_like_callback,
                "join": on_join_callback,
            }
            
            # Регистрируем обработчики событий
            @client.on(ConnectEvent)
            async def on_connect(event: ConnectEvent):
                logger.info(f"TikTok Live подключен: {tiktok_username}")
            
            @client.on(CommentEvent)
            async def on_comment(event: CommentEvent):
                """Обработка комментариев - только новые события после подключения"""
                if on_comment_callback:
                    # Фильтрация: пропускаем события, которые были до подключения
                    # TikTokLive может отправить несколько старых событий при подключении
                    username = event.user.nickname or event.user.unique_id
                    text = event.comment
                    logger.info(f"TikTok комментарий от {username}: {text}")
                    try:
                        await on_comment_callback(username, text)
                    except Exception as e:
                        logger.error(f"Ошибка в comment callback: {e}")
            
            @client.on(GiftEvent)
            async def on_gift(event: GiftEvent):
                """Обработка подарков"""
                if not on_gift_callback:
                    return
                # Логика: если подарок стриковый — шлём событие только по завершению стрика,
                # если не стриковый — шлём сразу.
                streakable = getattr(event.gift, 'streakable', False)
                streaking = getattr(event.gift, 'streaking', False)
                if streakable and streaking:
                    return  # ждём окончания стрика
                username = event.user.nickname or event.user.unique_id
                gift_id = getattr(event.gift, 'id', None) or event.gift.name  # Пытаемся получить ID, fallback на name
                gift_name = event.gift.name
                count = event.gift.count
                diamonds = event.gift.diamond_count * count
                logger.info(f"TikTok подарок от {username}: {gift_name} (ID: {gift_id}) x{count} ({diamonds} алмазов)")
                try:
                    await on_gift_callback(username, gift_id, gift_name, count, diamonds)
                except Exception as e:
                    logger.error(f"Ошибка в gift callback: {e}")
            
            @client.on(LikeEvent)
            async def on_like(event: LikeEvent):
                """Обработка лайков"""
                if on_like_callback:
                    username = event.user.nickname or event.user.unique_id
                    count = event.count
                    logger.info(f"TikTok лайки от {username}: {count}")
                    try:
                        await on_like_callback(username, count)
                    except Exception as e:
                        logger.error(f"Ошибка в like callback: {e}")
            
            @client.on(JoinEvent)
            async def on_join(event: JoinEvent):
                """Обработка входа зрителя в стрим"""
                if on_join_callback:
                    username = event.user.nickname or event.user.unique_id
                    logger.info(f"TikTok зритель присоединился: {username}")
                    try:
                        await on_join_callback(username)
                    except Exception as e:
                        logger.error(f"Ошибка в join callback: {e}")

            if FollowEvent is not None and on_follow_callback is not None:
                @client.on(FollowEvent)
                async def on_follow(event):  # type: ignore
                    username = getattr(event.user, 'nickname', None) or getattr(event.user, 'unique_id', '')
                    logger.info(f"TikTok подписка: {username}")
                    try:
                        await on_follow_callback(username)
                    except Exception as e:
                        logger.error(f"Ошибка в follow callback: {e}")

            if SubscribeEvent is not None and on_subscribe_callback is not None:
                @client.on(SubscribeEvent)
                async def on_subscribe(event):  # type: ignore
                    username = getattr(event.user, 'nickname', None) or getattr(event.user, 'unique_id', '')
                    logger.info(f"TikTok супер-подписка: {username}")
                    try:
                        await on_subscribe_callback(username)
                    except Exception as e:
                        logger.error(f"Ошибка в subscribe callback: {e}")
            
            @client.on(DisconnectEvent)
            async def on_disconnect(event: DisconnectEvent):
                logger.warning(f"TikTok Live отключен: {tiktok_username}")
            
            # Сохраняем клиент и запускаем с ретраями при временных ошибках подписи/лимитов
            self._clients[user_id] = client

            attempts = int(os.getenv("SIGN_RETRY_ATTEMPTS", "3"))
            backoff_base = float(os.getenv("SIGN_RETRY_BACKOFF", "2.0"))  # секунды
            last_err: Optional[Exception] = None

            for attempt in range(1, attempts + 1):
                try:
                    logger.info(f"Запуск TikTok клиента (попытка {attempt}/{attempts}) для @{tiktok_username}")
                    await client.start()
                    last_err = None
                    break
                except (SignAPIError, SignatureRateLimitError) as e:
                    last_err = e
                    if attempt >= attempts:
                        break
                    delay = backoff_base ** attempt
                    logger.warning(f"Не удалось запустить (попытка {attempt}/{attempts}): {e}. Повтор через {delay:.1f}с")
                    await asyncio.sleep(delay)

            if last_err is not None:
                raise last_err
            
            logger.info(f"TikTok клиент запущен для {user_id} (@{tiktok_username})")
            
        except Exception as e:
            logger.error(f"Ошибка запуска TikTok клиента для {user_id}: {e}")
            if user_id in self._clients:
                del self._clients[user_id]
            if user_id in self._callbacks:
                del self._callbacks[user_id]
            raise
    
    async def stop_client(self, user_id: str):
        """Останавливает клиент TikTok Live"""
        if user_id not in self._clients:
            logger.warning(f"TikTok клиент не найден для {user_id}")
            return
        
        try:
            client = self._clients[user_id]
            await client.disconnect()
            del self._clients[user_id]
            if user_id in self._callbacks:
                del self._callbacks[user_id]
            if user_id in self._connection_times:
                del self._connection_times[user_id]
            logger.info(f"TikTok клиент остановлен для {user_id}")
        except Exception as e:
            logger.error(f"Ошибка остановки TikTok клиента: {e}")
    
    def is_running(self, user_id: str) -> bool:
        """Проверяет, запущен ли клиент"""
        return user_id in self._clients


# Глобальный экземпляр сервиса
tiktok_service = TikTokService()
