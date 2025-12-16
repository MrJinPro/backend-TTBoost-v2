from fastapi import APIRouter, Depends, HTTPException, Header
from pydantic import BaseModel
from sqlalchemy.orm import Session
import os
import secrets
from datetime import datetime, timedelta

from app.db.database import SessionLocal
from app.db import models
from app.services.plans import canonicalize_license_plan

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


class IssueLicenseResponse(BaseModel):
    key: str
    plan: str | None = None
    expires_at: str | None = None


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


def _generate_key(prefix: str = "TTB") -> str:
    # Генерируем ключ вида TTB-XXXX-XXXX-XXXX
    parts = [secrets.token_hex(2).upper() for _ in range(3)]
    return f"{prefix}-{parts[0]}-{parts[1]}-{parts[2]}"


def _require_admin(admin_api_key: str | None) -> None:
    key_required = os.getenv("ADMIN_API_KEY")
    if key_required and admin_api_key != key_required:
        raise HTTPException(status_code=401, detail="unauthorized")


@router.post("/issue", response_model=IssueLicenseResponse)
def issue_license(req: IssueLicenseRequest, db: Session = Depends(get_db), admin_api_key: str | None = Header(default=None, alias="Admin-Api-Key")):
    _require_admin(admin_api_key)

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


@router.get("/list", response_model=ListLicensesResponse)
def list_licenses(
    limit: int = 200,
    offset: int = 0,
    db: Session = Depends(get_db),
    admin_api_key: str | None = Header(default=None, alias="Admin-Api-Key"),
):
    _require_admin(admin_api_key)
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
