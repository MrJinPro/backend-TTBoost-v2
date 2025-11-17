"""
API для управления звуковыми файлами
"""
from fastapi import APIRouter, UploadFile, File, HTTPException, Form
from fastapi.responses import FileResponse
from app.services.license_service import verify_ws_token
from app.models.profile import UploadSoundResponse
import os
import math
import aiofiles
import uuid
import logging
from typing import Optional

try:
    from mutagen import File as MutagenFile  # type: ignore
except Exception:
    MutagenFile = None  # будет обработано при попытке чтения длительности
import wave
import contextlib

logger = logging.getLogger(__name__)
router = APIRouter()

# Директория для хранения звуков
SOUNDS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "static", "sounds")
os.makedirs(SOUNDS_DIR, exist_ok=True)

ALLOWED_EXTENSIONS = {".mp3", ".wav", ".ogg", ".m4a"}
# Требования заказчика: до 100KB и не более 5 секунд
MAX_FILE_SIZE = 100 * 1024  # 100 KB
MAX_DURATION_SEC = 5.0

async def _get_audio_duration_seconds(path: str, ext: str) -> Optional[float]:
    """Попытаться определить длительность аудио в секундах.
    Возвращает None, если определить не удалось."""
    try:
        # Сначала пробуем через mutagen (поддерживает mp3/ogg/m4a и др.)
        if MutagenFile is not None:
            f = MutagenFile(path)
            if f is not None and getattr(f, 'info', None) is not None:
                length = getattr(f.info, 'length', None)
                if isinstance(length, (int, float)):
                    return float(length)
        # WAV можно быстро считать стандартной библиотекой
        if ext == ".wav":
            with contextlib.closing(wave.open(path, 'rb')) as wf:
                frames = wf.getnframes()
                rate = wf.getframerate()
                if rate > 0:
                    return frames / float(rate)
    except Exception as e:
        logger.warning(f"Не удалось определить длительность файла '{os.path.basename(path)}': {e}")
    return None


@router.post("/upload", response_model=UploadSoundResponse)
async def upload_sound(
    ws_token: str = Form(...),
    sound_name: str = Form(...),
    file: UploadFile = File(...)
):
    """
    Загрузить звуковой файл на сервер
    
    Args:
        ws_token: Токен пользователя
        sound_name: Название звука (для UI)
        file: Аудио файл (MP3, WAV, OGG, M4A)
    """
    # Проверяем токен
    user_data = await verify_ws_token(ws_token)
    if not user_data:
        raise HTTPException(status_code=401, detail="Invalid token")
    
    user_id = user_data.get("user_id")
    
    # Проверяем расширение файла
    file_ext = os.path.splitext(file.filename)[1].lower()
    if file_ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid file type. Allowed: {', '.join(ALLOWED_EXTENSIONS)}"
        )
    
    # Создаём директорию пользователя
    user_sounds_dir = os.path.join(SOUNDS_DIR, user_id)
    os.makedirs(user_sounds_dir, exist_ok=True)
    
    # Генерируем уникальное имя файла
    unique_id = uuid.uuid4().hex[:8]
    safe_name = "".join(c for c in sound_name if c.isalnum() or c in ('-', '_'))
    sound_filename = f"{safe_name}_{unique_id}{file_ext}"
    file_path = os.path.join(user_sounds_dir, sound_filename)
    
    # Читаем и сохраняем файл
    try:
        content = await file.read()
        
        # Проверяем размер
        if len(content) > MAX_FILE_SIZE:
            raise HTTPException(status_code=400, detail="File too large (max 100KB)")
        
        async with aiofiles.open(file_path, "wb") as f:
            await f.write(content)
        
        # Проверяем длительность (если можем определить)
        duration = await _get_audio_duration_seconds(file_path, file_ext)
        if duration is not None and duration > MAX_DURATION_SEC + 1e-6:
            # Удаляем сохранённый файл и отклоняем загрузку
            try:
                os.remove(file_path)
            finally:
                raise HTTPException(status_code=400, detail="Audio too long (max 5s)")

        # URL для доступа к файлу
        sound_url = f"/static/sounds/{user_id}/{sound_filename}"
        
        logger.info(f"Звук загружен: {sound_filename} для {user_id}")
        
        return UploadSoundResponse(
            sound_file=sound_filename,
            sound_url=sound_url,
        )
        
    except Exception as e:
        logger.error(f"Ошибка загрузки звука: {e}")
        if os.path.exists(file_path):
            os.remove(file_path)
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")


@router.get("/list/{ws_token}")
async def list_sounds(ws_token: str):
    """Получить список всех загруженных звуков пользователя"""
    user_data = await verify_ws_token(ws_token)
    if not user_data:
        raise HTTPException(status_code=401, detail="Invalid token")
    
    user_id = user_data.get("user_id")
    user_sounds_dir = os.path.join(SOUNDS_DIR, user_id)
    
    if not os.path.exists(user_sounds_dir):
        return {"sounds": []}
    
    sounds = []
    for filename in os.listdir(user_sounds_dir):
        if any(filename.endswith(ext) for ext in ALLOWED_EXTENSIONS):
            sounds.append({
                "filename": filename,
                "url": f"/static/sounds/{user_id}/{filename}",
            })
    
    return {"sounds": sounds}


@router.delete("/delete/{ws_token}/{filename}")
async def delete_sound(ws_token: str, filename: str):
    """Удалить звуковой файл"""
    user_data = await verify_ws_token(ws_token)
    if not user_data:
        raise HTTPException(status_code=401, detail="Invalid token")
    
    user_id = user_data.get("user_id")
    
    # Проверяем безопасность пути (защита от path traversal)
    if ".." in filename or "/" in filename or "\\" in filename:
        raise HTTPException(status_code=400, detail="Invalid filename")
    
    file_path = os.path.join(SOUNDS_DIR, user_id, filename)
    
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")
    
    try:
        os.remove(file_path)
        logger.info(f"Звук удалён: {filename} для {user_id}")
        return {"status": "ok", "message": f"File {filename} deleted"}
    except Exception as e:
        logger.error(f"Ошибка удаления звука: {e}")
        raise HTTPException(status_code=500, detail=f"Delete failed: {str(e)}")
