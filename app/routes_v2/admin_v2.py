from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from datetime import datetime, timedelta

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


router = APIRouter()


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
    role: str
    created_at: str
    tiktok_username: str | None = None
    tariff_id: str | None = None
    tariff_name: str | None = None
    license_expires_at: str | None = None


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
    limit: int = 50,
    offset: int = 0,
    _user: models.User = Depends(require_staff_user),
    db: Session = Depends(get_db),
):
    if limit < 1 or limit > 200:
        raise HTTPException(status_code=400, detail="invalid limit")
    if offset < 0:
        raise HTTPException(status_code=400, detail="invalid offset")

    query = db.query(models.User)
    if q:
        qq = q.strip().lower()
        query = query.filter(models.User.username.ilike(f"%{qq}%"))

    total = query.count()
    rows = (
        query.order_by(models.User.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    user_ids = [u.id for u in rows]
    best_lic = _get_active_licenses_for_users(db, user_ids)

    return ListUsersResponse(
        total=total,
        items=[
            AdminUserItem(
                id=u.id,
                username=u.username,
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
            )
            for u in rows
        ],
    )


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
