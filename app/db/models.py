import enum
import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, Boolean, Integer, Enum, ForeignKey, UniqueConstraint, JSON, Date
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from .database import Base


def _uuid():
    return str(uuid.uuid4())


class User(Base):
    __tablename__ = "users"
    id = Column(String, primary_key=True, default=_uuid)
    username = Column(String(64), unique=True, index=True, nullable=False)  # Логин для входа
    tiktok_username = Column(String(64), nullable=True)  # TikTok аккаунт для Live
    email = Column(String(256), nullable=True)
    avatar_filename = Column(String(255), nullable=True)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(32), default="user", nullable=False)
    is_banned = Column(Boolean, default=False, nullable=False)
    banned_at = Column(DateTime, nullable=True)
    banned_reason = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    settings = relationship("UserSettings", back_populates="user", uselist=False, cascade="all, delete-orphan")
    tiktok_accounts = relationship("UserTikTokAccount", back_populates="user", cascade="all, delete-orphan")


class UserTikTokAccount(Base):
    __tablename__ = "user_tiktok_accounts"
    id = Column(String, primary_key=True, default=_uuid)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    username = Column(String(64), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    last_used_at = Column(DateTime, nullable=True)

    user = relationship("User", back_populates="tiktok_accounts")

    __table_args__ = (UniqueConstraint('user_id', 'username', name='uq_user_tiktok_username'),)


class UserSettings(Base):
    __tablename__ = "user_settings"
    id = Column(String, primary_key=True, default=_uuid)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    voice_id = Column(String(100), default="ru-RU-SvetlanaNeural")
    tts_enabled = Column(Boolean, default=True)
    gift_sounds_enabled = Column(Boolean, default=True)
    auto_connect_live = Column(Boolean, default=False)
    tts_volume = Column(Integer, default=100)
    gifts_volume = Column(Integer, default=100)

    # Chat TTS filtering
    # mode: all | prefix | donor
    chat_tts_mode = Column(String(16), default="all")
    chat_tts_prefixes = Column(String(32), default=".")
    chat_tts_min_diamonds = Column(Integer, default=0)

    # Premium feature: auto-engagement when chat is silent
    silence_enabled = Column(Boolean, default=False)
    silence_minutes = Column(Integer, default=5)

    user = relationship("User", back_populates="settings")


class SoundType(str, enum.Enum):
    uploaded = "uploaded"  # пользователь загрузил файл
    tts = "tts"            # файл сгенерирован TTS


class SoundFile(Base):
    __tablename__ = "sound_files"
    id = Column(String, primary_key=True, default=_uuid)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    filename = Column(String(255), nullable=False)  # имя файла в каталоге пользователя
    url = Column(String(512), nullable=False)       # абсолютный URL на media.*
    bytes = Column(Integer, nullable=False)
    duration_ms = Column(Integer, nullable=True)
    kind = Column(Enum(SoundType), default=SoundType.uploaded, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (UniqueConstraint('user_id', 'filename', name='uq_user_filename'),)


class TriggerAction(str, enum.Enum):
    play_sound = "play_sound"
    tts = "tts"


class Trigger(Base):
    __tablename__ = "triggers"
    id = Column(String, primary_key=True, default=_uuid)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    event_type = Column(String(40), nullable=False)  # chat|gift|viewer_join|viewer_first_message|follow|subscribe
    condition_key = Column(String(40), nullable=True)
    condition_value = Column(String(200), nullable=True)
    enabled = Column(Boolean, default=True)
    priority = Column(Integer, default=0)
    action = Column(Enum(TriggerAction), nullable=False)
    action_params = Column(JSON, nullable=True)  # {text_template?, sound_file_id?}
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    executed_count = Column(Integer, default=0, nullable=False)
    # Новые поля для продвинутых триггеров
    trigger_name = Column(String(100), nullable=True)  # пользовательское название триггера
    combo_count = Column(Integer, default=0, nullable=False)  # порог combo для подарков (0 = любое количество)


class Event(Base):
    __tablename__ = "events"
    id = Column(String, primary_key=True, default=_uuid)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    type = Column(String(40), nullable=False)
    payload = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class StreamSession(Base):
    __tablename__ = "stream_sessions"
    id = Column(String, primary_key=True, default=_uuid)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    tiktok_username = Column(String(64), nullable=False)
    started_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    ended_at = Column(DateTime, nullable=True)
    status = Column(String(32), default="running")


class LicenseStatus(str, enum.Enum):
    active = "active"
    inactive = "inactive"
    revoked = "revoked"


class LicenseKey(Base):
    __tablename__ = "license_keys"
    id = Column(String, primary_key=True, default=_uuid)
    key = Column(String(100), unique=True, index=True, nullable=False)
    plan = Column(String(64), nullable=True)  # тариф/план
    status = Column(Enum(LicenseStatus), default=LicenseStatus.active, nullable=False)
    issued_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    expires_at = Column(DateTime, nullable=True)
    user_id = Column(String, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)  # может быть привязана к пользователю
    max_devices = Column(Integer, default=1)
    devices_bound = Column(Integer, default=0)


class WebPurchase(Base):
    """Запись об оплате/заказе из веб-приложения для выдачи лицензии.

    Нужна для идемпотентности: один order_id -> один license_key.
    Валидацию оплаты делает внешний сервис/веб-бэкенд; здесь только выдача ключа.
    """

    __tablename__ = "web_purchases"
    id = Column(String, primary_key=True, default=_uuid)
    order_id = Column(String(128), unique=True, index=True, nullable=False)
    email = Column(String(256), nullable=True)
    plan = Column(String(64), nullable=True)
    ttl_days = Column(Integer, nullable=True)
    amount = Column(Integer, nullable=True)  # обычно в минимальных единицах (копейки/центы)
    currency = Column(String(8), nullable=True)
    license_key = Column(String(100), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class StorePlatform(str, enum.Enum):
    android = "android"
    ios = "ios"


class StorePurchaseStatus(str, enum.Enum):
    active = "active"
    expired = "expired"
    canceled = "canceled"
    unknown = "unknown"


class StorePurchase(Base):
    """Покупка/подписка из Google Play / App Store.

    Храним сырой ответ верификации и нормализованный expires_at.
    """

    __tablename__ = "store_purchases"

    id = Column(String, primary_key=True, default=_uuid)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    platform = Column(Enum(StorePlatform), nullable=False)
    product_id = Column(String(128), nullable=False)
    purchase_token = Column(String(512), nullable=True)  # Android purchaseToken / iOS receipt hash
    transaction_id = Column(String(128), nullable=True)  # iOS transaction id (если доступен)
    status = Column(Enum(StorePurchaseStatus), default=StorePurchaseStatus.unknown, nullable=False)
    expires_at = Column(DateTime, nullable=True)
    raw = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        UniqueConstraint("platform", "purchase_token", name="uq_store_platform_token"),
    )


class TikTokProfileCache(Base):
    __tablename__ = "tiktok_profile_cache"

    id = Column(String, primary_key=True, default=_uuid)
    username = Column(String(64), unique=True, index=True, nullable=False)
    avatar_url = Column(String(1024), nullable=True)
    display_name = Column(String(256), nullable=True)
    fetched_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class NotificationAudience(str, enum.Enum):
    all = "all"
    users = "users"              # explicit user targets in notification_targets
    plan = "plan"                # audience_value: tariff id (or comma-separated ids)
    missing_email = "missing_email"  # users without email


class NotificationLevel(str, enum.Enum):
    info = "info"
    warning = "warning"
    promo = "promo"


class NotificationType(str, enum.Enum):
    system = "system"
    product = "product"
    marketing = "marketing"


class Notification(Base):
    __tablename__ = "notifications"

    id = Column(String, primary_key=True, default=_uuid)
    dedupe_key = Column(String(256), nullable=True, unique=True)
    title = Column(String(120), nullable=False)
    body = Column(String(2000), nullable=False)
    link = Column(String(512), nullable=True)
    level = Column(Enum(NotificationLevel), default=NotificationLevel.info, nullable=False)

    # New unified notifications fields (kept alongside legacy audience fields for backward compatibility)
    type = Column(Enum(NotificationType), default=NotificationType.product, nullable=False)
    targeting = Column(JSON, nullable=True)  # JSON filter object (intersection semantics)
    in_app_enabled = Column(Boolean, default=True, nullable=False)
    push_enabled = Column(Boolean, default=False, nullable=False)
    created_by_user_id = Column(String, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    audience = Column(Enum(NotificationAudience), default=NotificationAudience.all, nullable=False)
    audience_value = Column(String(256), nullable=True)

    starts_at = Column(DateTime, nullable=True)
    ends_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class NotificationTarget(Base):
    __tablename__ = "notification_targets"

    id = Column(String, primary_key=True, default=_uuid)
    notification_id = Column(String, ForeignKey("notifications.id", ondelete="CASCADE"), index=True, nullable=False)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        UniqueConstraint("notification_id", "user_id", name="uq_notification_target"),
    )


class NotificationRead(Base):
    __tablename__ = "notification_reads"

    id = Column(String, primary_key=True, default=_uuid)
    notification_id = Column(String, ForeignKey("notifications.id", ondelete="CASCADE"), index=True, nullable=False)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    read_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        UniqueConstraint("notification_id", "user_id", name="uq_notification_read"),
    )


class PushPlatform(str, enum.Enum):
    android = "android"
    ios = "ios"
    web = "web"


class PushDeviceToken(Base):
    __tablename__ = "push_device_tokens"

    id = Column(String, primary_key=True, default=_uuid)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    platform = Column(Enum(PushPlatform), nullable=False)
    token = Column(String(512), nullable=False)
    enabled = Column(Boolean, default=True, nullable=False)
    last_seen_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    __table_args__ = (
        UniqueConstraint("platform", "token", name="uq_push_platform_token"),
    )


class GiftEvent(Base):
    __tablename__ = "gift_events"

    id = Column(String, primary_key=True, default=_uuid)
    streamer_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    donor_username = Column(String(64), index=True, nullable=False)

    gift_id = Column(String(64), nullable=True)
    gift_name = Column(String(256), nullable=True)
    gift_count = Column(Integer, default=1, nullable=False)
    gift_coins = Column(Integer, default=0, nullable=False)

    day = Column(Date, index=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class DonorStats(Base):
    __tablename__ = "donor_stats"

    id = Column(String, primary_key=True, default=_uuid)
    streamer_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    donor_username = Column(String(64), nullable=False)

    total_coins = Column(Integer, default=0, nullable=False)
    total_gifts = Column(Integer, default=0, nullable=False)

    today_date = Column(Date, nullable=True)
    today_coins = Column(Integer, default=0, nullable=False)

    yesterday_date = Column(Date, nullable=True)
    yesterday_coins = Column(Integer, default=0, nullable=False)

    last_7d_anchor = Column(Date, nullable=True)
    last_7d_coins = Column(Integer, default=0, nullable=False)

    last_30d_anchor = Column(Date, nullable=True)
    last_30d_coins = Column(Integer, default=0, nullable=False)

    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    __table_args__ = (
        UniqueConstraint("streamer_id", "donor_username", name="uq_donor_stats_streamer_donor"),
    )


class StreamerStats(Base):
    __tablename__ = "streamer_stats"

    id = Column(String, primary_key=True, default=_uuid)
    streamer_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), unique=True, index=True, nullable=False)

    total_coins = Column(Integer, default=0, nullable=False)
    total_gifts = Column(Integer, default=0, nullable=False)

    today_date = Column(Date, nullable=True)
    today_coins = Column(Integer, default=0, nullable=False)

    yesterday_date = Column(Date, nullable=True)
    yesterday_coins = Column(Integer, default=0, nullable=False)

    last_7d_anchor = Column(Date, nullable=True)
    last_7d_coins = Column(Integer, default=0, nullable=False)

    last_30d_anchor = Column(Date, nullable=True)
    last_30d_coins = Column(Integer, default=0, nullable=False)

    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class GiftEventTikTok(Base):
    __tablename__ = "gift_events_tt"

    id = Column(String, primary_key=True, default=_uuid)
    streamer_tiktok_username = Column(String(64), index=True, nullable=False)
    donor_username = Column(String(64), index=True, nullable=False)

    gift_id = Column(String(64), nullable=True)
    gift_name = Column(String(256), nullable=True)
    gift_count = Column(Integer, default=1, nullable=False)
    gift_coins = Column(Integer, default=0, nullable=False)

    day = Column(Date, index=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class DonorStatsTikTok(Base):
    __tablename__ = "donor_stats_tt"

    id = Column(String, primary_key=True, default=_uuid)
    streamer_tiktok_username = Column(String(64), index=True, nullable=False)
    donor_username = Column(String(64), nullable=False)

    total_coins = Column(Integer, default=0, nullable=False)
    total_gifts = Column(Integer, default=0, nullable=False)

    today_date = Column(Date, nullable=True)
    today_coins = Column(Integer, default=0, nullable=False)

    yesterday_date = Column(Date, nullable=True)
    yesterday_coins = Column(Integer, default=0, nullable=False)

    last_7d_anchor = Column(Date, nullable=True)
    last_7d_coins = Column(Integer, default=0, nullable=False)

    last_30d_anchor = Column(Date, nullable=True)
    last_30d_coins = Column(Integer, default=0, nullable=False)

    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    __table_args__ = (
        UniqueConstraint("streamer_tiktok_username", "donor_username", name="uq_donor_stats_tt_streamer_donor"),
    )


class StreamerStatsTikTok(Base):
    __tablename__ = "streamer_stats_tt"

    id = Column(String, primary_key=True, default=_uuid)
    streamer_tiktok_username = Column(String(64), unique=True, index=True, nullable=False)

    total_coins = Column(Integer, default=0, nullable=False)
    total_gifts = Column(Integer, default=0, nullable=False)

    today_date = Column(Date, nullable=True)
    today_coins = Column(Integer, default=0, nullable=False)

    yesterday_date = Column(Date, nullable=True)
    yesterday_coins = Column(Integer, default=0, nullable=False)

    last_7d_anchor = Column(Date, nullable=True)
    last_7d_coins = Column(Integer, default=0, nullable=False)

    last_30d_anchor = Column(Date, nullable=True)
    last_30d_coins = Column(Integer, default=0, nullable=False)

    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
