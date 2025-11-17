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
    voice_id: str | None = None
    tts_enabled: bool | None = None
    gift_sounds_enabled: bool | None = None
    tts_volume: int | None = None
    gifts_volume: int | None = None


@router.post("/update")
def update_settings(req: UpdateSettingsRequest, user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    s = user.settings
    if not s:
        s = models.UserSettings(user_id=user.id)
        db.add(s)
    if req.voice_id is not None:
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
    return {"status": "ok"}
