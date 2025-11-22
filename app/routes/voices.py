from fastapi import APIRouter
from pydantic import BaseModel
from app.services.tts_service import get_all_voices, generate_tts
from typing import List

router = APIRouter()


class Voice(BaseModel):
    id: str
    name: str
    lang: str | None = None
    engine: str
    voice: str | None = None  # внутреннее имя для openai
    unavailable: bool | None = None  # если движок недоступен (нет ключа)
    slow: bool | None = None  # флаг для медленных вариантов gTTS


class VoicesResponse(BaseModel):
    voices: List[Voice]


class GenerateSampleRequest(BaseModel):
    voice_id: str
    text: str = "Привет! Это пример голоса TTBoost."


class GenerateSampleResponse(BaseModel):
    audio_url: str


@router.get("/voices", response_model=VoicesResponse)
@router.get("/", response_model=VoicesResponse)
async def get_voices():
    """Получить список всех доступных голосов (дублируем /voices и / для совместимости с фронтом)."""
    voices = get_all_voices()
    # Приводим к расширенной модели, сохраняя дополнительные поля если есть
    return VoicesResponse(voices=[Voice(**v) for v in voices])


@router.post("/generate-sample", response_model=GenerateSampleResponse)
async def generate_sample(req: GenerateSampleRequest):
    """Сгенерировать пример озвучки для выбранного голоса"""
    audio_url = await generate_tts(req.text, req.voice_id)
    return GenerateSampleResponse(audio_url=audio_url)
