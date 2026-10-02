"""Applicazione FastAPI (API /api/v1). Nessuna interfaccia web: la UI è l'estensione Chrome."""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone

from fastapi import Body, FastAPI, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool
from starlette.exceptions import HTTPException as StarletteHTTPException

from . import __version__, health, meetings, messages, processing, recording
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
        wh = health.check_whisper(cfg, config_mod.data_dirs(cfg)["models_dir"])
        lm = health.check_llm(cfg, config_mod.data_dirs(cfg)["models_dir"])
        return {
            "status": "ok",
            "version": __version__,
            "uptime_seconds": round(time.time() - started_at, 1),
            "ffmpeg": {"available": ff["available"], "user_message": None if ff["available"] else messages.FFMPEG_UNAVAILABLE},
            "whisper": {**wh, "user_message": None if wh["available"] else messages.WHISPER_UNAVAILABLE},
            "llm": {**lm, "user_message": None if lm["available"] else messages.LLM_UNAVAILABLE},
        }


    meetings_dir = config_mod.data_dirs(cfg)["meetings_dir"]
    recorder = recording.Recorder(cfg, meetings_dir)
    recorder.recover()
    app.state.recorder = recorder
    processor = processing.Processor(cfg, config_mod.data_dirs(cfg), recorder.lock)
    app.state.processor = processor
    if cfg.get("processing", {}).get("enabled", True):
        pending = processor.recover()
        if pending:
            log.info("Riunioni da elaborare rimesse in coda: %d", len(pending))
        processor.start_worker()

    @app.exception_handler(recording.RecordingError)
    async def _rec_exc(request: Request, exc: recording.RecordingError):
        return JSONResponse(status_code=exc.status, content={"error_code": exc.code, "user_message": exc.user_message,
                                                             "detail_logged": False, **exc.extra})

    def _not_found():
        return JSONResponse(status_code=404, content={"error_code": "meeting_not_found", "user_message": "Riunione non trovata.", "detail_logged": False})

    @app.get("/api/v1/status")
    def get_status():
        return {
            "time": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
            "recording": recorder.status(),
            "processing": processor.status()["current"],
            "queue_length": processor.status()["queue_length"],
        }

    @app.post("/api/v1/meetings", status_code=201)
    def post_meeting(payload: dict = Body(default={})):
        md = recorder.start(payload.get("title"), payload.get("meet_code"), payload.get("tracks") or ["tab"])
        return md

    @app.post("/api/v1/meetings/{meeting_id}/chunks")
    async def post_chunk(meeting_id: str, request: Request, track: str = Query(...), seq: int = Query(..., ge=0)):
        data = await request.body()
        try:
            return await run_in_threadpool(recorder.add_chunk, meeting_id, track, seq, data)
        except meetings.MeetingNotFound:
            return _not_found()

    @app.post("/api/v1/meetings/{meeting_id}/stop")
    def post_stop(meeting_id: str, payload: dict = Body(default={})):
        cd = payload.get("client_duration_seconds")
        try:
            md = recorder.stop(meeting_id, float(cd) if isinstance(cd, (int, float)) else None)
        except meetings.MeetingNotFound:
            return _not_found()
        if md.get("status") == "stopped":
            processor.enqueue(meeting_id)
        return md

    @app.post("/api/v1/meetings/{meeting_id}/reprocess")
    def post_reprocess(meeting_id: str):
        try:
            md = meetings.get_meeting(meetings_dir, meeting_id)
        except meetings.MeetingNotFound:
            return _not_found()
        if md.get("status") in ("recording", "interrupted"):
            raise recording.RecordingError(409, "still_recording", "La registrazione è ancora attiva.")
        queued = processor.enqueue(meeting_id)
        return {"queued": queued, "queue_length": processor.status()["queue_length"]}

    @app.get("/api/v1/meetings/{meeting_id}/transcript")
    def get_transcript(meeting_id: str, format: str = Query("txt", pattern="^(txt|md)$")):
        from fastapi.responses import PlainTextResponse  # noqa: PLC0415
        try:
            md = meetings.get_meeting(meetings_dir, meeting_id)
        except meetings.MeetingNotFound:
            return _not_found()
        f = meetings_dir / md["id"] / f"transcript.{format}"
        if not f.exists():
            return JSONResponse(status_code=404, content={"error_code": "transcript_not_ready",
                                                          "user_message": "Trascrizione non ancora disponibile.", "detail_logged": False})
        return PlainTextResponse(f.read_text(encoding="utf-8"),
                                 media_type="text/markdown; charset=utf-8" if format == "md" else "text/plain; charset=utf-8")

    @app.patch("/api/v1/meetings/{meeting_id}")
    def patch_meeting(meeting_id: str, payload: dict = Body(...)):
        try:
            return recorder.rename(meeting_id, str(payload.get("title", "")))
        except meetings.MeetingNotFound:
            return _not_found()

    @app.get("/api/v1/meetings")
    def get_meetings():
        return {"meetings": meetings.list_meetings(meetings_dir)}

    @app.get("/api/v1/meetings/{meeting_id}")
    def get_meeting(meeting_id: str):
        try:
            return meetings.get_meeting(meetings_dir, meeting_id)
        except meetings.MeetingNotFound:
            return _not_found()

    log.info("Backend %s avviato (config: %s)", __version__, cfg.get("_config_path"))
    return app
