import json
from pathlib import Path
from typing import Dict, Optional


def _mapping_path() -> Path:
    return Path(__file__).parent.parent.parent / "data" / "gift_sounds_global.json"


def load_global_gift_sound_map() -> Dict[int, str]:
    """Loads mapping gift_id -> sound path or URL.

    The mapping file is optional. Values may be:
    - relative path like /static/sounds/global/gift_7604.mp3
    - absolute URL https://...
    """
    p = _mapping_path()
    if not p.exists():
        return {}
    try:
        with open(p, "r", encoding="utf-8") as f:
            raw = json.load(f)
        if not isinstance(raw, dict):
            return {}
        out: Dict[int, str] = {}
        for k, v in raw.items():
            try:
                gid = int(k)
            except Exception:
                continue
            if isinstance(v, str) and v.strip():
                out[gid] = v.strip()
        return out
    except Exception:
        return {}


_GLOBAL_MAP: Dict[int, str] = load_global_gift_sound_map()


def get_global_gift_sound_path(gift_id: int) -> Optional[str]:
    return _GLOBAL_MAP.get(int(gift_id))
