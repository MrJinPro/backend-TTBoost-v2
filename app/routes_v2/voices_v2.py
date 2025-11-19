from fastapi import APIRouter
from pydantic import BaseModel
from typing import List
from app.services.tts_service import get_all_voices

router = APIRouter()


class Voice(BaseModel):
    id: str
    name: str
    lang: str
    engine: str


class VoicesResponse(BaseModel):
    voices: List[Voice]


@router.get("/voices", response_model=VoicesResponse)
async def get_voices():
    """Получить список всех доступных голосов для TTS"""
    voices = get_all_voices()
    return VoicesResponse(voices=[Voice(**v) for v in voices])
