"""Сервис интеграции с OpenAI GPT.

Функции:
- generate_text: базовая генерация
- safe_moderate: (заглушка) потенциальная точка для модерации

Особенности:
- Асинхронный вызов через официальную библиотеку openai>=1.0
- Таймаут через asyncio.wait_for
- Обработка сетевых ошибок и возврат структурированного результата
- Кеш последних N ответов для экономии токенов
"""
from __future__ import annotations
import os
import asyncio
import logging
from typing import Optional, Dict, Any, Tuple

logger = logging.getLogger(__name__)

# Попытка импортировать OpenAI SDK нового формата
try:  # pragma: no cover
    from openai import OpenAI
except ImportError:  # pragma: no cover
    OpenAI = None  # type: ignore

_CACHE_SIZE = int(os.getenv("OPENAI_CACHE_SIZE", "25"))
_cache: Dict[Tuple[str, str, str, int, float], Dict[str, Any]] = {}

DEFAULT_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
API_KEY = os.getenv("OPENAI_API_KEY")

if API_KEY:
    logger.info("OpenAI API key обнаружен (не показываем). GPT интеграция доступна.")
else:
    logger.warning("OPENAI_API_KEY не установлен. GPT вызовы будут недоступны.")

_client: Optional[OpenAI] = None
if OpenAI and API_KEY:
    try:
        _client = OpenAI(api_key=API_KEY)
    except Exception as e:  # pragma: no cover
        logger.error(f"Не удалось инициализировать OpenAI клиент: {e}")
        _client = None

class OpenAIError(Exception):
    pass

async def generate_text(
    prompt: str,
    system: Optional[str] = None,
    model: str = DEFAULT_MODEL,
    max_tokens: int = 512,
    temperature: float = 0.7,
    timeout_sec: float = 20.0,
) -> Dict[str, Any]:
    """Генерация текста GPT.

    Возвращает dict: { "text": str, "usage": {...}, "cached": bool }
    """
    if not _client:
        raise OpenAIError("OpenAI клиент не инициализирован (нет ключа или библиотеки).")

    # Формируем ключ кеша
    cache_key = (model, prompt, system or "", max_tokens, temperature)
    if cache_key in _cache:
        return {**_cache[cache_key], "cached": True}

    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    async def _call():
        # Вызов chat.completions (новый SDK)
        return _client.chat.completions.create(
            model=model,
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
        )

    try:
        resp = await asyncio.wait_for(_call(), timeout=timeout_sec)
    except asyncio.TimeoutError:
        raise OpenAIError("GPT таймаут")
    except Exception as e:  # pragma: no cover
        raise OpenAIError(f"GPT ошибка: {e}")

    try:
        choice = resp.choices[0]
        text = choice.message.content
    except Exception as e:  # pragma: no cover
        raise OpenAIError(f"Неверный формат ответа: {e}")

    usage = getattr(resp, 'usage', None)
    result = {"text": text, "usage": getattr(usage, 'to_dict', lambda: dict(usage or {}))(), "cached": False}

    # Кеширование с ограничением размера
    if len(_cache) >= _CACHE_SIZE:
        # Удаляем произвольный первый элемент (простой LRU не реализуем пока)
        _cache.pop(next(iter(_cache)))
    _cache[cache_key] = result

    return result

async def safe_moderate(text: str) -> Dict[str, Any]:
    """Заглушка для будущей модерации (можно подключить OpenAI moderation)."""
    # Пока просто возвращаем allow=True
    return {"allow": True, "reasons": []}

__all__ = ["generate_text", "OpenAIError", "safe_moderate"]
