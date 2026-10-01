"""Gestione delle registrazioni: creazione cartella riunione, ricezione chunk audio, stop.

Regole:
- una sola registrazione attiva alla volta;
- chunk numerati per traccia (seq 0,1,2…): duplicati ignorati, buchi rifiutati con il seq atteso;
- metadata.json scritto in modo atomico;
- dopo un riavvio del backend le riunioni "recording" diventano "interrupted" ma possono riprendere a ricevere chunk.
"""

from __future__ import annotations

import json
import logging
import os
import re
import shutil
import threading
import unicodedata
from datetime import datetime
from pathlib import Path

from . import __version__
from .meetings import ID_RE, MeetingNotFound, _read_metadata

log = logging.getLogger("meetlocalai.recording")

TRACKS = ("tab", "mic")
MAX_CHUNK_BYTES = 10 * 1024 * 1024
MIN_FREE_BYTES = 1 * 1024**3
ACTIVE = ("recording", "interrupted")


class RecordingError(Exception):
    def __init__(self, status: int, code: str, user_message: str, **extra):
        super().__init__(user_message)
        self.status, self.code, self.user_message, self.extra = status, code, user_message, extra


def now() -> datetime:
    return datetime.now().astimezone()


def iso(dt: datetime) -> str:
    return dt.isoformat(timespec="seconds")


def slugify_title(title: str | None, max_len: int = 60) -> str:
    t = unicodedata.normalize("NFKD", title or "").encode("ascii", "ignore").decode("ascii")
    t = re.sub(r"[^A-Za-z0-9_-]+", "-", t).strip("-_")
    t = re.sub(r"-{2,}", "-", t)[:max_len].strip("-_")
    return t or "Riunione"


def clean_title(title: str | None, meet_code: str | None) -> str:
    t = " ".join((title or "").split())[:200]
    if t:
        return t
    return f"Riunione {meet_code}" if meet_code else "Riunione"


def write_metadata(folder: Path, md: dict) -> None:
    md["updated_at"] = iso(now())
    tmp = folder / "metadata.json.tmp"
    tmp.write_text(json.dumps(md, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, folder / "metadata.json")


class Recorder:
    def __init__(self, cfg: dict, meetings_dir: Path):
        self.cfg = cfg
        self.dir = meetings_dir
        self.lock = threading.Lock()
        self.active_id: str | None = None

    # ---------- avvio backend ----------
    def recover(self) -> None:
        """Riunioni rimaste in 'recording' da un'esecuzione precedente → 'interrupted'."""
        if not self.dir.is_dir():
            return
        for folder in self.dir.iterdir():
            if not (folder.is_dir() and ID_RE.match(folder.name)):
                continue
            md = _read_metadata(folder)
            if md and md.get("status") == "recording":
                md["status"] = "interrupted"
                write_metadata(folder, md)
                log.warning("Riunione %s segnata come interrotta (backend riavviato durante la registrazione)", folder.name)

    # ---------- utilità ----------
    def _folder(self, meeting_id: str) -> Path:
        if not ID_RE.match(meeting_id):
            raise MeetingNotFound(meeting_id)
        return self.dir / meeting_id

    def _load(self, meeting_id: str) -> tuple[Path, dict]:
        folder = self._folder(meeting_id)
        md = _read_metadata(folder)
        if md is None:
            raise MeetingNotFound(meeting_id)
        return folder, md

    @staticmethod
    def _seq_file(folder: Path, track: str) -> Path:
        return folder / "raw" / f"{track}.seq"

    def _next_seq(self, folder: Path, track: str) -> int:
        try:
            return int(self._seq_file(folder, track).read_text().strip())
        except (FileNotFoundError, ValueError):
            return 0

    # ---------- API ----------
    def status(self) -> dict | None:
        with self.lock:
            if not self.active_id:
                return None
            try:
                folder, md = self._load(self.active_id)
            except MeetingNotFound:
                self.active_id = None
                return None
            raw = folder / "raw"
            return {
                "id": md["id"], "title": md["title"], "started_at": md["created_at"], "status": md["status"],
                "bytes": {t: (raw / f"{t}.webm").stat().st_size if (raw / f"{t}.webm").exists() else 0 for t in TRACKS},
            }

    def start(self, title: str | None, meet_code: str | None, tracks: list[str]) -> dict:
        tracks = [t for t in dict.fromkeys(tracks or ["tab"]) if t in TRACKS]
        if not tracks:
            raise RecordingError(422, "invalid_tracks", "Tracce audio non valide.")
        if meet_code is not None and not re.fullmatch(r"[a-z]{3}-[a-z]{4}-[a-z]{3}", meet_code):
            meet_code = None
        with self.lock:
            if self.active_id:
                try:
                    _, md = self._load(self.active_id)
                    if md.get("status") in ACTIVE:
                        raise RecordingError(409, "already_recording", "Registrazione già in corso.", meeting_id=self.active_id)
                except MeetingNotFound:
                    pass
            self.dir.mkdir(parents=True, exist_ok=True)
            if shutil.disk_usage(self.dir).free < MIN_FREE_BYTES:
                raise RecordingError(507, "disk_full", "Spazio su disco insufficiente per registrare.")
            started = now()
            human_title = clean_title(title, meet_code)
            base = f"{started:%Y-%m-%d_%H-%M}_{slugify_title(human_title)}"
            mid, n = base, 2
            while (self.dir / mid).exists():
                mid, n = f"{base}_{n}", n + 1
            folder = self.dir / mid
            (folder / "raw").mkdir(parents=True)
            md = {
                "schema_version": 1,
                "id": mid,
                "title": human_title,
                "created_at": iso(started),
                "ended_at": None,
                "date": f"{started:%Y-%m-%d}",
                "start_time": f"{started:%H:%M}",
                "duration_seconds": None,
                "status": "recording",
                "error": None,
                "language": self.cfg["transcription"].get("language", "it"),
                "detected_language": None,
                "source": {"meet_code": meet_code},
                "audio": {"tracks": tracks, "sample_rate": self.cfg["audio"].get("wav_sample_rate", 16000),
                          "channels": self.cfg["audio"].get("wav_channels", 1), "size_bytes": None},
                "whisper": {"engine": None, "model": None},
                "llm": {"provider": self.cfg["llm"].get("provider"), "model": self.cfg["llm"].get("model") or None},
                "files": {"folder": str(folder), "audio": None, "transcript_txt": None, "transcript_md": None, "summary_md": None},
                "performance": {},
                "app_version": __version__,
            }
            write_metadata(folder, md)
            self.active_id = mid
            log.info("Registrazione avviata: %s (tracce: %s)", mid, ",".join(tracks))
            return md

    def add_chunk(self, meeting_id: str, track: str, seq: int, data: bytes) -> dict:
        if track not in TRACKS:
            raise RecordingError(422, "invalid_track", "Traccia audio non valida.")
        if len(data) > MAX_CHUNK_BYTES:
            raise RecordingError(413, "chunk_too_large", "Blocco audio troppo grande.")
        with self.lock:
            folder, md = self._load(meeting_id)
            if md.get("status") not in ACTIVE:
                raise RecordingError(409, "not_recording", "La registrazione non è attiva.")
            if track not in md["audio"]["tracks"]:
                raise RecordingError(422, "track_not_enabled", "Traccia audio non prevista per questa riunione.")
            expected = self._next_seq(folder, track)
            if seq < expected:
                return {"accepted": False, "duplicate": True, "next_seq": expected}
            if seq > expected:
                raise RecordingError(409, "seq_gap", "Blocco audio fuori sequenza.", next_seq=expected)
            with open(folder / "raw" / f"{track}.webm", "ab") as f:
                f.write(data)
                f.flush()
                os.fsync(f.fileno())
            self._seq_file(folder, track).write_text(str(seq + 1))
            if md["status"] == "interrupted":
                md["status"] = "recording"
                write_metadata(folder, md)
                log.info("Registrazione %s ripresa dopo interruzione", meeting_id)
            self.active_id = meeting_id
            return {"accepted": True, "duplicate": False, "next_seq": seq + 1}

    def stop(self, meeting_id: str, client_duration: float | None) -> dict:
        with self.lock:
            folder, md = self._load(meeting_id)
            if md.get("status") not in ACTIVE:
                if self.active_id == meeting_id:
                    self.active_id = None
                return md  # stop idempotente
            ended = now()
            started = datetime.fromisoformat(md["created_at"])
            md["ended_at"] = iso(ended)
            md["duration_seconds"] = round((ended - started).total_seconds())
            md["status"] = "stopped"
            md["performance"]["recording_seconds"] = md["duration_seconds"]
            if client_duration is not None and client_duration >= 0:
                md["performance"]["client_duration_seconds"] = round(client_duration)
            raw = folder / "raw"
            md["audio"]["raw_bytes"] = {t: (raw / f"{t}.webm").stat().st_size for t in TRACKS if (raw / f"{t}.webm").exists()}
            write_metadata(folder, md)
            if self.active_id == meeting_id:
                self.active_id = None
            log.info("Registrazione terminata: %s (%s s)", meeting_id, md["duration_seconds"])
            return md

    def rename(self, meeting_id: str, title: str) -> dict:
        t = " ".join((title or "").split())[:200]
        if not t:
            raise RecordingError(422, "invalid_title", "Il titolo non può essere vuoto.")
        with self.lock:
            folder, md = self._load(meeting_id)
            md["title"] = t
            write_metadata(folder, md)
            return md
