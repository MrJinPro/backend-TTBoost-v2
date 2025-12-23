from __future__ import annotations

import os
import re
import uuid
from typing import Final
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Request
from pydantic import BaseModel
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.database import SessionLocal
from app.db import models
from app.routes_v2.auth_v2 import get_current_user
from app.services.security import hash_password, verify_password


router = APIRouter()


_USERNAME_RE = re.compile(r"^[a-z0-9._-]{2,64}$")


_MAX_SNIFF_BYTES: Final[int] = 64 * 1024


def _detect_image_ext(header: bytes) -> str | None:
    # JPEG
    if len(header) >= 3 and header[0:3] == b"\xFF\xD8\xFF":
        return ".jpg"
    # PNG
    if len(header) >= 8 and header[0:8] == b"\x89PNG\r\n\x1a\n":
        return ".png"
    # GIF
    if len(header) >= 6 and header[0:6] in (b"GIF87a", b"GIF89a"):
        return ".gif"
    # WEBP (RIFF....WEBP)
    if len(header) >= 12 and header[0:4] == b"RIFF" and header[8:12] == b"WEBP":
        return ".webp"
    return None


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _abs_url(path: str, request: Request | None = None) -> str:
    media_base = (os.getenv("MEDIA_BASE_URL") or "").strip().rstrip("/")
    base = media_base
    if not base and request is not None:
        proto = (request.headers.get("x-forwarded-proto") or request.url.scheme or "http").strip()
        host = (
            request.headers.get("x-forwarded-host")
            or request.headers.get("host")
            or request.url.netloc
        )
        host = (host or "").strip()
        if host:
            base = f"{proto}://{host}".rstrip("/")
        else:
            base = str(request.base_url).rstrip("/")
    if not base:
        base = (
            os.getenv("SERVER_HOST")
            or os.getenv("TTS_BASE_URL")
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


def _normalize_username(raw: str) -> str:
    return raw.strip().lower().replace("@", "")


def _validate_username(username: str) -> None:
    if not _USERNAME_RE.match(username):
        raise HTTPException(status_code=400, detail="invalid username")


def _validate_password(password: str) -> None:
    if not password or len(password) < 6:
        raise HTTPException(status_code=400, detail="invalid password")


@router.patch("", response_model=UpdateProfileResponse)
def update_profile(
    req: UpdateProfileRequest,
    user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # `user` comes from auth_v2 DB session; merge into this request session.
    user = db.merge(user)
    email = (req.email or "").strip() or None
    user.email = email
    db.commit()
    return UpdateProfileResponse(email=user.email)


class UpdateCredentialsRequest(BaseModel):
    current_password: str
    new_username: str | None = None
    new_password: str | None = None


class UpdateCredentialsResponse(BaseModel):
    status: str = "ok"
    username: str


@router.post("/credentials", response_model=UpdateCredentialsResponse)
def update_credentials(
    req: UpdateCredentialsRequest,
    user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # `user` comes from auth_v2 DB session; merge into this request session.
    user = db.merge(user)

    if not (req.new_username is not None or req.new_password is not None):
        raise HTTPException(status_code=400, detail="nothing to update")

    if not verify_password(req.current_password or "", user.password_hash):
        raise HTTPException(status_code=401, detail="invalid credentials")

    if req.new_username is not None:
        new_username = _normalize_username(req.new_username)
        _validate_username(new_username)
        if new_username != user.username:
            user.username = new_username

    if req.new_password is not None:
        _validate_password(req.new_password)
        user.password_hash = hash_password(req.new_password)

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="username already exists")

    return UpdateCredentialsResponse(username=user.username)


class UploadAvatarResponse(BaseModel):
    status: str = "ok"
    avatar_url: str


@router.post("/avatar", response_model=UploadAvatarResponse)
def upload_avatar(
    request: Request,
    file: UploadFile = File(...),
    user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # `user` comes from auth_v2 DB session; merge into this request session.
    user = db.merge(user)

    ct = (file.content_type or "").lower().strip()
    # Some clients send "application/octet-stream" or omit content-type.
    # We validate primarily by magic-bytes and/or filename extension.
    if ct and ct not in {
        "image/jpeg",
        "image/jpg",
        "image/png",
        "image/webp",
        "image/gif",
        "application/octet-stream",
    }:
        # If it's explicitly a non-image, reject early.
        if not ct.startswith("image/"):
            raise HTTPException(status_code=400, detail="unsupported file type")

    original_name = (file.filename or "avatar").strip()
    _, ext = os.path.splitext(original_name)
    ext = ext.lower()
    if ext == ".jpeg":
        ext = ".jpg"

    # sniff header to determine real type
    header = b""
    try:
        header = file.file.read(_MAX_SNIFF_BYTES)
        try:
            file.file.seek(0)
        except Exception:
            pass
    except Exception:
        header = b""

    sniffed_ext = _detect_image_ext(header) if header else None
    allowed_ext = {".jpg", ".png", ".webp", ".gif"}

    if sniffed_ext is not None:
        ext = sniffed_ext
    elif ext in {".jpg", ".png", ".webp", ".gif"}:
        # use provided ext
        pass
    else:
        # fallback by content-type
        if ct in ("image/png",):
            ext = ".png"
        elif ct in ("image/webp",):
            ext = ".webp"
        elif ct in ("image/gif",):
            ext = ".gif"
        else:
            ext = ".jpg"

    if ext not in allowed_ext:
        raise HTTPException(status_code=400, detail="unsupported file type")

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
    db.commit()

    avatar_url = _abs_url(f"/static/avatars/{user.id}/{filename}", request=request)
    return UploadAvatarResponse(avatar_url=avatar_url)
