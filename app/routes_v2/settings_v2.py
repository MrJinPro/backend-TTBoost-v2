from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.database import SessionLocal
from app.db import models
from .auth_v2 import get_current_user


router = APIRouter()


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
def update_settings(req: UpdateSettingsRequest, user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    print(f"📥 Update settings request: {req.model_dump()}")
    print(f"User ID: {user.id}, Username: {user.username}")
    
    # Update user tiktok_username if provided
    if req.tiktok_username is not None:
        user.tiktok_username = req.tiktok_username
        user = db.merge(user)  # Используем merge вместо add для избежания конфликта сессий
    
    # Query settings directly from current DB session
    s = db.query(models.UserSettings).filter(models.UserSettings.user_id == user.id).first()
    
    print(f"Current settings object: {s}")
    if s:
        print(f"Current voice_id in DB: {s.voice_id}")
    if not s:
        print("Creating new settings")
        s = models.UserSettings(user_id=user.id)
        db.add(s)
    
    if req.voice_id is not None:
        print(f"Setting voice_id from {s.voice_id if s.voice_id else 'None'} to {req.voice_id}")
        s.voice_id = req.voice_id
    if req.tts_enabled is not None:
        s.tts_enabled = req.tts_enabled
    if req.gift_sounds_enabled is not None:
        s.gift_sounds_enabled = req.gift_sounds_enabled
    if req.tts_volume is not None:
        s.tts_volume = int(req.tts_volume)
    if req.gifts_volume is not None:
        s.gifts_volume = int(req.gifts_volume)
    
    print(f"Before commit - voice_id: {s.voice_id}")
    db.commit()
    db.refresh(s)
    print(f"✅ After commit - voice_id: {s.voice_id}")
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
