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
    JoinEvent,  # Событие когда зритель заходит в стрим
    ShareEvent,  # Событие когда кто-то делится стримом
    RoomUserSeqEvent,  # Счётчик зрителей в реальном времени
)
# Импорт для работы с RAW protobuf событиями
try:
    from TikTokLive.proto import WebcastResponse, WebcastPushFrame
except ImportError:
    WebcastResponse = None
    WebcastPushFrame = None
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
        self._last_activity: Dict[str, datetime] = {}
        self._watchdogs: Dict[str, asyncio.Task] = {}
        self._usernames: Dict[str, str] = {}
        # Хранение метрик зрителей (текущие онлайн и накопительные всего посетившие)
        self._viewer_current: Dict[str, int] = {}
        self._viewer_total: Dict[str, int] = {}

        self._sign_api_key: Optional[str] = os.getenv("SIGN_API_KEY")
        self._sign_api_url: Optional[str] = os.getenv("SIGN_API_URL")

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
        on_share_callback: Optional[Callable] = None,
        on_viewer_callback: Optional[Callable] = None,
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
            on_share_callback: callback когда зритель делится стримом (user)
            on_viewer_callback: callback обновления метрик зрителей (current, total)
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
                    f"🔑 EulerStream SIGN_API_KEY установлен: {self._sign_api_key[:15]}...{self._sign_api_key[-10:]}"
                )
                logger.info(f"🔑 Free tier ключ - подарки могут быть недоступны без Premium подписки")
            else:
                logger.warning("⚠️ SIGN_API_KEY НЕ УСТАНОВЛЕН! Будет анонимное подключение (только комментарии/лайки)")
                
            if self._sign_api_url:
                WebDefaults.tiktok_sign_url = self._sign_api_url
                os.environ.setdefault("SIGN_API_URL", self._sign_api_url)
                logger.info(f"🌐 Sign server URL: {self._sign_api_url}")
            else:
                logger.info(f"🌐 Sign server URL (по умолчанию): {WebDefaults.tiktok_sign_url}")

            # Создаем клиент для конкретного стримера (без несуществующих kwargs)
            logger.info(f"🔧 Создаём TikTok клиент для @{tiktok_username}")
            client: TikTokLiveClient = TikTokLiveClient(unique_id=f"@{tiktok_username}")
            
            # ВКЛЮЧАЕМ DEBUG РЕЖИМ БИБЛИОТЕКИ чтобы видеть ВСЕ raw события
            import logging as stdlib_logging
            stdlib_logging.basicConfig(level=stdlib_logging.DEBUG)
            client.logger.setLevel(stdlib_logging.DEBUG)
            logger.info("🐛 DEBUG режим TikTokLive включён - будут видны все raw события")
            
            # Сохраняем время подключения для фильтрации старых событий
            connection_time = datetime.now()
            self._connection_times[user_id] = connection_time
            self._last_activity[user_id] = connection_time
            self._usernames[user_id] = tiktok_username
            
            # Сохраняем callbacks
            self._callbacks[user_id] = {
                "comment": on_comment_callback,
                "gift": on_gift_callback,
                "like": on_like_callback,
                "join": on_join_callback,
                "share": on_share_callback,
                "viewer": on_viewer_callback,
            }
            
            # Регистрируем обработчики событий
            
            # RAW WebSocket handler - ловим ВСЕ сообщения на низком уровне
            if WebcastPushFrame is not None:
                @client.on("raw")
                async def on_raw_message(frame):
                    """Обработка RAW WebSocket фреймов: декодируем protobuf и ищем Gift-сообщения"""
                    try:
                        # Базовый лог о типе и размере фрейма
                        f_type = getattr(frame, 'payload_type', None)
                        f_payload = getattr(frame, 'payload', None)
                        if f_type is not None:
                            logger.debug(f"🔍 RAW Frame: type={f_type}, size={len(f_payload) if f_payload else 0} bytes")
                        # Отмечаем активность
                        self._last_activity[user_id] = datetime.now()

                        # Унифицированно получаем байты WebcastPushFrame
                        push_bytes = None
                        if hasattr(frame, 'SerializeToString'):
                            # Это уже protobuf-объект
                            push_bytes = frame.SerializeToString()
                        elif isinstance(frame, (bytes, bytearray)):
                            push_bytes = bytes(frame)

                        if not push_bytes:
                            return

                        # Парсим WebcastPushFrame
                        push = WebcastPushFrame()
                        push.ParseFromString(push_bytes)

                        # Получаем полезную нагрузку и пытаемся распаковать (некоторые кадры сжаты)
                        payload = push.payload if hasattr(push, 'payload') else b""
                        if not payload:
                            return

                        decompressed = payload
                        try:
                            import zlib
                            decompressed = zlib.decompress(payload)
                        except Exception:
                            # Не сжатый payload — используем как есть
                            decompressed = payload

                        # Парсим WebcastResponse и считаем типы сообщений
                        resp = WebcastResponse()
                        resp.ParseFromString(decompressed)

                        type_counts = {}
                        gift_messages = 0
                        for msg in getattr(resp, 'messages', []):
                            mtype = getattr(msg, 'type', '')
                            type_counts[mtype] = type_counts.get(mtype, 0) + 1
                            if mtype.endswith('GiftMessage') or mtype == 'WebcastGiftMessage' or 'Gift' in mtype:
                                gift_messages += 1

                        if type_counts:
                            logger.debug(f"📦 RAW Frame decoded: types={type_counts}")
                        if gift_messages:
                            logger.info(f"🎁 Обнаружены Gift-сообщения в RAW кадре: count={gift_messages}")
                    except Exception as e:
                        logger.debug(f"🔍 RAW Frame decode error: {e}")
            
            @client.on(ConnectEvent)
            async def on_connect(event: ConnectEvent):
                logger.info(f"TikTok Live подключен: {tiktok_username}")
                self._last_activity[user_id] = datetime.now()
            
            @client.on(CommentEvent)
            async def on_comment(event: CommentEvent):
                """Обработка комментариев - только новые события после подключения"""
                if on_comment_callback:
                    # Фильтрация: пропускаем события, которые были до подключения
                    # TikTokLive может отправить несколько старых событий при подключении
                    username = event.user.nickname or event.user.unique_id
                    text = event.comment
                    logger.info(f"TikTok комментарий от {username}: {text}")
                    self._last_activity[user_id] = datetime.now()
                    try:
                        await on_comment_callback(username, text)
                    except Exception as e:
                        logger.error(f"Ошибка в comment callback: {e}")
            
            @client.on(GiftEvent)
            async def on_gift(event: GiftEvent):
                """Обработка подарков"""
                logger.info(f"🎁 GiftEvent получен: raw={event.gift}")
                if not on_gift_callback:
                    logger.warning("on_gift_callback не установлен")
                    return
                # В live_tester мы НЕ задерживаем стриковые подарки, сразу отдаём каждое обновление.
                # Повторяем ту же логику здесь: убираем фильтр streaking.
                gift_obj = event.gift
                username = event.user.nickname or event.user.unique_id
                # Надёжное извлечение ID и имени
                gift_id = getattr(gift_obj, 'id', None) or getattr(gift_obj, 'name', 'unknown_gift')
                gift_name = getattr(gift_obj, 'name', str(gift_id))
                # Безопасное извлечение количества: сначала gift.count, затем repeat_count, затем 1
                count = getattr(gift_obj, 'count', None) or getattr(event, 'repeat_count', None) or 1
                diamond_unit = getattr(gift_obj, 'diamond_count', 0) or getattr(gift_obj, 'diamond', 0)
                diamonds = diamond_unit * count
                logger.info(
                    f"TikTok подарок от {username}: {gift_name} (ID: {gift_id}) x{count} (единица {diamond_unit}, всего {diamonds} алмазов)"
                )
                self._last_activity[user_id] = datetime.now()
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
                    self._last_activity[user_id] = datetime.now()
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
                    self._last_activity[user_id] = datetime.now()
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
            
            # Share Event
            @client.on(ShareEvent)
            async def on_share(event: ShareEvent):
                """Обработка события когда кто-то делится стримом"""
                username = getattr(event.user, 'nickname', None) or getattr(event.user, 'unique_id', 'Unknown')
                logger.info(f"📤 TikTok Share: {username} поделился стримом")
                self._last_activity[user_id] = datetime.now()
                if on_share_callback:
                    try:
                        await on_share_callback(username)
                    except Exception as e:
                        logger.error(f"Ошибка в share callback: {e}")
            
            # RoomUserSeqEvent - Счётчик зрителей
            @client.on(RoomUserSeqEvent)
            async def on_room_user_seq(event: RoomUserSeqEvent):
                """Обработка счётчика зрителей"""
                # В live_tester мы разделяем текущих онлайн и накопительный total.
                current = getattr(event, 'viewer_count', None)
                total = getattr(event, 'total', None)
                # Fallback когда библиотека не даёт полей (аноним сессия): current может быть 0,
                # тогда пробуем другие варианты.
                if current in (None, 0):
                    # Иногда viewer_count отсутствует, но есть top_viewer_count или member_count и т.п.
                    # Здесь минималистично используем total если он > 0.
                    if total and total > 0:
                        current = min(total, current or total)
                if current is None:
                    current = 0
                if total is None or total < current:
                    total = current
                self._viewer_current[user_id] = current
                self._viewer_total[user_id] = total
                logger.info(f"👥 Зрителей: current={current}, total={total}")
                self._last_activity[user_id] = datetime.now()
                if on_viewer_callback:
                    try:
                        await on_viewer_callback(current, total)
                    except Exception as e:
                        logger.error(f"Ошибка в viewer callback: {e}")
            
            @client.on(DisconnectEvent)
            async def on_disconnect(event: DisconnectEvent):
                logger.warning(f"TikTok Live отключен: {tiktok_username}")
                # Не обновляем last_activity здесь, чтобы watchdog мог перезапускать
            
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

            # Запускаем watchdog: если нет активности N секунд — мягкий рестарт клиента
            inactivity_limit = int(os.getenv("TT_WATCHDOG_INACTIVITY_SEC", "75"))
            check_period = int(os.getenv("TT_WATCHDOG_CHECK_SEC", "15"))

            async def watchdog_loop(uid: str):
                try:
                    while uid in self._clients:
                        await asyncio.sleep(check_period)
                        last = self._last_activity.get(uid)
                        if not last:
                            continue
                        delta = (datetime.now() - last).total_seconds()
                        if delta > inactivity_limit:
                            logger.warning(
                                f"🛟 Watchdog: нет активности {delta:.0f}s (> {inactivity_limit}s). Перезапуск клиента @{self._usernames.get(uid, '?')}"
                            )
                            # Сохраняем параметры для рестарта
                            name = self._usernames.get(uid, tiktok_username)
                            cbs = self._callbacks.get(uid, {})
                            # Останавливаем и перезапускаем
                            try:
                                await self.stop_client(uid)
                            except Exception as e:
                                logger.error(f"Ошибка при остановке клиента watchdog'ом: {e}")
                            await asyncio.sleep(2)
                            try:
                                await self.start_client(
                                    uid,
                                    name,
                                    on_comment_callback=cbs.get("comment"),
                                    on_gift_callback=cbs.get("gift"),
                                    on_like_callback=cbs.get("like"),
                                    on_join_callback=cbs.get("join"),
                                    on_follow_callback=on_follow_callback,
                                    on_subscribe_callback=on_subscribe_callback,
                                )
                            except Exception as e:
                                logger.error(f"Ошибка при рестарте клиента watchdog'ом: {e}")
                except asyncio.CancelledError:
                    pass

            # Отменяем предыдущий watchdog (если был) и запускаем новый
            if user_id in self._watchdogs:
                task = self._watchdogs.pop(user_id)
                task.cancel()
            self._watchdogs[user_id] = asyncio.create_task(watchdog_loop(user_id))
            
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
            if user_id in self._last_activity:
                del self._last_activity[user_id]
            if user_id in self._usernames:
                del self._usernames[user_id]
            if user_id in self._watchdogs:
                task = self._watchdogs.pop(user_id)
                task.cancel()
            logger.info(f"TikTok клиент остановлен для {user_id}")
        except Exception as e:
            logger.error(f"Ошибка остановки TikTok клиента: {e}")
    
    def is_running(self, user_id: str) -> bool:
        """Проверяет, запущен ли клиент"""
        return user_id in self._clients


# Глобальный экземпляр сервиса
tiktok_service = TikTokService()
