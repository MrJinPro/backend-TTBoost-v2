import enum
import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, Boolean, Integer, Enum, ForeignKey, UniqueConstraint, JSON
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
    password_hash = Column(String(255), nullable=False)
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
    tts_volume = Column(Integer, default=100)
    gifts_volume = Column(Integer, default=100)

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
