import os
from functools import lru_cache
import json
import time

import httpx
import jwt
from jwt import algorithms


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
    # Supabase may expose JWKS either at /auth/v1/keys or /.well-known/jwks.json.
    # We'll try multiple endpoints during fetch.
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


def _get_supabase_apikey() -> str:
    # `SUPABASE_ANON_KEY` is safe to use as apikey header for JWKS/userinfo endpoints.
    return (os.getenv("SUPABASE_ANON_KEY") or os.getenv("SUPABASE_KEY") or "").strip()


_JWKS_CACHE: dict = {"ts": 0.0, "jwks": None, "src": None}


def _fetch_supabase_jwks() -> dict:
    base = _get_supabase_url()
    jwks_url = _get_jwks_url()
    if not base and not jwks_url:
        raise SupabaseJwtError("SUPABASE_URL or SUPABASE_JWKS_URL is not configured")

    ttl_s = float((os.getenv("SUPABASE_JWKS_CACHE_TTL_SECONDS") or "600").strip() or "600")
    now = time.time()
    cached = _JWKS_CACHE.get("jwks")
    if cached is not None and (now - float(_JWKS_CACHE.get("ts") or 0.0)) < ttl_s:
        return cached

    timeout_s = float((os.getenv("SUPABASE_JWKS_TIMEOUT_SECONDS") or "8").strip() or "8")
    apikey = _get_supabase_apikey()
    headers = {"apikey": apikey} if apikey else {}

    candidates: list[str] = []
    if jwks_url:
        candidates.append(jwks_url)
    if base:
        # Common locations.
        candidates.extend(
            [
                f"{base}/auth/v1/.well-known/jwks.json",
                f"{base}/auth/v1/keys",
                f"{base}/.well-known/jwks.json",
            ]
        )

    last_status = None
    last_body = None
    for url in candidates:
        try:
            r = httpx.get(url, headers=headers, timeout=timeout_s)
        except Exception as e:
            last_body = str(e)
            continue

        last_status = r.status_code
        if r.status_code != 200:
            # keep last response text for diagnostics
            try:
                last_body = r.text[:400]
            except Exception:
                last_body = None
            continue

        try:
            jwks = r.json() or {}
        except Exception as e:
            last_body = f"invalid json: {e}"
            continue

        # Normalize: some endpoints may return {"keys": [...]}.
        if isinstance(jwks, dict) and "keys" in jwks and isinstance(jwks.get("keys"), list):
            normalized = jwks
        elif isinstance(jwks, list):
            normalized = {"keys": jwks}
        else:
            normalized = jwks

        _JWKS_CACHE["ts"] = now
        _JWKS_CACHE["jwks"] = normalized
        _JWKS_CACHE["src"] = url
        return normalized

    raise SupabaseJwtError(f"unable to fetch JWKS (status={last_status}, body={last_body})")


def _select_key_for_token(token: str) -> object:
    try:
        hdr = jwt.get_unverified_header(token)
    except Exception as e:
        raise SupabaseJwtError(f"invalid token header: {e}")

    kid = (hdr.get("kid") or "").strip()
    jwks = _fetch_supabase_jwks()
    keys = jwks.get("keys") if isinstance(jwks, dict) else None
    if not isinstance(keys, list) or not keys:
        raise SupabaseJwtError("JWKS has no keys")

    chosen = None
    if kid:
        for k in keys:
            if isinstance(k, dict) and str(k.get("kid") or "").strip() == kid:
                chosen = k
                break
    if chosen is None:
        # Fallback: pick the first key if kid is absent/unmatched.
        chosen = keys[0]

    if not isinstance(chosen, dict):
        raise SupabaseJwtError("invalid JWKS key format")

    jwk_json = json.dumps(chosen)
    kty = (chosen.get("kty") or "").upper()
    try:
        if kty == "EC":
            return algorithms.ECAlgorithm.from_jwk(jwk_json)
        if kty == "RSA":
            return algorithms.RSAAlgorithm.from_jwk(jwk_json)
    except Exception as e:
        raise SupabaseJwtError(f"unable to build public key: {e}")

    raise SupabaseJwtError(f"unsupported jwk kty: {kty}")


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
        public_key = _select_key_for_token(token)
        payload = jwt.decode(
            token,
            public_key,
            # Supabase may use RS256 (older) or ES256 (ECC P-256 signing keys).
            algorithms=["RS256", "ES256"],
            audience=aud,
            issuer=issuer,
            options={"require": ["exp", "iat", "sub"]},
        )
        return payload
    except Exception as e:
        raise SupabaseJwtError(str(e))
