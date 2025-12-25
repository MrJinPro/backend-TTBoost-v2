from __future__ import annotations

from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import or_

from app.db.database import SessionLocal
from app.db import models
from app.routes_v2.auth_v2 import get_current_user
from app.services.plans import resolve_tariff


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


def _eligible_notification_ids(db: Session, user: models.User) -> list[str]:
    now = _now()

    email = (getattr(user, "email", None) or "").strip()
    tariff, _lic = resolve_tariff(db, user.id)
    plan_id = (tariff.id or "").strip().lower()

    target_rows = (
        db.query(models.NotificationTarget.notification_id)
        .filter(models.NotificationTarget.user_id == user.id)
        .all()
    )
    target_ids = {r[0] for r in target_rows}

    q = db.query(
        models.Notification.id,
        models.Notification.audience,
        models.Notification.audience_value,
        models.Notification.created_at,
    )
    q = _is_active_window(q, now)
    q = q.order_by(models.Notification.created_at.desc())

    out: list[str] = []
    for nid, audience, audience_value, _created_at in q.all():
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
