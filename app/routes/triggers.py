from fastapi import APIRouter, HTTPException
from app.services.license_service import verify_ws_token
from app.models.triggers import SetTriggerRequest, DeleteTriggerRequest, TriggersResponse, Trigger, TriggersMetaResponse
from app.services.gift_catalog import get_gift_id_by_name
from app.services.triggers_service import add_or_update_trigger, delete_trigger, list_triggers

router = APIRouter()


@router.post('/set')
async def set_trigger(req: SetTriggerRequest):
    user = await verify_ws_token(req.ws_token)
    if not user:
        raise HTTPException(status_code=401, detail='Invalid token')
    user_id = user['user_id']
    # Политика: для чата (event_type='chat') разрешён только action.type='tts'
    if req.event_type == 'chat' and req.action.type == 'play_sound':
        raise HTTPException(status_code=400, detail='Chat supports only TTS action')
    gift_id = None
    if req.event_type == 'gift':
        # Автоподтягивание gift_id если задано по имени
        if req.condition_key == 'gift_name' and req.condition_value:
            gift_id = get_gift_id_by_name(req.condition_value)
    trigger = Trigger(
        event_type=req.event_type,
        condition_key=req.condition_key,
        condition_value=req.condition_value,
        gift_id=gift_id,
        action=req.action,
        enabled=req.enabled,
        priority=req.priority,
    )
    await add_or_update_trigger(user_id, trigger)
    return {"status": "ok"}


@router.post('/delete')
async def delete_trigger_endpoint(req: DeleteTriggerRequest):
    user = await verify_ws_token(req.ws_token)
    if not user:
        raise HTTPException(status_code=401, detail='Invalid token')
    user_id = user['user_id']
    ok = await delete_trigger(user_id, req.event_type, req.condition_key, req.condition_value)
    if not ok:
        raise HTTPException(status_code=404, detail='Trigger not found')
    return {"status": "ok"}


@router.get('/list/{ws_token}', response_model=TriggersResponse)
async def list_triggers_endpoint(ws_token: str):
    user = await verify_ws_token(ws_token)
    if not user:
        raise HTTPException(status_code=401, detail='Invalid token')
    user_id = user['user_id']
    items = await list_triggers(user_id)
    return TriggersResponse(triggers=items)


@router.get('/meta', response_model=TriggersMetaResponse)
async def triggers_meta():
    return TriggersMetaResponse(
        event_types=["gift","viewer_join","viewer_first_message","follow","subscribe","chat"],
        action_types=["play_sound","tts"],
        condition_keys=["gift_name","username","message_contains"],
    )
