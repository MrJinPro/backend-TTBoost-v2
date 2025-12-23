from __future__ import annotations

import os
import uuid
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.database import SessionLocal
from app.db import models
from app.routes_v2.auth_v2 import get_current_user


router = APIRouter()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _abs_url(path: str) -> str:
    base = (
        os.getenv("MEDIA_BASE_URL")
        or os.getenv("TTS_BASE_URL")
        or os.getenv("SERVER_HOST")
        or "http://localhost:8000"
    ).rstrip("/")
    if not path.startswith("/"):
        path = "/" + path
    return base + path


class UpdateProfileRequest(BaseModel):
    email: str | None = None


class UpdateProfileResponse(BaseModel):
    status: str = "ok"
    email: str | None = None


@router.patch("", response_model=UpdateProfileResponse)
def update_profile(
    req: UpdateProfileRequest,
    user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    email = (req.email or "").strip() or None
    user.email = email
    db.add(user)
    db.commit()
    return UpdateProfileResponse(email=user.email)


class UploadAvatarResponse(BaseModel):
    status: str = "ok"
    avatar_url: str


@router.post("/avatar", response_model=UploadAvatarResponse)
def upload_avatar(
    file: UploadFile = File(...),
    user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    ct = (file.content_type or "").lower()
    allowed_ct = {"image/jpeg", "image/png", "image/webp"}
    if ct and ct not in allowed_ct:
        raise HTTPException(status_code=400, detail="unsupported file type")

    original_name = (file.filename or "avatar").strip()
    _, ext = os.path.splitext(original_name)
    ext = ext.lower()
    if ext not in {".jpg", ".jpeg", ".png", ".webp"}:
        # fallback by content-type
        if ct == "image/png":
            ext = ".png"
        elif ct == "image/webp":
            ext = ".webp"
        else:
            ext = ".jpg"

    static_dir = os.path.join(os.path.dirname(__file__), "..", "static")
    static_dir = os.path.abspath(static_dir)
    avatars_dir = os.path.join(static_dir, "avatars", user.id)
    os.makedirs(avatars_dir, exist_ok=True)

    filename = f"{uuid.uuid4().hex}{ext}"
    dst_path = os.path.join(avatars_dir, filename)

    # Save file
    try:
        with open(dst_path, "wb") as out:
            while True:
                chunk = file.file.read(1024 * 1024)
                if not chunk:
                    break
                out.write(chunk)
    except Exception:
        raise HTTPException(status_code=500, detail="failed to save file")

    user.avatar_filename = filename
    db.add(user)
    db.commit()

    avatar_url = _abs_url(f"/static/avatars/{user.id}/{filename}")
    return UploadAvatarResponse(avatar_url=avatar_url)
