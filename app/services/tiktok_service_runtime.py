import logging
import os

logger = logging.getLogger(__name__)

connector_backend = str(os.getenv("TIKTOK_CONNECTOR_BACKEND", "python")).strip().lower()

if connector_backend == "js":
    try:
        from app.services.tiktok_service_js import tiktok_service  # type: ignore
        logger.info("TikTok connector backend: js bridge")
    except Exception as exc:  # pragma: no cover
        logger.exception("Failed to initialize JS TikTok bridge, falling back to Python connector: %s", exc)
        from app.services.tiktok_service import tiktok_service  # type: ignore
else:
    from app.services.tiktok_service import tiktok_service  # type: ignore