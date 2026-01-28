from __future__ import annotations

import os
import re
import uuid
import shutil
from typing import Final
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Request
from pydantic import BaseModel
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.db.database import SessionLocal
from app.db import models
from app.routes_v2.auth_v2 import get_current_user, _normalize_email
from app.services.security import hash_password, verify_password


_EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


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
    email = _normalize_email(req.email) if (req.email or "").strip() else None
    if email is not None:
        if len(email) > 256 or not _EMAIL_RE.match(email):
            raise HTTPException(status_code=400, detail="invalid email")
        # Uniqueness check (case-insensitive)
        exists = (
            db.query(models.User)
            .filter(models.User.id != user.id)
            .filter(models.User.email.is_not(None))
            .filter(func.lower(models.User.email) == email)
            .first()
        )
        if exists:
            raise HTTPException(status_code=409, detail="email already in use")
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


class DeleteAccountRequest(BaseModel):
    confirm: str
    password: str | None = None


class DeleteAccountResponse(BaseModel):
    status: str = "ok"


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

    old_filename = getattr(user, "avatar_filename", None)

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

    # Keep only the latest avatar file.
    if old_filename and old_filename != filename:
        old_path = os.path.join(avatars_dir, old_filename)
        try:
            if os.path.exists(old_path):
                os.remove(old_path)
        except Exception:
            # Not critical: the new avatar is already saved and committed.
            pass

    avatar_url = _abs_url(f"/static/avatars/{user.id}/{filename}", request=request)
    return UploadAvatarResponse(avatar_url=avatar_url)


def _app_static_root() -> str:
    # If MEDIA_ROOT is configured as root for /static, use it.
    media_root = (os.getenv("MEDIA_ROOT") or "").strip()
    if media_root:
        return os.path.abspath(media_root)
    # fallback to backend/app/static
    return os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "static"))


@router.post("/delete", response_model=DeleteAccountResponse)
def delete_account(
    req: DeleteAccountRequest,
    user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    user = db.merge(user)

    confirm = (req.confirm or "").strip().upper()
    if confirm != "DELETE":
        raise HTTPException(status_code=400, detail="confirmation required")

    # Optional re-auth: if password provided, verify it.
    if req.password is not None and req.password.strip() != "":
        if not verify_password(req.password, user.password_hash):
            raise HTTPException(status_code=401, detail="invalid credentials")

    user_id = user.id

    # Best-effort delete related records (DB-level cascade may not be enabled everywhere).
    try:
        db.query(models.Trigger).filter(models.Trigger.user_id == user_id).delete(synchronize_session=False)
    except Exception:
        pass
    try:
        db.query(models.Event).filter(models.Event.user_id == user_id).delete(synchronize_session=False)
    except Exception:
        pass
    try:
        db.query(models.StreamSession).filter(models.StreamSession.user_id == user_id).delete(synchronize_session=False)
    except Exception:
        pass
    try:
        db.query(models.SoundFile).filter(models.SoundFile.user_id == user_id).delete(synchronize_session=False)
    except Exception:
        pass
    try:
        db.query(models.StorePurchase).filter(models.StorePurchase.user_id == user_id).delete(synchronize_session=False)
    except Exception:
        pass
    try:
        db.query(models.UserTikTokAccount).filter(models.UserTikTokAccount.user_id == user_id).delete(synchronize_session=False)
    except Exception:
        pass
    try:
        db.query(models.UserSettings).filter(models.UserSettings.user_id == user_id).delete(synchronize_session=False)
    except Exception:
        pass

    # Finally delete the user.
    try:
        db.delete(user)
        db.commit()
    except Exception:
        db.rollback()
        raise

    # Best-effort cleanup user media.
    static_root = _app_static_root()
    for rel in (
        os.path.join("avatars", user_id),
        os.path.join("sounds", user_id),
        os.path.join("tts", user_id),
    ):
        try:
            shutil.rmtree(os.path.join(static_root, rel), ignore_errors=True)
        except Exception:
            pass

    return DeleteAccountResponse()
