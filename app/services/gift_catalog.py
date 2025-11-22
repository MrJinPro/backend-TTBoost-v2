"""Каталог подарков TikTok для сопоставления имени -> ID.
Минимальная версия: можно расширять. Если доступен исходный JS каталог, можно парсить.
"""
import os
import re
import logging
from functools import lru_cache

logger = logging.getLogger(__name__)

FALLBACK_GIFTS = {
    # Базовые популярные подарки (пополнять при необходимости)
    "rose": 5655,
    # Примеры (id условные, заменить реальными при расширении):
    "heart": 5507,
    "galaxy": 5760,
    "lion": 5766,
}

@lru_cache(maxsize=1)
def _load_js_catalog() -> dict:
    """Пытаемся прочитать tiktok-gifts.js и извлечь пары name->id.
    Ожидаем шаблоны вида: { id: 5655, name: 'Rose' } или "id":5655,"name":"Rose"
    Если файл отсутствует или парсинг не удался — возвращаем FALLBACK_GIFTS.
    """
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
    js_path = os.path.join(root, "tiktok-gifts.js")
    if not os.path.exists(js_path):
        return FALLBACK_GIFTS
    try:
        text = open(js_path, "r", encoding="utf-8", errors="ignore").read()
        pattern = re.compile(r"id\s*[:=]\s*(\d+)\s*[,;].{0,40}?name\s*[:=]\s*['\"]([^'\"]+)['\"]", re.IGNORECASE)
        mapping = {}
        for m in pattern.finditer(text):
            gid = int(m.group(1))
            name = m.group(2).strip()
            mapping[name.lower()] = gid
        # Сливаем фолбэки
        for k,v in FALLBACK_GIFTS.items():
            mapping.setdefault(k, v)
        if not mapping:
            return FALLBACK_GIFTS
        logger.info(f"Gift catalog parsed: {len(mapping)} items")
        return mapping
    except Exception as e:
        logger.warning(f"Не удалось распарсить tiktok-gifts.js: {e}")
        return FALLBACK_GIFTS


def get_gift_id_by_name(name: str) -> int | None:
    if not name:
        return None
    catalog = _load_js_catalog()
    return catalog.get(name.lower())
