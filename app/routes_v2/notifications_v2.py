from __future__ import annotations

from datetime import datetime
import json
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import or_

from app.db.database import SessionLocal
from app.db import models
from app.routes_v2.auth_v2 import get_current_user
from app.services.plans import resolve_tariff
from app.services.system_notifications import ensure_tariff_expiry_notifications


router = APIRouter()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _now() -> datetime:
    return datetime.utcnow()


def _is_active_window(q, now: datetime):
    return q.filter(or_(models.Notification.starts_at.is_(None), models.Notification.starts_at <= now)).filter(
        or_(models.Notification.ends_at.is_(None), models.Notification.ends_at >= now)
    )


def _normalize_targeting(raw) -> dict:
    if raw is None:
        return {}
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        s = raw.strip()
        if not s:
            return {}
        try:
            v = json.loads(s)
            return v if isinstance(v, dict) else {}
        except Exception:
            return {}
    return {}


def _get_user_purchase_info(db: Session, user_id: str) -> tuple[str | None, str | None]:
    # Best-effort: most recent StorePurchase.
    row = (
        db.query(models.StorePurchase.platform, models.StorePurchase.status)
        .filter(models.StorePurchase.user_id == user_id)
        .order_by(models.StorePurchase.updated_at.desc())
        .order_by(models.StorePurchase.created_at.desc())
        .first()
    )
    if not row:
        return None, None
    plat, st = row
    plat_s = (plat.value if hasattr(plat, "value") else str(plat)) if plat is not None else None
    st_s = (st.value if hasattr(st, "value") else str(st)) if st is not None else None
    return (plat_s or None), (st_s or None)


def _eligible_by_targeting(
    targeting: dict,
    *,
    user: models.User,
    email: str,
    plan_id: str,
    purchase_platform: str | None,
    purchase_status: str | None,
    legacy_target_ids: set[str],
    notification_id: str,
) -> bool:
    # Intersection semantics for all provided filters.
    if targeting.get("users") is True:
        return notification_id in legacy_target_ids

    user_ids = targeting.get("user_ids") or []
    if isinstance(user_ids, list) and user_ids:
        if user.id not in {str(x) for x in user_ids if x is not None}:
            return False

    usernames = targeting.get("usernames") or []
    if isinstance(usernames, list) and usernames:
        uname = (user.username or "").strip().lower().replace("@", "")
        allowed = {str(x).strip().lower().replace("@", "") for x in usernames if x is not None}
        if uname not in allowed:
            return False

    if targeting.get("missing_email") is True:
        if email:
            return False

    plans = targeting.get("plans") or []
    if isinstance(plans, list) and plans:
        if not plan_id:
            return False
        allowed = {str(x).strip().lower() for x in plans if x is not None and str(x).strip()}
        if plan_id not in allowed:
            return False

    platforms = targeting.get("purchase_platforms") or []
    if isinstance(platforms, list) and platforms:
        if not purchase_platform:
            return False
        allowed = {str(x).strip().lower() for x in platforms if x is not None and str(x).strip()}
        if (purchase_platform or "").strip().lower() not in allowed:
            return False

    statuses = targeting.get("purchase_statuses") or []
    if isinstance(statuses, list) and statuses:
        if not purchase_status:
            return False
        allowed = {str(x).strip().lower() for x in statuses if x is not None and str(x).strip()}
        if (purchase_status or "").strip().lower() not in allowed:
            return False

    # If explicitly marked as all_users (or nothing specified) it's fine.
    if targeting.get("all_users") is True:
        return True

    # Empty targeting means allow-all.
    if not targeting:
        return True

    # Non-empty targeting without all_users still can be valid (e.g. usernames only) and would've returned above.
    return True


def _eligible_notification_ids(db: Session, user: models.User) -> list[str]:
    now = _now()

    email = (getattr(user, "email", None) or "").strip()
    tariff, _lic = resolve_tariff(db, user.id)
    plan_id = (tariff.id or "").strip().lower()
    purchase_platform, purchase_status = _get_user_purchase_info(db, user.id)

    target_rows = (
        db.query(models.NotificationTarget.notification_id)
        .filter(models.NotificationTarget.user_id == user.id)
        .all()
    )
    target_ids = {r[0] for r in target_rows}

    q = db.query(
        models.Notification.id,
        models.Notification.in_app_enabled,
        models.Notification.targeting,
        models.Notification.audience,
        models.Notification.audience_value,
        models.Notification.created_at,
    )
    q = _is_active_window(q, now)
    q = q.order_by(models.Notification.created_at.desc())

    out: list[str] = []
    for nid, in_app_enabled, targeting_raw, audience, audience_value, _created_at in q.all():
        if in_app_enabled is False:
            continue

        targeting = _normalize_targeting(targeting_raw)
        if targeting:
            if _eligible_by_targeting(
                targeting,
                user=user,
                email=email,
                plan_id=plan_id,
                purchase_platform=purchase_platform,
                purchase_status=purchase_status,
                legacy_target_ids=target_ids,
                notification_id=nid,
            ):
                out.append(nid)
            continue

        # Legacy fallback
        a = audience.value if hasattr(audience, "value") else str(audience)
        a = (a or "").strip().lower()

        if a == models.NotificationAudience.all.value:
            out.append(nid)
            continue

        if a == models.NotificationAudience.missing_email.value:
            if not email:
                out.append(nid)
            continue

        if a == models.NotificationAudience.plan.value:
            if not plan_id:
                continue
            raw = (audience_value or "").strip().lower()
            if not raw:
                continue
            allowed = {p.strip() for p in raw.replace(";", ",").split(",") if p.strip()}
            if plan_id in allowed:
                out.append(nid)
            continue

        if a == models.NotificationAudience.users.value:
            if nid in target_ids:
                out.append(nid)
            continue

    return out


class NotificationItem(BaseModel):
    id: str
    title: str
    body: str
    link: str | None = None
    type: str | None = None
    level: str
    created_at: str
    is_read: bool


class ListNotificationsResponse(BaseModel):
    items: list[NotificationItem]
    unread_count: int


@router.get("/notifications", response_model=ListNotificationsResponse)
def list_notifications(
    limit: int = 50,
    offset: int = 0,
    user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # Auto system notifications (idempotent)
    try:
        ensure_tariff_expiry_notifications(db, user)
    except Exception:
        # Never break notifications UI due to background/system notification logic.
        pass

    if limit < 1 or limit > 200:
        raise HTTPException(status_code=400, detail="invalid limit")
    if offset < 0:
        raise HTTPException(status_code=400, detail="invalid offset")

    ids = _eligible_notification_ids(db, user)
    if not ids:
        return ListNotificationsResponse(items=[], unread_count=0)

    # Page
    page_ids = ids[offset : offset + limit]
    if not page_ids:
        return ListNotificationsResponse(items=[], unread_count=0)

    rows = (
        db.query(models.Notification)
        .filter(models.Notification.id.in_(page_ids))
        .all()
    )
    by_id = {n.id: n for n in rows}

    read_rows = (
        db.query(models.NotificationRead.notification_id)
        .filter(models.NotificationRead.user_id == user.id)
        .filter(models.NotificationRead.notification_id.in_(page_ids))
        .all()
    )
    read_ids = {r[0] for r in read_rows}

    # unread_count for all eligible
    unread_count = (
        db.query(models.Notification.id)
        .filter(models.Notification.id.in_(ids))
        .filter(
            ~models.Notification.id.in_(
                db.query(models.NotificationRead.notification_id)
                .filter(models.NotificationRead.user_id == user.id)
                .subquery()
            )
        )
        .count()
    )

    items: list[NotificationItem] = []
    for nid in page_ids:
        n = by_id.get(nid)
        if not n:
            continue
        items.append(
            NotificationItem(
                id=n.id,
                title=n.title,
                body=n.body,
                link=n.link,
                type=(n.type.value if hasattr(n.type, "value") else (str(n.type) if n.type is not None else None)),
                level=(n.level.value if hasattr(n.level, "value") else str(n.level)),
                created_at=n.created_at.isoformat() if n.created_at else "",
                is_read=n.id in read_ids,
            )
        )

    return ListNotificationsResponse(items=items, unread_count=unread_count)


class UnreadCountResponse(BaseModel):
    unread_count: int


@router.get("/notifications/unread_count", response_model=UnreadCountResponse)
def unread_count(
    user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # Auto system notifications (idempotent)
    try:
        ensure_tariff_expiry_notifications(db, user)
    except Exception:
        pass

    ids = _eligible_notification_ids(db, user)
    if not ids:
        return UnreadCountResponse(unread_count=0)

    unread = (
        db.query(models.Notification.id)
        .filter(models.Notification.id.in_(ids))
        .filter(
            ~models.Notification.id.in_(
                db.query(models.NotificationRead.notification_id)
                .filter(models.NotificationRead.user_id == user.id)
                .subquery()
            )
        )
        .count()
    )
    return UnreadCountResponse(unread_count=unread)


class MarkReadResponse(BaseModel):
    status: str = "ok"


@router.post("/notifications/{notification_id}/read", response_model=MarkReadResponse)
def mark_read(
    notification_id: str,
    user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # ensure exists and eligible
    ids = _eligible_notification_ids(db, user)
    if notification_id not in set(ids):
        raise HTTPException(status_code=404, detail="notification not found")

    existing = (
        db.query(models.NotificationRead)
        .filter(models.NotificationRead.user_id == user.id)
        .filter(models.NotificationRead.notification_id == notification_id)
        .first()
    )
    if existing:
        return MarkReadResponse()

    db.add(
        models.NotificationRead(
            user_id=user.id,
            notification_id=notification_id,
            read_at=_now(),
        )
    )
    db.commit()
    return MarkReadResponse()


@router.post("/notifications/read_all", response_model=MarkReadResponse)
def mark_all_read(
    user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    ids = _eligible_notification_ids(db, user)
    if not ids:
        return MarkReadResponse()

    existing = (
        db.query(models.NotificationRead.notification_id)
        .filter(models.NotificationRead.user_id == user.id)
        .filter(models.NotificationRead.notification_id.in_(ids))
        .all()
    )
    existing_ids = {r[0] for r in existing}

    now = _now()
    to_add = [
        models.NotificationRead(user_id=user.id, notification_id=nid, read_at=now)
        for nid in ids
        if nid not in existing_ids
    ]
    if to_add:
        db.add_all(to_add)
        db.commit()
    return MarkReadResponse()
