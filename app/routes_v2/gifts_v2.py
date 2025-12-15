from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import json
from pathlib import Path

from app.services.gift_sounds import get_global_gift_sound_path

router = APIRouter()


class Gift(BaseModel):
    gift_id: int
    name_en: str
    name_ru: str
    image: str
    diamond_count: int


def load_gifts_library() -> list[Gift]:
    """Загрузка библиотеки подарков из JSON"""
    library_path = Path(__file__).parent.parent.parent / "data" / "gifts_library.json"
    
    if not library_path.exists():
        return []
    
    try:
        with open(library_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return [Gift(**g) for g in data]
    except Exception as e:
        print(f"Ошибка загрузки gifts_library.json: {e}")
        return []


def _library_path() -> Path:
    return Path(__file__).parent.parent.parent / "data" / "gifts_library.json"


def _library_mtime() -> float | None:
    try:
        return _library_path().stat().st_mtime
    except Exception:
        return None


# Кэш библиотеки подарков
GIFTS_LIBRARY: list[Gift] = load_gifts_library()
_GIFTS_LIBRARY_MTIME: float | None = _library_mtime()


def _ensure_gifts_library_loaded() -> None:
    """Подгружает/перезагружает библиотеку, если файл появился или изменился.

    Это важно для деплоя: если файл добавили через git pull после старта сервиса,
    старый процесс иначе навсегда останется с пустым списком.
    """
    global GIFTS_LIBRARY, _GIFTS_LIBRARY_MTIME
    m = _library_mtime()
    if m is None:
        return
    if _GIFTS_LIBRARY_MTIME != m or not GIFTS_LIBRARY:
        GIFTS_LIBRARY = load_gifts_library()
        _GIFTS_LIBRARY_MTIME = m


@router.get("/library")
def get_gifts_library():
    """Получить полную библиотеку подарков с русскими названиями и изображениями"""
    _ensure_gifts_library_loaded()
    gifts = []
    for g in GIFTS_LIBRARY:
        d = g.model_dump()
        sound = get_global_gift_sound_path(g.gift_id)
        if sound:
            d["sound"] = sound
        gifts.append(d)
    return {
        "gifts": gifts,
        "total": len(GIFTS_LIBRARY)
    }


@router.get("/list")
def list_gifts():
    """Устаревший endpoint - использовать /library"""
    return get_gifts_library()


@router.get("/{gift_id}")
def get_gift(gift_id: int):
    """Получить информацию о конкретном подарке по ID"""
    gift = next((g for g in GIFTS_LIBRARY if g.gift_id == gift_id), None)
    if not gift:
        raise HTTPException(status_code=404, detail="Gift not found")
    return gift.model_dump()
