from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import os
import logging
from logging.handlers import RotatingFileHandler
from dotenv import load_dotenv
from urllib.parse import urlparse

# Важно: загружаем .env до импорта роутов, чтобы переменные окружения
# были доступны во всех сервисах при инициализации (например, SIGN_SERVER_URL)
load_dotenv()  # Load ENV, SERVER_HOST, TTS_BASE_URL, SIGN_SERVER_URL

from app.routes import auth, tts, ws, voices, sounds, profile, catalog, triggers
from app.db.database import init_db
from app.routes_v2 import auth_v2, settings_v2, sounds_v2, triggers_v2, ws_v2, license_v2, voices_v2, gifts_v2, admin_v2, profile_v2, billing_v2, tiktok_v2, notifications_v2

from datetime import datetime
from sqlalchemy import text
from app.services.tiktok_service import tiktok_service

app = FastAPI(title="TTBoost Backend", version="0.1.0")
START_TIME = datetime.utcnow()

ALLOWED_ORIGINS_ENV = os.getenv("ALLOWED_ORIGINS")
ALLOW_LOCALHOST_DEV = os.getenv("ALLOW_LOCALHOST_DEV", "1")  # если 1, то любые http://localhost:<port> и http://127.0.0.1:<port>

# Безопасно парсим ALLOWED_ORIGINS: если переменная отсутствует или не содержит валидных
# значений (пустая строка, пустые значения через запятую), используем дефолтный набор.
parsed_allowed = []
if ALLOWED_ORIGINS_ENV:
    # Разделяем по запятой и убираем пустые/пробельные элементы
    parsed_allowed = [o.strip() for o in ALLOWED_ORIGINS_ENV.split(",") if o and o.strip()]

if parsed_allowed:
    allowed_origins = parsed_allowed
else:
    # По умолчанию разрешаем localhost и 127.* (Flutter web dev) + прод домен из SERVER_HOST
    server_host = os.getenv("SERVER_HOST", "https://api.ttboost.pro").rstrip("/")
    allowed_origins = [
        "http://localhost",
        "http://127.0.0.1",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        # основной веб-домен (покупка/активация лицензии)
        "https://ttboost.pro",
        "https://www.ttboost.pro",
        # фронтенд на production
        "https://mobile.ttboost.pro",
        server_host.replace("https://", "http://"),
        server_host,
    ]


def _normalize_allowed_origins(entries: list[str]) -> tuple[list[str], list[str]]:
    """Нормализует ALLOWED_ORIGINS.

    Поддерживаем варианты:
    - https://example.com
    - https://example.com/
    - https://example.com/path
    - example.com
    - example.com:3000
    """
    origin_prefixes: list[str] = []
    hosts: list[str] = []

    for raw in entries or []:
        if not raw:
            continue
        s = raw.strip()
        if not s:
            continue
        s = s.rstrip("/")

        if "://" in s:
            p = urlparse(s)
            if p.scheme and p.netloc:
                origin_prefixes.append(f"{p.scheme}://{p.netloc}")
            else:
                # Fallback: оставляем как есть (лучше, чем потерять правило)
                origin_prefixes.append(s)
        else:
            # host[:port][/path] -> host[:port]
            if "/" in s:
                s = s.split("/", 1)[0]
            hosts.append(s)

    return origin_prefixes, hosts


_ALLOWED_ORIGIN_PREFIXES, _ALLOWED_HOSTS = _normalize_allowed_origins(allowed_origins)

# ВАЖНО: если allow_credentials=True, нельзя использовать "*" как origin, иначе браузер отбросит ответ.
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

# ==== ЛОГИРОВАНИЕ С РОТАЦИЕЙ =====
LOG_DIR = os.path.join(os.path.dirname(__file__), "logs")
os.makedirs(LOG_DIR, exist_ok=True)
LOG_FILE = os.getenv("BACKEND_LOG_FILE", os.path.join(LOG_DIR, "backend.log"))
_log_handler_exists = any(isinstance(h, RotatingFileHandler) for h in logging.getLogger().handlers)
if not _log_handler_exists:
    file_handler = RotatingFileHandler(LOG_FILE, maxBytes=2_000_000, backupCount=3, encoding="utf-8")
    formatter = logging.Formatter(fmt="%(asctime)s [%(levelname)s] %(name)s: %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
    file_handler.setFormatter(formatter)
    logging.getLogger().addHandler(file_handler)
    logging.getLogger().setLevel(logging.INFO)
    logging.getLogger(__name__).info(f"Файловый лог активирован: {LOG_FILE}")

ALLOW_LOGS = os.getenv("ALLOW_LOGS", "0")  # Если 1, разрешаем /logs

@app.middleware("http")
async def dynamic_origin(request: Request, call_next):
    """Динамическая установка CORS Origin + надёжный preflight.
    Логика допуска origin:
    1. Точное или prefix совпадение из allowed_origins.
    2. Если ALLOW_LOCALHOST_DEV=1, то любой http://localhost:<port> или http://127.0.0.1:<port>.
    """
    origin = request.headers.get("origin") or request.headers.get("Origin")

    def _parse_origin(o: str):
        try:
            p = urlparse(o)
        except Exception:
            return None, None, None
        if not p.scheme or not p.netloc:
            return None, None, None
        origin_base = f"{p.scheme}://{p.netloc}"
        return origin_base, p.netloc, p.hostname

    def is_allowed_origin(o: str) -> bool:
        if not o:
            return False

        origin_base, origin_netloc, origin_host = _parse_origin(o)
        if not origin_base:
            return False

        # 1) Явное или prefix совпадение по origin (scheme://host[:port])
        if any(origin_base.startswith(prefix) for prefix in _ALLOWED_ORIGIN_PREFIXES):
            return True

        # 2) Совпадение по hostname / host:port (если в ALLOWED_ORIGINS указали без схемы)
        if origin_host:
            for h in _ALLOWED_HOSTS:
                if not h:
                    continue
                if ":" in h:
                    if origin_netloc == h:
                        return True
                else:
                    if origin_host == h or origin_host.endswith(f".{h}"):
                        return True

        if ALLOW_LOCALHOST_DEV == "1":
            if o.startswith("http://localhost:") or o.startswith("http://127.0.0.1:"):
                return True
        return False

    if request.method == "OPTIONS":
        from fastapi.responses import Response
        resp = Response(status_code=200)
        if is_allowed_origin(origin):
            resp.headers["Access-Control-Allow-Origin"] = origin
        resp.headers["Access-Control-Allow-Credentials"] = "true"
        resp.headers["Access-Control-Allow-Methods"] = "GET,POST,PUT,PATCH,DELETE,OPTIONS"
        # Если клиент запросил конкретные заголовки - возвращаем их, иначе базовый набор
        req_headers = request.headers.get("Access-Control-Request-Headers")
        allow_headers = req_headers or "Authorization, Content-Type, Accept, X-Requested-With"
        resp.headers["Access-Control-Allow-Headers"] = allow_headers
        resp.headers["Access-Control-Expose-Headers"] = "Content-Length, X-Request-Id"
        resp.headers["Vary"] = "Origin"
        # Дополнительная отладка CORS при AUTH_DEBUG
        if os.getenv("AUTH_DEBUG") == "1":
            print(f"[CORS-DEBUG] Preflight origin={origin} allowed={is_allowed_origin(origin)} headers={allow_headers}")
        return resp

    try:
        response = await call_next(request)
    except Exception:
        # Важно: при 500 response может не сформироваться и браузер покажет CORS,
        # хотя реальная причина — внутренняя ошибка. Возвращаем JSON + CORS.
        logging.getLogger(__name__).exception("Unhandled exception during request")
        from fastapi.responses import JSONResponse

        response = JSONResponse(status_code=500, content={"detail": "Internal Server Error"})
    if is_allowed_origin(origin):
        response.headers.setdefault("Access-Control-Allow-Origin", origin)
        response.headers.setdefault("Vary", "Origin")
        response.headers.setdefault("Access-Control-Allow-Credentials", "true")
    elif os.getenv("AUTH_DEBUG") == "1":
        print(f"[CORS-DEBUG] Origin '{origin}' отклонён. allowed_origins={allowed_origins} ALLOW_LOCALHOST_DEV={ALLOW_LOCALHOST_DEV}")
    return response

# Static files
BASE_DIR = os.path.dirname(__file__)
STATIC_DIR = os.path.join(BASE_DIR, "static")
os.makedirs(os.path.join(STATIC_DIR, "tts"), exist_ok=True)
os.makedirs(os.path.join(STATIC_DIR, "sounds"), exist_ok=True)
os.makedirs(os.path.join(STATIC_DIR, "avatars"), exist_ok=True)

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

# Простая попытка авто-ALTER для добавления новых полей.
# Важно: выполняем шаги независимо — ошибка в одном не должна ломать остальные.
from sqlalchemy import inspect, text as sql_text
from app.db.database import engine


def _has_column(insp, table: str, column: str) -> bool:
    try:
        return any(c.get("name") == column for c in insp.get_columns(table))
    except Exception:
        return False


def _try_exec(label: str, sql: str) -> bool:
    try:
        with engine.connect() as conn:
            conn.execute(sql_text(sql))
            conn.commit()
        print(label)
        return True
    except Exception as e:  # pragma: no cover
        print(f"[DB] {label} FAILED: {e}")
        return False


def _refresh_insp():
    return inspect(engine)


insp = _refresh_insp()

# 0) Best-effort cleanup (не критично)
if _has_column(insp, "user_settings", "gift_tts_alongside"):
    _try_exec(
        "[DB] Removed column user_settings.gift_tts_alongside (no longer needed)",
        "ALTER TABLE user_settings DROP COLUMN gift_tts_alongside",
    )
    insp = _refresh_insp()

# 1) user_settings
if not _has_column(insp, "user_settings", "auto_connect_live"):
    _try_exec(
        "[DB] Added column user_settings.auto_connect_live",
        "ALTER TABLE user_settings ADD COLUMN auto_connect_live BOOLEAN NOT NULL DEFAULT FALSE",
    )
    insp = _refresh_insp()

# 2) triggers
if not _has_column(insp, "triggers", "executed_count"):
    _try_exec(
        "[DB] Added column triggers.executed_count",
        "ALTER TABLE triggers ADD COLUMN executed_count INTEGER DEFAULT 0",
    )
    insp = _refresh_insp()

if not _has_column(insp, "triggers", "trigger_name"):
    _try_exec(
        "[DB] Added column triggers.trigger_name",
        "ALTER TABLE triggers ADD COLUMN trigger_name VARCHAR(100)",
    )
    insp = _refresh_insp()

if not _has_column(insp, "triggers", "combo_count"):
    _try_exec(
        "[DB] Added column triggers.combo_count",
        "ALTER TABLE triggers ADD COLUMN combo_count INTEGER DEFAULT 0",
    )
    insp = _refresh_insp()

# 3) users
if not _has_column(insp, "users", "role"):
    _try_exec(
        "[DB] Added column users.role",
        "ALTER TABLE users ADD COLUMN role VARCHAR(32) NOT NULL DEFAULT 'user'",
    )
    insp = _refresh_insp()

if not _has_column(insp, "users", "email"):
    _try_exec(
        "[DB] Added column users.email",
        "ALTER TABLE users ADD COLUMN email VARCHAR(256)",
    )
    insp = _refresh_insp()

if not _has_column(insp, "users", "avatar_filename"):
    _try_exec(
        "[DB] Added column users.avatar_filename",
        "ALTER TABLE users ADD COLUMN avatar_filename VARCHAR(255)",
    )
    insp = _refresh_insp()

# 4) store_purchases table
try:
    tables = set(insp.get_table_names())
except Exception:  # pragma: no cover
    tables = set()

if "store_purchases" not in tables:
    _try_exec(
        "[DB] Created table store_purchases",
        """
        CREATE TABLE store_purchases (
            id VARCHAR PRIMARY KEY,
            user_id VARCHAR NOT NULL,
            platform VARCHAR NOT NULL,
            product_id VARCHAR(128) NOT NULL,
            purchase_token VARCHAR(512),
            transaction_id VARCHAR(128),
            status VARCHAR NOT NULL DEFAULT 'unknown',
            expires_at TIMESTAMP,
            raw JSON,
            created_at TIMESTAMP NOT NULL,
            updated_at TIMESTAMP NOT NULL,
            CONSTRAINT fk_store_purchases_user_id FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE,
            CONSTRAINT uq_store_platform_token UNIQUE(platform, purchase_token)
        )
        """.strip(),
    )
app.include_router(auth_v2.router, prefix="/v2/auth", tags=["v2-auth"])
app.include_router(settings_v2.router, prefix="/v2/settings", tags=["v2-settings"])
app.include_router(sounds_v2.router, prefix="/v2/sounds", tags=["v2-sounds"])
app.include_router(triggers_v2.router, prefix="/v2/triggers", tags=["v2-triggers"])
app.include_router(ws_v2.router, prefix="/v2", tags=["v2-ws"])
app.include_router(license_v2.router, prefix="/v2/license", tags=["v2-license"])
app.include_router(voices_v2.router, prefix="/v2", tags=["v2-voices"])
app.include_router(gifts_v2.router, prefix="/v2/gifts", tags=["v2-gifts"])
app.include_router(notifications_v2.router, prefix="/v2", tags=["v2-notifications"])
app.include_router(admin_v2.router, prefix="/v2/admin", tags=["v2-admin"])
app.include_router(profile_v2.router, prefix="/v2/profile", tags=["v2-profile"])
app.include_router(tiktok_v2.router, prefix="/v2/tiktok", tags=["v2-tiktok"])
app.include_router(billing_v2.router, prefix="/v2/billing", tags=["v2-billing"])


@app.get("/")
async def root():
    return {
        "status": "ok",
        "service": "ttboost-backend",
        "env": os.getenv("ENV", "dev"),
        "server_host": os.getenv("SERVER_HOST"),
        "tts_base_url": os.getenv("TTS_BASE_URL"),
    }

@app.get("/status")
async def status():
    """Расширенный health-эндпойнт для фронта и мониторинга."""
    # DB ping
    db_ok = True
    db_error = None
    try:
        from app.db.database import engine
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception as e:  # pragma: no cover
        db_ok = False
        db_error = str(e)
    # TikTok clients info
    try:
        clients_cnt = len(getattr(tiktok_service, '_clients', {}))
        # Добавим максимальный лаг по подаркам для диагностики (в секундах)
        gift_lags = []
        from datetime import datetime as _dt
        for uid, last_evt in getattr(tiktok_service, '_last_gift_event', {}).items():
            gift_lags.append((_dt.utcnow() - last_evt).total_seconds())
        max_gift_lag_sec = max(gift_lags) if gift_lags else None
    except Exception:
        clients_cnt = 0
        max_gift_lag_sec = None
    uptime_sec = (datetime.utcnow() - START_TIME).total_seconds()
    return {
        "status": "ok" if db_ok else "degraded",
        "service": "ttboost-backend",
        "version": app.version,
        "env": os.getenv("ENV", "dev"),
        "uptime_sec": int(uptime_sec),
        "db_ok": db_ok,
        "db_error": db_error,
        "tiktok_clients": clients_cnt,
        "allowed_origins": allowed_origins,
        "allow_localhost_dev": os.getenv("ALLOW_LOCALHOST_DEV", "1"),
        "max_gift_event_lag_sec": int(max_gift_lag_sec) if max_gift_lag_sec is not None else None,
    }

@app.get("/health")
async def health():
    """Алиас /health для внешних мониторингов (HEAD/GET). Возвращает тот же JSON что /status."""
    return await status()

def _tail_log(path: str, lines: int) -> list[str]:
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            data = f.readlines()
        return data[-lines:]
    except FileNotFoundError:
        return ["<log file not found>"]

@app.get("/logs")
async def logs(lines: int = 200):
    """Возвращает последние N строк логов. Требует ALLOW_LOGS=1. Для прод осторожно."""
    if ALLOW_LOGS != "1":
        raise HTTPException(status_code=403, detail="/logs disabled")
    if lines <= 0:
        raise HTTPException(status_code=400, detail="lines must be > 0")
    if lines > 2000:
        lines = 2000  # ограничение во избежание больших ответов
    content = _tail_log(LOG_FILE, lines)
    return {
        "file": LOG_FILE,
        "lines": lines,
        "content": content,
    }
