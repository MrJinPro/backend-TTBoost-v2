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


def _first_non_empty_str(*values):
    for v in values:
        if isinstance(v, str):
            s = v.strip()
            if s:
                return s
    return None


def _extract_user_identifiers(user) -> tuple[str | None, str | None]:
    """Возвращает (login, nickname) из объекта пользователя TikTokLive.

    В разных событиях/версиях TikTokLive поля могут называться по-разному.
    Для триггеров важнее login (unique id), но для UI полезен nickname.
    """
    if user is None:
        return None, None

    # dict-like
    if isinstance(user, dict):
        login = _first_non_empty_str(
            user.get("unique_id"),
            user.get("uniqueId"),
            user.get("uniqueID"),
            user.get("username"),
        )
        nickname = _first_non_empty_str(
            user.get("nickname"),
            user.get("display_name"),
            user.get("displayName"),
            user.get("name"),
        )
        return login, nickname

    # object-like
    login = _first_non_empty_str(
        getattr(user, "unique_id", None),
        getattr(user, "uniqueId", None),
        getattr(user, "uniqueID", None),
        getattr(user, "username", None),
    )
    nickname = _first_non_empty_str(
        getattr(user, "nickname", None),
        getattr(user, "display_name", None),
        getattr(user, "displayName", None),
        getattr(user, "name", None),
    )

    # some versions keep raw dict on the user
    raw = getattr(user, "raw", None) or getattr(user, "data", None) or getattr(user, "_data", None)
    if isinstance(raw, dict):
        login = login or _first_non_empty_str(
            raw.get("unique_id"),
            raw.get("uniqueId"),
            raw.get("uniqueID"),
            raw.get("username"),
        )
        nickname = nickname or _first_non_empty_str(
            raw.get("nickname"),
            raw.get("display_name"),
            raw.get("displayName"),
            raw.get("name"),
        )

    return login, nickname
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
import inspect
from typing import Dict, Callable, Optional
from datetime import datetime
from TikTokLive.client.errors import SignAPIError, SignatureRateLimitError

try:
    from TikTokLive.client.errors import WebcastBlocked200Error  # type: ignore
except Exception:  # pragma: no cover
    WebcastBlocked200Error = None  # type: ignore

logger = logging.getLogger(__name__)


class TikTokService:
    """Сервис для управления подключениями к TikTok Live"""
    def __init__(self):
        # Словари состояния клиентов и колбэков
        self._clients = {}
        self._callbacks = {}
        self._connection_times = {}
        self._last_activity = {}
        self._watchdogs = {}
        self._usernames = {}
        self._client_tasks = {}
        self._connect_events = {}
        self._fail_events = {}
        self._last_start_error = {}
        self._last_start_exc = {}
        self._reconnect_tasks = {}
        self._stopping = {}
        # Метрики зрителей
        self._viewer_current = {}
        self._viewer_total = {}
        # Анти-дублирование подарков: (username+gift_id) -> (last_count, last_timestamp)
        self._recent_gifts = {}
        # Время последнего успешно полученного GiftEvent на клиента
        self._last_gift_event = {}
        # Сигнатура последнего отправленного подарка (для дополнительного анти-дублирования)
        self._last_gift_signature = {}  # type: Dict[str, tuple[str, datetime]]  # user_id -> (signature, ts)

        self._sign_api_key = os.getenv("SIGN_API_KEY")
        self._sign_api_url = os.getenv("SIGN_API_URL")

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
        on_connect_callback: Optional[Callable] = None,
        on_disconnect_callback: Optional[Callable] = None,
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
        print(f"🚀 start_client вызван для user_id={user_id}, tiktok_username={tiktok_username}")
        if user_id in self._clients:
            print(f"🔄 TikTok клиент уже запущен для {user_id}, перезапускаем с новыми колбеками")
            await self.stop_client(user_id)

        # Сброс флага остановки
        self._stopping[user_id] = False
        
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

            # ===== Дополнительная авторизация через куки (для получения Gift / расширенного потока) =====
            # Ожидаемый формат: TIKTOK_COOKIES="sessionid=xxxx; ttwid=yyyy; passport_csrf_token=zzz"
            cookies_env = os.getenv("TIKTOK_COOKIES")

            # Часто критично при DEVICE_BLOCKED на VPS
            user_agent_env = (os.getenv("TIKTOK_USER_AGENT") or "").strip()
            proxy_env = (os.getenv("TIKTOK_PROXY") or "").strip()
            if proxy_env:
                # Фолбэк: некоторые клиенты читают прокси из env
                os.environ.setdefault("HTTPS_PROXY", proxy_env)
                os.environ.setdefault("HTTP_PROXY", proxy_env)
                os.environ.setdefault("ALL_PROXY", proxy_env)
                logger.info("🧭 TIKTOK_PROXY задан (выставлены env HTTP(S)_PROXY/ALL_PROXY)")

            if cookies_env:
                try:
                    # В библиотеке нет публичного API для куки, но многие версии читают request_headers
                    # Добавляем/обновляем заголовок Cookie на уровне WebDefaults.
                    base_headers = getattr(WebDefaults, "request_headers", {}) or {}
                    # Не перетираем другие заголовки (например User-Agent)
                    base_headers["Cookie"] = cookies_env.strip()
                    if user_agent_env:
                        base_headers["User-Agent"] = user_agent_env
                    WebDefaults.request_headers = base_headers
                    logger.info("🍪 TikTok cookies добавлены в WebDefaults (Cookie заголовок установлен)")
                except Exception as e:
                    logger.warning(f"Не удалось применить куки из TIKTOK_COOKIES: {e}")
            else:
                logger.info("🍪 TIKTOK_COOKIES не заданы (анонимное подключение может не получать подарки)")

            if user_agent_env:
                try:
                    base_headers = getattr(WebDefaults, "request_headers", {}) or {}
                    base_headers.setdefault("User-Agent", user_agent_env)
                    WebDefaults.request_headers = base_headers
                    logger.info("🧩 TIKTOK_USER_AGENT применён в WebDefaults.request_headers")
                except Exception as e:
                    logger.warning(f"Не удалось применить TIKTOK_USER_AGENT: {e}")

            # Создаем клиент для конкретного стримера (без несуществующих kwargs)
            logger.info(f"🔧 Создаём TikTok клиент для @{tiktok_username}")
            # ВАЖНО: Проверяем, не содержит ли username уже символ @
            clean_username = tiktok_username.lstrip('@')  # Удаляем @ если есть
            if clean_username != tiktok_username:
                logger.warning(f"⚠️ Username содержал @, очищено: '{tiktok_username}' -> '{clean_username}'")

            # Подбираем kwargs динамически (разные версии TikTokLive имеют разный __init__)
            client_kwargs: dict = {}
            try:
                init_params = set(inspect.signature(TikTokLiveClient.__init__).parameters.keys())
            except Exception:
                init_params = set()

            effective_headers: dict = {}
            try:
                effective_headers = dict(getattr(WebDefaults, "request_headers", {}) or {})
            except Exception:
                effective_headers = {}
            if cookies_env:
                effective_headers["Cookie"] = cookies_env.strip()
            if user_agent_env:
                effective_headers["User-Agent"] = user_agent_env

            if effective_headers:
                if "request_headers" in init_params:
                    client_kwargs["request_headers"] = effective_headers
                elif "headers" in init_params:
                    client_kwargs["headers"] = effective_headers

            if proxy_env:
                for key in ("proxy", "http_proxy", "https_proxy"):
                    if key in init_params:
                        client_kwargs[key] = proxy_env
                        break

            client: TikTokLiveClient = TikTokLiveClient(unique_id=f"@{clean_username}", **client_kwargs)

            # Опционально включаем DEBUG режим TikTokLive (очень многословно, для прод лучше держать выключенным)
            tt_debug = str(os.getenv("TT_TIKTOKLIVE_DEBUG", "0")).strip().lower() in ("1", "true", "yes", "on")
            if tt_debug:
                try:
                    import logging as stdlib_logging
                    stdlib_logging.getLogger("TikTokLive").setLevel(stdlib_logging.DEBUG)
                    client.logger.setLevel(stdlib_logging.DEBUG)
                    logger.info("🐛 DEBUG режим TikTokLive включён (TT_TIKTOKLIVE_DEBUG=1)")
                except Exception:
                    logger.warning("Не удалось включить DEBUG режим TikTokLive")
            
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
                "follow": on_follow_callback,
                "subscribe": on_subscribe_callback,
                "share": on_share_callback,
                "viewer": on_viewer_callback,
                "connect": on_connect_callback,
                "disconnect": on_disconnect_callback,
            }

            # Для UX/диагностики: ждём реального ConnectEvent или явной ошибки запуска
            connect_event = asyncio.Event()
            self._connect_events[user_id] = connect_event
            
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
                            last_evt = self._last_gift_event.get(user_id)
                            if not last_evt or (datetime.now() - last_evt).total_seconds() > 10:
                                logger.warning("🎁 RAW содержит подарки, но GiftEvent не поступал >10s — возможно ограничение бесплатного ключа/отсутствие нужных cookies")
                    except Exception as e:
                        logger.debug(f"🔍 RAW Frame decode error: {e}")
            
            @client.on(ConnectEvent)
            async def on_connect(event: ConnectEvent):
                logger.info(f"✅ TikTok Live подключен: {tiktok_username}")
                connect_event.set()
                self._last_activity[user_id] = datetime.now()
                if on_connect_callback:
                    try:
                        await on_connect_callback(tiktok_username)
                    except Exception as e:
                        logger.error(f"Ошибка в connect callback: {e}")
            
            @client.on(CommentEvent)
            async def on_comment(event: CommentEvent):
                """Обработка комментариев - только новые события после подключения"""
                # В разных версиях TikTokLive структура user может отличаться.
                login, nickname = _extract_user_identifiers(getattr(event, "user", None))
                username = login or nickname or "anonymous"
                text = getattr(event, "comment", None) or getattr(event, "text", None) or ""
                try:
                    text = str(text)
                except Exception:
                    text = ""

                logger.debug(
                    "📨 CommentEvent: login=%s nickname=%s text_len=%s callback=%s",
                    login,
                    nickname,
                    len(text),
                    bool(on_comment_callback),
                )
                if on_comment_callback:
                    # Фильтрация: пропускаем события, которые были до подключения
                    # TikTokLive может отправить несколько старых событий при подключении
                    logger.info(f"💬 TikTok комментарий от {username}: {text}")
                    self._last_activity[user_id] = datetime.now()
                    try:
                        await on_comment_callback(username, text)
                    except Exception as e:
                        logger.error(f"❌ Ошибка в comment callback: {e}")
            
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
                login, nickname = _extract_user_identifiers(getattr(event, "user", None))
                username = login or nickname or "anonymous"
                # Надёжное извлечение ID и имени
                gift_id = getattr(gift_obj, 'id', None) or getattr(gift_obj, 'name', 'unknown_gift')
                gift_name = getattr(gift_obj, 'name', str(gift_id))
                # Безопасное извлечение количества: сначала gift.count, затем repeat_count, затем 1
                count = getattr(gift_obj, 'count', None) or getattr(event, 'repeat_count', None) or 1
                diamond_unit = getattr(gift_obj, 'diamond_count', 0) or getattr(gift_obj, 'diamond', 0)
                diamonds = diamond_unit * count
                # Анти-дубль логика (можно отключить для диагностики через ENV DISABLE_GIFT_DEDUP=1)
                disable_dedup = os.getenv("DISABLE_GIFT_DEDUP") == "1"
                # Дополнительный тайм-аут по сигнатуре (ENV GIFT_DEDUP_DELTA_SEC, по умолчанию 5)
                dedup_delta_sec = float(os.getenv("GIFT_DEDUP_DELTA_SEC", "5"))
                now = datetime.now()
                gift_map = self._recent_gifts.setdefault(user_id, {})
                signature = f"{username}:{gift_id}"
                prev = gift_map.get(signature)
                streakable = getattr(gift_obj, 'streakable', False)
                streaking = getattr(gift_obj, 'streaking', False)
                # Сигнатура с деталями для более строгого дублирования
                full_signature = f"{username}:{gift_id}:{count}:{diamond_unit}:{diamonds}"
                last_sig = self._last_gift_signature.get(user_id)
                if disable_dedup:
                    logger.debug("🚫 Gift dedup отключён (DISABLE_GIFT_DEDUP=1) – отправляем каждое событие")
                else:
                    # Если последний отправленный подарок идентичен и прошел недостаточный интервал — пропускаем
                    if last_sig and last_sig[0] == full_signature and (now - last_sig[1]).total_seconds() < dedup_delta_sec:
                        logger.debug(f"🔁 Пропуск полного дубликата подарка (full_signature) delta={(now - last_sig[1]).total_seconds():.2f}s < {dedup_delta_sec}s")
                        return
                    # Если стриковый подарок в процессе streaking и число не изменилось — пропускаем
                    if streakable and streaking and prev and prev[0] == count:
                        logger.debug(f"↺ Пропуск стрикового повторяющегося кадра подарка {signature} count={count}")
                        return
                    # Если точный дубль (тот же count) приходит слишком быстро (<3s) — пропускаем
                    if prev and prev[0] == count and (now - prev[1]).total_seconds() < 3:
                        logger.debug(f"⏱️ Пропуск дубликата подарка {signature} count={count} delta={(now - prev[1]).total_seconds():.2f}s")
                        return
                # Обновляем запись
                gift_map[signature] = (count, now)
                self._last_gift_signature[user_id] = (full_signature, now)
                logger.info(
                    f"TikTok подарок от {username}: {gift_name} (ID: {gift_id}) x{count} (единица {diamond_unit}, всего {diamonds} алмазов)"
                )
                self._last_gift_event[user_id] = now
                self._last_activity[user_id] = datetime.now()
                try:
                    await on_gift_callback(username, gift_id, gift_name, count, diamonds)
                except Exception as e:
                    logger.error(f"Ошибка в gift callback: {e}")
            
            @client.on(LikeEvent)
            async def on_like(event: LikeEvent):
                """Обработка лайков"""
                if on_like_callback:
                    login, nickname = _extract_user_identifiers(getattr(event, "user", None))
                    username = login or nickname or "anonymous"
                    count = getattr(event, "count", None) or 0
                    logger.info(f"TikTok лайки от {username}: {count}")
                    self._last_activity[user_id] = datetime.now()
                    try:
                        await on_like_callback(username, count)
                    except Exception as e:
                        logger.error(f"Ошибка в like callback: {e}")
            
            @client.on(JoinEvent)
            async def on_join(event: JoinEvent):
                """Обработка входа зрителя в стрим"""
                login, nickname = _extract_user_identifiers(getattr(event, "user", None))
                username = login or nickname
                print(f"👤 JoinEvent: {username} присоединился к стриму")
                logger.info(f"TikTok зритель присоединился: login={login} nickname={nickname}")
                self._last_activity[user_id] = datetime.now()
                if on_join_callback:
                    try:
                        # Передаём структурированные данные, чтобы ws мог показывать имя
                        # и матчить триггеры даже если login/никнейм отличаются.
                        await on_join_callback({"username": login, "nickname": nickname})
                    except Exception as e:
                        logger.error(f"Ошибка в join callback: {e}")

            if FollowEvent is not None and on_follow_callback is not None:
                @client.on(FollowEvent)
                async def on_follow(event):  # type: ignore
                    username = getattr(event.user, 'unique_id', None) or getattr(event.user, 'nickname', '')
                    logger.info(f"TikTok подписка: {username}")
                    try:
                        await on_follow_callback(username)
                    except Exception as e:
                        logger.error(f"Ошибка в follow callback: {e}")

            if SubscribeEvent is not None and on_subscribe_callback is not None:
                @client.on(SubscribeEvent)
                async def on_subscribe(event):  # type: ignore
                    username = getattr(event.user, 'unique_id', None) or getattr(event.user, 'nickname', '')
                    logger.info(f"TikTok супер-подписка: {username}")
                    try:
                        await on_subscribe_callback(username)
                    except Exception as e:
                        logger.error(f"Ошибка в subscribe callback: {e}")
            
            # Share Event
            @client.on(ShareEvent)
            async def on_share(event: ShareEvent):
                """Обработка события когда кто-то делится стримом"""
                username = getattr(event.user, 'unique_id', None) or getattr(event.user, 'nickname', 'Unknown')
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
                print(f"🔔 RoomUserSeqEvent received")
                
                prev_current = self._viewer_current.get(user_id, 0)
                prev_total = self._viewer_total.get(user_id, 0)
                
                # Собираем все возможные поля для текущих онлайн
                current_candidates = [
                    getattr(event, 'viewer_count', 0),
                    getattr(event, 'user_count', 0),
                    getattr(event, 'online_count', 0),
                    getattr(event, 'onlineUserCount', 0),
                ]
                current = next((v for v in current_candidates if isinstance(v, (int, float)) and v > 0), 0)
                
                # Собираем все возможные поля для total
                total_candidates = [
                    getattr(event, 'total_user_count', 0),
                    getattr(event, 'totalUserCount', 0),
                    getattr(event, 'total_viewer_count', 0),
                    getattr(event, 'total_viewer', 0),
                    getattr(event, 'total', 0),
                ]
                totals = [v for v in total_candidates if isinstance(v, (int, float)) and v >= 0]
                total = max(totals) if totals else prev_total
                
                # Логика: total не может быть меньше current
                if total < current:
                    total = current
                # Накопительный total не уменьшается
                total = max(total, prev_total)
                
                self._viewer_current[user_id] = current
                self._viewer_total[user_id] = total
                
                print(f"📊 Viewers: current={current}, total={total} (prev: {prev_current}/{prev_total})")
                logger.info(f"👥 Зрителей: current={current}, total={total}")
                self._last_activity[user_id] = datetime.now()
                
                # Отправляем callback только если изменились
                if (current != prev_current or total != prev_total) and on_viewer_callback:
                    try:
                        await on_viewer_callback(current, total)
                    except Exception as e:
                        logger.error(f"Ошибка в viewer callback: {e}")
            
            @client.on(DisconnectEvent)
            async def on_disconnect(event: DisconnectEvent):
                logger.warning(f"TikTok Live отключен: {tiktok_username}")
                # Не обновляем last_activity здесь, чтобы watchdog мог перезапускать
                if on_disconnect_callback:
                    try:
                        await on_disconnect_callback(tiktok_username)
                    except Exception as e:
                        logger.error(f"Ошибка в disconnect callback: {e}")

                # Автопереподключение (если включено)
                auto_reconnect = str(os.getenv("TT_AUTO_RECONNECT", "1")).strip().lower() in ("1", "true", "yes", "on")
                if not auto_reconnect:
                    return
                if self._stopping.get(user_id):
                    return
                if user_id not in self._clients:
                    return
                if user_id in self._reconnect_tasks and self._reconnect_tasks[user_id] and not self._reconnect_tasks[user_id].done():
                    return

                base_delay = float(os.getenv("TT_RECONNECT_BASE_DELAY_SEC", "2"))
                max_delay = float(os.getenv("TT_RECONNECT_MAX_DELAY_SEC", "30"))
                max_attempts = int(os.getenv("TT_RECONNECT_ATTEMPTS", "5"))

                async def _reconnect_loop():
                    delay = base_delay
                    for attempt in range(1, max_attempts + 1):
                        if self._stopping.get(user_id):
                            return
                        try:
                            logger.warning(
                                "🔁 Auto-reconnect TikTokLive (attempt %s/%s) for @%s in %.1fs",
                                attempt,
                                max_attempts,
                                self._usernames.get(user_id, tiktok_username),
                                delay,
                            )
                            await asyncio.sleep(delay)

                            # Важно: перезапускаем с сохранёнными колбэками
                            name = self._usernames.get(user_id, tiktok_username)
                            cbs = self._callbacks.get(user_id, {})
                            try:
                                await self.stop_client(user_id)
                            except Exception:
                                pass
                            await asyncio.sleep(0.5)
                            await self.start_client(
                                user_id,
                                name,
                                on_comment_callback=cbs.get("comment"),
                                on_gift_callback=cbs.get("gift"),
                                on_like_callback=cbs.get("like"),
                                on_join_callback=cbs.get("join"),
                                on_follow_callback=cbs.get("follow"),
                                on_subscribe_callback=cbs.get("subscribe"),
                                on_share_callback=cbs.get("share"),
                                on_viewer_callback=cbs.get("viewer"),
                                on_connect_callback=cbs.get("connect"),
                                on_disconnect_callback=cbs.get("disconnect"),
                            )
                            return
                        except Exception as e:
                            # DEVICE_BLOCKED имеет смысл не ретраить (будет бесконечная дерготня)
                            if WebcastBlocked200Error is not None and isinstance(e, WebcastBlocked200Error):
                                logger.error("⛔ DEVICE_BLOCKED на авто-reconnect, прекращаем попытки: %s", e)
                                return
                            if "DEVICE_BLOCKED" in str(e):
                                logger.error("⛔ DEVICE_BLOCKED на авто-reconnect, прекращаем попытки: %s", e)
                                return
                            logger.warning("Auto-reconnect failed: %s", e)
                            delay = min(max_delay, delay * 2)

                self._reconnect_tasks[user_id] = asyncio.create_task(_reconnect_loop())
            
            # Сохраняем клиент и запускаем с ретраями при временных ошибках подписи/лимитов
            self._clients[user_id] = client

            attempts = int(os.getenv("SIGN_RETRY_ATTEMPTS", "3"))
            backoff_base = float(os.getenv("SIGN_RETRY_BACKOFF", "2.0"))  # секунды
            last_err: Optional[Exception] = None

            for attempt in range(1, attempts + 1):
                try:
                    logger.info(f"Запуск TikTok клиента (попытка {attempt}/{attempts}) для @{clean_username}")
                    fail_event = asyncio.Event()
                    self._fail_events[user_id] = fail_event
                    self._last_start_error.pop(user_id, None)
                    self._last_start_exc.pop(user_id, None)

                    start_task = asyncio.create_task(client.start())
                    self._client_tasks[user_id] = start_task

                    def _done_cb(t: asyncio.Task):
                        try:
                            exc = t.exception()
                        except Exception as cb_e:  # pragma: no cover
                            self._last_start_error[user_id] = f"{type(cb_e).__name__}: {cb_e}"
                            self._last_start_exc[user_id] = cb_e
                            fail_event.set()
                            return
                        if exc is not None:
                            self._last_start_error[user_id] = f"{type(exc).__name__}: {exc}"
                            self._last_start_exc[user_id] = exc
                            fail_event.set()

                    start_task.add_done_callback(_done_cb)

                    connect_timeout = float(os.getenv("TT_CONNECT_TIMEOUT_SEC", "25"))
                    done, pending = await asyncio.wait(
                        [asyncio.create_task(connect_event.wait()), asyncio.create_task(fail_event.wait())],
                        timeout=connect_timeout,
                        return_when=asyncio.FIRST_COMPLETED,
                    )
                    for p in pending:
                        p.cancel()

                    if not done:
                        raise TimeoutError(
                            f"Не удалось подключиться к TikTok Live за {connect_timeout:.0f}с. "
                            f"Частая причина на VPS: DEVICE_BLOCKED (нужен residential proxy / cookies)."
                        )

                    if fail_event.is_set():
                        exc = self._last_start_exc.get(user_id)
                        if exc is None:
                            raise RuntimeError(self._last_start_error.get(user_id, "Ошибка запуска TikTokLive"))
                        raise exc

                    # connected
                    last_err = None
                    break
                except (SignAPIError, SignatureRateLimitError) as e:
                    last_err = e
                    if attempt >= attempts:
                        break
                    delay = backoff_base ** attempt
                    logger.warning(f"Не удалось запустить (попытка {attempt}/{attempts}): {e}. Повтор через {delay:.1f}с")
                    await asyncio.sleep(delay)
                except TimeoutError as e:
                    last_err = e
                    break
                except Exception as e:
                    last_err = e
                    break  # Не ретраим при критических ошибках

            if last_err is not None:
                # Убираем за собой на ошибке, чтобы не оставлять "мертвые" клиенты
                try:
                    await self.stop_client(user_id)
                except Exception:
                    pass
                raise last_err
            
            logger.info(f"TikTok клиент запущен для {user_id} (@{tiktok_username})")

            # Запускаем watchdog: если нет активности N секунд — мягкий рестарт клиента
            inactivity_limit = int(os.getenv("TT_WATCHDOG_INACTIVITY_SEC", "75"))
            check_period = int(os.getenv("TT_WATCHDOG_CHECK_SEC", "15"))

            # Можно отключить watchdog полностью (полезно, если эфир "тихий" и рестарты мешают)
            if inactivity_limit <= 0:
                if user_id in self._watchdogs:
                    task = self._watchdogs.pop(user_id)
                    task.cancel()
                logger.info("🛟 Watchdog отключён (TT_WATCHDOG_INACTIVITY_SEC=%s)", inactivity_limit)
                return

            async def watchdog_loop(uid: str):
                try:
                    while uid in self._clients:
                        await asyncio.sleep(check_period)
                        client_obj = self._clients.get(uid)
                        if client_obj is None:
                            continue

                        is_connected = False
                        try:
                            is_connected = bool(getattr(client_obj, "connected", False))
                        except Exception:
                            is_connected = False

                        # В quiet/live-low-activity эфирах отсутствие новых comment/gift/like событий
                        # само по себе не означает потерю соединения. Перезапускаем только если сам
                        # клиент больше не считает себя connected.
                        if is_connected:
                            continue

                        last = self._last_activity.get(uid)
                        if not last:
                            continue
                        delta = (datetime.now() - last).total_seconds()
                        if delta > inactivity_limit:
                            logger.warning(
                                f"🛟 Watchdog: клиент disconnected и нет активности {delta:.0f}s (> {inactivity_limit}s). Перезапуск клиента @{self._usernames.get(uid, '?')}"
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
                                    on_follow_callback=cbs.get("follow"),
                                    on_subscribe_callback=cbs.get("subscribe"),
                                    on_share_callback=cbs.get("share"),
                                    on_viewer_callback=cbs.get("viewer"),
                                    on_connect_callback=cbs.get("connect"),
                                    on_disconnect_callback=cbs.get("disconnect"),
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
            self._stopping[user_id] = True

            # Отменяем pending reconnect
            rt = self._reconnect_tasks.pop(user_id, None)
            if rt is not None and not rt.done():
                rt.cancel()

            client = self._clients[user_id]
            await client.disconnect()

            task = self._client_tasks.pop(user_id, None)
            if task is not None and not task.done():
                task.cancel()
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
            if user_id in self._connect_events:
                del self._connect_events[user_id]
            if user_id in self._fail_events:
                del self._fail_events[user_id]
            if user_id in self._last_start_error:
                del self._last_start_error[user_id]
            if user_id in self._last_start_exc:
                del self._last_start_exc[user_id]
            if user_id in self._stopping:
                del self._stopping[user_id]
            logger.info(f"TikTok клиент остановлен для {user_id}")
        except Exception as e:
            logger.error(f"Ошибка остановки TikTok клиента: {e}")
    
    def is_running(self, user_id: str) -> bool:
        """Проверяет, запущен ли клиент"""
        client = self._clients.get(user_id)
        if client is None:
            return False
        try:
            return bool(getattr(client, "connected", False))
        except Exception:
            return False


# Глобальный экземпляр сервиса
tiktok_service = TikTokService()
