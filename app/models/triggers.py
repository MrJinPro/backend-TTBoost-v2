from pydantic import BaseModel
from typing import Optional, List


class TriggerAction(BaseModel):
    type: str  # 'play_sound' | 'tts'
    sound_file: Optional[str] = None  # static/sounds/{user_id}/{file}
    text_template: Optional[str] = None  # используется если type == 'tts'


class Trigger(BaseModel):
    event_type: str  # 'gift' | 'viewer_join' | 'follow' | 'subscribe' | 'chat'
    condition_key: Optional[str] = None  # e.g. 'gift_name' | 'username' | 'message_contains'
    condition_value: Optional[str] = None
    gift_id: Optional[int] = None  # Для event_type='gift' автоматическое сопоставление ID из каталога
    action: TriggerAction
    enabled: bool = True
    priority: int = 0  # больший priority выигрывает при множестве совпадений


class SetTriggerRequest(BaseModel):
    ws_token: str
    event_type: str
    condition_key: Optional[str] = None
    condition_value: Optional[str] = None
    gift_id: Optional[int] = None
    action: TriggerAction
    enabled: bool = True
    priority: int = 0


class DeleteTriggerRequest(BaseModel):
    ws_token: str
    event_type: str
    condition_key: Optional[str] = None
    condition_value: Optional[str] = None


class TriggersResponse(BaseModel):
    status: str = "ok"
    triggers: List[Trigger]

class TriggersMetaResponse(BaseModel):
    status: str = "ok"
    event_types: List[str]
    action_types: List[str]
    condition_keys: List[str]
