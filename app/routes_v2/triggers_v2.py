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


@router.post("/set")
def set_trigger(req: SetTriggerRequest, user=Depends(get_current_user), db: Session = Depends(get_db)):
    if req.action not in (models.TriggerAction.play_sound.value, models.TriggerAction.tts.value):
        raise HTTPException(400, detail="invalid action")

    action_params = {}
    if req.action == models.TriggerAction.tts.value:
        action_params["text_template"] = req.text_template or "{message}"
    else:
        if not req.sound_filename:
            raise HTTPException(400, detail="sound required for play_sound")
        # ensure sound exists
        sf = db.query(models.SoundFile).filter(models.SoundFile.user_id == user.id, models.SoundFile.filename == req.sound_filename).first()
        if not sf:
            raise HTTPException(404, detail="sound file not found")
        action_params["sound_filename"] = req.sound_filename

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
