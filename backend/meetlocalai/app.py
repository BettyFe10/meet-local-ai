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

from . import __version__, files, health, meetings, messages, processing, recording
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
        removed = files.cleanup_temp(config_mod.data_dirs(cfg)["temp_dir"])
        if removed:
            log.info("Cartelle temporanee rimosse all'avvio: %d", removed)
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
    def post_reprocess(meeting_id: str, payload: dict = Body(default={})):
        """Rimette in coda l'elaborazione. {"steps": ["summarize"]} = rifà solo la sintesi."""
        try:
            md = meetings.get_meeting(meetings_dir, meeting_id)
        except meetings.MeetingNotFound:
            return _not_found()
        if md.get("status") in ("recording", "interrupted"):
            raise recording.RecordingError(409, "still_recording", "La registrazione è ancora attiva.")
        only_summary = payload.get("steps") == ["summarize"]
        if only_summary and not (meetings_dir / md["id"] / "transcript.txt").exists():
            raise recording.RecordingError(409, "transcript_not_ready", "Trascrizione non ancora disponibile.")
        queued = processor.enqueue(meeting_id, "summary" if only_summary else "full")
        return {"queued": queued, "queue_length": processor.status()["queue_length"]}

    # ---------- audio (token temporaneo per il tag <audio>) ----------
    audio_tokens: dict[str, tuple[str, float]] = {}

    @app.post("/api/v1/meetings/{meeting_id}/audio-token")
    def post_audio_token(meeting_id: str):
        import secrets  # noqa: PLC0415
        try:
            md = meetings.get_meeting(meetings_dir, meeting_id)
        except meetings.MeetingNotFound:
            return _not_found()
        if not (meetings_dir / md["id"] / "audio.wav").exists():
            return JSONResponse(status_code=404, content={"error_code": "audio_not_ready",
                                                          "user_message": "Audio non ancora disponibile.", "detail_logged": False})
        now_t = time.time()
        for t in [t for t, (_, exp) in audio_tokens.items() if exp < now_t]:
            audio_tokens.pop(t, None)
        token = secrets.token_urlsafe(24)
        audio_tokens[token] = (md["id"], now_t + 4 * 3600)
        return {"token": token, "expires_in": 4 * 3600}

    @app.get("/api/v1/meetings/{meeting_id}/audio")
    def get_audio(meeting_id: str, request: Request, token: str | None = None):
        from fastapi.responses import FileResponse  # noqa: PLC0415
        if request.headers.get("x-meetlocalai") != "1":
            entry = audio_tokens.get(token or "")
            if not entry or entry[0] != meeting_id or entry[1] < time.time():
                return JSONResponse(status_code=403, content={"error_code": "invalid_token",
                                                              "user_message": messages.FORBIDDEN, "detail_logged": False})
        try:
            md = meetings.get_meeting(meetings_dir, meeting_id)
        except meetings.MeetingNotFound:
            return _not_found()
        f = meetings_dir / md["id"] / "audio.wav"
        if not f.exists():
            return JSONResponse(status_code=404, content={"error_code": "audio_not_ready",
                                                          "user_message": "Audio non ancora disponibile.", "detail_logged": False})
        return FileResponse(f, media_type="audio/wav", filename=f"{md['id']}.wav", content_disposition_type="inline")

    # ---------- file: elimina, esporta, spazio ----------
    @app.delete("/api/v1/meetings/{meeting_id}")
    def delete_meeting(meeting_id: str):
        """Sposta la riunione nel Cestino (recuperabile). Mai cancellazione definitiva."""
        try:
            md = meetings.get_meeting(meetings_dir, meeting_id)
        except meetings.MeetingNotFound:
            return _not_found()
        if md.get("status") == "recording" or recorder.active_id == meeting_id:
            raise recording.RecordingError(409, "still_recording", "La registrazione è ancora attiva.")
        if processor.busy_with(meeting_id) and md.get("status") in ("converting", "transcribing", "summarizing"):
            raise recording.RecordingError(409, "processing", "La riunione è in elaborazione: riprova tra poco.")
        with recorder.lock:
            where = files.trash(meetings_dir / md["id"], config_mod.data_dirs(cfg)["data_root"] / "Cestino")
        log.info("Riunione %s eliminata (%s)", md["id"], where)
        return {"deleted": True, "where": where,
                "user_message": "Riunione spostata nel Cestino." if where == "trash"
                else "Riunione spostata nella cartella MeetLocalAI/Cestino."}

    @app.get("/api/v1/meetings/{meeting_id}/export")
    def get_export(meeting_id: str, format: str = Query("md", pattern="^(md|txt)$")):
        from fastapi.responses import PlainTextResponse  # noqa: PLC0415
        try:
            md = meetings.get_meeting(meetings_dir, meeting_id)
        except meetings.MeetingNotFound:
            return _not_found()
        text, out = files.export(meetings_dir / md["id"], md, format, config_mod.data_dirs(cfg)["exports_dir"])
        return PlainTextResponse(text, media_type="text/markdown; charset=utf-8" if format == "md" else "text/plain; charset=utf-8",
                                 headers={"X-Export-Path": out.name})

    @app.get("/api/v1/storage")
    def get_storage():
        return files.storage(config_mod.data_dirs(cfg))

    # ---------- Finder ----------
    def _open_in_finder(path) -> JSONResponse | dict:
        import subprocess  # noqa: PLC0415
        import sys  # noqa: PLC0415
        if sys.platform != "darwin":
            return JSONResponse(status_code=501, content={"error_code": "not_supported",
                                                          "user_message": "Funzione disponibile solo su macOS.", "detail_logged": False})
        subprocess.Popen(["/usr/bin/open", str(path)])
        return {"opened": True}

    @app.post("/api/v1/meetings/{meeting_id}/open-folder")
    def post_open_folder(meeting_id: str):
        try:
            md = meetings.get_meeting(meetings_dir, meeting_id)
        except meetings.MeetingNotFound:
            return _not_found()
        return _open_in_finder(meetings_dir / md["id"])

    @app.post("/api/v1/open-data-root")
    def post_open_data_root():
        return _open_in_finder(config_mod.data_dirs(cfg)["data_root"])

    @app.get("/api/v1/meetings/{meeting_id}/summary")
    def get_summary(meeting_id: str):
        from . import summarize as summ  # noqa: PLC0415
        try:
            md = meetings.get_meeting(meetings_dir, meeting_id)
        except meetings.MeetingNotFound:
            return _not_found()
        f = meetings_dir / md["id"] / "summary.md"
        if not f.exists():
            return JSONResponse(status_code=404, content={"error_code": "summary_not_ready",
                                                          "user_message": "Sintesi non ancora disponibile.", "detail_logged": False})
        text = f.read_text(encoding="utf-8")
        return {"markdown": text, "sections": summ.parse_sections(text), "model": md.get("llm", {}).get("model")}

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
