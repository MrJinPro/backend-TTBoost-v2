from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.db import models
from app.services.plans import resolve_tariff


def _now() -> datetime:
    return datetime.utcnow()


def _best_expiry(db: Session, user_id: str):
    """Return (expires_at, source) best-effort.

    source: "license" | "store" | None
    """
    _tariff, lic = resolve_tariff(db, user_id)
    if lic and lic.expires_at:
        return lic.expires_at, "license"

    sp = (
        db.query(models.StorePurchase)
        .filter(models.StorePurchase.user_id == user_id)
        .filter(models.StorePurchase.expires_at.is_not(None))
        .order_by(models.StorePurchase.updated_at.desc())
        .order_by(models.StorePurchase.created_at.desc())
        .first()
    )
    if sp and sp.expires_at:
        return sp.expires_at, "store"

    return None, None


def ensure_tariff_expiry_notifications(db: Session, user: models.User) -> None:
    """Idempotently creates per-user system notifications about subscription expiry."""

    expires_at, source = _best_expiry(db, user.id)
    if not expires_at:
        return

    now = _now()

    # If expiry is far in the future, do nothing.
    delta = expires_at - now

    state: str | None = None
    level: models.NotificationLevel = models.NotificationLevel.info

    if delta <= timedelta(seconds=0):
        state = "expired"
        level = models.NotificationLevel.warning
    elif delta <= timedelta(days=1):
        state = "expires_1d"
        level = models.NotificationLevel.warning
    elif delta <= timedelta(days=3):
        state = "expires_3d"
        level = models.NotificationLevel.info

    if not state:
        return

    expires_date = expires_at.date().isoformat()
    dedupe_key = f"system:tariff:{state}:{source}:{user.id}:{expires_date}"

    exists = db.query(models.Notification.id).filter(models.Notification.dedupe_key == dedupe_key).first()
    if exists:
        return

    if state == "expired":
        title = "Подписка истекла"
        body = "Срок подписки истёк. Продлите подписку, чтобы продолжить использовать функции тарифа."
    elif state == "expires_1d":
        title = "Подписка скоро истечёт"
        body = "До окончания подписки осталось меньше 1 дня. Продлите подписку заранее, чтобы не потерять доступ."
    else:
        title = "Подписка скоро истечёт"
        body = "До окончания подписки осталось меньше 3 дней. Продлите подписку заранее."

    # Keep notification visible for some time.
    ends_at = now + timedelta(days=14)

    n = models.Notification(
        dedupe_key=dedupe_key,
        title=title,
        body=body,
        link=None,
        level=level,
        type=models.NotificationType.system,
        targeting={"user_ids": [user.id]},
        in_app_enabled=True,
        push_enabled=False,
        created_by_user_id=None,
        starts_at=now,
        ends_at=ends_at,
        created_at=now,
        # Legacy fields for compatibility
        audience=models.NotificationAudience.users,
        audience_value=None,
    )

    db.add(n)
    db.commit()
