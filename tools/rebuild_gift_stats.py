"""Nightly rebuild of gift stats.

Runs expensive GROUP BY over gift_events and rewrites donor_stats + streamer_stats.
Intended to be executed by cron once per day (UTC).

Usage:
    python tools/rebuild_gift_stats.py
"""

from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import case, func, select

from app.db import models
from app.db.database import SessionLocal


def main() -> None:
    now = datetime.utcnow()
    today = now.date()
    yesterday = today - timedelta(days=1)
    day7 = today - timedelta(days=6)
    day30 = today - timedelta(days=29)

    db = SessionLocal()
    try:
        # donor_stats
        db.query(models.DonorStats).delete()

        donor_stmt = (
            select(
                models.GiftEvent.streamer_id.label("streamer_id"),
                models.GiftEvent.donor_username.label("donor_username"),
                func.coalesce(func.sum(models.GiftEvent.gift_coins), 0).label("total_coins"),
                func.coalesce(func.sum(models.GiftEvent.gift_count), 0).label("total_gifts"),
                func.coalesce(
                    func.sum(case((models.GiftEvent.day == today, models.GiftEvent.gift_coins), else_=0)),
                    0,
                ).label("today_coins"),
                func.coalesce(
                    func.sum(case((models.GiftEvent.day == yesterday, models.GiftEvent.gift_coins), else_=0)),
                    0,
                ).label("yesterday_coins"),
                func.coalesce(
                    func.sum(case((models.GiftEvent.day >= day7, models.GiftEvent.gift_coins), else_=0)),
                    0,
                ).label("last_7d_coins"),
                func.coalesce(
                    func.sum(case((models.GiftEvent.day >= day30, models.GiftEvent.gift_coins), else_=0)),
                    0,
                ).label("last_30d_coins"),
            )
            .group_by(models.GiftEvent.streamer_id, models.GiftEvent.donor_username)
        )

        for row in db.execute(donor_stmt).all():
            db.add(
                models.DonorStats(
                    streamer_id=row.streamer_id,
                    donor_username=row.donor_username,
                    total_coins=int(row.total_coins or 0),
                    total_gifts=int(row.total_gifts or 0),
                    today_date=today,
                    today_coins=int(row.today_coins or 0),
                    yesterday_date=yesterday,
                    yesterday_coins=int(row.yesterday_coins or 0),
                    last_7d_anchor=today,
                    last_7d_coins=int(row.last_7d_coins or 0),
                    last_30d_anchor=today,
                    last_30d_coins=int(row.last_30d_coins or 0),
                    updated_at=now,
                )
            )

        # streamer_stats
        db.query(models.StreamerStats).delete()

        streamer_stmt = (
            select(
                models.GiftEvent.streamer_id.label("streamer_id"),
                func.coalesce(func.sum(models.GiftEvent.gift_coins), 0).label("total_coins"),
                func.coalesce(func.sum(models.GiftEvent.gift_count), 0).label("total_gifts"),
                func.coalesce(
                    func.sum(case((models.GiftEvent.day == today, models.GiftEvent.gift_coins), else_=0)),
                    0,
                ).label("today_coins"),
                func.coalesce(
                    func.sum(case((models.GiftEvent.day == yesterday, models.GiftEvent.gift_coins), else_=0)),
                    0,
                ).label("yesterday_coins"),
                func.coalesce(
                    func.sum(case((models.GiftEvent.day >= day7, models.GiftEvent.gift_coins), else_=0)),
                    0,
                ).label("last_7d_coins"),
                func.coalesce(
                    func.sum(case((models.GiftEvent.day >= day30, models.GiftEvent.gift_coins), else_=0)),
                    0,
                ).label("last_30d_coins"),
            )
            .group_by(models.GiftEvent.streamer_id)
        )

        for row in db.execute(streamer_stmt).all():
            db.add(
                models.StreamerStats(
                    streamer_id=row.streamer_id,
                    total_coins=int(row.total_coins or 0),
                    total_gifts=int(row.total_gifts or 0),
                    today_date=today,
                    today_coins=int(row.today_coins or 0),
                    yesterday_date=yesterday,
                    yesterday_coins=int(row.yesterday_coins or 0),
                    last_7d_anchor=today,
                    last_7d_coins=int(row.last_7d_coins or 0),
                    last_30d_anchor=today,
                    last_30d_coins=int(row.last_30d_coins or 0),
                    updated_at=now,
                )
            )

        db.commit()
        print("OK")
    finally:
        db.close()


if __name__ == "__main__":
    main()
