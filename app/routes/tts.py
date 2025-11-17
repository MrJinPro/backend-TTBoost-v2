from fastapi import APIRouter
from pydantic import BaseModel
from app.services.tts_service import generate_tts


router = APIRouter()


class TTSRequest(BaseModel):
    text: str


class TTSResponse(BaseModel):
    url: str


@router.post("/generate", response_model=TTSResponse)
async def tts(req: TTSRequest):
    url = await generate_tts(req.text)
    return TTSResponse(url=url)
