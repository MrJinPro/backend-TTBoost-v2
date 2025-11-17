from fastapi import APIRouter
from pydantic import BaseModel
from app.services.tts_service import get_all_voices, generate_tts
from typing import List

router = APIRouter()


class Voice(BaseModel):
    id: str
    name: str
    lang: str
    engine: str


class VoicesResponse(BaseModel):
    voices: List[Voice]


class GenerateSampleRequest(BaseModel):
    voice_id: str
    text: str = "Привет! Это пример голоса TTBoost."


class GenerateSampleResponse(BaseModel):
    audio_url: str


@router.get("/voices", response_model=VoicesResponse)
async def get_voices():
    """Получить список всех доступных голосов"""
    voices = get_all_voices()
    return VoicesResponse(voices=[Voice(**v) for v in voices])


@router.post("/generate-sample", response_model=GenerateSampleResponse)
async def generate_sample(req: GenerateSampleRequest):
    """Сгенерировать пример озвучки для выбранного голоса"""
    audio_url = await generate_tts(req.text, req.voice_id)
    return GenerateSampleResponse(audio_url=audio_url)
