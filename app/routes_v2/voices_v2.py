from fastapi import APIRouter, Depends, Header
from pydantic import BaseModel
from typing import List
from app.services.tts_service import get_all_voices
from app.services.security import decode_token
from app.services.plans import resolve_tariff
from app.db.database import SessionLocal
from app.db import models
from sqlalchemy.orm import Session

router = APIRouter()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


class Voice(BaseModel):
    id: str
    name: str
    lang: str | None = None
    engine: str
    voice: str | None = None
    unavailable: bool | None = None
    slow: bool | None = None


class VoicesResponse(BaseModel):
    voices: List[Voice]


@router.get("/voices", response_model=VoicesResponse)
@router.get("/voices/list", response_model=VoicesResponse)
async def get_voices(
    authorization: str | None = Header(default=None, alias="Authorization"),
    db: Session = Depends(get_db),
):
    """Получить список всех доступных голосов для TTS (дополнительный алиас /voices/list)."""
    user_id: str | None = None
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization.split(" ", 1)[1]
        sub = decode_token(token)
        if sub:
            user_id = str(sub)

    allowed_engines = {"gtts"}
    if user_id:
        user = db.get(models.User, user_id)
        if user:
            tariff, _lic = resolve_tariff(db, user.id)
            allowed_engines = set(tariff.allowed_tts_engines)

    voices = [v for v in get_all_voices() if (v.get("engine") in allowed_engines)]
    return VoicesResponse(voices=[Voice(**v) for v in voices])
