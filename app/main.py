from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import os
from dotenv import load_dotenv

# Важно: загружаем .env до импорта роутов, чтобы переменные окружения
# были доступны во всех сервисах при инициализации (например, SIGN_SERVER_URL)
load_dotenv()  # Load ENV, SERVER_HOST, TTS_BASE_URL, SIGN_SERVER_URL

from app.routes import auth, tts, ws, voices, sounds, profile, catalog, triggers
from app.db.database import init_db
from app.routes_v2 import auth_v2, settings_v2, sounds_v2, triggers_v2, ws_v2, license_v2, voices_v2, gifts_v2

app = FastAPI(title="TTBoost Backend", version="0.1.0")

ALLOWED_ORIGINS_ENV = os.getenv("ALLOWED_ORIGINS")
if ALLOWED_ORIGINS_ENV:
    allowed_origins = [o.strip() for o in ALLOWED_ORIGINS_ENV.split(",") if o.strip()]
else:
    # По умолчанию разрешаем localhost и 127.* (Flutter web dev) + прод домен из SERVER_HOST
    server_host = os.getenv("SERVER_HOST", "https://api.ttboost.pro").rstrip("/")
    allowed_origins = [
        "http://localhost",
        "http://127.0.0.1",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        server_host.replace("https://", "http://"),
        server_host,
    ]

# ВАЖНО: если allow_credentials=True, нельзя использовать "*" как origin, иначе браузер отбросит ответ.
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

@app.middleware("http")
async def dynamic_origin(request: Request, call_next):
    """Подстраховка: проставляем точный Access-Control-Allow-Origin если Origin входит в разрешённый список.
    А также корректно отвечаем на preflight OPTIONS (даже если роут не найден)."""
    origin = request.headers.get("origin") or request.headers.get("Origin")
    if request.method == "OPTIONS":
        # Формируем быстрый preflight ответ (FastAPI сам тоже обработает, но мы гарантируем заголовки).
        from fastapi.responses import Response
        resp = Response(status_code=200)
        if origin and any(origin.startswith(o.rstrip("/")) for o in allowed_origins):
            resp.headers["Access-Control-Allow-Origin"] = origin
        resp.headers["Access-Control-Allow-Credentials"] = "true"
        resp.headers["Access-Control-Allow-Methods"] = "GET,POST,PUT,PATCH,DELETE,OPTIONS"
        req_headers = request.headers.get("Access-Control-Request-Headers", "*")
        resp.headers["Access-Control-Allow-Headers"] = req_headers or "*"
        resp.headers["Vary"] = "Origin"
        return resp

    response = await call_next(request)
    if origin and any(origin.startswith(o.rstrip("/")) for o in allowed_origins):
        # Ставим конкретный origin (не *) если он разрешён
        response.headers.setdefault("Access-Control-Allow-Origin", origin)
        response.headers.setdefault("Vary", "Origin")
        response.headers.setdefault("Access-Control-Allow-Credentials", "true")
    return response

# Static files
BASE_DIR = os.path.dirname(__file__)
STATIC_DIR = os.path.join(BASE_DIR, "static")
os.makedirs(os.path.join(STATIC_DIR, "tts"), exist_ok=True)
os.makedirs(os.path.join(STATIC_DIR, "sounds"), exist_ok=True)

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

app.include_router(auth.router, prefix="/auth", tags=["auth"])
app.include_router(tts.router, prefix="/tts", tags=["tts"])
app.include_router(voices.router, prefix="/voices", tags=["voices"])
app.include_router(sounds.router, prefix="/sounds", tags=["sounds"])
app.include_router(profile.router, prefix="/profile", tags=["profile"])
app.include_router(catalog.router, prefix="/catalog", tags=["catalog"])
app.include_router(triggers.router, prefix="/triggers", tags=["triggers"])
app.include_router(ws.router, tags=["ws"])

# v2 API (логин/пароль, Bearer JWT, хранение в БД)
init_db()
app.include_router(auth_v2.router, prefix="/v2/auth", tags=["v2-auth"])
app.include_router(settings_v2.router, prefix="/v2/settings", tags=["v2-settings"])
app.include_router(sounds_v2.router, prefix="/v2/sounds", tags=["v2-sounds"])
app.include_router(triggers_v2.router, prefix="/v2/triggers", tags=["v2-triggers"])
app.include_router(ws_v2.router, prefix="/v2", tags=["v2-ws"])
app.include_router(license_v2.router, prefix="/v2/license", tags=["v2-license"])
app.include_router(voices_v2.router, prefix="/v2", tags=["v2-voices"])
app.include_router(gifts_v2.router, prefix="/v2/gifts", tags=["v2-gifts"])


@app.get("/")
async def root():
    return {
        "status": "ok",
        "service": "ttboost-backend",
        "env": os.getenv("ENV", "dev"),
        "server_host": os.getenv("SERVER_HOST"),
        "tts_base_url": os.getenv("TTS_BASE_URL"),
    }
