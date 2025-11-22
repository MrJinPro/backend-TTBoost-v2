from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional
from app.services.tts_service import generate_tts


router = APIRouter()


class TTSRequest(BaseModel):
    text: str
    voice_id: Optional[str] = None  # gtts-ru | ru-RU-SvetlanaNeural | openai-alloy etc.


class TTSResponse(BaseModel):
    url: str


@router.post("/generate", response_model=TTSResponse)
async def tts(req: TTSRequest):
    """Сгенерировать TTS. Если voice_id не указан — берём gTTS (ru).
    Для OpenAI голосов (openai-alloy / openai-coral / openai-verse) требуется OPENAI_API_KEY.
    """
    voice = req.voice_id or "gtts-ru"
    url = await generate_tts(req.text, voice_id=voice)
    return TTSResponse(url=url)
