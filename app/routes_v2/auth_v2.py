from fastapi import APIRouter, Depends, HTTPException, status, Header, Request
import os
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.db.database import SessionLocal, init_db
from app.db import models
from app.services.security import hash_password, verify_password, create_access_token, decode_token
from datetime import datetime
from datetime import timedelta
import hashlib
import hmac
import re
from app.services.plans import resolve_tariff
import secrets

from app.services.email_resend import send_email, ResendError


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
def login(req: LoginRequest, request: Request, db: Session = Depends(get_db)):
    username = _normalize_username(req.username)
    # Backward-compat: older deployments may have stored mixed-case usernames.
    # We normalize input to lowercase, so search case-insensitively.
    user = db.query(models.User).filter(func.lower(models.User.username) == username).first()
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
    if getattr(user, "is_banned", False):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="user banned")
    if auth_debug:
        import logging
        logging.getLogger(__name__).info(f"AUTH_DEBUG login success for '{username}' user_id={user.id}")
    # Record login metadata (best-effort).
    try:
        now = datetime.utcnow()

        # Resolve IP behind proxy.
        ip = None
        xff = request.headers.get("x-forwarded-for")
        if xff:
            # Can be a comma-separated list.
            ip = xff.split(",")[0].strip() or None
        if not ip:
            ip = request.client.host if request.client else None

        ua = (request.headers.get("user-agent") or "").strip()[:255] or None

        # Best-effort region/country headers (Cloudflare/Vercel/etc.)
        region = (
            request.headers.get("cf-ipcountry")
            or request.headers.get("x-vercel-ip-country")
            or request.headers.get("x-country")
            or request.headers.get("x-geo-country")
            or request.headers.get("x-client-region")
        )
        region = (region or "").strip()[:64] or None

        # Optional client hints.
        platform = (request.headers.get("x-client-platform") or "").strip()[:32] or None
        client_os = (request.headers.get("x-client-os") or "").strip()[:32] or None
        device = (request.headers.get("x-client-device") or "").strip()[:255] or None

        # Update denormalized last_* fields.
        try:
            user.last_login_at = now
            user.last_login_ip = ip
            user.last_user_agent = ua
            if platform:
                user.last_client_platform = platform
            if client_os:
                user.last_client_os = client_os
            if device:
                user.last_device = device
            if region:
                user.region = region
        except Exception:
            pass

        db.add(models.UserSession(
            user_id=user.id,
            platform=platform,
            ip=ip,
            user_agent=ua,
            region=region,
            created_at=now,
        ))
        db.commit()
    except Exception:
        try:
            db.rollback()
        except Exception:
            pass

    token = create_access_token(user.id)
    return AuthResponse(access_token=token)


class PasswordResetRequest(BaseModel):
    login_or_email: str


class PasswordResetRequestResponse(BaseModel):
    status: str = "ok"


class PasswordResetConfirmRequest(BaseModel):
    login_or_email: str
    code: str
    new_password: str


class PasswordResetConfirmResponse(BaseModel):
    status: str = "ok"


def _hash_reset_code(code: str) -> str:
    # Short numeric codes must never be stored in plaintext.
    # We salt with a server secret to prevent rainbow tables.
    secret = (os.getenv("RESET_CODE_SECRET") or os.getenv("JWT_SECRET") or "dev-secret-change-me").encode("utf-8")
    msg = (code or "").strip().encode("utf-8")
    return hmac.new(secret, msg, hashlib.sha256).hexdigest()


def _extract_request_ip(request: Request) -> str | None:
    xff = request.headers.get("x-forwarded-for")
    if xff:
        return xff.split(",")[0].strip() or None
    return request.client.host if request.client else None


@router.post("/password/reset/request", response_model=PasswordResetRequestResponse)
async def request_password_reset(req: PasswordResetRequest, request: Request, db: Session = Depends(get_db)):
    """Send a one-time reset code to the user's email.

    Privacy: always returns {status: ok} even if user/email doesn't exist.
    """
    init_db()

    raw = (req.login_or_email or "").strip()
    if not raw:
        raise HTTPException(status_code=400, detail="login_or_email is required")

    value = raw.strip().lower()
    is_email = "@" in value

    user = None
    if is_email:
        user = db.query(models.User).filter(func.lower(models.User.email) == value).first()
    else:
        username = _normalize_username(value)
        # Case-insensitive for backward-compat.
        user = db.query(models.User).filter(func.lower(models.User.username) == username).first()

    # If no user or no email, do not disclose.
    if not user or not getattr(user, "email", None):
        return PasswordResetRequestResponse()

    # Basic send cooldown: don't spam.
    now = datetime.utcnow()
    cooldown_sec = int(os.getenv("RESET_SEND_COOLDOWN_SEC", "60") or "60")
    try:
        last = (
            db.query(models.PasswordResetToken)
            .filter(models.PasswordResetToken.user_id == user.id)
            .order_by(models.PasswordResetToken.created_at.desc())
            .first()
        )
        if last and last.created_at and (now - last.created_at).total_seconds() < cooldown_sec:
            return PasswordResetRequestResponse()
    except Exception:
        pass

    ttl_min = int(os.getenv("RESET_CODE_TTL_MIN", "15") or "15")
    if ttl_min < 5:
        ttl_min = 5
    if ttl_min > 60:
        ttl_min = 60

    code = f"{secrets.randbelow(1_000_000):06d}"
    token = models.PasswordResetToken(
        user_id=user.id,
        code_hash=_hash_reset_code(code),
        expires_at=now + timedelta(minutes=ttl_min),
        used_at=None,
        attempts=0,
        request_ip=_extract_request_ip(request),
        user_agent=(request.headers.get("user-agent") or "")[:255] or None,
    )
    db.add(token)
    db.commit()

    subject = "Сброс пароля NovaBoost"
    text = (
        "Код для сброса пароля:\n\n"
        f"{code}\n\n"
        f"Срок действия: {ttl_min} мин.\n\n"
        "Если это были не вы — просто игнорируйте письмо."
    )
    try:
        await send_email(to_email=str(user.email).strip(), subject=subject, text=text)
    except ResendError as e:
        # Configuration / upstream errors should be visible to client.
        raise HTTPException(status_code=502, detail=str(e))
    except Exception:
        raise HTTPException(status_code=502, detail="email send failed")

    return PasswordResetRequestResponse()


@router.post("/password/reset/confirm", response_model=PasswordResetConfirmResponse)
def confirm_password_reset(req: PasswordResetConfirmRequest, db: Session = Depends(get_db)):
    init_db()
    raw = (req.login_or_email or "").strip()
    if not raw:
        raise HTTPException(status_code=400, detail="login_or_email is required")
    code = (req.code or "").strip()
    if not code or len(code) < 4:
        raise HTTPException(status_code=400, detail="invalid code")

    _validate_password(req.new_password)

    value = raw.strip().lower()
    is_email = "@" in value

    user = None
    if is_email:
        user = db.query(models.User).filter(func.lower(models.User.email) == value).first()
    else:
        username = _normalize_username(value)
        user = db.query(models.User).filter(func.lower(models.User.username) == username).first()

    # Don't disclose user existence.
    if not user:
        raise HTTPException(status_code=401, detail="invalid code")

    now = datetime.utcnow()
    token = (
        db.query(models.PasswordResetToken)
        .filter(
            models.PasswordResetToken.user_id == user.id,
            models.PasswordResetToken.used_at.is_(None),
            models.PasswordResetToken.expires_at > now,
        )
        .order_by(models.PasswordResetToken.created_at.desc())
        .first()
    )
    if not token:
        raise HTTPException(status_code=401, detail="invalid code")

    max_attempts = int(os.getenv("RESET_CODE_MAX_ATTEMPTS", "10") or "10")
    if token.attempts is not None and int(token.attempts) >= max_attempts:
        raise HTTPException(status_code=429, detail="too many attempts")

    expected = str(token.code_hash or "")
    actual = _hash_reset_code(code)
    if not hmac.compare_digest(expected, actual):
        try:
            token.attempts = int(token.attempts or 0) + 1
            db.add(token)
            db.commit()
        except Exception:
            try:
                db.rollback()
            except Exception:
                pass
        raise HTTPException(status_code=401, detail="invalid code")

    # Code matches: set new password and consume token.
    user.password_hash = hash_password(req.new_password)
    user.last_login_at = now
    token.used_at = now
    token.attempts = int(token.attempts or 0)
    db.add(user)
    db.add(token)
    db.commit()
    return PasswordResetConfirmResponse()


@router.post("/redeem-license", response_model=RedeemLicenseResponse)
def redeem_license(req: RedeemLicenseRequest, db: Session = Depends(get_db)):
    raise HTTPException(status_code=410, detail="license keys removed; use in-app subscriptions")
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

    if getattr(user, "is_banned", False):
        raise HTTPException(status_code=403, detail="user banned")

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
    raise HTTPException(status_code=410, detail="license keys removed; use in-app subscriptions")
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
    email: str | None = None
    avatar_url: str | None = None
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
def me(request: Request, user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    settings = None
    try:
        # Не используем relationship напрямую: при несоответствии схемы (например, не добавили колонку)
        # lazy-load может упасть и сломать весь /me.
        settings = (
            db.query(models.UserSettings)
            .filter(models.UserSettings.user_id == user.id)
            .first()
        )
    except Exception as e:
        if os.getenv("AUTH_DEBUG") == "1":
            import logging
            logging.getLogger(__name__).exception(f"AUTH_DEBUG /me: failed to load user_settings for user_id={user.id}: {e}")
    tariff, lic = resolve_tariff(db, user.id)

    def _request_base_url() -> str:
        # Prefer proxy-provided headers when behind nginx/caddy.
        proto = (request.headers.get("x-forwarded-proto") or request.url.scheme or "http").strip()
        host = (
            request.headers.get("x-forwarded-host")
            or request.headers.get("host")
            or request.url.netloc
        )
        host = (host or "").strip()
        if host:
            return f"{proto}://{host}".rstrip("/")
        return str(request.base_url).rstrip("/")

    def _abs_url(path: str) -> str:
        media_base = (os.getenv("MEDIA_BASE_URL") or "").strip().rstrip("/")
        base = media_base or _request_base_url()
        if not base:
            base = (
                os.getenv("SERVER_HOST")
                or os.getenv("TTS_BASE_URL")
                or "http://localhost:8000"
            ).rstrip("/")
        if not path.startswith("/"):
            path = "/" + path
        return base + path

    avatar_url = None
    if getattr(user, "avatar_filename", None):
        avatar_url = _abs_url(f"/static/avatars/{user.id}/{user.avatar_filename}")

    return MeResponse(
        id=user.id,
        username=user.username,
        email=getattr(user, "email", None),
        avatar_url=avatar_url,
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
