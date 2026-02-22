from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional
from app.services import tts_service


router = APIRouter()


class TTSRequest(BaseModel):
    text: str
    voice_id: Optional[str] = None  # gtts-ru | ru-RU-SvetlanaNeural | openai-alloy etc.


class TTSResponse(BaseModel):
    url: str
    engine_used: Optional[str] = None
    voice_id_used: Optional[str] = None
    fallback_used: Optional[bool] = None
    error: Optional[str] = None


@router.post("/generate", response_model=TTSResponse)
async def tts(req: TTSRequest):
    """Сгенерировать TTS. Если voice_id не указан — берём gTTS (ru).
    Для OpenAI голосов (openai-alloy / openai-coral / openai-verse) требуется OPENAI_API_KEY.
    """
    voice = req.voice_id or "gtts-ru"
    url = await tts_service.generate_tts(req.text, voice_id=voice)

    meta = tts_service.get_last_tts_meta() or {}
    # В error отдаём первичную ошибку (если был фолбэк) — чтобы клиент видел причину,
    # но не раскрываем лишнего.
    err = meta.get("primary_error") if meta.get("fallback_used") else meta.get("primary_error")
    if err is not None:
        err = str(err)
        if len(err) > 400:
            err = err[:400]

    return TTSResponse(
        url=url,
        engine_used=(meta.get("used_engine") or None),
        voice_id_used=(meta.get("used_voice_id") or None),
        fallback_used=bool(meta.get("fallback_used")) if ("fallback_used" in meta) else None,
        error=err,
    )
