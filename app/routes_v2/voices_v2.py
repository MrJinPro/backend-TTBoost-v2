from fastapi import APIRouter
from pydantic import BaseModel
from typing import List
from app.services.tts_service import get_all_voices

router = APIRouter()


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
async def get_voices():
    """Получить список всех доступных голосов для TTS (дополнительный алиас /voices/list)."""
    voices = get_all_voices()
    return VoicesResponse(voices=[Voice(**v) for v in voices])
