from fastapi import APIRouter, Depends, HTTPException
import logging
import os
import shutil
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import func, or_
from datetime import datetime, timedelta, date

from app.db.database import SessionLocal
from app.db import models
from .auth_v2 import get_current_user
from app.services.plans import (
    TARIFF_FREE,
    TARIFF_ONE_MOBILE,
    TARIFF_ONE_DESKTOP,
    TARIFF_DUO,
    canonicalize_license_plan,
)

from app.services.admin_state import STATE as ADMIN_STATE
from app.routes_v2 import ws_v2


router = APIRouter()
logger = logging.getLogger(__name__)


ROLES_ORDER = [
    "user",
    "support",
    "curator",
    "moderator",
    "admin",
    "manager",
    "superadmin",
]

ROLE_ALIASES = {
    "menager": "manager",
    "super_admin": "superadmin",
    "super-admin": "superadmin",
    "super": "superadmin",
}


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _normalize_role(raw: str) -> str:
    role = (raw or "").strip().lower()
    role = ROLE_ALIASES.get(role, role)
    if role not in ROLES_ORDER:
        raise HTTPException(status_code=400, detail="invalid role")
    return role


def _role_rank(role: str | None) -> int:
    r = (role or "user").strip().lower()
    r = ROLE_ALIASES.get(r, r)
    try:
        return ROLES_ORDER.index(r)
    except ValueError:
        return 0


def require_staff_user(user: models.User = Depends(get_current_user)) -> models.User:
    # Staff: всё, что выше обычного user
    if _role_rank(user.role) <= _role_rank("user"):
        raise HTTPException(status_code=403, detail="forbidden")
    return user


def require_superadmin(user: models.User = Depends(get_current_user)) -> models.User:
    if (user.role or "user").lower() != "superadmin":
        raise HTTPException(status_code=403, detail="forbidden")
    return user


def _log_admin_action(
    db: Session,
    actor_user_id: str | None,
    action: str,
    target_user_id: str | None = None,
    before: dict | None = None,
    after: dict | None = None,
) -> None:
    try:
        db.add(
            models.AdminAction(
                actor_user_id=actor_user_id,
                action=(action or "").strip()[:80] or "unknown",
                target_user_id=target_user_id,
                before=before,
                after=after,
                created_at=datetime.utcnow(),
            )
        )
        db.flush()
    except Exception:
        # Never break business flow due to audit logging.
        pass


def _guess_platform_from_ua(ua: str | None) -> str | None:
    s = (ua or "").strip().lower()
    if not s:
        return None
    if "android" in s:
        return "android"
    if "iphone" in s or "ipad" in s or "ios" in s:
        return "ios"
    # Desktop/web fallback.
    return "desktop"


def _is_online(last_ws_at: datetime | None, ttl_seconds: int = 90) -> bool:
    if not last_ws_at:
        return False
    try:
        return (datetime.utcnow() - last_ws_at).total_seconds() <= float(ttl_seconds)
    except Exception:
        return False


class RoleItem(BaseModel):
    id: str


class RolesResponse(BaseModel):
    items: list[RoleItem]


@router.get("/roles", response_model=RolesResponse)
def list_roles(_user: models.User = Depends(require_staff_user)):
    return RolesResponse(items=[RoleItem(id=r) for r in ROLES_ORDER])


class AdminUserItem(BaseModel):
    id: str
    username: str
    email: str | None = None
    role: str
    created_at: str
    tiktok_username: str | None = None
    tariff_id: str | None = None
    tariff_name: str | None = None
    license_expires_at: str | None = None
    status: str | None = None  # active|blocked|expired
    platform: str | None = None  # android|ios|desktop|unknown
    device: str | None = None
    client_os: str | None = None
    region: str | None = None
    last_login_at: str | None = None
    last_live_at: str | None = None
    last_live_tiktok_username: str | None = None
    online_now: bool = False
    tiktok_accounts_count: int = 0
    total_gifts: int = 0
    total_coins: int = 0
    today_coins: int = 0
    last_7d_coins: int = 0
    last_30d_coins: int = 0
    top_donors: list[dict] = []
    top_donors_all: list[dict] = []
    top_donors_today: list[dict] = []
    top_donors_7d: list[dict] = []
    top_donors_30d: list[dict] = []

    top_gifts_all: list[dict] = []
    top_gifts_today: list[dict] = []
    top_gifts_7d: list[dict] = []
    top_gifts_30d: list[dict] = []
    is_banned: bool = False
    banned_at: str | None = None
    banned_reason: str | None = None


def _top_donors_by_metric(db: Session, user_ids: list[str], metric_attr: str) -> dict[str, list[dict]]:
    if not user_ids:
        return {}
    metric_col = getattr(models.DonorStats, metric_attr, None)
    if metric_col is None:
        return {str(uid): [] for uid in user_ids}

    rn = func.row_number().over(
        partition_by=models.DonorStats.streamer_id,
        order_by=metric_col.desc(),
    ).label("rn")

    sub = (
        db.query(
            models.DonorStats.streamer_id.label("streamer_id"),
            models.DonorStats.donor_username.label("donor_username"),
            models.DonorStats.total_coins.label("total_coins"),
            models.DonorStats.total_gifts.label("total_gifts"),
            metric_col.label("coins"),
            rn,
        )
        .filter(models.DonorStats.streamer_id.in_(user_ids))
        .filter(metric_col.is_not(None))
        .filter(metric_col > 0)
        .subquery()
    )

    rows = (
        db.query(sub)
        .filter(sub.c.rn <= 3)
        .order_by(sub.c.streamer_id.asc(), sub.c.coins.desc())
        .all()
    )

    out: dict[str, list[dict]] = {str(uid): [] for uid in user_ids}
    for r in rows:
        sid = str(getattr(r, "streamer_id", "") or "")
        if not sid:
            continue
        out.setdefault(sid, []).append(
            {
                "username": getattr(r, "donor_username", None),
                "coins": int(getattr(r, "coins", 0) or 0),
                "total_coins": int(getattr(r, "total_coins", 0) or 0),
                "total_gifts": int(getattr(r, "total_gifts", 0) or 0),
            }
        )
    return out


def _top_gifts(db: Session, user_ids: list[str], *, since_day: date | None) -> dict[str, list[dict]]:
    if not user_ids:
        return {}

    coins_expr = func.sum(models.GiftEvent.gift_coins * models.GiftEvent.gift_count).label("coins")
    count_expr = func.sum(models.GiftEvent.gift_count).label("count")

    q = (
        db.query(
            models.GiftEvent.streamer_id.label("streamer_id"),
            models.GiftEvent.gift_name.label("gift_name"),
            count_expr,
            coins_expr,
        )
        .filter(models.GiftEvent.streamer_id.in_(user_ids))
        .filter(models.GiftEvent.gift_name.is_not(None))
    )
    if since_day is not None:
        q = q.filter(models.GiftEvent.day >= since_day)

    agg = q.group_by(models.GiftEvent.streamer_id, models.GiftEvent.gift_name).subquery()

    rn = func.row_number().over(
        partition_by=agg.c.streamer_id,
        order_by=agg.c.coins.desc(),
    ).label("rn")

    ranked = (
        db.query(
            agg.c.streamer_id.label("streamer_id"),
            agg.c.gift_name.label("gift_name"),
            agg.c.count.label("count"),
            agg.c.coins.label("coins"),
            rn,
        )
        .subquery()
    )

    rows = (
        db.query(ranked)
        .filter(ranked.c.rn <= 3)
        .order_by(ranked.c.streamer_id.asc(), ranked.c.coins.desc())
        .all()
    )

    out: dict[str, list[dict]] = {str(uid): [] for uid in user_ids}
    for r in rows:
        sid = str(getattr(r, "streamer_id", "") or "")
        if not sid:
            continue
        out.setdefault(sid, []).append(
            {
                "name": getattr(r, "gift_name", None),
                "coins": int(getattr(r, "coins", 0) or 0),
                "count": int(getattr(r, "count", 0) or 0),
            }
        )
    return out


class ListUsersResponse(BaseModel):
    items: list[AdminUserItem]
    total: int


def _tariff_from_license_plan(plan: str | None):
    if not plan:
        return TARIFF_FREE
    try:
        pid = canonicalize_license_plan(plan)
    except Exception:
        return TARIFF_FREE
    if pid == TARIFF_ONE_MOBILE.id:
        return TARIFF_ONE_MOBILE
    if pid == TARIFF_ONE_DESKTOP.id:
        return TARIFF_ONE_DESKTOP
    if pid == TARIFF_DUO.id:
        return TARIFF_DUO
    return TARIFF_FREE


def _get_active_licenses_for_users(db: Session, user_ids: list[str]) -> dict[str, models.LicenseKey]:
    if not user_ids:
        return {}
    now = datetime.utcnow()
    rows = (
        db.query(models.LicenseKey)
        .filter(models.LicenseKey.user_id.in_(user_ids))
        .filter(models.LicenseKey.status == models.LicenseStatus.active)
        .filter((models.LicenseKey.expires_at.is_(None)) | (models.LicenseKey.expires_at >= now))
        .order_by(models.LicenseKey.user_id.asc())
        .order_by(models.LicenseKey.expires_at.is_(None).desc())
        .order_by(models.LicenseKey.expires_at.desc())
        .order_by(models.LicenseKey.issued_at.desc())
        .all()
    )

    best: dict[str, models.LicenseKey] = {}
    for lic in rows:
        if lic.user_id and lic.user_id not in best:
            best[lic.user_id] = lic
    return best


@router.get("/users", response_model=ListUsersResponse)
def list_users(
    q: str | None = None,
    tariff_id: str | None = None,
    activity: str | None = None,  # online|inactive
    inactive_days: int | None = None,
    platform: str | None = None,  # android|ios|desktop
    region: str | None = None,
    limit: int = 50,
    offset: int = 0,
    _user: models.User = Depends(require_staff_user),
    db: Session = Depends(get_db),
):
    if limit < 1 or limit > 200:
        raise HTTPException(status_code=400, detail="invalid limit")
    if offset < 0:
        raise HTTPException(status_code=400, detail="invalid offset")

    now = datetime.utcnow()

    query = db.query(models.User)
    if q:
        qq = q.strip().lower()
        query = query.filter(
            or_(
                models.User.username.ilike(f"%{qq}%"),
                models.User.email.ilike(f"%{qq}%"),
            )
        )

    # Region filter
    if region is not None and region.strip():
        rr = region.strip().lower()
        query = query.filter(func.lower(models.User.region) == rr)

    # Activity filters
    if activity is not None and activity.strip():
        a = activity.strip().lower()
        # Keep semantics simple for MVP: online = last_ws_at within 90s; inactive = last_login_at older than X days (or NULL).
        if a == "online":
            cutoff = now - timedelta(seconds=90)
            query = query.filter(models.User.last_ws_at.is_not(None)).filter(models.User.last_ws_at >= cutoff)
        elif a in ("inactive", "stale"):
            days = int(inactive_days or 30)
            if days < 1:
                days = 1
            if days > 3650:
                days = 3650
            cutoff = now - timedelta(days=days)
            query = query.filter(or_(models.User.last_login_at.is_(None), models.User.last_login_at < cutoff))

    # Explicit inactive_days (when activity filter isn't used)
    if (activity is None or not activity.strip()) and inactive_days is not None:
        days = int(inactive_days)
        if days < 1:
            days = 1
        if days > 3650:
            days = 3650
        cutoff = now - timedelta(days=days)
        query = query.filter(or_(models.User.last_login_at.is_(None), models.User.last_login_at < cutoff))

    # Platform filter (best-effort): prefer explicit client_os/client_platform, fallback to UA.
    if platform is not None and platform.strip():
        p = platform.strip().lower()
        ua_lower = func.lower(models.User.last_user_agent)
        os_lower = func.lower(models.User.last_client_os)
        plat_lower = func.lower(models.User.last_client_platform)
        is_android = ua_lower.like("%android%")
        is_ios = or_(ua_lower.like("%iphone%"), ua_lower.like("%ipad%"), ua_lower.like("%ios%"))
        if p == "android":
            query = query.filter(or_(os_lower == "android", is_android))
        elif p == "ios":
            query = query.filter(or_(os_lower == "ios", is_ios))
        elif p == "desktop":
            query = query.filter(or_(plat_lower == "desktop", models.User.last_user_agent.is_(None), (~is_android & ~is_ios)))

    # Tariff filter (based on active entitlement licenses)
    if tariff_id is not None and tariff_id.strip():
        tid = tariff_id.strip().lower()
        paid_plans = [TARIFF_ONE_MOBILE.id, TARIFF_ONE_DESKTOP.id, TARIFF_DUO.id]
        paid_license_plans = ["nova_streamer_one_mobile", "nova_streamer_one_desktop", "nova_streamer_duo"]

        active_lic = (
            db.query(models.LicenseKey.user_id)
            .filter(models.LicenseKey.status == models.LicenseStatus.active)
            .filter((models.LicenseKey.expires_at.is_(None)) | (models.LicenseKey.expires_at >= now))
        )

        if tid == TARIFF_ONE_MOBILE.id:
            query = query.filter(models.User.id.in_(active_lic.filter(models.LicenseKey.plan == "nova_streamer_one_mobile")))
        elif tid == TARIFF_ONE_DESKTOP.id:
            query = query.filter(models.User.id.in_(active_lic.filter(models.LicenseKey.plan == "nova_streamer_one_desktop")))
        elif tid == TARIFF_DUO.id:
            query = query.filter(models.User.id.in_(active_lic.filter(models.LicenseKey.plan == "nova_streamer_duo")))
        elif tid == TARIFF_FREE.id:
            # Free = no active paid entitlement.
            query = query.filter(models.User.id.notin_(active_lic.filter(models.LicenseKey.plan.in_(paid_license_plans))))

    total = query.count()
    rows = (
        query.order_by(models.User.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    user_ids = [u.id for u in rows]
    best_lic = _get_active_licenses_for_users(db, user_ids)

    # Ever had paid plan? (for expired status)
    paid_license_plans = ["nova_streamer_one_mobile", "nova_streamer_one_desktop", "nova_streamer_duo"]
    paid_user_ids = {
        r[0]
        for r in (
            db.query(models.LicenseKey.user_id)
            .filter(models.LicenseKey.user_id.in_(user_ids))
            .filter(models.LicenseKey.plan.in_(paid_license_plans))
            .distinct()
            .all()
        )
        if r and r[0]
    }

    # TikTok accounts count
    tiktok_counts = {
        uid: int(cnt or 0)
        for (uid, cnt) in (
            db.query(models.UserTikTokAccount.user_id, func.count(models.UserTikTokAccount.id))
            .filter(models.UserTikTokAccount.user_id.in_(user_ids))
            .group_by(models.UserTikTokAccount.user_id)
            .all()
        )
    }

    # Last LIVE session per user
    last_live: dict[str, tuple[datetime | None, str | None]] = {}
    try:
        ss_rows = (
            db.query(models.StreamSession)
            .filter(models.StreamSession.user_id.in_(user_ids))
            .order_by(models.StreamSession.started_at.desc())
            .all()
        )
        for ss in ss_rows:
            uid = getattr(ss, "user_id", None)
            if not uid or uid in last_live:
                continue
            last_live[str(uid)] = (getattr(ss, "started_at", None), getattr(ss, "tiktok_username", None))
    except Exception:
        last_live = {}

    # Streamer gift stats
    streamer_stats: dict[str, models.StreamerStats] = {}
    try:
        ss = (
            db.query(models.StreamerStats)
            .filter(models.StreamerStats.streamer_id.in_(user_ids))
            .all()
        )
        streamer_stats = {str(s.streamer_id): s for s in ss if getattr(s, "streamer_id", None)}
    except Exception:
        streamer_stats = {}

    # Donor analytics (top-3) using window functions
    try:
        top_donors_all_by_user = _top_donors_by_metric(db, user_ids, "total_coins")
        top_donors_today_by_user = _top_donors_by_metric(db, user_ids, "today_coins")
        top_donors_7d_by_user = _top_donors_by_metric(db, user_ids, "last_7d_coins")
        top_donors_30d_by_user = _top_donors_by_metric(db, user_ids, "last_30d_coins")
    except Exception:
        top_donors_all_by_user = {str(uid): [] for uid in user_ids}
        top_donors_today_by_user = {str(uid): [] for uid in user_ids}
        top_donors_7d_by_user = {str(uid): [] for uid in user_ids}
        top_donors_30d_by_user = {str(uid): [] for uid in user_ids}

    # Gift analytics (top-3) by coins, based on raw gift_events
    today = date.today()
    try:
        top_gifts_all_by_user = _top_gifts(db, user_ids, since_day=None)
        top_gifts_today_by_user = _top_gifts(db, user_ids, since_day=today)
        top_gifts_7d_by_user = _top_gifts(db, user_ids, since_day=(today - timedelta(days=6)))
        top_gifts_30d_by_user = _top_gifts(db, user_ids, since_day=(today - timedelta(days=29)))
    except Exception:
        top_gifts_all_by_user = {str(uid): [] for uid in user_ids}
        top_gifts_today_by_user = {str(uid): [] for uid in user_ids}
        top_gifts_7d_by_user = {str(uid): [] for uid in user_ids}
        top_gifts_30d_by_user = {str(uid): [] for uid in user_ids}

    def _platform_for_user(u: models.User) -> str:
        os_hint = (getattr(u, "last_client_os", None) or "").strip().lower()
        if os_hint in ("android", "ios"):
            return os_hint
        ua_guess = _guess_platform_from_ua(getattr(u, "last_user_agent", None))
        return ua_guess or "unknown"

    return ListUsersResponse(
        total=total,
        items=[
            AdminUserItem(
                id=u.id,
                username=u.username,
                email=getattr(u, "email", None),
                role=(u.role or "user"),
                created_at=u.created_at.isoformat() if u.created_at else "",
                tiktok_username=u.tiktok_username,
                tariff_id=_tariff_from_license_plan(best_lic.get(u.id).plan if best_lic.get(u.id) else None).id,
                tariff_name=_tariff_from_license_plan(best_lic.get(u.id).plan if best_lic.get(u.id) else None).name,
                license_expires_at=(
                    best_lic.get(u.id).expires_at.isoformat()
                    if (best_lic.get(u.id) and best_lic.get(u.id).expires_at)
                    else None
                ),
                status=(
                    "blocked"
                    if bool(getattr(u, "is_banned", False))
                    else (
                        "expired"
                        if (
                            _tariff_from_license_plan(best_lic.get(u.id).plan if best_lic.get(u.id) else None).id == TARIFF_FREE.id
                            and (u.id in paid_user_ids)
                        )
                        else "active"
                    )
                ),
                platform=_platform_for_user(u),
                device=getattr(u, "last_device", None),
                client_os=getattr(u, "last_client_os", None),
                region=getattr(u, "region", None),
                last_login_at=(getattr(u, "last_login_at", None).isoformat() if getattr(u, "last_login_at", None) else None),
                last_live_at=(last_live.get(u.id)[0].isoformat() if (last_live.get(u.id) and last_live.get(u.id)[0]) else None),
                last_live_tiktok_username=(last_live.get(u.id)[1] if last_live.get(u.id) else None),
                online_now=_is_online(getattr(u, "last_ws_at", None), ttl_seconds=90),
                tiktok_accounts_count=int(tiktok_counts.get(u.id, 0)),
                total_gifts=int(getattr(streamer_stats.get(u.id), "total_gifts", 0) or 0),
                total_coins=int(getattr(streamer_stats.get(u.id), "total_coins", 0) or 0),
                today_coins=int(getattr(streamer_stats.get(u.id), "today_coins", 0) or 0),
                last_7d_coins=int(getattr(streamer_stats.get(u.id), "last_7d_coins", 0) or 0),
                last_30d_coins=int(getattr(streamer_stats.get(u.id), "last_30d_coins", 0) or 0),
                top_donors=top_donors_all_by_user.get(u.id, []),
                top_donors_all=top_donors_all_by_user.get(u.id, []),
                top_donors_today=top_donors_today_by_user.get(u.id, []),
                top_donors_7d=top_donors_7d_by_user.get(u.id, []),
                top_donors_30d=top_donors_30d_by_user.get(u.id, []),

                top_gifts_all=top_gifts_all_by_user.get(u.id, []),
                top_gifts_today=top_gifts_today_by_user.get(u.id, []),
                top_gifts_7d=top_gifts_7d_by_user.get(u.id, []),
                top_gifts_30d=top_gifts_30d_by_user.get(u.id, []),
                is_banned=bool(getattr(u, "is_banned", False)),
                banned_at=(u.banned_at.isoformat() if getattr(u, "banned_at", None) else None),
                banned_reason=getattr(u, "banned_reason", None),
            )
            for u in rows
        ],
    )


class SetUserBanRequest(BaseModel):
    banned: bool
    reason: str | None = None


class SetUserBanResponse(BaseModel):
    status: str = "ok"
    user_id: str
    username: str
    banned: bool
    banned_at: str | None = None
    banned_reason: str | None = None


@router.post("/users/{user_id}/ban", response_model=SetUserBanResponse)
def set_user_ban(
    user_id: str,
    req: SetUserBanRequest,
    actor: models.User = Depends(require_superadmin),
    db: Session = Depends(get_db),
):
    target = db.get(models.User, user_id)
    if not target:
        raise HTTPException(status_code=404, detail="user not found")

    if actor.id == target.id and req.banned:
        raise HTTPException(status_code=409, detail="cannot ban yourself")

    if req.banned:
        target.is_banned = True
        target.banned_at = datetime.utcnow()
        target.banned_reason = (req.reason or "").strip()[:255] or None
    else:
        target.is_banned = False
        target.banned_at = None
        target.banned_reason = None

    db.commit()
    return SetUserBanResponse(
        user_id=target.id,
        username=target.username,
        banned=bool(target.is_banned),
        banned_at=target.banned_at.isoformat() if target.banned_at else None,
        banned_reason=target.banned_reason,
    )


class DeleteUserResponse(BaseModel):
    status: str = "ok"
    user_id: str
    username: str


@router.delete("/users/{user_id}", response_model=DeleteUserResponse)
def delete_user(
    user_id: str,
    actor: models.User = Depends(require_superadmin),
    db: Session = Depends(get_db),
):
    target = db.get(models.User, user_id)
    if not target:
        raise HTTPException(status_code=404, detail="user not found")

    if actor.id == target.id:
        raise HTTPException(status_code=409, detail="cannot delete yourself")

    username = target.username
    db.delete(target)
    db.commit()

    # Best-effort cleanup user media (avatars/sounds/tts) to avoid disk bloat.
    static_root = os.path.abspath((os.getenv("MEDIA_ROOT") or "").strip() or os.path.join(os.path.dirname(__file__), "..", "static"))
    for rel in (
        os.path.join("avatars", user_id),
        os.path.join("sounds", user_id),
        os.path.join("tts", user_id),
    ):
        try:
            shutil.rmtree(os.path.join(static_root, rel), ignore_errors=True)
        except Exception:
            pass
    return DeleteUserResponse(user_id=user_id, username=username)


class CreateNotificationRequest(BaseModel):
    title: str
    body: str
    link: str | None = None
    # Legacy fields (still supported)
    level: str | None = None  # info|warning|promo
    audience: str = "all"  # all|users|plan|missing_email
    audience_value: str | None = None

    # New unified fields
    type: str | None = None  # system|product|marketing
    severity: str | None = None  # alias for level
    in_app_enabled: bool | None = None
    push_enabled: bool | None = None
    # JSON-ish targeting (intersection semantics). If provided, preferred over legacy audience.
    # Supported keys: all_users, users, user_ids, usernames, plans, missing_email, purchase_platforms, purchase_statuses
    targeting: dict | None = None
    starts_at: str | None = None  # ISO
    ends_at: str | None = None  # ISO
    target_usernames: list[str] | None = None  # legacy: only for audience=users


class CreateNotificationResponse(BaseModel):
    status: str = "ok"
    id: str


@router.post("/notifications", response_model=CreateNotificationResponse)
def create_notification(
    req: CreateNotificationRequest,
    _user: models.User = Depends(require_staff_user),
    db: Session = Depends(get_db),
):
    title = (req.title or "").strip()[:120]
    body = (req.body or "").strip()[:2000]
    if not title or not body:
        raise HTTPException(status_code=400, detail="title/body required")

    audience = (req.audience or "all").strip().lower()
    if audience not in {"all", "users", "plan", "missing_email"}:
        audience = "all"

    level = (req.severity or req.level or "info").strip().lower()
    if level not in {"info", "warning", "promo"}:
        level = "info"

    ntype = (req.type or "").strip().lower() or None
    if ntype not in {"system", "product", "marketing", None}:
        raise HTTPException(status_code=400, detail="invalid type")

    if ntype == "system":
        raise HTTPException(status_code=400, detail="system notifications are auto-generated")

    in_app_enabled = True if req.in_app_enabled is None else bool(req.in_app_enabled)
    push_enabled = False if req.push_enabled is None else bool(req.push_enabled)

    targeting: dict | None = None
    if isinstance(req.targeting, dict) and req.targeting:
        targeting = req.targeting

    def _parse_dt(s: str | None):
        if not s:
            return None
        ss = s.strip()
        if not ss:
            return None
        try:
            return datetime.fromisoformat(ss.replace("Z", "+00:00")).replace(tzinfo=None)
        except Exception:
            raise HTTPException(status_code=400, detail="invalid datetime")

    n = models.Notification(
        title=title,
        body=body,
        link=(req.link or "").strip()[:512] or None,
        level=models.NotificationLevel(level),
        audience=models.NotificationAudience(audience),
        audience_value=(req.audience_value or "").strip()[:256] or None,
        type=models.NotificationType(ntype or ("marketing" if level == "promo" else "product")),
        targeting=targeting,
        in_app_enabled=in_app_enabled,
        push_enabled=push_enabled,
        created_by_user_id=_user.id,
        starts_at=_parse_dt(req.starts_at),
        ends_at=_parse_dt(req.ends_at),
        created_at=datetime.utcnow(),
    )
    db.add(n)
    db.flush()

    # Legacy explicit targeting
    if audience == "users":
        names = [
            u.strip().lower().replace("@", "")
            for u in (req.target_usernames or [])
            if u and u.strip()
        ]
        if not names:
            raise HTTPException(status_code=400, detail="target_usernames required for audience=users")
        rows = db.query(models.User).filter(models.User.username.in_(names)).all()
        by_name = {u.username.lower(): u for u in rows}
        targets = []
        for nm in names:
            u = by_name.get(nm)
            if not u:
                continue
            targets.append(models.NotificationTarget(notification_id=n.id, user_id=u.id))
        if targets:
            db.add_all(targets)

        # Ensure new targeting works for legacy rows too.
        if not n.targeting:
            n.targeting = {"users": True}

    # If no explicit targeting provided and not legacy users, derive from legacy audience for consistency.
    if not n.targeting and audience != "users":
        if audience == "all":
            n.targeting = {"all_users": True}
        elif audience == "missing_email":
            n.targeting = {"all_users": True, "missing_email": True}
        elif audience == "plan":
            raw = (req.audience_value or "").strip()
            plans = [p.strip().lower() for p in raw.replace(";", ",").split(",") if p and p.strip()]
            n.targeting = {"all_users": True, "plans": plans}

    try:
        db.commit()
    except Exception:
        # Most common cause in production is schema mismatch (missing columns) after deploy.
        logger.exception("Failed to create notification")
        raise HTTPException(status_code=500, detail="failed to create notification")

    return CreateNotificationResponse(id=n.id)


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


class AdminLicenseInfoResponse(BaseModel):
    tariff_id: str
    tariff_name: str
    license_key: str | None = None
    license_plan: str | None = None
    license_status: str | None = None
    license_expires_at: str | None = None


@router.get("/users/{user_id}/license", response_model=AdminLicenseInfoResponse)
def get_user_license_info(
    user_id: str,
    _actor: models.User = Depends(require_staff_user),
    db: Session = Depends(get_db),
):
    user = db.get(models.User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="user not found")

    lic = _get_active_license_for_user(db, user_id)
    tariff = _tariff_from_license_plan(lic.plan if lic else None)
    return AdminLicenseInfoResponse(
        tariff_id=tariff.id,
        tariff_name=tariff.name,
        license_key=lic.key if lic else None,
        license_plan=lic.plan if lic else None,
        license_status=str(lic.status.value) if lic else None,
        license_expires_at=lic.expires_at.isoformat() if (lic and lic.expires_at) else None,
    )


class AdminSetUserLicenseRequest(BaseModel):
    plan: str | None = None
    ttl_days: int = 30


class AdminSetUserLicenseResponse(BaseModel):
    status: str = "ok"
    user_id: str
    license_key: str
    plan: str | None = None
    expires_at: str | None = None


@router.post("/users/{user_id}/license/set", response_model=AdminSetUserLicenseResponse)
def set_user_license(
    user_id: str,
    req: AdminSetUserLicenseRequest,
    _actor: models.User = Depends(require_superadmin),
    db: Session = Depends(get_db),
):
    if req.ttl_days < 1 or req.ttl_days > 3650:
        raise HTTPException(status_code=400, detail="invalid ttl_days")

    user = db.get(models.User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="user not found")

    plan: str | None = None
    if req.plan is not None:
        try:
            plan = canonicalize_license_plan(req.plan)
        except Exception:
            raise HTTPException(status_code=400, detail="invalid plan")

    now = datetime.utcnow()
    lic = _get_active_license_for_user(db, user_id)
    if not lic:
        import secrets

        parts = [secrets.token_hex(2).upper() for _ in range(3)]
        key = f"TTB-{parts[0]}-{parts[1]}-{parts[2]}"
        expires_at = now + timedelta(days=req.ttl_days)
        lic = models.LicenseKey(
            key=key,
            plan=plan,
            expires_at=expires_at,
            status=models.LicenseStatus.active,
            user_id=user_id,
        )
        db.add(lic)
        db.commit()
        return AdminSetUserLicenseResponse(
            user_id=user_id,
            license_key=lic.key,
            plan=lic.plan,
            expires_at=lic.expires_at.isoformat() if lic.expires_at else None,
        )

    # update existing active license
    if req.plan is not None:
        lic.plan = plan

    desired_expires = now + timedelta(days=req.ttl_days)
    if lic.expires_at is None or lic.expires_at < desired_expires:
        lic.expires_at = desired_expires
    db.commit()

    return AdminSetUserLicenseResponse(
        user_id=user_id,
        license_key=lic.key,
        plan=lic.plan,
        expires_at=lic.expires_at.isoformat() if lic.expires_at else None,
    )


class AdminExtendUserLicenseRequest(BaseModel):
    extend_days: int = 30


class AdminExtendUserLicenseResponse(BaseModel):
    status: str = "ok"
    user_id: str
    license_key: str
    expires_at: str | None = None


@router.post("/users/{user_id}/license/extend", response_model=AdminExtendUserLicenseResponse)
def extend_user_license(
    user_id: str,
    req: AdminExtendUserLicenseRequest,
    _actor: models.User = Depends(require_superadmin),
    db: Session = Depends(get_db),
):
    if req.extend_days < 1 or req.extend_days > 3650:
        raise HTTPException(status_code=400, detail="invalid extend_days")
    user = db.get(models.User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="user not found")

    lic = _get_active_license_for_user(db, user_id)
    if not lic:
        raise HTTPException(status_code=404, detail="active license not found")

    base = lic.expires_at or datetime.utcnow()
    lic.expires_at = base + timedelta(days=req.extend_days)
    db.commit()

    return AdminExtendUserLicenseResponse(
        user_id=user_id,
        license_key=lic.key,
        expires_at=lic.expires_at.isoformat() if lic.expires_at else None,
    )


class AdminRevokeUserLicenseResponse(BaseModel):
    status: str = "ok"
    user_id: str
    license_key: str


@router.post("/users/{user_id}/license/revoke", response_model=AdminRevokeUserLicenseResponse)
def revoke_user_license(
    user_id: str,
    _actor: models.User = Depends(require_superadmin),
    db: Session = Depends(get_db),
):
    user = db.get(models.User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="user not found")

    lic = _get_active_license_for_user(db, user_id)
    if not lic:
        raise HTTPException(status_code=404, detail="active license not found")
    lic.status = models.LicenseStatus.revoked
    db.commit()
    return AdminRevokeUserLicenseResponse(user_id=user_id, license_key=lic.key)


class AdminBindUserLicenseRequest(BaseModel):
    license_key: str


class AdminBindUserLicenseResponse(BaseModel):
    status: str = "ok"
    user_id: str
    license_key: str


@router.post("/users/{user_id}/license/bind", response_model=AdminBindUserLicenseResponse)
def bind_user_license(
    user_id: str,
    req: AdminBindUserLicenseRequest,
    _actor: models.User = Depends(require_superadmin),
    db: Session = Depends(get_db),
):
    key = (req.license_key or "").strip()
    if not key:
        raise HTTPException(status_code=400, detail="license not found")
    user = db.get(models.User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="user not found")

    lic = db.query(models.LicenseKey).filter(models.LicenseKey.key == key).first()
    if not lic:
        raise HTTPException(status_code=404, detail="license not found")
    if lic.status != models.LicenseStatus.active:
        raise HTTPException(status_code=403, detail="license not active")
    if lic.expires_at and lic.expires_at < datetime.utcnow():
        raise HTTPException(status_code=403, detail="license expired")
    if lic.user_id and lic.user_id != user_id:
        raise HTTPException(status_code=409, detail="license already bound to another user")
    if not lic.user_id:
        lic.user_id = user_id
        db.commit()

    return AdminBindUserLicenseResponse(user_id=user_id, license_key=lic.key)


class SetUserRoleRequest(BaseModel):
    role: str


class SetUserRoleResponse(BaseModel):
    status: str = "ok"
    user_id: str
    username: str
    role: str


def _set_role_guard(actor: models.User, target: models.User, new_role: str) -> None:
    # Только superadmin может менять роли.
    if (actor.role or "user").lower() != "superadmin":
        raise HTTPException(status_code=403, detail="forbidden")

    # Нельзя понизить/повысить superadmin'а, кроме как самим superadmin'ом (мы уже проверили).
    # Защитимся от случайного "самоубийства": запрет снять superadmin с себя.
    if actor.id == target.id and (target.role or "user") == "superadmin" and new_role != "superadmin":
        raise HTTPException(status_code=409, detail="cannot demote yourself")


@router.patch("/users/{user_id}/role", response_model=SetUserRoleResponse)
def set_user_role(
    user_id: str,
    req: SetUserRoleRequest,
    actor: models.User = Depends(require_superadmin),
    db: Session = Depends(get_db),
):
    new_role = _normalize_role(req.role)
    target = db.get(models.User, user_id)
    if not target:
        raise HTTPException(status_code=404, detail="user not found")

    _set_role_guard(actor=actor, target=target, new_role=new_role)

    target.role = new_role
    db.commit()

    return SetUserRoleResponse(user_id=target.id, username=target.username, role=target.role)


@router.patch("/users/by-username/{username}/role", response_model=SetUserRoleResponse)
def set_user_role_by_username(
    username: str,
    req: SetUserRoleRequest,
    actor: models.User = Depends(require_superadmin),
    db: Session = Depends(get_db),
):
    new_role = _normalize_role(req.role)
    uname = username.strip().lower().replace("@", "")
    target = db.query(models.User).filter(models.User.username == uname).first()
    if not target:
        raise HTTPException(status_code=404, detail="user not found")

    _set_role_guard(actor=actor, target=target, new_role=new_role)

    target.role = new_role
    db.commit()

    return SetUserRoleResponse(user_id=target.id, username=target.username, role=target.role)
