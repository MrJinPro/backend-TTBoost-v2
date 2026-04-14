import os
import re
import time
from urllib.parse import quote, urljoin, urlparse

import httpx
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from pydantic import BaseModel
from mutagen import File as MutagenFile

from app.db.database import SessionLocal
from app.db import models
from .auth_v2 import get_current_user


router = APIRouter()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# Ограничение только по размеру файла (1 MiB)
MAX_BYTES = 1024 * 1024
_MYINSTANTS_BASE = "https://www.myinstants.com"
_HTTP_TIMEOUT = httpx.Timeout(20.0)
_MYINSTANTS_CATALOG_TTL_SECONDS = 600.0
_MYINSTANTS_CATALOG_CACHE: list[dict[str, str]] = []
_MYINSTANTS_CATALOG_CACHE_AT = 0.0


def _media_root(user_id: str) -> str:
    """Базовая директория для пользовательских звуков.

    Если задан MEDIA_ROOT (как корень для /static), кладём звуки в MEDIA_ROOT/sounds/<user_id>.
    Иначе используем локальную app/static/sounds/<user_id>.
    Это должно соответствовать URL /static/sounds/<user_id>/<filename>.
    """
    media_root = os.getenv("MEDIA_ROOT")
    if media_root:
        root = os.path.join(media_root, "sounds")
    else:
        root = os.path.join(os.path.dirname(__file__), "..", "static", "sounds")
    root = os.path.abspath(root)
    path = os.path.join(root, user_id)
    os.makedirs(path, exist_ok=True)
    return path


def _media_base_url() -> str:
    return (os.getenv("MEDIA_BASE_URL") or os.getenv("TTS_BASE_URL") or os.getenv("SERVER_HOST") or "http://localhost:8000").rstrip("/")


def _safe_filename(name: str) -> str:
    base = re.sub(r"[^A-Za-z0-9._-]+", "_", (name or "").strip()).strip("._")
    return base or "sound"


def _unique_user_filename(db: Session, user_id: str, preferred_name: str) -> str:
    safe_name = _safe_filename(preferred_name)
    stem, ext = os.path.splitext(safe_name)
    ext = ext or ".mp3"
    candidate = f"{stem}{ext}"
    index = 2
    while db.query(models.SoundFile).filter(models.SoundFile.user_id == user_id, models.SoundFile.filename == candidate).first() is not None:
        candidate = f"{stem}_{index}{ext}"
        index += 1
    return candidate


def _store_sound_bytes(db: Session, user: models.User, filename: str, content: bytes, kind: models.SoundType = models.SoundType.uploaded):
    if len(content) > MAX_BYTES:
        raise HTTPException(400, detail="file too large (1MB max)")

    duration_sec = None
    root = _media_root(user.id)
    tmp_path = None
    try:
        tmp_path = os.path.join(root, "._tmp_" + filename)
        with open(tmp_path, "wb") as tmp:
            tmp.write(content)
        mf = MutagenFile(tmp_path)
        if mf and mf.info and getattr(mf.info, 'length', None):
            duration_sec = float(mf.info.length)
    except Exception:
        duration_sec = None
    finally:
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except Exception:
                pass

    final_name = _unique_user_filename(db, user.id, filename)
    dst = os.path.join(root, final_name)
    with open(dst, "wb") as f:
        f.write(content)

    url = f"{_media_base_url()}/static/sounds/{user.id}/{final_name}"
    rec = models.SoundFile(
        user_id=user.id,
        filename=final_name,
        url=url,
        bytes=len(content),
        duration_ms=int(duration_sec * 1000) if duration_sec else None,
        kind=kind,
    )
    db.add(rec)
    db.commit()
    return {"status": "ok", "filename": final_name, "url": url}


def _myinstants_headers() -> dict[str, str]:
    return {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0 Safari/537.36",
        "Accept-Language": "ru,en;q=0.9",
    }


def _parse_myinstants_search(html: str) -> list[dict[str, str]]:
    matches = re.findall(r'<a[^>]+href="([^"]*?/instant/[^"]+/)"[^>]*>([^<]+)</a>', html, flags=re.IGNORECASE)
    seen: set[str] = set()
    results: list[dict[str, str]] = []
    for href, title in matches:
        page_url = urljoin(_MYINSTANTS_BASE, href)
        if page_url in seen:
            continue
        seen.add(page_url)
        clean_title = re.sub(r"\s+", " ", title).strip()
        if not clean_title:
            continue
        results.append({"title": clean_title, "page_url": page_url})
        if len(results) >= 20:
            break
    return results


async def _load_myinstants_catalog(force_refresh: bool = False) -> list[dict[str, str]]:
    global _MYINSTANTS_CATALOG_CACHE, _MYINSTANTS_CATALOG_CACHE_AT

    now = time.monotonic()
    if not force_refresh and _MYINSTANTS_CATALOG_CACHE and (now - _MYINSTANTS_CATALOG_CACHE_AT) < _MYINSTANTS_CATALOG_TTL_SECONDS:
        return list(_MYINSTANTS_CATALOG_CACHE)

    catalog_urls = [
        f"{_MYINSTANTS_BASE}/ru/",
        f"{_MYINSTANTS_BASE}/",
    ]
    parsed_items: list[dict[str, str]] = []

    async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT, follow_redirects=True, headers=_myinstants_headers()) as client:
        for catalog_url in catalog_urls:
            try:
                resp = await client.get(catalog_url)
            except Exception:
                continue

            if resp.status_code < 200 or resp.status_code >= 300:
                continue

            parsed_items = _parse_myinstants_search(resp.text)
            if parsed_items:
                break

    if parsed_items:
        _MYINSTANTS_CATALOG_CACHE = parsed_items
        _MYINSTANTS_CATALOG_CACHE_AT = now

    return list(_MYINSTANTS_CATALOG_CACHE)


def _extract_myinstants_mp3(html: str, page_url: str) -> tuple[str | None, str | None]:
    title_match = re.search(r"<h1[^>]*>\s*([^<]+?)\s*</h1>", html, flags=re.IGNORECASE)
    title = title_match.group(1).strip() if title_match else None
    mp3_match = re.search(r'href="([^"]+/media/sounds/[^"]+\.mp3)"', html, flags=re.IGNORECASE)
    mp3_url = urljoin(page_url, mp3_match.group(1)) if mp3_match else None
    return title, mp3_url


class ExternalSoundImportRequest(BaseModel):
    page_url: str
    title: str | None = None


@router.get("/external/myinstants/preview")
async def myinstants_preview(page_url: str, user: models.User = Depends(get_current_user)):
    target_url = (page_url or "").strip()
    if not target_url:
        raise HTTPException(400, detail="page_url is required")

    parsed = urlparse(target_url)
    if parsed.netloc.lower() != "www.myinstants.com" or "/instant/" not in parsed.path:
        raise HTTPException(400, detail="invalid myinstants url")

    async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT, follow_redirects=True, headers=_myinstants_headers()) as client:
        page_resp = await client.get(target_url)

    if page_resp.status_code < 200 or page_resp.status_code >= 300:
        raise HTTPException(502, detail="failed to open myinstants page")

    title, mp3_url = _extract_myinstants_mp3(page_resp.text, target_url)
    if not mp3_url:
        raise HTTPException(502, detail="failed to locate mp3 on myinstants page")

    return {"title": title, "preview_url": mp3_url}


@router.get("/external/myinstants/catalog")
async def myinstants_catalog(
    q: str = "",
    limit: int = 30,
    offset: int = 0,
    user: models.User = Depends(get_current_user),
):
    query = (q or "").strip().lower()
    safe_limit = min(max(int(limit or 30), 1), 100)
    safe_offset = max(int(offset or 0), 0)

    items = await _load_myinstants_catalog()
    if query:
        items = [
            item for item in items
            if query in (item.get("title") or "").lower() or query in (item.get("page_url") or "").lower()
        ]

    page = items[safe_offset:safe_offset + safe_limit]
    return {
        "items": page,
        "total": len(items),
        "offset": safe_offset,
        "limit": safe_limit,
    }


@router.get("/external/myinstants/search")
async def myinstants_search(q: str, user: models.User = Depends(get_current_user)):
    query = (q or "").strip()
    if len(query) < 2:
        items = await _load_myinstants_catalog()
        return {"items": items[:20]}

    search_url = f"{_MYINSTANTS_BASE}/ru/search/?name={quote(query)}"
    async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT, follow_redirects=True, headers=_myinstants_headers()) as client:
        resp = await client.get(search_url)

    if resp.status_code < 200 or resp.status_code >= 300:
        raise HTTPException(502, detail="myinstants search failed")

    items = _parse_myinstants_search(resp.text)
    if not items:
        catalog_items = await _load_myinstants_catalog()
        q_lower = query.lower()
        items = [
            item for item in catalog_items
            if q_lower in (item.get("title") or "").lower() or q_lower in (item.get("page_url") or "").lower()
        ]
    return {"items": items}


@router.post("/external/myinstants/import")
async def myinstants_import(req: ExternalSoundImportRequest, user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    page_url = (req.page_url or "").strip()
    if not page_url:
        raise HTTPException(400, detail="page_url is required")

    parsed = urlparse(page_url)
    if parsed.netloc.lower() != "www.myinstants.com" or "/instant/" not in parsed.path:
        raise HTTPException(400, detail="invalid myinstants url")

    async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT, follow_redirects=True, headers=_myinstants_headers()) as client:
        page_resp = await client.get(page_url)
        if page_resp.status_code < 200 or page_resp.status_code >= 300:
            raise HTTPException(502, detail="failed to open myinstants page")

        parsed_title, mp3_url = _extract_myinstants_mp3(page_resp.text, page_url)
        if not mp3_url:
            raise HTTPException(502, detail="failed to locate mp3 on myinstants page")

        media_resp = await client.get(mp3_url)
        if media_resp.status_code < 200 or media_resp.status_code >= 300:
            raise HTTPException(502, detail="failed to download myinstants mp3")

    content = media_resp.content
    if not content:
        raise HTTPException(502, detail="empty myinstants mp3")

    title = (req.title or parsed_title or "myinstants_sound").strip()
    filename = _safe_filename(f"myinstants_{title}.mp3")
    return _store_sound_bytes(db, user, filename, content, kind=models.SoundType.uploaded)


@router.post("/upload")
async def upload_sound(user: models.User = Depends(get_current_user), db: Session = Depends(get_db), file: UploadFile = File(...)):
    content = await file.read()
    safe_name = file.filename.replace("/", "_").replace("\\", "_")
    try:
        return _store_sound_bytes(db, user, safe_name, content, kind=models.SoundType.uploaded)
    except IntegrityError:
        db.rollback()
        existing = db.query(models.SoundFile).filter(models.SoundFile.user_id == user.id, models.SoundFile.filename == safe_name).first()
        if existing:
            return {"status": "exists", "filename": existing.filename, "url": existing.url}
        raise HTTPException(409, detail="duplicate sound filename")


class SoundListItem(BaseModel):
    filename: str
    url: str


@router.get("/list")
def list_sounds(user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    items = db.query(models.SoundFile).filter(models.SoundFile.user_id == user.id).order_by(models.SoundFile.created_at.desc()).all()
    return {"sounds": [{"filename": it.filename, "url": it.url} for it in items]}
