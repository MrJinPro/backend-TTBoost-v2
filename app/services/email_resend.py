import os
from typing import Any

import httpx


class ResendError(RuntimeError):
    pass


def _resend_api_key() -> str:
    key = (os.getenv("RESEND_API_KEY") or "").strip()
    if not key:
        raise ResendError("RESEND_API_KEY is not set")
    return key


def _resend_from() -> str:
    sender = (os.getenv("RESEND_FROM") or "").strip()
    if not sender:
        # Must be a verified sender/domain in Resend.
        raise ResendError("RESEND_FROM is not set")
    return sender


async def send_email(*, to_email: str, subject: str, text: str) -> dict[str, Any]:
    """Send an email using Resend (https://resend.com).

    Env:
      - RESEND_API_KEY
      - RESEND_FROM (e.g. 'NovaBoost <no-reply@novaboost.cloud>')
    """

    api_key = _resend_api_key()
    sender = _resend_from()

    payload = {
        "from": sender,
        "to": [to_email],
        "subject": subject,
        "text": text,
    }

    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(
            "https://api.resend.com/emails",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
        )

    if resp.status_code >= 400:
        # Don't leak API key or full response; include minimal diagnostics.
        raise ResendError(f"Resend API error: {resp.status_code} {resp.text[:300]}")

    try:
        return resp.json()
    except Exception:
        return {"status": "ok"}
