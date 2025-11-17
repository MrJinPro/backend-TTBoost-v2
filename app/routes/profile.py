"""
API для управления профилем пользователя
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.services.license_service import verify_ws_token
from app.services.profile_service import (
    get_or_create_profile,
    set_gift_sound,
    remove_gift_sound,
    set_viewer_sound,
    remove_viewer_sound,
    list_user_sounds,
)
from app.models.profile import (
    SetGiftSoundRequest,
    SetViewerSoundRequest,
    ProfileResponse,
)
import logging

logger = logging.getLogger(__name__)
router = APIRouter()


class GetProfileRequest(BaseModel):
    ws_token: str


class DeleteGiftSoundRequest(BaseModel):
    ws_token: str
    gift_name: str


class DeleteViewerSoundRequest(BaseModel):
    ws_token: str
    viewer_username: str


@router.post("/get", response_model=ProfileResponse)
async def get_profile(req: GetProfileRequest):
    """Получить профиль пользователя"""
    user_data = await verify_ws_token(req.ws_token)
    if not user_data:
        raise HTTPException(status_code=401, detail="Invalid token")
    
    user_id = user_data.get("user_id")
    profile = await get_or_create_profile(user_id)
    
    return ProfileResponse(profile=profile)


@router.post("/gift-sound/set")
async def set_gift_sound_endpoint(req: SetGiftSoundRequest):
    """Установить звук для подарка"""
    user_data = await verify_ws_token(req.ws_token)
    if not user_data:
        raise HTTPException(status_code=401, detail="Invalid token")
    
    user_id = user_data.get("user_id")
    success = await set_gift_sound(
        user_id,
        req.gift_name,
        req.sound_file,
        req.enabled
    )
    
    if not success:
        raise HTTPException(status_code=400, detail="Failed to set gift sound")
    
    return {"status": "ok", "message": f"Sound set for gift '{req.gift_name}'"}


@router.post("/gift-sound/delete")
async def delete_gift_sound_endpoint(req: DeleteGiftSoundRequest):
    """Удалить привязку звука к подарку"""
    user_data = await verify_ws_token(req.ws_token)
    if not user_data:
        raise HTTPException(status_code=401, detail="Invalid token")
    
    user_id = user_data.get("user_id")
    success = await remove_gift_sound(user_id, req.gift_name)
    
    if not success:
        raise HTTPException(status_code=404, detail="Gift sound not found")
    
    return {"status": "ok", "message": f"Sound removed for gift '{req.gift_name}'"}


@router.post("/viewer-sound/set")
async def set_viewer_sound_endpoint(req: SetViewerSoundRequest):
    """Установить звук для зрителя"""
    user_data = await verify_ws_token(req.ws_token)
    if not user_data:
        raise HTTPException(status_code=401, detail="Invalid token")
    
    user_id = user_data.get("user_id")
    success = await set_viewer_sound(
        user_id,
        req.viewer_username,
        req.sound_file,
        req.enabled
    )
    
    if not success:
        raise HTTPException(status_code=400, detail="Failed to set viewer sound")
    
    return {"status": "ok", "message": f"Sound set for viewer '@{req.viewer_username}'"}


@router.post("/viewer-sound/delete")
async def delete_viewer_sound_endpoint(req: DeleteViewerSoundRequest):
    """Удалить привязку звука к зрителю"""
    user_data = await verify_ws_token(req.ws_token)
    if not user_data:
        raise HTTPException(status_code=401, detail="Invalid token")
    
    user_id = user_data.get("user_id")
    success = await remove_viewer_sound(user_id, req.viewer_username)
    
    if not success:
        raise HTTPException(status_code=404, detail="Viewer sound not found")
    
    return {"status": "ok", "message": f"Sound removed for viewer '@{req.viewer_username}'"}


@router.get("/sounds/list/{ws_token}")
async def list_profile_sounds(ws_token: str):
    """Получить список всех настроенных звуков профиля"""
    user_data = await verify_ws_token(ws_token)
    if not user_data:
        raise HTTPException(status_code=401, detail="Invalid token")
    
    user_id = user_data.get("user_id")
    sounds = await list_user_sounds(user_id)
    
    return sounds
