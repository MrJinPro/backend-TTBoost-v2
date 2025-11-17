from typing import Dict, List, Optional
from app.models.triggers import Trigger
from datetime import datetime, timezone
import logging
import os
import json

logger = logging.getLogger(__name__)

# In-memory + файловая персистенция: user_id -> list of triggers
TRIGGERS: Dict[str, List[Trigger]] = {}
BASE_DIR = os.path.dirname(os.path.dirname(__file__))
TRIGGERS_DIR = os.path.join(BASE_DIR, 'static', 'triggers')
os.makedirs(TRIGGERS_DIR, exist_ok=True)


def _triggers_path(user_id: str) -> str:
    return os.path.join(TRIGGERS_DIR, f"{user_id}.json")


def _load_user_triggers(user_id: str) -> List[Trigger]:
    if user_id in TRIGGERS:
        return TRIGGERS[user_id]
    path = _triggers_path(user_id)
    items: List[Trigger] = []
    if os.path.exists(path):
        try:
            with open(path, 'r', encoding='utf-8') as f:
                raw = json.load(f)
            if isinstance(raw, list):
                for obj in raw:
                    try:
                        items.append(Trigger(**obj))
                    except Exception:
                        continue
        except Exception as e:
            logger.error(f"Не удалось прочитать triggers для {user_id}: {e}")
    TRIGGERS[user_id] = items
    return items


def _save_user_triggers(user_id: str):
    path = _triggers_path(user_id)
    try:
        with open(path, 'w', encoding='utf-8') as f:
            json.dump([t.model_dump() for t in TRIGGERS.get(user_id, [])], f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Не удалось сохранить triggers для {user_id}: {e}")


async def list_triggers(user_id: str) -> List[Trigger]:
    return _load_user_triggers(user_id)


async def add_or_update_trigger(user_id: str, trigger: Trigger) -> None:
    items = _load_user_triggers(user_id)
    # replace if exists by (event_type, condition_key, condition_value)
    idx = next((i for i, t in enumerate(items)
                if t.event_type == trigger.event_type
                and t.condition_key == trigger.condition_key
                and t.condition_value == trigger.condition_value), -1)
    if idx >= 0:
        items[idx] = trigger
        logger.info(f"Trigger updated for {user_id}: {trigger.event_type} {trigger.condition_key}={trigger.condition_value}")
    else:
        items.append(trigger)
        logger.info(f"Trigger added for {user_id}: {trigger.event_type} {trigger.condition_key}={trigger.condition_value}")
    TRIGGERS[user_id] = items
    _save_user_triggers(user_id)


async def delete_trigger(user_id: str, event_type: str, condition_key: Optional[str], condition_value: Optional[str]) -> bool:
    items = _load_user_triggers(user_id)
    n0 = len(items)
    items[:] = [t for t in items if not (t.event_type == event_type and t.condition_key == condition_key and t.condition_value == condition_value)]
    TRIGGERS[user_id] = items
    if len(items) != n0:
        _save_user_triggers(user_id)
        return True
    return False


async def find_applicable_trigger(user_id: str, event_type: str, condition_key: Optional[str], condition_value: Optional[str]) -> Optional[Trigger]:
    items = [t for t in TRIGGERS.get(user_id, []) if t.enabled and t.event_type == event_type]
    if not items:
        return None

    matched: List[Trigger] = []
    for t in items:
        # Если триггер без условия — он подходит всегда
        if not t.condition_key:
            matched.append(t)
            continue
        # Стандартное точное совпадение
        if t.condition_key == condition_key and t.condition_value == condition_value:
            matched.append(t)
            continue
        # Дополнительный режим: substring для message_contains при event_type 'chat'
        if event_type == 'chat' and t.condition_key == 'message_contains' and t.condition_value:
            haystack = (condition_value or '').lower()
            needle = t.condition_value.lower()
            if needle in haystack:
                matched.append(t)

    if not matched:
        return None
    # Выбираем с наивысшим priority (при равенстве — первый добавленный)
    matched.sort(key=lambda x: x.priority, reverse=True)
    return matched[0]
