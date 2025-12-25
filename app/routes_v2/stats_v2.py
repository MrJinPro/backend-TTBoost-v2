from datetime import date, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

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


def _period_to_column(period: str) -> tuple[str, date | None]:
    p = (period or "").strip().lower()
    today = datetime.utcnow().date()

    if p in ("today", "utc_today"):
        return "today_coins", today
    if p == "yesterday":
        return "yesterday_coins", today - timedelta(days=1)
    if p in ("7d", "last_7d", "week"):
        return "last_7d_coins", today
    if p in ("30d", "last_30d", "month"):
        return "last_30d_coins", today
    if p in ("all", "all_time", "total"):
        return "total_coins", None

    raise HTTPException(status_code=400, detail="invalid period")


@router.get("/stats/overview")
def stats_overview(
    user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    row = db.query(models.StreamerStats).filter(models.StreamerStats.streamer_id == user.id).first()
    if not row:
        return {
            "total_coins": 0,
            "total_gifts": 0,
            "today_utc": 0,
            "yesterday_utc": 0,
            "last_7d": 0,
            "last_30d": 0,
            "updated_at": None,
        }

    return {
        "total_coins": int(row.total_coins or 0),
        "total_gifts": int(row.total_gifts or 0),
        "today_utc": int(row.today_coins or 0) if row.today_date == datetime.utcnow().date() else int(row.today_coins or 0),
        "yesterday_utc": int(row.yesterday_coins or 0),
        "last_7d": int(row.last_7d_coins or 0),
        "last_30d": int(row.last_30d_coins or 0),
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


@router.get("/stats/top-donors")
def stats_top_donors(
    period: str = "today",
    limit: int = 5,
    user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if limit <= 0:
        raise HTTPException(status_code=400, detail="limit must be > 0")
    if limit > 50:
        limit = 50

    col_name, anchor = _period_to_column(period)

    q = db.query(models.DonorStats).filter(models.DonorStats.streamer_id == user.id)

    # Для today/yesterday используем date-колонки, чтобы не показывать устаревшие значения.
    if col_name == "today_coins":
        q = q.filter(models.DonorStats.today_date == datetime.utcnow().date())
    elif col_name == "yesterday_coins":
        q = q.filter(models.DonorStats.yesterday_date == (datetime.utcnow().date() - timedelta(days=1)))
    elif col_name == "last_7d_coins":
        q = q.filter(models.DonorStats.last_7d_anchor == (anchor or datetime.utcnow().date()))
    elif col_name == "last_30d_coins":
        q = q.filter(models.DonorStats.last_30d_anchor == (anchor or datetime.utcnow().date()))

    col = getattr(models.DonorStats, col_name)
    rows = q.order_by(col.desc()).limit(limit).all()

    donors = []
    for r in rows:
        donors.append(
            {
                "donor_username": r.donor_username,
                "coins": int(getattr(r, col_name) or 0),
                "total_coins": int(r.total_coins or 0),
                "total_gifts": int(r.total_gifts or 0),
            }
        )

    return {
        "period": period,
        "limit": limit,
        "donors": donors,
    }


@router.get("/stats/donor/{donor_username}")
def stats_donor(
    donor_username: str,
    user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    key = (donor_username or "").strip().lstrip("@").lower()
    if not key:
        raise HTTPException(status_code=400, detail="donor_username required")

    r = (
        db.query(models.DonorStats)
        .filter(models.DonorStats.streamer_id == user.id)
        .filter(models.DonorStats.donor_username == key)
        .first()
    )

    if not r:
        raise HTTPException(status_code=404, detail="donor not found")

    return {
        "donor_username": r.donor_username,
        "total_coins": int(r.total_coins or 0),
        "total_gifts": int(r.total_gifts or 0),
        "today_utc": int(r.today_coins or 0) if r.today_date == datetime.utcnow().date() else int(r.today_coins or 0),
        "yesterday_utc": int(r.yesterday_coins or 0),
        "last_7d": int(r.last_7d_coins or 0),
        "last_30d": int(r.last_30d_coins or 0),
        "updated_at": r.updated_at.isoformat() if r.updated_at else None,
    }
