from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db import models
from app.db.database import SessionLocal
from app.routes_v2.auth_v2 import get_current_user
from app.services.plans import canonicalize_license_plan

router = APIRouter()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _now_utc() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()[:24]


def _product_to_plan(platform: str, product_id: str) -> str:
    """Маппинг store product_id -> внутренний plan (tariff id).

    Конфиг через env:
      BILLING_ANDROID_ONE_PRODUCT_ID / BILLING_ANDROID_DUO_PRODUCT_ID
      BILLING_IOS_ONE_PRODUCT_ID / BILLING_IOS_DUO_PRODUCT_ID
    """

    pid = (product_id or "").strip()
    p = (platform or "").strip().lower()

    if p == "android":
        if pid and pid == (os.getenv("BILLING_ANDROID_ONE_PRODUCT_ID") or "").strip():
            return "nova_streamer_one_mobile"
        if pid and pid == (os.getenv("BILLING_ANDROID_DUO_PRODUCT_ID") or "").strip():
            return "nova_streamer_duo"
    if p == "ios":
        if pid and pid == (os.getenv("BILLING_IOS_ONE_PRODUCT_ID") or "").strip():
            return "nova_streamer_one_mobile"
        if pid and pid == (os.getenv("BILLING_IOS_DUO_PRODUCT_ID") or "").strip():
            return "nova_streamer_duo"

    raise HTTPException(status_code=400, detail="unknown product_id")


class VerifyRequest(BaseModel):
    platform: str  # android|ios
    product_id: str
    verification_data: str
    package_name: str | None = None  # android


class VerifyResponse(BaseModel):
    status: str = "ok"
    plan: str
    expires_at: str | None = None


async def _verify_ios_receipt(receipt_b64: str) -> tuple[bool, datetime | None, dict]:
    password = (os.getenv("APPLE_SHARED_SECRET") or "").strip()
    if not password:
        raise HTTPException(status_code=500, detail="APPLE_SHARED_SECRET not set")

    payload = {
        "receipt-data": receipt_b64,
        "password": password,
        "exclude-old-transactions": True,
    }

    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.post("https://buy.itunes.apple.com/verifyReceipt", json=payload)
        data = resp.json()

        # sandbox redirect
        if data.get("status") == 21007:
            resp = await client.post("https://sandbox.itunes.apple.com/verifyReceipt", json=payload)
            data = resp.json()

    if data.get("status") != 0:
        return (False, None, data)

    # берем самое позднее expires_date_ms
    latest = None
    infos = data.get("latest_receipt_info") or []
    for item in infos:
        ms = item.get("expires_date_ms")
        try:
            v = int(ms)
        except Exception:
            continue
        if latest is None or v > latest:
            latest = v

    if latest is None:
        return (False, None, data)

    expires_at = datetime.fromtimestamp(latest / 1000, tz=timezone.utc).replace(tzinfo=None)
    active = expires_at >= _now_utc()
    return (active, expires_at, data)


async def _verify_android_subscription(package_name: str, product_id: str, purchase_token: str) -> tuple[bool, datetime | None, dict]:
    """Google Play verify через Android Publisher API.

    Требует env:
      GOOGLE_SERVICE_ACCOUNT_JSON или GOOGLE_SERVICE_ACCOUNT_FILE
    """

    try:
        from google.oauth2 import service_account
        from googleapiclient.discovery import build
    except Exception:
        raise HTTPException(status_code=500, detail="google api libs not installed")

    sa_json = (os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON") or "").strip()
    sa_file = (os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE") or "").strip()
    if not sa_json and not sa_file:
        raise HTTPException(status_code=500, detail="GOOGLE_SERVICE_ACCOUNT_JSON/FILE not set")

    if sa_json:
        info = json.loads(sa_json)
        creds = service_account.Credentials.from_service_account_info(
            info,
            scopes=["https://www.googleapis.com/auth/androidpublisher"],
        )
    else:
        creds = service_account.Credentials.from_service_account_file(
            sa_file,
            scopes=["https://www.googleapis.com/auth/androidpublisher"],
        )

    service = build("androidpublisher", "v3", credentials=creds, cache_discovery=False)

    # Старый endpoint subscriptions.get поддерживается широко.
    req = service.purchases().subscriptions().get(
        packageName=package_name,
        subscriptionId=product_id,
        token=purchase_token,
    )
    data = req.execute()

    expiry_ms = data.get("expiryTimeMillis")
    expires_at = None
    if expiry_ms is not None:
        try:
            expires_at = datetime.fromtimestamp(int(expiry_ms) / 1000, tz=timezone.utc).replace(tzinfo=None)
        except Exception:
            expires_at = None

    cancel_reason = data.get("cancelReason")
    payment_state = data.get("paymentState")

    active = bool(expires_at and expires_at >= _now_utc())
    # если явно отменено (cancelReason != null), считаем не active
    if cancel_reason is not None:
        active = False
    # если paymentState == 0 (pending), тоже не active
    if payment_state == 0:
        active = False

    return (active, expires_at, data)


def _upsert_entitlement_license(db: Session, user_id: str, plan: str, expires_at: datetime | None, key: str) -> None:
    now = _now_utc()
    status = models.LicenseStatus.active if (expires_at is None or expires_at >= now) else models.LicenseStatus.inactive

    lic = db.query(models.LicenseKey).filter(models.LicenseKey.key == key).first()
    if not lic:
        lic = models.LicenseKey(
            key=key,
            plan=plan,
            status=status,
            expires_at=expires_at,
            user_id=user_id,
            max_devices=1,
            devices_bound=1,
        )
        db.add(lic)
        return

    lic.user_id = user_id
    lic.plan = plan
    lic.status = status
    lic.expires_at = expires_at


@router.post("/verify", response_model=VerifyResponse)
async def verify(
    req: VerifyRequest,
    user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    platform = (req.platform or "").strip().lower()
    product_id = (req.product_id or "").strip()
    token = (req.verification_data or "").strip()

    if platform not in ("android", "ios"):
        raise HTTPException(status_code=400, detail="invalid platform")
    if not product_id or not token:
        raise HTTPException(status_code=400, detail="missing product_id/verification_data")

    plan = canonicalize_license_plan(_product_to_plan(platform, product_id))

    active = False
    expires_at: datetime | None = None
    raw: dict = {}

    if platform == "ios":
        active, expires_at, raw = await _verify_ios_receipt(token)
        purchase_token = _hash_token(token)
    else:
        package_name = (req.package_name or os.getenv("ANDROID_PACKAGE_NAME") or "").strip()
        if not package_name:
            raise HTTPException(status_code=400, detail="missing package_name")
        active, expires_at, raw = await _verify_android_subscription(package_name, product_id, token)
        purchase_token = token

    status = models.StorePurchaseStatus.active if active else models.StorePurchaseStatus.expired

    # upsert store_purchases
    sp = (
        db.query(models.StorePurchase)
        .filter(models.StorePurchase.platform == platform)
        .filter(models.StorePurchase.purchase_token == purchase_token)
        .first()
    )
    now = _now_utc()
    if not sp:
        sp = models.StorePurchase(
            user_id=user.id,
            platform=platform,
            product_id=product_id,
            purchase_token=purchase_token,
            status=status,
            expires_at=expires_at,
            raw=raw,
            created_at=now,
            updated_at=now,
        )
        db.add(sp)
    else:
        sp.user_id = user.id
        sp.product_id = product_id
        sp.status = status
        sp.expires_at = expires_at
        sp.raw = raw
        sp.updated_at = now

    # upsert entitlement license (internal)
    license_key = f"SUB-{platform.upper()}-{_hash_token(purchase_token)}"
    _upsert_entitlement_license(db, user.id, plan, expires_at if active else expires_at, license_key)

    db.commit()

    return VerifyResponse(plan=plan, expires_at=expires_at.isoformat() if expires_at else None)
