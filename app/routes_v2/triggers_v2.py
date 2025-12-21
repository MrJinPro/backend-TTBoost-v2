from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.database import SessionLocal
from app.db import models
from .auth_v2 import get_current_user


router = APIRouter()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


class SetTriggerRequest(BaseModel):
    event_type: str
    condition_key: str | None = None
    condition_value: str | None = None
    enabled: bool = True
    priority: int = 0
    action: str
    text_template: str | None = None
    sound_filename: str | None = None
    trigger_name: str | None = None
    combo_count: int = 0
    cooldown_seconds: int | None = None
    once_per_stream: bool | None = None
    autoplay_sound: bool | None = None


@router.post("/set")
def set_trigger(req: SetTriggerRequest, user=Depends(get_current_user), db: Session = Depends(get_db)):
    print(f"🔵 set_trigger received: event={req.event_type}, key={req.condition_key}, value={req.condition_value}, action={req.action}, sound={req.sound_filename}, combo={req.combo_count}")
    
    if req.action not in (models.TriggerAction.play_sound.value, models.TriggerAction.tts.value):
        raise HTTPException(400, detail="invalid action")

    action_params = {}
    if req.action == models.TriggerAction.tts.value:
        action_params["text_template"] = req.text_template or "{message}"
        if req.cooldown_seconds is not None and req.cooldown_seconds > 0:
            action_params["cooldown_seconds"] = req.cooldown_seconds
    else:
        if not req.sound_filename:
            raise HTTPException(400, detail="sound required for play_sound")
        # ensure sound exists
        sf = db.query(models.SoundFile).filter(models.SoundFile.user_id == user.id, models.SoundFile.filename == req.sound_filename).first()
        if not sf:
            raise HTTPException(404, detail="sound file not found")
        action_params["sound_filename"] = req.sound_filename
        if req.cooldown_seconds is not None and req.cooldown_seconds > 0:
            action_params["cooldown_seconds"] = req.cooldown_seconds

        # Доп. опции поведения (актуально для viewer_join, но храним универсально)
        if req.once_per_stream is not None:
            action_params["once_per_stream"] = bool(req.once_per_stream)
        if req.autoplay_sound is not None:
            action_params["autoplay_sound"] = bool(req.autoplay_sound)

    trig = models.Trigger(
        user_id=user.id,
        event_type=req.event_type,
        condition_key=req.condition_key,
        condition_value=req.condition_value,
        enabled=req.enabled,
        priority=req.priority,
        action=models.TriggerAction(req.action),
        action_params=action_params,
        trigger_name=req.trigger_name,
        combo_count=req.combo_count,
    )
    db.add(trig)
    db.commit()
    print(f"🟢 set_trigger saved: id={trig.id}, event={trig.event_type}, key={trig.condition_key}, value={trig.condition_value}")
    return {"status": "ok"}


@router.get("/list")
def list_triggers(user=Depends(get_current_user), db: Session = Depends(get_db)):
    items = (
        db.query(models.Trigger)
        .filter(models.Trigger.user_id == user.id)
        .order_by(models.Trigger.priority.desc(), models.Trigger.created_at.asc())
        .all()
    )
    return {"triggers": [
        {
            "id": t.id,
            "event_type": t.event_type,
            "condition_key": t.condition_key,
            "condition_value": t.condition_value,
            "enabled": t.enabled,
            "priority": t.priority,
            "action": t.action.value,
            "action_params": t.action_params,
            "executed_count": t.executed_count,
            "trigger_name": t.trigger_name,
            "combo_count": t.combo_count,
        }
        for t in items
    ]}


# Алиас для мобильного приложения, которое ожидает /v2/triggers (без /list)
@router.get("/")
def get_triggers_root(user=Depends(get_current_user), db: Session = Depends(get_db)):
    """
    Алиас для list_triggers - мобильное приложение ожидает GET /v2/triggers
    """
    return list_triggers(user, db)


class DeleteTriggerRequest(BaseModel):
    id: str


@router.post("/delete")
def delete_trigger(req: DeleteTriggerRequest, user=Depends(get_current_user), db: Session = Depends(get_db)):
    t = db.get(models.Trigger, req.id)
    if not t or t.user_id != user.id:
        raise HTTPException(404, detail="not found")
    db.delete(t)
    db.commit()
    return {"status": "ok"}

class UpdateTriggerEnabledRequest(BaseModel):
    id: str
    enabled: bool

@router.post('/update-enabled')
def update_trigger_enabled(req: UpdateTriggerEnabledRequest, user=Depends(get_current_user), db: Session = Depends(get_db)):
    t = db.get(models.Trigger, req.id)
    if not t or t.user_id != user.id:
        raise HTTPException(404, detail='not found')
    t.enabled = req.enabled
    db.add(t)
    db.commit()
    return {'status': 'ok', 'id': t.id, 'enabled': t.enabled}


class UpdateTriggerRequest(BaseModel):
    id: str
    trigger_name: str | None = None
    enabled: bool | None = None
    priority: int | None = None
    condition_key: str | None = None
    condition_value: str | None = None
    combo_count: int | None = None
    text_template: str | None = None
    sound_filename: str | None = None
    cooldown_seconds: int | None = None
    once_per_stream: bool | None = None
    autoplay_sound: bool | None = None


@router.post('/update')
def update_trigger(req: UpdateTriggerRequest, user=Depends(get_current_user), db: Session = Depends(get_db)):
    t = db.get(models.Trigger, req.id)
    if not t or t.user_id != user.id:
        raise HTTPException(404, detail='not found')

    if req.trigger_name is not None:
        tn = req.trigger_name.strip()
        t.trigger_name = tn if tn else None
    if req.enabled is not None:
        t.enabled = req.enabled
    if req.priority is not None:
        t.priority = req.priority
    if req.condition_key is not None:
        t.condition_key = req.condition_key
    if req.condition_value is not None:
        t.condition_value = req.condition_value
    if req.combo_count is not None:
        t.combo_count = max(0, int(req.combo_count))

    action_params = dict(t.action_params or {})

    # Обновляем action_params в зависимости от типа действия
    if t.action == models.TriggerAction.tts:
        if req.text_template is not None:
            tt = req.text_template.strip()
            if not tt:
                action_params.pop('text_template', None)
            else:
                action_params['text_template'] = tt
    elif t.action == models.TriggerAction.play_sound:
        if req.sound_filename is not None:
            if not req.sound_filename.strip():
                raise HTTPException(400, detail='sound_filename cannot be empty')
            sf = (
                db.query(models.SoundFile)
                .filter(models.SoundFile.user_id == user.id, models.SoundFile.filename == req.sound_filename)
                .first()
            )
            if not sf:
                raise HTTPException(404, detail='sound file not found')
            action_params['sound_filename'] = req.sound_filename

    if req.cooldown_seconds is not None:
        if req.cooldown_seconds <= 0:
            action_params.pop('cooldown_seconds', None)
        else:
            action_params['cooldown_seconds'] = req.cooldown_seconds

    if req.once_per_stream is not None:
        action_params['once_per_stream'] = bool(req.once_per_stream)
    if req.autoplay_sound is not None:
        action_params['autoplay_sound'] = bool(req.autoplay_sound)

    t.action_params = action_params

    db.add(t)
    db.commit()
    return {'status': 'ok', 'id': t.id}
