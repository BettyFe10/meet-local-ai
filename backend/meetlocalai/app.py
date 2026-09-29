"""Applicazione FastAPI (API /api/v1). Nessuna interfaccia web: la UI è l'estensione Chrome."""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from . import __version__, health, messages
from . import config as config_mod
from . import logging_setup
from .security import SecurityPolicy

log = logging.getLogger("meetlocalai.app")


def create_app(cfg: dict | None = None) -> FastAPI:
    cfg = cfg or config_mod.load()
    config_mod.ensure_dirs(cfg)
    logging_setup.setup(cfg)
    started_at = time.time()

    app = FastAPI(title="Meet Local AI backend", version=__version__, docs_url=None, redoc_url=None, openapi_url=None)
    app.state.cfg = cfg
    app.middleware("http")(SecurityPolicy(cfg["backend"]["port"], cfg["backend"]["allowed_extension_ids"]))

    @app.exception_handler(StarletteHTTPException)
    async def _http_exc(request: Request, exc: StarletteHTTPException):
        msg = messages.NOT_FOUND if exc.status_code == 404 else messages.INTERNAL_ERROR
        return JSONResponse(status_code=exc.status_code, content={"error_code": f"http_{exc.status_code}", "user_message": msg, "detail_logged": True})

    @app.exception_handler(RequestValidationError)
    async def _validation_exc(request: Request, exc: RequestValidationError):
        log.warning("Richiesta non valida su %s: %s", request.url.path, exc.errors()[:3])
        return JSONResponse(status_code=422, content={"error_code": "invalid_request", "user_message": "Richiesta non valida.", "detail_logged": True})

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception):
        log.exception("Errore non gestito su %s", request.url.path)
        return JSONResponse(status_code=500, content={"error_code": "internal_error", "user_message": messages.INTERNAL_ERROR, "detail_logged": True})

    @app.get("/api/v1/health")
    def get_health():
        ff = health.check_ffmpeg()
        ol = health.check_ollama(cfg["llm"]["base_url"])
        llm_model = cfg["llm"].get("model") or None
        return {
            "status": "ok",
            "version": __version__,
            "uptime_seconds": round(time.time() - started_at, 1),
            "ffmpeg": {"available": ff["available"], "user_message": None if ff["available"] else messages.FFMPEG_UNAVAILABLE},
            # Whisper viene integrato in Fase 7: finché non c'è, è dichiarato non disponibile.
            "whisper": {"available": False, "engine": None, "model": None, "user_message": messages.WHISPER_UNAVAILABLE},
            "llm": {
                "available": ol["available"] and llm_model is not None,
                "provider": cfg["llm"]["provider"],
                "ollama_running": ol["available"],
                "model": llm_model,
                "user_message": None if (ol["available"] and llm_model) else messages.LLM_UNAVAILABLE,
            },
        }

    @app.get("/api/v1/status")
    def get_status():
        return {
            "time": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
            "recording": None,   # Fase 5/6
            "processing": None,  # Fase 8
            "queue_length": 0,
        }

    log.info("Backend %s avviato (config: %s)", __version__, cfg.get("_config_path"))
    return app
