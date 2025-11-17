from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.services.license_service import login_license, set_user_tiktok, set_user_voice
from app.db.database import SessionLocal
from app.db import models
import os
from urllib.parse import urlparse
from datetime import datetime, timedelta, timezone


router = APIRouter()


class LoginRequest(BaseModel):
    license_key: str


class LoginResponse(BaseModel):
    status: str = "ok"
    user_id: str
    ws_token: str
    ws_url: str
    server_time: str
    expires_at: str


class SetTikTokRequest(BaseModel):
    ws_token: str
    tiktok_username: str


class SetTikTokResponse(BaseModel):
    status: str = "ok"
    message: str


class SetVoiceRequest(BaseModel):
    ws_token: str
    voice_id: str


class SetVoiceResponse(BaseModel):
    status: str = "ok"
    message: str


@router.post("/login", response_model=LoginResponse)
async def login(req: LoginRequest):
    user_id, ws_token = await login_license(req.license_key)
    if not ws_token:
        raise HTTPException(status_code=401, detail="Invalid license key")
    ws_url = _build_ws_url(ws_token)
    now = datetime.now(timezone.utc)
    # Пытаемся получить реальный срок действия лицензии из БД
    expires = None
    try:
        db = SessionLocal()
        lic = db.query(models.LicenseKey).filter(models.LicenseKey.key == req.license_key).first()
        if lic and lic.expires_at:
            expires = lic.expires_at
    except Exception:
        expires = None
    finally:
        try:
            db.close()
        except Exception:
            pass
    if not expires:
        ttl_hours = int(os.getenv("TOKEN_TTL_HOURS", "24"))
        expires = now + timedelta(hours=ttl_hours)
    return LoginResponse(
        user_id=user_id,
        ws_token=ws_token,
        ws_url=ws_url,
        server_time=now.isoformat(),
        expires_at=expires.isoformat(),
    )


@router.post("/set-tiktok", response_model=SetTikTokResponse)
async def set_tiktok(req: SetTikTokRequest):
    """Установить TikTok username для пользователя"""
    success = await set_user_tiktok(req.ws_token, req.tiktok_username)
    if not success:
        raise HTTPException(status_code=400, detail="Invalid token or username")
    return SetTikTokResponse(
        message=f"TikTok username установлен: @{req.tiktok_username}"
    )


@router.post("/set-voice", response_model=SetVoiceResponse)
async def set_voice(req: SetVoiceRequest):
    """Установить voice_id для пользователя"""
    success = await set_user_voice(req.ws_token, req.voice_id)
    if not success:
        raise HTTPException(status_code=400, detail="Invalid token")
    return SetVoiceResponse(
        message=f"Voice ID установлен: {req.voice_id}"
    )


def _build_ws_url(token: str) -> str:
    env = os.getenv("ENV", "dev").lower()
    server_host = os.getenv("SERVER_HOST", "https://api.ttboost.pro").rstrip('/')
    parsed = urlparse(server_host)
    host = parsed.netloc or parsed.path  # handle values like "api.example.com"
    if env == "prod":
        scheme = "wss"
    else:
        # derive from SERVER_HOST scheme in non-prod
        scheme = "wss" if parsed.scheme == "https" else "ws"
    return f"{scheme}://{host}/ws/{token}"
