import os
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from pydantic import BaseModel
from mutagen import File as MutagenFile

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


MAX_BYTES = 100 * 1024
MAX_DURATION_SEC = 5


def _media_root(user_id: str) -> str:
    root = os.getenv("MEDIA_ROOT", os.path.join(os.path.dirname(__file__), "..", "static", "sounds"))
    root = os.path.abspath(os.path.join(root))
    path = os.path.join(root, user_id)
    os.makedirs(path, exist_ok=True)
    return path


def _media_base_url() -> str:
    return (os.getenv("MEDIA_BASE_URL") or os.getenv("TTS_BASE_URL") or os.getenv("SERVER_HOST") or "http://localhost:8000").rstrip("/")


@router.post("/upload")
async def upload_sound(user: models.User = Depends(get_current_user), db: Session = Depends(get_db), file: UploadFile = File(...)):
    content = await file.read()
    if len(content) > MAX_BYTES:
        raise HTTPException(400, detail="file too large (100KB max)")

    # Try read duration
    duration_sec = None
    try:
        tmp_path = os.path.join(_media_root(user.id), "._tmp_" + file.filename)
        with open(tmp_path, "wb") as tmp:
            tmp.write(content)
        mf = MutagenFile(tmp_path)
        if mf and mf.info and getattr(mf.info, 'length', None):
            duration_sec = float(mf.info.length)
        os.remove(tmp_path)
    except Exception:
        duration_sec = None

    if duration_sec is not None and duration_sec > MAX_DURATION_SEC:
        raise HTTPException(400, detail="duration must be <= 5s")

    # store
    safe_name = file.filename.replace("/", "_").replace("\\", "_")
    dst = os.path.join(_media_root(user.id), safe_name)
    with open(dst, "wb") as f:
        f.write(content)

    url = f"{_media_base_url()}/static/sounds/{user.id}/{safe_name}"
    rec = models.SoundFile(user_id=user.id, filename=safe_name, url=url, bytes=len(content), duration_ms=int(duration_sec*1000) if duration_sec else None, kind=models.SoundType.uploaded)
    db.add(rec)
    try:
        db.commit()
    except IntegrityError:
        # Откатим транзакцию и вернём 409 с данными существующей записи
        db.rollback()
        existing = db.query(models.SoundFile).filter(models.SoundFile.user_id == user.id, models.SoundFile.filename == safe_name).first()
        if existing:
            return {"status": "exists", "filename": existing.filename, "url": existing.url}
        raise HTTPException(409, detail="duplicate sound filename")
    return {"status": "ok", "filename": safe_name, "url": url}


class SoundListItem(BaseModel):
    filename: str
    url: str


@router.get("/list")
def list_sounds(user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    items = db.query(models.SoundFile).filter(models.SoundFile.user_id == user.id).order_by(models.SoundFile.created_at.desc()).all()
    return {"sounds": [{"filename": it.filename, "url": it.url} for it in items]}
