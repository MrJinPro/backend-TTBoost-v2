import logging
from datetime import datetime, timedelta, date

from sqlalchemy import case
from sqlalchemy.orm import Session

from app.db import models

logger = logging.getLogger(__name__)


def _norm_username(s: str | None) -> str:
    return (s or "").strip().lstrip("@").lower()


def _dialect_name(db: Session) -> str:
    try:
        bind = db.get_bind()
        return getattr(getattr(bind, "dialect", None), "name", "") or ""
    except Exception:
        return ""


def _upsert_donor_stats(
    db: Session,
    *,
    streamer_id: str,
    donor_username: str,
    day_utc: date,
    gift_coins: int,
    gift_count: int,
) -> None:
    donor_username = _norm_username(donor_username)
    if not donor_username:
        return

    table = models.DonorStats.__table__
    now = datetime.utcnow()

    values = {
        "streamer_id": streamer_id,
        "donor_username": donor_username,
        "total_coins": int(gift_coins),
        "total_gifts": int(gift_count),
        "today_date": day_utc,
        "today_coins": int(gift_coins),
        "last_7d_anchor": day_utc,
        "last_7d_coins": int(gift_coins),
        "last_30d_anchor": day_utc,
        "last_30d_coins": int(gift_coins),
        "updated_at": now,
    }

    dialect = _dialect_name(db)
    insert_stmt = None
    try:
        if dialect == "postgresql":
            from sqlalchemy.dialects.postgresql import insert as pg_insert

            insert_stmt = pg_insert(table).values(**values)
        elif dialect == "sqlite":
            from sqlalchemy.dialects.sqlite import insert as sqlite_insert

            insert_stmt = sqlite_insert(table).values(**values)
        else:
            from sqlalchemy import insert

            insert_stmt = insert(table).values(**values)
    except Exception:
        from sqlalchemy import insert

        insert_stmt = insert(table).values(**values)

    if hasattr(insert_stmt, "on_conflict_do_update"):
        excluded = insert_stmt.excluded
        update_set = {
            "total_coins": table.c.total_coins + excluded.total_coins,
            "total_gifts": table.c.total_gifts + excluded.total_gifts,
            "today_date": excluded.today_date,
            "today_coins": case(
                (table.c.today_date == excluded.today_date, table.c.today_coins + excluded.today_coins),
                else_=excluded.today_coins,
            ),
            "last_7d_anchor": excluded.last_7d_anchor,
            "last_7d_coins": case(
                (table.c.last_7d_anchor == excluded.last_7d_anchor, table.c.last_7d_coins + excluded.last_7d_coins),
                else_=excluded.last_7d_coins,
            ),
            "last_30d_anchor": excluded.last_30d_anchor,
            "last_30d_coins": case(
                (table.c.last_30d_anchor == excluded.last_30d_anchor, table.c.last_30d_coins + excluded.last_30d_coins),
                else_=excluded.last_30d_coins,
            ),
            "updated_at": excluded.updated_at,
        }

        stmt = insert_stmt.on_conflict_do_update(
            index_elements=[table.c.streamer_id, table.c.donor_username],
            set_=update_set,
        )
        db.execute(stmt)
        return

    # Fallback: update-then-insert (best-effort, no hard guarantee under races)
    updated = (
        db.query(models.DonorStats)
        .filter(models.DonorStats.streamer_id == streamer_id)
        .filter(models.DonorStats.donor_username == donor_username)
        .first()
    )
    if updated:
        updated.total_coins += int(gift_coins)
        updated.total_gifts += int(gift_count)
        if updated.today_date == day_utc:
            updated.today_coins += int(gift_coins)
        else:
            updated.today_date = day_utc
            updated.today_coins = int(gift_coins)
        if updated.last_7d_anchor == day_utc:
            updated.last_7d_coins += int(gift_coins)
        else:
            updated.last_7d_anchor = day_utc
            updated.last_7d_coins = int(gift_coins)
        if updated.last_30d_anchor == day_utc:
            updated.last_30d_coins += int(gift_coins)
        else:
            updated.last_30d_anchor = day_utc
            updated.last_30d_coins = int(gift_coins)
        updated.updated_at = now
        db.add(updated)
    else:
        db.add(models.DonorStats(**values))


def _upsert_donor_stats_tt(
    db: Session,
    *,
    streamer_tiktok_username: str,
    donor_username: str,
    day_utc: date,
    gift_coins: int,
    gift_count: int,
) -> None:
    streamer_tiktok_username = _norm_username(streamer_tiktok_username)
    donor_username = _norm_username(donor_username)
    if not streamer_tiktok_username or not donor_username:
        return

    table = models.DonorStatsTikTok.__table__
    now = datetime.utcnow()

    values = {
        "streamer_tiktok_username": streamer_tiktok_username,
        "donor_username": donor_username,
        "total_coins": int(gift_coins),
        "total_gifts": int(gift_count),
        "today_date": day_utc,
        "today_coins": int(gift_coins),
        "last_7d_anchor": day_utc,
        "last_7d_coins": int(gift_coins),
        "last_30d_anchor": day_utc,
        "last_30d_coins": int(gift_coins),
        "updated_at": now,
    }

    dialect = _dialect_name(db)
    insert_stmt = None
    try:
        if dialect == "postgresql":
            from sqlalchemy.dialects.postgresql import insert as pg_insert

            insert_stmt = pg_insert(table).values(**values)
        elif dialect == "sqlite":
            from sqlalchemy.dialects.sqlite import insert as sqlite_insert

            insert_stmt = sqlite_insert(table).values(**values)
        else:
            from sqlalchemy import insert

            insert_stmt = insert(table).values(**values)
    except Exception:
        from sqlalchemy import insert

        insert_stmt = insert(table).values(**values)

    if hasattr(insert_stmt, "on_conflict_do_update"):
        excluded = insert_stmt.excluded
        update_set = {
            "total_coins": table.c.total_coins + excluded.total_coins,
            "total_gifts": table.c.total_gifts + excluded.total_gifts,
            "today_date": excluded.today_date,
            "today_coins": case(
                (table.c.today_date == excluded.today_date, table.c.today_coins + excluded.today_coins),
                else_=excluded.today_coins,
            ),
            "last_7d_anchor": excluded.last_7d_anchor,
            "last_7d_coins": case(
                (table.c.last_7d_anchor == excluded.last_7d_anchor, table.c.last_7d_coins + excluded.last_7d_coins),
                else_=excluded.last_7d_coins,
            ),
            "last_30d_anchor": excluded.last_30d_anchor,
            "last_30d_coins": case(
                (table.c.last_30d_anchor == excluded.last_30d_anchor, table.c.last_30d_coins + excluded.last_30d_coins),
                else_=excluded.last_30d_coins,
            ),
            "updated_at": excluded.updated_at,
        }

        stmt = insert_stmt.on_conflict_do_update(
            index_elements=[table.c.streamer_tiktok_username, table.c.donor_username],
            set_=update_set,
        )
        db.execute(stmt)
        return

    updated = (
        db.query(models.DonorStatsTikTok)
        .filter(models.DonorStatsTikTok.streamer_tiktok_username == streamer_tiktok_username)
        .filter(models.DonorStatsTikTok.donor_username == donor_username)
        .first()
    )
    if updated:
        updated.total_coins += int(gift_coins)
        updated.total_gifts += int(gift_count)
        if updated.today_date == day_utc:
            updated.today_coins += int(gift_coins)
        else:
            updated.today_date = day_utc
            updated.today_coins = int(gift_coins)
        if updated.last_7d_anchor == day_utc:
            updated.last_7d_coins += int(gift_coins)
        else:
            updated.last_7d_anchor = day_utc
            updated.last_7d_coins = int(gift_coins)
        if updated.last_30d_anchor == day_utc:
            updated.last_30d_coins += int(gift_coins)
        else:
            updated.last_30d_anchor = day_utc
            updated.last_30d_coins = int(gift_coins)
        updated.updated_at = now
        db.add(updated)
    else:
        db.add(models.DonorStatsTikTok(**values))


def _upsert_streamer_stats(
    db: Session,
    *,
    streamer_id: str,
    day_utc: date,
    gift_coins: int,
    gift_count: int,
) -> None:
    table = models.StreamerStats.__table__
    now = datetime.utcnow()

    values = {
        "streamer_id": streamer_id,
        "total_coins": int(gift_coins),
        "total_gifts": int(gift_count),
        "today_date": day_utc,
        "today_coins": int(gift_coins),
        "last_7d_anchor": day_utc,
        "last_7d_coins": int(gift_coins),
        "last_30d_anchor": day_utc,
        "last_30d_coins": int(gift_coins),
        "updated_at": now,
    }

    dialect = _dialect_name(db)
    insert_stmt = None
    try:
        if dialect == "postgresql":
            from sqlalchemy.dialects.postgresql import insert as pg_insert

            insert_stmt = pg_insert(table).values(**values)
        elif dialect == "sqlite":
            from sqlalchemy.dialects.sqlite import insert as sqlite_insert

            insert_stmt = sqlite_insert(table).values(**values)
        else:
            from sqlalchemy import insert

            insert_stmt = insert(table).values(**values)
    except Exception:
        from sqlalchemy import insert

        insert_stmt = insert(table).values(**values)

    if hasattr(insert_stmt, "on_conflict_do_update"):
        excluded = insert_stmt.excluded
        update_set = {
            "total_coins": table.c.total_coins + excluded.total_coins,
            "total_gifts": table.c.total_gifts + excluded.total_gifts,
            "today_date": excluded.today_date,
            "today_coins": case(
                (table.c.today_date == excluded.today_date, table.c.today_coins + excluded.today_coins),
                else_=excluded.today_coins,
            ),
            "last_7d_anchor": excluded.last_7d_anchor,
            "last_7d_coins": case(
                (table.c.last_7d_anchor == excluded.last_7d_anchor, table.c.last_7d_coins + excluded.last_7d_coins),
                else_=excluded.last_7d_coins,
            ),
            "last_30d_anchor": excluded.last_30d_anchor,
            "last_30d_coins": case(
                (table.c.last_30d_anchor == excluded.last_30d_anchor, table.c.last_30d_coins + excluded.last_30d_coins),
                else_=excluded.last_30d_coins,
            ),
            "updated_at": excluded.updated_at,
        }

        stmt = insert_stmt.on_conflict_do_update(
            index_elements=[table.c.streamer_id],
            set_=update_set,
        )
        db.execute(stmt)
        return

    updated = db.query(models.StreamerStats).filter(models.StreamerStats.streamer_id == streamer_id).first()
    if updated:
        updated.total_coins += int(gift_coins)
        updated.total_gifts += int(gift_count)
        if updated.today_date == day_utc:
            updated.today_coins += int(gift_coins)
        else:
            updated.today_date = day_utc
            updated.today_coins = int(gift_coins)
        if updated.last_7d_anchor == day_utc:
            updated.last_7d_coins += int(gift_coins)
        else:
            updated.last_7d_anchor = day_utc
            updated.last_7d_coins = int(gift_coins)
        if updated.last_30d_anchor == day_utc:
            updated.last_30d_coins += int(gift_coins)
        else:
            updated.last_30d_anchor = day_utc
            updated.last_30d_coins = int(gift_coins)
        updated.updated_at = now
        db.add(updated)
    else:
        db.add(models.StreamerStats(**values))


def _upsert_streamer_stats_tt(
    db: Session,
    *,
    streamer_tiktok_username: str,
    day_utc: date,
    gift_coins: int,
    gift_count: int,
) -> None:
    streamer_tiktok_username = _norm_username(streamer_tiktok_username)
    if not streamer_tiktok_username:
        return

    table = models.StreamerStatsTikTok.__table__
    now = datetime.utcnow()

    values = {
        "streamer_tiktok_username": streamer_tiktok_username,
        "total_coins": int(gift_coins),
        "total_gifts": int(gift_count),
        "today_date": day_utc,
        "today_coins": int(gift_coins),
        "last_7d_anchor": day_utc,
        "last_7d_coins": int(gift_coins),
        "last_30d_anchor": day_utc,
        "last_30d_coins": int(gift_coins),
        "updated_at": now,
    }

    dialect = _dialect_name(db)
    insert_stmt = None
    try:
        if dialect == "postgresql":
            from sqlalchemy.dialects.postgresql import insert as pg_insert

            insert_stmt = pg_insert(table).values(**values)
        elif dialect == "sqlite":
            from sqlalchemy.dialects.sqlite import insert as sqlite_insert

            insert_stmt = sqlite_insert(table).values(**values)
        else:
            from sqlalchemy import insert

            insert_stmt = insert(table).values(**values)
    except Exception:
        from sqlalchemy import insert

        insert_stmt = insert(table).values(**values)

    if hasattr(insert_stmt, "on_conflict_do_update"):
        excluded = insert_stmt.excluded
        update_set = {
            "total_coins": table.c.total_coins + excluded.total_coins,
            "total_gifts": table.c.total_gifts + excluded.total_gifts,
            "today_date": excluded.today_date,
            "today_coins": case(
                (table.c.today_date == excluded.today_date, table.c.today_coins + excluded.today_coins),
                else_=excluded.today_coins,
            ),
            "last_7d_anchor": excluded.last_7d_anchor,
            "last_7d_coins": case(
                (table.c.last_7d_anchor == excluded.last_7d_anchor, table.c.last_7d_coins + excluded.last_7d_coins),
                else_=excluded.last_7d_coins,
            ),
            "last_30d_anchor": excluded.last_30d_anchor,
            "last_30d_coins": case(
                (table.c.last_30d_anchor == excluded.last_30d_anchor, table.c.last_30d_coins + excluded.last_30d_coins),
                else_=excluded.last_30d_coins,
            ),
            "updated_at": excluded.updated_at,
        }

        stmt = insert_stmt.on_conflict_do_update(
            index_elements=[table.c.streamer_tiktok_username],
            set_=update_set,
        )
        db.execute(stmt)
        return

    updated = (
        db.query(models.StreamerStatsTikTok)
        .filter(models.StreamerStatsTikTok.streamer_tiktok_username == streamer_tiktok_username)
        .first()
    )
    if updated:
        updated.total_coins += int(gift_coins)
        updated.total_gifts += int(gift_count)
        if updated.today_date == day_utc:
            updated.today_coins += int(gift_coins)
        else:
            updated.today_date = day_utc
            updated.today_coins = int(gift_coins)
        if updated.last_7d_anchor == day_utc:
            updated.last_7d_coins += int(gift_coins)
        else:
            updated.last_7d_anchor = day_utc
            updated.last_7d_coins = int(gift_coins)
        if updated.last_30d_anchor == day_utc:
            updated.last_30d_coins += int(gift_coins)
        else:
            updated.last_30d_anchor = day_utc
            updated.last_30d_coins = int(gift_coins)
        updated.updated_at = now
        db.add(updated)
    else:
        db.add(models.StreamerStatsTikTok(**values))


def record_gift_and_update_stats(
    db: Session,
    *,
    streamer_id: str,
    streamer_tiktok_username: str | None = None,
    donor_username: str,
    gift_id: str | None,
    gift_name: str | None,
    gift_count: int,
    gift_coins: int,
    created_at_utc: datetime | None = None,
) -> None:
    created_at_utc = created_at_utc or datetime.utcnow()
    day_utc = created_at_utc.date()

    donor_username_norm = _norm_username(donor_username)
    if not donor_username_norm:
        return

    try:
        streamer_tt = _norm_username(streamer_tiktok_username)
        if streamer_tt:
            db.add(
                models.GiftEventTikTok(
                    streamer_tiktok_username=streamer_tt,
                    donor_username=donor_username_norm,
                    gift_id=str(gift_id) if gift_id is not None else None,
                    gift_name=str(gift_name) if gift_name is not None else None,
                    gift_count=int(gift_count or 0),
                    gift_coins=int(gift_coins or 0),
                    day=day_utc,
                    created_at=created_at_utc,
                )
            )
            _upsert_donor_stats_tt(
                db,
                streamer_tiktok_username=streamer_tt,
                donor_username=donor_username_norm,
                day_utc=day_utc,
                gift_coins=int(gift_coins or 0),
                gift_count=int(gift_count or 0),
            )
            _upsert_streamer_stats_tt(
                db,
                streamer_tiktok_username=streamer_tt,
                day_utc=day_utc,
                gift_coins=int(gift_coins or 0),
                gift_count=int(gift_count or 0),
            )
        else:
            db.add(
                models.GiftEvent(
                    streamer_id=streamer_id,
                    donor_username=donor_username_norm,
                    gift_id=str(gift_id) if gift_id is not None else None,
                    gift_name=str(gift_name) if gift_name is not None else None,
                    gift_count=int(gift_count or 0),
                    gift_coins=int(gift_coins or 0),
                    day=day_utc,
                    created_at=created_at_utc,
                )
            )

            _upsert_donor_stats(
                db,
                streamer_id=streamer_id,
                donor_username=donor_username_norm,
                day_utc=day_utc,
                gift_coins=int(gift_coins or 0),
                gift_count=int(gift_count or 0),
            )
            _upsert_streamer_stats(
                db,
                streamer_id=streamer_id,
                day_utc=day_utc,
                gift_coins=int(gift_coins or 0),
                gift_count=int(gift_count or 0),
            )

        db.commit()
    except Exception:
        db.rollback()
        logger.exception("Failed to record gift stats")
