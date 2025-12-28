from fastapi import APIRouter, Depends, HTTPException, Header
from pydantic import BaseModel
from sqlalchemy.orm import Session
from datetime import datetime

from app.db.database import SessionLocal
from app.db import models
from .auth_v2 import get_current_user
from app.services.plans import resolve_tariff, normalize_platform
from app.services.tts_service import AVAILABLE_VOICES


router = APIRouter()


def _normalize_tiktok_username(raw: str) -> str:
    return raw.strip().lower().replace("@", "")


def _voice_engine_for_id(voice_id: str) -> str | None:
    for voices in AVAILABLE_VOICES.values():
        for v in voices:
            if v.get("id") == voice_id:
                return v.get("engine")
    return None


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


class UpdateSettingsRequest(BaseModel):
    tiktok_username: str | None = None
    voice_id: str | None = None
    tts_enabled: bool | None = None
    gift_sounds_enabled: bool | None = None
    auto_connect_live: bool | None = None
    tts_volume: int | None = None
    gifts_volume: int | None = None
    silence_enabled: bool | None = None
    silence_minutes: int | None = None
    chat_tts_mode: str | None = None
    chat_tts_prefixes: str | None = None
    chat_tts_min_diamonds: int | None = None


@router.post("/update")
def update_settings(
    req: UpdateSettingsRequest,
    user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
    client_platform: str | None = Header(default=None, alias="X-Client-Platform"),
):
    tariff, _lic = resolve_tariff(db, user.id)
    platform = normalize_platform(client_platform)
    if platform not in tariff.allowed_platforms:
        raise HTTPException(status_code=403, detail="tariff does not allow this platform")
    
    # Update user tiktok_username if provided (with tariff rules)
    if req.tiktok_username is not None:
        new_tt = _normalize_tiktok_username(req.tiktok_username)
        current_tt = _normalize_tiktok_username(user.tiktok_username or "")
        # Allow clearing username by sending empty string
        if not new_tt:
            user.tiktok_username = None
            user = db.merge(user)
            # continue processing other settings updates
            new_tt = ""
        
    if req.tiktok_username is not None and new_tt:

        # backfill current username into accounts table if missing
        if current_tt:
            cur_row = (
                db.query(models.UserTikTokAccount)
                .filter(models.UserTikTokAccount.user_id == user.id)
                .filter(models.UserTikTokAccount.username == current_tt)
                .first()
            )
            if not cur_row:
                db.add(models.UserTikTokAccount(user_id=user.id, username=current_tt, last_used_at=datetime.utcnow()))
                db.flush()

        if tariff.lock_tiktok_username_after_set and current_tt and new_tt != current_tt:
            raise HTTPException(status_code=403, detail="tariff does not allow changing tiktok account")

        # ensure account is recorded and within limits
        existing = (
            db.query(models.UserTikTokAccount)
            .filter(models.UserTikTokAccount.user_id == user.id)
            .filter(models.UserTikTokAccount.username == new_tt)
            .first()
        )
        if not existing:
            if tariff.max_tiktok_accounts is not None:
                total = db.query(models.UserTikTokAccount).filter(models.UserTikTokAccount.user_id == user.id).count()
                if total >= int(tariff.max_tiktok_accounts):
                    raise HTTPException(status_code=403, detail="tariff tiktok account limit reached")
            existing = models.UserTikTokAccount(user_id=user.id, username=new_tt, last_used_at=datetime.utcnow())
            db.add(existing)
            db.flush()
        else:
            existing.last_used_at = datetime.utcnow()

        user.tiktok_username = new_tt
        user = db.merge(user)  # избегаем конфликтов сессий
    
    # Query settings directly from current DB session
    s = db.query(models.UserSettings).filter(models.UserSettings.user_id == user.id).first()
    if not s:
        s = models.UserSettings(user_id=user.id)
        db.add(s)
    
    if req.voice_id is not None:
        engine = _voice_engine_for_id(req.voice_id)
        if engine and engine not in tariff.allowed_tts_engines:
            raise HTTPException(status_code=403, detail="tariff does not allow this voice")
        s.voice_id = req.voice_id
    if req.tts_enabled is not None:
        s.tts_enabled = req.tts_enabled
    if req.gift_sounds_enabled is not None:
        s.gift_sounds_enabled = req.gift_sounds_enabled
    if req.auto_connect_live is not None:
        s.auto_connect_live = req.auto_connect_live
    if req.tts_volume is not None:
        s.tts_volume = int(req.tts_volume)
    if req.gifts_volume is not None:
        s.gifts_volume = int(req.gifts_volume)

    # Chat TTS filter settings
    if req.chat_tts_mode is not None:
        v = str(req.chat_tts_mode).strip().lower()
        if v not in ("all", "prefix", "donor"):
            raise HTTPException(status_code=400, detail="invalid chat_tts_mode")
        s.chat_tts_mode = v

    if req.chat_tts_prefixes is not None:
        raw = str(req.chat_tts_prefixes)
        # keep only first 8 non-space characters
        cleaned = "".join([c for c in raw if not c.isspace()])[:8]
        s.chat_tts_prefixes = cleaned or "."

    if req.chat_tts_min_diamonds is not None:
        try:
            md = int(req.chat_tts_min_diamonds)
        except Exception:
            md = 0
        if md < 0:
            md = 0
        if md > 100000:
            md = 100000
        s.chat_tts_min_diamonds = md

    # Premium feature: silence mode (requires premium engines; we gate by eleven availability in tariff)
    if req.silence_enabled is not None:
        if req.silence_enabled and ("eleven" not in tariff.allowed_tts_engines):
            raise HTTPException(status_code=403, detail="premium required")
        s.silence_enabled = bool(req.silence_enabled)

    if req.silence_minutes is not None:
        if "eleven" not in tariff.allowed_tts_engines:
            raise HTTPException(status_code=403, detail="premium required")
        try:
            minutes = int(req.silence_minutes)
        except Exception:
            minutes = 5
        if minutes < 1:
            minutes = 1
        if minutes > 60:
            minutes = 60
        s.silence_minutes = minutes
    
    db.commit()
    db.refresh(s)
    return {"status": "ok", "settings": {
        "voice_id": s.voice_id,
        "tts_enabled": s.tts_enabled,
        "gift_sounds_enabled": s.gift_sounds_enabled,
        "auto_connect_live": s.auto_connect_live,
        "tts_volume": s.tts_volume,
        "gifts_volume": s.gifts_volume,
        "silence_enabled": bool(getattr(s, "silence_enabled", False)),
        "silence_minutes": int(getattr(s, "silence_minutes", 5) or 5),
        "chat_tts_mode": str(getattr(s, "chat_tts_mode", "all") or "all"),
        "chat_tts_prefixes": str(getattr(s, "chat_tts_prefixes", ".") or "."),
        "chat_tts_min_diamonds": int(getattr(s, "chat_tts_min_diamonds", 0) or 0),
        "tiktok_username": user.tiktok_username,
    }}


class SettingsResponse(BaseModel):
    voice_id: str
    tts_enabled: bool
    gift_sounds_enabled: bool
    auto_connect_live: bool
    tts_volume: int
    gifts_volume: int
    silence_enabled: bool = False
    silence_minutes: int = 5
    chat_tts_mode: str = "all"
    chat_tts_prefixes: str = "."
    chat_tts_min_diamonds: int = 0
    tiktok_username: str | None = None


@router.get("/get", response_model=SettingsResponse)
def get_settings(user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    tariff, _lic = resolve_tariff(db, user.id)
    s = db.query(models.UserSettings).filter(models.UserSettings.user_id == user.id).first()
    if not s:
        s = models.UserSettings(user_id=user.id)
        db.add(s)
        db.commit()
        db.refresh(s)

    # do not expose enabled=true for free tariffs
    silence_enabled = bool(getattr(s, "silence_enabled", False))
    if "eleven" not in tariff.allowed_tts_engines:
        silence_enabled = False

    return SettingsResponse(
        voice_id=s.voice_id,
        tts_enabled=s.tts_enabled,
        gift_sounds_enabled=s.gift_sounds_enabled,
        auto_connect_live=s.auto_connect_live,
        tts_volume=s.tts_volume,
        gifts_volume=s.gifts_volume,
        silence_enabled=silence_enabled,
        silence_minutes=int(getattr(s, "silence_minutes", 5) or 5),
        chat_tts_mode=str(getattr(s, "chat_tts_mode", "all") or "all"),
        chat_tts_prefixes=str(getattr(s, "chat_tts_prefixes", ".") or "."),
        chat_tts_min_diamonds=int(getattr(s, "chat_tts_min_diamonds", 0) or 0),
        tiktok_username=user.tiktok_username,
    )
