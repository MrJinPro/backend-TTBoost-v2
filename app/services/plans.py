from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from app.db import models


@dataclass(frozen=True)
class Tariff:
    id: str
    name: str
    allowed_platforms: set[str]
    max_tiktok_accounts: Optional[int]  # None = unlimited
    lock_tiktok_username_after_set: bool
    allowed_tts_engines: set[str]


TARIFF_FREE = Tariff(
    id="nova_free_streamer",
    name="NovaFree Streamer",
    allowed_platforms={"mobile", "desktop"},
    max_tiktok_accounts=1,
    lock_tiktok_username_after_set=True,
    allowed_tts_engines={"gtts", "edge"},
)

TARIFF_ONE_MOBILE = Tariff(
    id="nova_streamer_one_mobile",
    name="NovaStreamer One (Mobile)",
    allowed_platforms={"mobile"},
    max_tiktok_accounts=3,
    lock_tiktok_username_after_set=False,
    allowed_tts_engines={"gtts", "edge", "openai", "eleven"},
)

TARIFF_ONE_DESKTOP = Tariff(
    id="nova_streamer_one_desktop",
    name="NovaStreamer One (Desktop)",
    allowed_platforms={"desktop"},
    max_tiktok_accounts=3,
    lock_tiktok_username_after_set=False,
    allowed_tts_engines={"gtts", "edge", "openai", "eleven"},
)

TARIFF_DUO = Tariff(
    id="nova_streamer_duo",
    name="NovaStreamer Duo",
    allowed_platforms={"mobile", "desktop"},
    max_tiktok_accounts=None,
    lock_tiktok_username_after_set=False,
    allowed_tts_engines={"gtts", "edge", "openai", "eleven"},
)


def normalize_platform(value: str | None) -> str:
    v = (value or "").strip().lower()
    if v in ("mobile", "m"):
        return "mobile"
    if v in ("desktop", "pc", "windows", "mac", "linux", "d"):
        return "desktop"
    return "mobile"


def _get_active_license_for_user(db: Session, user_id: str) -> models.LicenseKey | None:
    now = datetime.utcnow()
    return (
        db.query(models.LicenseKey)
        .filter(models.LicenseKey.user_id == user_id)
        .filter(models.LicenseKey.status == models.LicenseStatus.active)
        .filter((models.LicenseKey.expires_at.is_(None)) | (models.LicenseKey.expires_at >= now))
        .order_by(models.LicenseKey.expires_at.is_(None).desc())
        .order_by(models.LicenseKey.expires_at.desc())
        .order_by(models.LicenseKey.issued_at.desc())
        .first()
    )


def _normalize_plan(raw: str | None) -> str:
    v = (raw or "").strip().lower()
    v = v.replace("-", "_").replace(" ", "_")
    return v


def canonicalize_license_plan(raw: str | None) -> str | None:
    if raw is None:
        return None
    plan = _normalize_plan(raw)
    if not plan:
        return None
    if plan in ("nova_streamer_one_mobile", "nova_one_mobile", "one_mobile"):
        return "nova_streamer_one_mobile"
    if plan in ("nova_streamer_one_desktop", "nova_one_desktop", "one_desktop"):
        return "nova_streamer_one_desktop"
    if plan in ("nova_streamer_duo", "nova_duo", "duo"):
        return "nova_streamer_duo"
    raise ValueError("invalid plan")


def resolve_tariff(db: Session, user_id: str) -> tuple[Tariff, models.LicenseKey | None]:
    lic = _get_active_license_for_user(db, user_id)
    if not lic or not lic.plan:
        return (TARIFF_FREE, lic)

    plan = _normalize_plan(lic.plan)

    if plan in ("nova_streamer_one_mobile", "nova_one_mobile", "one_mobile"):
        return (TARIFF_ONE_MOBILE, lic)
    if plan in ("nova_streamer_one_desktop", "nova_one_desktop", "one_desktop"):
        return (TARIFF_ONE_DESKTOP, lic)
    if plan in ("nova_streamer_duo", "nova_duo", "duo"):
        return (TARIFF_DUO, lic)

    # неизвестный план — безопасный дефолт
    return (TARIFF_FREE, lic)
