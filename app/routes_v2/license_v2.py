from fastapi import APIRouter, Depends, HTTPException, Header
from pydantic import BaseModel
from sqlalchemy.orm import Session
import os
import secrets
from datetime import datetime, timedelta

from app.db.database import SessionLocal
from app.db import models

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


def _generate_key(prefix: str = "TTB") -> str:
    # Генерируем ключ вида TTB-XXXX-XXXX-XXXX
    parts = [secrets.token_hex(2).upper() for _ in range(3)]
    return f"{prefix}-{parts[0]}-{parts[1]}-{parts[2]}"


@router.post("/issue", response_model=IssueLicenseResponse)
def issue_license(req: IssueLicenseRequest, db: Session = Depends(get_db), admin_api_key: str | None = Header(default=None, alias="Admin-Api-Key")):
    key_required = os.getenv("ADMIN_API_KEY")
    if key_required and admin_api_key != key_required:
        raise HTTPException(status_code=401, detail="unauthorized")

    key = _generate_key()
    expires_at = datetime.utcnow() + timedelta(days=req.ttl_days or 30)
    lic = models.LicenseKey(key=key, plan=req.plan or None, expires_at=expires_at, status=models.LicenseStatus.active)
    db.add(lic)
    db.commit()
    return IssueLicenseResponse(key=key, plan=req.plan or None, expires_at=expires_at.isoformat())


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
