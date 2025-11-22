from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional
import os

from app.db.database import get_session
from app.db.models import User
from sqlalchemy.orm import Session
from app.services.openai_service import generate_text, OpenAIError

router = APIRouter()

class ChatRequest(BaseModel):
    prompt: str
    system: Optional[str] = None
    model: Optional[str] = None
    max_tokens: int = 256
    temperature: float = 0.7

class ChatResponse(BaseModel):
    text: str
    cached: bool
    usage: dict | None

# Простая зависимость авторизации (Bearer) - упрощённо: ключ из заголовка Authorization
from fastapi import Header

def get_current_user(authorization: Optional[str] = Header(None), session: Session = Depends(get_session)) -> User:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Unauthorized")
    token = authorization.split(" ", 1)[1]
    user = session.query(User).filter(User.jwt_token == token).first()
    if not user:
        raise HTTPException(status_code=401, detail="Invalid token")
    return user

@router.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest, user: User = Depends(get_current_user)):
    if not os.getenv("OPENAI_API_KEY"):
        raise HTTPException(status_code=503, detail="GPT недоступен: нет OPENAI_API_KEY")
    try:
        result = await generate_text(
            prompt=req.prompt,
            system=req.system,
            model=req.model or os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
            max_tokens=req.max_tokens,
            temperature=req.temperature,
        )
        return ChatResponse(text=result["text"], cached=result["cached"], usage=result.get("usage"))
    except OpenAIError as e:
        raise HTTPException(status_code=400, detail=str(e))
