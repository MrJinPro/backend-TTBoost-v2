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
    import logging
    logger = logging.getLogger(__name__)
    logger.info(f"📥 Update settings request: {req.model_dump()}")
    
    # Update user tiktok_username if provided
    if req.tiktok_username is not None:
        user.tiktok_username = req.tiktok_username
        user = db.merge(user)  # Используем merge вместо add для избежания конфликта сессий
    
    # Update settings
    s = user.settings
    logger.info(f"Current settings: {s}")
    if not s:
        logger.info("Creating new settings")
        s = models.UserSettings(user_id=user.id)
        db.add(s)
    if req.voice_id is not None:
        logger.info(f"Setting voice_id: {req.voice_id}")
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
    logger.info(f"✅ Settings saved. voice_id={s.voice_id}")
    return {"status": "ok"}
