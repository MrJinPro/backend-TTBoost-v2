from fastapi import APIRouter, Depends, HTTPException, Header
from pydantic import BaseModel
from sqlalchemy.orm import Session
import os
import secrets
from datetime import datetime, timedelta

from app.db.database import SessionLocal, init_db
from app.db import models
from app.services.plans import (
    TARIFF_DUO,
    TARIFF_FREE,
    TARIFF_ONE_DESKTOP,
    TARIFF_ONE_MOBILE,
    canonicalize_license_plan,
)

router = APIRouter()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


class IssueLicenseRequest(BaseModel):
    plan: str | None = None
    ttl_days: int | None = 30


class IssueBulkRequest(BaseModel):
    plan: str | None = None
    ttl_days: int | None = 30
    count: int = 10
    prefix: str | None = None


class IssueLicenseResponse(BaseModel):
    key: str
    plan: str | None = None
    expires_at: str | None = None


class IssueBulkResponse(BaseModel):
    items: list[IssueLicenseResponse]


class LicenseItem(BaseModel):
    key: str
    plan: str | None = None
    status: str
    issued_at: str | None = None
    expires_at: str | None = None
    user_id: str | None = None
    max_devices: int | None = None
    devices_bound: int | None = None


class ListLicensesResponse(BaseModel):
    items: list[LicenseItem]


class RevokeLicenseRequest(BaseModel):
    key: str


class ExtendLicenseRequest(BaseModel):
    key: str
    extend_days: int = 30


class SetPlanRequest(BaseModel):
    key: str
    plan: str | None = None


class PlanItem(BaseModel):
    id: str
    name: str
    allowed_platforms: list[str]


class ListPlansResponse(BaseModel):
    items: list[PlanItem]


@router.get("/plans", response_model=ListPlansResponse)
def list_plans():
    """Список тарифов (для веб-витрины/чекаута).

    По умолчанию отдаём только платные планы. Ограничение можно задать через env
    `WEB_ALLOWED_PLANS` (ids через запятую).
    """

    all_paid = [TARIFF_ONE_MOBILE, TARIFF_ONE_DESKTOP, TARIFF_DUO]
    allowed_raw = (os.getenv("WEB_ALLOWED_PLANS") or "").strip()
    if allowed_raw:
        allowed_ids = {canonicalize_license_plan(p.strip()) for p in allowed_raw.split(",") if p.strip()}
        all_paid = [t for t in all_paid if t.id in allowed_ids]

    return ListPlansResponse(
        items=[
            PlanItem(id=t.id, name=t.name, allowed_platforms=sorted(list(t.allowed_platforms)))
            for t in all_paid
        ]
    )


def _generate_key(prefix: str = "TTB") -> str:
    # Генерируем ключ вида TTB-XXXX-XXXX-XXXX
    parts = [secrets.token_hex(2).upper() for _ in range(3)]
    return f"{prefix}-{parts[0]}-{parts[1]}-{parts[2]}"


def _require_admin(admin_api_key: str | None) -> None:
    key_required = os.getenv("ADMIN_API_KEY")
    if key_required and admin_api_key != key_required:
        raise HTTPException(status_code=401, detail="unauthorized")


def _require_web(web_api_key: str | None) -> None:
    """Отдельный ключ доступа для веб-выдачи лицензий.

    Этот ключ должен храниться только server-side (веб-бэкенд/серверлесс).
    Никогда не кладите его в браузерный фронтенд.
    """
    key_required = os.getenv("WEB_ISSUE_API_KEY")
    if key_required and web_api_key != key_required:
        raise HTTPException(status_code=401, detail="unauthorized")


class IssueWebLicenseRequest(BaseModel):
    order_id: str
    plan: str
    ttl_days: int | None = 30
    email: str | None = None
    amount: int | None = None
    currency: str | None = None


@router.post("/issue", response_model=IssueLicenseResponse)
def issue_license(req: IssueLicenseRequest, db: Session = Depends(get_db), admin_api_key: str | None = Header(default=None, alias="Admin-Api-Key")):
    _require_admin(admin_api_key)
    init_db()

    try:
        plan = canonicalize_license_plan(req.plan)
    except Exception:
        raise HTTPException(status_code=400, detail="invalid plan")

    key = _generate_key()
    expires_at = datetime.utcnow() + timedelta(days=req.ttl_days or 30)
    lic = models.LicenseKey(key=key, plan=plan, expires_at=expires_at, status=models.LicenseStatus.active)
    db.add(lic)
    db.commit()
    return IssueLicenseResponse(key=key, plan=plan, expires_at=expires_at.isoformat())


@router.post("/issue-web", response_model=IssueLicenseResponse)
def issue_license_web(
    req: IssueWebLicenseRequest,
    db: Session = Depends(get_db),
    web_api_key: str | None = Header(default=None, alias="Web-Api-Key"),
):
    """Выдать ключ для веб-покупки.

    Endpoint должен вызываться только вашим веб-бэкендом после подтверждения оплаты.
    """

    _require_web(web_api_key)
    init_db()

    order_id = (req.order_id or "").strip()
    if not order_id:
        raise HTTPException(status_code=400, detail="order_id is required")

    try:
        plan = canonicalize_license_plan(req.plan)
    except Exception:
        raise HTTPException(status_code=400, detail="invalid plan")

    ttl = req.ttl_days or 30
    if ttl <= 0 or ttl > 3650:
        raise HTTPException(status_code=400, detail="invalid ttl_days")

    # Ограничим список допустимых планов через env, если задан
    allowed_raw = (os.getenv("WEB_ALLOWED_PLANS") or "").strip()
    if allowed_raw:
        allowed = {canonicalize_license_plan(p.strip()) for p in allowed_raw.split(",") if p.strip()}
        if plan not in allowed:
            raise HTTPException(status_code=403, detail="plan not allowed")

    # Идемпотентность по order_id
    existing = db.query(models.WebPurchase).filter(models.WebPurchase.order_id == order_id).first()
    if existing and existing.license_key:
        lic = db.query(models.LicenseKey).filter(models.LicenseKey.key == existing.license_key).first()
        if lic:
            return IssueLicenseResponse(
                key=lic.key,
                plan=lic.plan,
                expires_at=lic.expires_at.isoformat() if lic.expires_at else None,
            )

    expires_at = datetime.utcnow() + timedelta(days=ttl)

    # Генерируем с защитой от редкой коллизии
    for _attempt in range(5):
        key = _generate_key()
        exists = db.query(models.LicenseKey).filter(models.LicenseKey.key == key).first()
        if exists:
            continue
        db.add(models.LicenseKey(key=key, plan=plan, expires_at=expires_at, status=models.LicenseStatus.active))
        break
    else:
        raise HTTPException(status_code=500, detail="failed to generate unique key")

    if not existing:
        db.add(
            models.WebPurchase(
                order_id=order_id,
                email=(req.email or None),
                plan=plan,
                ttl_days=ttl,
                amount=req.amount,
                currency=(req.currency or None),
                license_key=key,
            )
        )
    else:
        existing.plan = plan
        existing.ttl_days = ttl
        existing.email = (req.email or existing.email)
        existing.amount = req.amount if req.amount is not None else existing.amount
        existing.currency = (req.currency or existing.currency)
        existing.license_key = key

    db.commit()
    return IssueLicenseResponse(key=key, plan=plan, expires_at=expires_at.isoformat())


@router.post("/issue-bulk", response_model=IssueBulkResponse)
def issue_bulk(
    req: IssueBulkRequest,
    db: Session = Depends(get_db),
    admin_api_key: str | None = Header(default=None, alias="Admin-Api-Key"),
):
    """Сгенерировать пачку ключей и записать в БД (удобно раздавать друзьям)."""
    _require_admin(admin_api_key)
    init_db()

    if req.count <= 0 or req.count > 500:
        raise HTTPException(status_code=400, detail="invalid count")

    try:
        plan = canonicalize_license_plan(req.plan)
    except Exception:
        raise HTTPException(status_code=400, detail="invalid plan")

    ttl = req.ttl_days or 30
    if ttl <= 0 or ttl > 3650:
        raise HTTPException(status_code=400, detail="invalid ttl_days")

    prefix = (req.prefix or "TTB").strip().upper()[:10] or "TTB"
    expires_at = datetime.utcnow() + timedelta(days=ttl)

    items: list[IssueLicenseResponse] = []
    # Генерируем с защитой от редкой коллизии
    for _ in range(int(req.count)):
        for _attempt in range(5):
            key = _generate_key(prefix=prefix)
            exists = db.query(models.LicenseKey).filter(models.LicenseKey.key == key).first()
            if exists:
                continue
            db.add(models.LicenseKey(key=key, plan=plan, expires_at=expires_at, status=models.LicenseStatus.active))
            items.append(IssueLicenseResponse(key=key, plan=plan, expires_at=expires_at.isoformat()))
            break
        else:
            raise HTTPException(status_code=500, detail="failed to generate unique key")

    db.commit()
    return IssueBulkResponse(items=items)


@router.get("/list", response_model=ListLicensesResponse)
def list_licenses(
    limit: int = 200,
    offset: int = 0,
    db: Session = Depends(get_db),
    admin_api_key: str | None = Header(default=None, alias="Admin-Api-Key"),
):
    _require_admin(admin_api_key)
    init_db()
    limit = max(1, min(limit, 1000))
    offset = max(0, offset)
    q = db.query(models.LicenseKey).order_by(models.LicenseKey.issued_at.desc()).offset(offset).limit(limit)
    items: list[LicenseItem] = []
    for lic in q.all():
        items.append(
            LicenseItem(
                key=lic.key,
                plan=lic.plan,
                status=lic.status.value,
                issued_at=lic.issued_at.isoformat() if lic.issued_at else None,
                expires_at=lic.expires_at.isoformat() if lic.expires_at else None,
                user_id=lic.user_id,
                max_devices=lic.max_devices,
                devices_bound=lic.devices_bound,
            )
        )
    return ListLicensesResponse(items=items)


@router.post("/revoke", response_model=LicenseItem)
def revoke_license(
    req: RevokeLicenseRequest,
    db: Session = Depends(get_db),
    admin_api_key: str | None = Header(default=None, alias="Admin-Api-Key"),
):
    _require_admin(admin_api_key)
    init_db()
    lic = db.query(models.LicenseKey).filter(models.LicenseKey.key == req.key.strip()).first()
    if not lic:
        raise HTTPException(status_code=404, detail="not found")
    lic.status = models.LicenseStatus.revoked
    db.commit()
    return LicenseItem(
        key=lic.key,
        plan=lic.plan,
        status=lic.status.value,
        issued_at=lic.issued_at.isoformat() if lic.issued_at else None,
        expires_at=lic.expires_at.isoformat() if lic.expires_at else None,
        user_id=lic.user_id,
        max_devices=lic.max_devices,
        devices_bound=lic.devices_bound,
    )


@router.post("/extend", response_model=LicenseItem)
def extend_license(
    req: ExtendLicenseRequest,
    db: Session = Depends(get_db),
    admin_api_key: str | None = Header(default=None, alias="Admin-Api-Key"),
):
    _require_admin(admin_api_key)
    init_db()
    lic = db.query(models.LicenseKey).filter(models.LicenseKey.key == req.key.strip()).first()
    if not lic:
        raise HTTPException(status_code=404, detail="not found")
    if req.extend_days <= 0 or req.extend_days > 3650:
        raise HTTPException(status_code=400, detail="invalid extend_days")
    base = lic.expires_at or datetime.utcnow()
    now = datetime.utcnow()
    if base < now:
        base = now
    lic.expires_at = base + timedelta(days=req.extend_days)
    if lic.status == models.LicenseStatus.revoked:
        lic.status = models.LicenseStatus.active
    db.commit()
    return LicenseItem(
        key=lic.key,
        plan=lic.plan,
        status=lic.status.value,
        issued_at=lic.issued_at.isoformat() if lic.issued_at else None,
        expires_at=lic.expires_at.isoformat() if lic.expires_at else None,
        user_id=lic.user_id,
        max_devices=lic.max_devices,
        devices_bound=lic.devices_bound,
    )


@router.post("/set-plan", response_model=LicenseItem)
def set_plan(
    req: SetPlanRequest,
    db: Session = Depends(get_db),
    admin_api_key: str | None = Header(default=None, alias="Admin-Api-Key"),
):
    _require_admin(admin_api_key)
    init_db()
    lic = db.query(models.LicenseKey).filter(models.LicenseKey.key == req.key.strip()).first()
    if not lic:
        raise HTTPException(status_code=404, detail="not found")

    try:
        lic.plan = canonicalize_license_plan(req.plan)
    except Exception:
        raise HTTPException(status_code=400, detail="invalid plan")
    db.commit()
    return LicenseItem(
        key=lic.key,
        plan=lic.plan,
        status=lic.status.value,
        issued_at=lic.issued_at.isoformat() if lic.issued_at else None,
        expires_at=lic.expires_at.isoformat() if lic.expires_at else None,
        user_id=lic.user_id,
        max_devices=lic.max_devices,
        devices_bound=lic.devices_bound,
    )


@router.get("/check")
def check_license(key: str, db: Session = Depends(get_db)):
    init_db()
    lic = db.query(models.LicenseKey).filter(models.LicenseKey.key == key).first()
    if not lic:
        raise HTTPException(status_code=404, detail="not found")
    return {
        "key": lic.key,
        "status": lic.status.value,
        "plan": lic.plan,
        "issued_at": lic.issued_at.isoformat() if lic.issued_at else None,
        "expires_at": lic.expires_at.isoformat() if lic.expires_at else None,
        "user_id": lic.user_id,
    }
