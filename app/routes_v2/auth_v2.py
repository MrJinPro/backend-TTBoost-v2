from fastapi import APIRouter, Depends, HTTPException, status, Header, Request
import os
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.database import SessionLocal, init_db
from app.db import models
from app.services.security import hash_password, verify_password, create_access_token, decode_token
from datetime import datetime
import re
from app.services.plans import resolve_tariff


router = APIRouter()


_USERNAME_RE = re.compile(r"^[a-z0-9._-]{2,64}$")


def _normalize_username(raw: str) -> str:
    return raw.strip().lower().replace("@", "")


def _validate_username(username: str) -> None:
    if not _USERNAME_RE.match(username):
        raise HTTPException(400, detail="invalid username")


def _validate_password(password: str) -> None:
    if not password or len(password) < 6:
        raise HTTPException(400, detail="invalid password")


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


class RegisterRequest(BaseModel):
    username: str
    password: str


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class RedeemLicenseRequest(BaseModel):
    username: str
    password: str
    license_key: str


class RedeemLicenseResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    license_expires_at: str | None = None
    plan: str | None = None


class UpgradeLicenseRequest(BaseModel):
    license_key: str


class UpgradeLicenseResponse(BaseModel):
    status: str = "ok"
    plan: str | None = None
    license_expires_at: str | None = None


@router.post("/register", response_model=AuthResponse)
def register(req: RegisterRequest, db: Session = Depends(get_db)):
    init_db()
    username = _normalize_username(req.username)
    _validate_username(username)
    _validate_password(req.password)
    exists = db.query(models.User).filter(models.User.username == username).first()
    if exists:
        raise HTTPException(409, detail="user exists")
    user = models.User(username=username, password_hash=hash_password(req.password))
    db.add(user)
    db.flush()
    # default settings
    settings = models.UserSettings(user_id=user.id)
    db.add(settings)
    db.commit()
    token = create_access_token(user.id)
    return AuthResponse(access_token=token)


class LoginRequest(BaseModel):
    username: str
    password: str


@router.post("/login", response_model=AuthResponse)
def login(req: LoginRequest, db: Session = Depends(get_db)):
    username = _normalize_username(req.username)
    user = db.query(models.User).filter(models.User.username == username).first()
    auth_debug = os.getenv("AUTH_DEBUG") == "1"
    if not user:
        if auth_debug:
            # Логируем причину конкретно
            import logging
            logging.getLogger(__name__).warning(f"AUTH_DEBUG login fail: user '{username}' not found")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid credentials")
    if not verify_password(req.password, user.password_hash):
        if auth_debug:
            import logging
            logging.getLogger(__name__).warning(f"AUTH_DEBUG login fail: password mismatch for '{username}'")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid credentials")
    if auth_debug:
        import logging
        logging.getLogger(__name__).info(f"AUTH_DEBUG login success for '{username}' user_id={user.id}")
    token = create_access_token(user.id)
    return AuthResponse(access_token=token)


@router.post("/redeem-license", response_model=RedeemLicenseResponse)
def redeem_license(req: RedeemLicenseRequest, db: Session = Depends(get_db)):
    """Обмен лицензионного ключа на JWT и (при необходимости) создание пользователя.
    Логика:
    1. Проверяем существование активной лицензии и срок.
    2. Создаём пользователя, если его нет.
    3. Привязываем лицензию к пользователю (user_id), если не привязана.
    4. Возвращаем JWT и данные по сроку лицензии.
    """
    username = _normalize_username(req.username)
    _validate_username(username)
    _validate_password(req.password)

    lic = db.query(models.LicenseKey).filter(models.LicenseKey.key == req.license_key.strip()).first()
    if not lic:
        raise HTTPException(404, detail="license not found")
    if lic.status != models.LicenseStatus.active:
        raise HTTPException(403, detail="license not active")
    if lic.expires_at and lic.expires_at < datetime.utcnow():
        raise HTTPException(403, detail="license expired")

    user = db.query(models.User).filter(models.User.username == username).first()
    if not user:
        # создать пользователя
        user = models.User(username=username, password_hash=hash_password(req.password))
        db.add(user)
        db.flush()
        settings = models.UserSettings(user_id=user.id)
        db.add(settings)
    else:
        # проверяем пароль
        if not verify_password(req.password, user.password_hash):
            raise HTTPException(401, detail="invalid credentials")

    # привязать лицензию, если еще не привязана или уже привязана к этому user
    if lic.user_id and lic.user_id != user.id:
        raise HTTPException(409, detail="license already bound to another user")
    if not lic.user_id:
        lic.user_id = user.id
    db.commit()

    token = create_access_token(user.id)
    return RedeemLicenseResponse(access_token=token, license_expires_at=lic.expires_at.isoformat() if lic.expires_at else None, plan=lic.plan)


def get_current_user(authorization: str | None = Header(default=None), db: Session = Depends(get_db)) -> models.User:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="missing bearer token")
    token = authorization.split(" ", 1)[1]
    sub = decode_token(token)
    if not sub:
        raise HTTPException(status_code=401, detail="invalid token")
    user = db.get(models.User, sub)
    if not user:
        raise HTTPException(status_code=401, detail="user not found")

    # Bootstrap SuperAdmin for selected usernames (comma-separated).
    # Example: SUPERADMIN_USERNAMES=novaboost,owner
    superadmins_raw = (os.getenv("SUPERADMIN_USERNAMES") or "").strip()
    if superadmins_raw:
        superadmins = {u.strip().lower() for u in superadmins_raw.split(",") if u.strip()}
        if user.username.lower() in superadmins and (user.role or "user") != "superadmin":
            user.role = "superadmin"
            db.commit()
    return user


def _upgrade_license_impl(
    req: UpgradeLicenseRequest,
    user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Применить лицензионный ключ к текущему пользователю (апгрейд тарифа из UI).

    - Не требует пароля (пользователь уже аутентифицирован).
    - Привязывает лицензию к user_id, если она свободна.
    - Если ключ уже привязан к другому пользователю — ошибка.
    """
    key = (req.license_key or "").strip()
    if not key:
        raise HTTPException(400, detail="license not found")

    lic = db.query(models.LicenseKey).filter(models.LicenseKey.key == key).first()
    if not lic:
        raise HTTPException(404, detail="license not found")
    if lic.status != models.LicenseStatus.active:
        raise HTTPException(403, detail="license not active")
    if lic.expires_at and lic.expires_at < datetime.utcnow():
        raise HTTPException(403, detail="license expired")
    if lic.user_id and lic.user_id != user.id:
        raise HTTPException(409, detail="license already bound to another user")
    if not lic.user_id:
        lic.user_id = user.id
        db.commit()

    return UpgradeLicenseResponse(
        plan=lic.plan,
        license_expires_at=lic.expires_at.isoformat() if lic.expires_at else None,
    )


# Primary (documented) path
@router.post("/upgrade-license", response_model=UpgradeLicenseResponse)
def upgrade_license(
    req: UpgradeLicenseRequest,
    user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return _upgrade_license_impl(req=req, user=user, db=db)


# Backward/compat aliases (some deployments/clients used underscore or camelCase)
@router.post("/upgrade_license", response_model=UpgradeLicenseResponse, include_in_schema=False)
def upgrade_license_alias_underscore(
    req: UpgradeLicenseRequest,
    user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return _upgrade_license_impl(req=req, user=user, db=db)


@router.post("/upgradeLicense", response_model=UpgradeLicenseResponse, include_in_schema=False)
def upgrade_license_alias_camel(
    req: UpgradeLicenseRequest,
    user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return _upgrade_license_impl(req=req, user=user, db=db)


class MeResponse(BaseModel):
    id: str
    username: str
    role: str
    plan: str | None = None  # tariff id
    tariff_name: str | None = None
    allowed_platforms: list[str] | None = None
    max_tiktok_accounts: int | None = None
    license_expires_at: str | None = None
    tiktok_username: str | None = None
    voice_id: str
    tts_enabled: bool
    gift_sounds_enabled: bool
    tts_volume: int
    gifts_volume: int


@router.get("/me", response_model=MeResponse)
def me(user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    settings = user.settings
    tariff, lic = resolve_tariff(db, user.id)
    return MeResponse(
        id=user.id,
        username=user.username,
        role=user.role or "user",
        plan=tariff.id,
        tariff_name=tariff.name,
        allowed_platforms=sorted(list(tariff.allowed_platforms)),
        max_tiktok_accounts=tariff.max_tiktok_accounts,
        license_expires_at=lic.expires_at.isoformat() if (lic and lic.expires_at) else None,
        tiktok_username=user.tiktok_username,
        voice_id=settings.voice_id if settings else "ru-RU-SvetlanaNeural",
        tts_enabled=settings.tts_enabled if settings else True,
        gift_sounds_enabled=settings.gift_sounds_enabled if settings else True,
        tts_volume=settings.tts_volume if settings else 100,
        gifts_volume=settings.gifts_volume if settings else 100,
    )
