import base64
import os

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from .auth_v2 import get_current_user

router = APIRouter()

_SPOTIFY_TOKEN_URL = 'https://accounts.spotify.com/api/token'


def _spotify_client_id() -> str:
    return (os.getenv('SPOTIFY_CLIENT_ID') or '').strip()


def _spotify_client_secret() -> str:
    return (os.getenv('SPOTIFY_CLIENT_SECRET') or '').strip()


def _spotify_redirect_uri() -> str:
    return (os.getenv('SPOTIFY_REDIRECT_URI') or 'novaboost://spotify-auth').strip()


def _spotify_enabled() -> bool:
    return bool(_spotify_client_id() and _spotify_redirect_uri())


def _spotify_basic_auth_header() -> str:
    client_id = _spotify_client_id()
    client_secret = _spotify_client_secret()
    if not client_id or not client_secret:
        raise HTTPException(status_code=503, detail='Spotify backend auth is not configured')

    raw = f'{client_id}:{client_secret}'.encode('utf-8')
    return f"Basic {base64.b64encode(raw).decode('ascii')}"


class SpotifyConfigResponse(BaseModel):
    enabled: bool
    client_id: str | None = None
    redirect_uri: str | None = None


class SpotifyExchangeRequest(BaseModel):
    code: str
    redirect_uri: str | None = None
    code_verifier: str | None = None


class SpotifyRefreshRequest(BaseModel):
    refresh_token: str


@router.get('/config', response_model=SpotifyConfigResponse)
def spotify_config():
    enabled = _spotify_enabled()
    return SpotifyConfigResponse(
        enabled=enabled,
        client_id=_spotify_client_id() if enabled else None,
        redirect_uri=_spotify_redirect_uri() if enabled else None,
    )


async def _spotify_token_request(form: dict[str, str]) -> dict:
    headers = {
        'Authorization': _spotify_basic_auth_header(),
        'Content-Type': 'application/x-www-form-urlencoded',
    }
    timeout = httpx.Timeout(15.0)
    async with httpx.AsyncClient(timeout=timeout) as client:
        resp = await client.post(_SPOTIFY_TOKEN_URL, data=form, headers=headers)

    try:
        payload = resp.json()
    except Exception:
        payload = {'error': resp.text}

    if resp.status_code < 200 or resp.status_code >= 300:
        detail = payload.get('error_description') or payload.get('error') or resp.text or 'Spotify token request failed'
        raise HTTPException(status_code=resp.status_code, detail=str(detail))

    if not isinstance(payload, dict):
        raise HTTPException(status_code=502, detail='Invalid Spotify token response')

    return payload


@router.post('/exchange')
async def spotify_exchange(req: SpotifyExchangeRequest, _user=Depends(get_current_user)):
    code = (req.code or '').strip()
    if not code:
        raise HTTPException(status_code=400, detail='code is required')

    redirect_uri = (req.redirect_uri or _spotify_redirect_uri()).strip()
    if not redirect_uri:
        raise HTTPException(status_code=503, detail='Spotify redirect_uri is not configured')

    form = {
        'grant_type': 'authorization_code',
        'code': code,
        'redirect_uri': redirect_uri,
    }
    code_verifier = (req.code_verifier or '').strip()
    if code_verifier:
        form['code_verifier'] = code_verifier

    payload = await _spotify_token_request(form)
    return {
        'access_token': payload.get('access_token'),
        'refresh_token': payload.get('refresh_token'),
        'expires_in': payload.get('expires_in'),
        'scope': payload.get('scope'),
        'token_type': payload.get('token_type'),
    }


@router.post('/refresh')
async def spotify_refresh(req: SpotifyRefreshRequest, _user=Depends(get_current_user)):
    refresh_token = (req.refresh_token or '').strip()
    if not refresh_token:
        raise HTTPException(status_code=400, detail='refresh_token is required')

    payload = await _spotify_token_request({
        'grant_type': 'refresh_token',
        'refresh_token': refresh_token,
    })

    return {
        'access_token': payload.get('access_token'),
        'refresh_token': payload.get('refresh_token') or refresh_token,
        'expires_in': payload.get('expires_in'),
        'scope': payload.get('scope'),
        'token_type': payload.get('token_type'),
    }
