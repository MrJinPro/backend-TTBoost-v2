from __future__ import annotations

import json
import re
from datetime import datetime, timedelta

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db import models
from app.db.database import SessionLocal
from app.routes_v2.auth_v2 import get_current_user


router = APIRouter()


_TIKTOK_USERNAME_RE = re.compile(r"^[a-z0-9._-]{2,64}$")
_TTL = timedelta(hours=24)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _normalize_username(raw: str) -> str:
    return (raw or "").strip().lower().replace("@", "")


def _validate_username(username: str) -> None:
    if not _TIKTOK_USERNAME_RE.match(username):
        raise HTTPException(status_code=400, detail="invalid username")


def _json_unescape(value: str) -> str:
    value = (value or "").strip()
    if not value:
        return value
    try:
        # `value` is typically already a JSON-escaped string (contains \u002F etc.)
        return json.loads(f'"{value}"')
    except Exception:
        return (
            value.replace("\\u002F", "/")
            .replace("\\/", "/")
            .replace("\\u0026", "&")
        )


def _fetch_tiktok_profile(username: str) -> tuple[str | None, str | None]:
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/json;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9,ru;q=0.8",
    }

    with httpx.Client(timeout=15.0, follow_redirects=True, headers=headers) as client:
        # 1) Try oEmbed (often works without signatures)
        oembed_url = "https://www.tiktok.com/oembed"
        profile_url = f"https://www.tiktok.com/@{username}"
        try:
            resp = client.get(oembed_url, params={"url": profile_url})
            if resp.status_code == 200:
                data = resp.json()
                avatar_url = (data.get("thumbnail_url") or "").strip() or None
                display_name = (data.get("author_name") or "").strip() or None
                if avatar_url:
                    return avatar_url, display_name
            elif resp.status_code == 404:
                return None, None
        except Exception:
            # fall back to HTML parse
            pass

        # 2) Fallback: fetch profile HTML and regex avatar fields
        try:
            resp = client.get(profile_url)
        except Exception:
            return None, None

        if resp.status_code == 404:
            return None, None

        body = resp.text or ""

        avatar_url = None
        for key in ("avatarLarger", "avatarMedium", "avatarThumb"):
            m = re.search(rf'"{key}"\s*:\s*"([^"]+)"', body)
            if m:
                avatar_url = _json_unescape(m.group(1))
                break

        display_name = None
        m = re.search(r'"nickname"\s*:\s*"([^"]+)"', body)
        if m:
            display_name = _json_unescape(m.group(1))

        return avatar_url, display_name


class TikTokProfileResponse(BaseModel):
    username: str
    avatar_url: str | None = None
    display_name: str | None = None
    fetched_at: datetime | None = None
    cached: bool = False


@router.get("/profile", response_model=TikTokProfileResponse)
def get_tiktok_profile(
    username: str | None = Query(None, description="TikTok username without @"),
    user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # `user` comes from auth_v2 DB session; merge into this request session.
    user = db.merge(user)

    effective = _normalize_username(username or user.tiktok_username or "")
    if not effective:
        raise HTTPException(status_code=400, detail="username is required")

    _validate_username(effective)

    now = datetime.utcnow()
    row = db.query(models.TikTokProfileCache).filter(models.TikTokProfileCache.username == effective).one_or_none()

    if row and row.fetched_at and (now - row.fetched_at) < _TTL and row.avatar_url:
        return TikTokProfileResponse(
            username=effective,
            avatar_url=row.avatar_url,
            display_name=row.display_name,
            fetched_at=row.fetched_at,
            cached=True,
        )

    avatar_url, display_name = _fetch_tiktok_profile(effective)

    # If refresh failed, still return whatever we have in cache (even if stale).
    if not avatar_url:
        if row and row.avatar_url:
            return TikTokProfileResponse(
                username=effective,
                avatar_url=row.avatar_url,
                display_name=row.display_name,
                fetched_at=row.fetched_at,
                cached=True,
            )
        raise HTTPException(status_code=404, detail="tiktok profile not found")

    if row is None:
        row = models.TikTokProfileCache(username=effective)

    row.avatar_url = avatar_url
    row.display_name = display_name
    row.fetched_at = now
    db.add(row)
    db.commit()

    return TikTokProfileResponse(
        username=effective,
        avatar_url=row.avatar_url,
        display_name=row.display_name,
        fetched_at=row.fetched_at,
        cached=False,
    )
