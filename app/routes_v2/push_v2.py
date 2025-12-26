from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
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


def _now() -> datetime:
    return datetime.utcnow()


class RegisterPushTokenRequest(BaseModel):
    token: str
    platform: str  # android|ios|web


class RegisterPushTokenResponse(BaseModel):
    status: str = "ok"


@router.post("/push/register", response_model=RegisterPushTokenResponse)
def register_push_token(
    req: RegisterPushTokenRequest,
    user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    token = (req.token or "").strip()
    if not token or len(token) < 8 or len(token) > 512:
        raise HTTPException(status_code=400, detail="invalid token")

    platform = (req.platform or "").strip().lower()
    if platform not in {"android", "ios", "web"}:
        raise HTTPException(status_code=400, detail="invalid platform")

    now = _now()

    # Upsert by (platform, token)
    row = (
        db.query(models.PushDeviceToken)
        .filter(models.PushDeviceToken.platform == models.PushPlatform(platform))
        .filter(models.PushDeviceToken.token == token)
        .first()
    )

    if row:
        row.user_id = user.id
        row.enabled = True
        row.last_seen_at = now
        row.updated_at = now
    else:
        db.add(
            models.PushDeviceToken(
                user_id=user.id,
                platform=models.PushPlatform(platform),
                token=token,
                enabled=True,
                last_seen_at=now,
                created_at=now,
                updated_at=now,
            )
        )

    db.commit()
    return RegisterPushTokenResponse()


class UnregisterPushTokenRequest(BaseModel):
    token: str
    platform: str


class UnregisterPushTokenResponse(BaseModel):
    status: str = "ok"


@router.post("/push/unregister", response_model=UnregisterPushTokenResponse)
def unregister_push_token(
    req: UnregisterPushTokenRequest,
    user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    token = (req.token or "").strip()
    platform = (req.platform or "").strip().lower()
    if not token or platform not in {"android", "ios", "web"}:
        raise HTTPException(status_code=400, detail="invalid request")

    row = (
        db.query(models.PushDeviceToken)
        .filter(models.PushDeviceToken.user_id == user.id)
        .filter(models.PushDeviceToken.platform == models.PushPlatform(platform))
        .filter(models.PushDeviceToken.token == token)
        .first()
    )
    if row:
        row.enabled = False
        row.updated_at = _now()
        db.commit()

    return UnregisterPushTokenResponse()
