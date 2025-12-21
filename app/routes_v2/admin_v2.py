from fastapi import APIRouter, Depends, HTTPException, Header
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.database import SessionLocal
from app.db import models
from .auth_v2 import get_current_user


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


class ListUsersResponse(BaseModel):
    items: list[AdminUserItem]
    total: int


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

    return ListUsersResponse(
        total=total,
        items=[
            AdminUserItem(
                id=u.id,
                username=u.username,
                role=(u.role or "user"),
                created_at=u.created_at.isoformat() if u.created_at else "",
                tiktok_username=u.tiktok_username,
            )
            for u in rows
        ],
    )


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
