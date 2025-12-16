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
    tts_volume: int | None = None
    gifts_volume: int | None = None


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
        if not new_tt:
            raise HTTPException(status_code=400, detail="invalid tiktok_username")

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
    if req.tts_volume is not None:
        s.tts_volume = int(req.tts_volume)
    if req.gifts_volume is not None:
        s.gifts_volume = int(req.gifts_volume)
    
    db.commit()
    db.refresh(s)
    return {"status": "ok", "settings": {
        "voice_id": s.voice_id,
        "tts_enabled": s.tts_enabled,
        "gift_sounds_enabled": s.gift_sounds_enabled,
        "tts_volume": s.tts_volume,
        "gifts_volume": s.gifts_volume,
        "tiktok_username": user.tiktok_username,
    }}


class SettingsResponse(BaseModel):
    voice_id: str
    tts_enabled: bool
    gift_sounds_enabled: bool
    tts_volume: int
    gifts_volume: int
    tiktok_username: str | None = None


@router.get("/get", response_model=SettingsResponse)
def get_settings(user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    s = db.query(models.UserSettings).filter(models.UserSettings.user_id == user.id).first()
    if not s:
        s = models.UserSettings(user_id=user.id)
        db.add(s)
        db.commit()
        db.refresh(s)
    return SettingsResponse(
        voice_id=s.voice_id,
        tts_enabled=s.tts_enabled,
        gift_sounds_enabled=s.gift_sounds_enabled,
        tts_volume=s.tts_volume,
        gifts_volume=s.gifts_volume,
        tiktok_username=user.tiktok_username,
    )
