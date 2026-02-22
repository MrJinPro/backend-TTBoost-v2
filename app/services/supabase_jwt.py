import os
from functools import lru_cache

import jwt
from jwt import PyJWKClient


class SupabaseJwtError(Exception):
    pass


def _get_supabase_url() -> str:
    url = (os.getenv("SUPABASE_URL") or "").strip()
    return url.rstrip("/")


def _get_jwks_url() -> str:
    explicit = (os.getenv("SUPABASE_JWKS_URL") or "").strip()
    if explicit:
        return explicit
    base = _get_supabase_url()
    if not base:
        return ""
    return f"{base}/auth/v1/keys"


def _get_issuer() -> str:
    explicit = (os.getenv("SUPABASE_ISSUER") or "").strip()
    if explicit:
        return explicit.rstrip("/")
    base = _get_supabase_url()
    if not base:
        return ""
    return f"{base}/auth/v1"


def _get_audience() -> str:
    return (os.getenv("SUPABASE_JWT_AUD") or os.getenv("SUPABASE_AUD") or "authenticated").strip() or "authenticated"


@lru_cache(maxsize=1)
def _jwk_client() -> PyJWKClient:
    jwks_url = _get_jwks_url()
    if not jwks_url:
        raise SupabaseJwtError("SUPABASE_URL or SUPABASE_JWKS_URL is not configured")
    return PyJWKClient(jwks_url)


def verify_supabase_access_token(token: str) -> dict:
    """Verifies Supabase RS256 access_token using JWKS.

    Returns decoded JWT payload.
    """
    if not token or not token.strip():
        raise SupabaseJwtError("missing token")

    issuer = _get_issuer()
    if not issuer:
        raise SupabaseJwtError("SUPABASE_URL or SUPABASE_ISSUER is not configured")

    aud = _get_audience()

    try:
        signing_key = _jwk_client().get_signing_key_from_jwt(token)
        payload = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            audience=aud,
            issuer=issuer,
            options={"require": ["exp", "iat", "sub"]},
        )
        return payload
    except Exception as e:
        raise SupabaseJwtError(str(e))
