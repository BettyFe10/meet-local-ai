"""Elaborazione delle riunioni dopo TERMINA: converting → transcribing → transcribed.
(La sintesi con LLM si aggiunge in Fase 10.)

- una riunione alla volta (coda FIFO, thread dedicato): Whisper e LLM non girano mai insieme;
- al riavvio del backend le riunioni rimaste a metà vengono rimesse in coda;
- nessun testo delle riunioni nei log.
"""

from __future__ import annotations

import json
import logging
import queue
import re
import resource
import shutil
import sys
import threading
import time
from dataclasses import dataclass
from pathlib import Path

from . import audio, files, health, llm, messages, summarize, transcribe
from .meetings import ID_RE, MeetingNotFound, _read_metadata
from .recording import iso, now, write_metadata

log = logging.getLogger("meetlocalai.processing")

LABELS = {"mic": "Microfono locale", "tab": "Partecipanti"}
PENDING = ("stopped", "converting", "transcribing", "summarizing")
NO_SUMMARY = "Sintesi non generata: "
MERGE_GAP_S = 2.0
SILENT_TRACK_DB = -60.0   # picco sotto questa soglia = traccia muta (es. scheda Meet senza audio)

# Frasi che Whisper "inventa" su silenzio/rumore (dai sottotitoli con cui è stato addestrato).
_HALLU_FULL = [  # la frase intera coincide
    r"grazie (a tutti )?per (la visione|l'attenzione|aver guardato)",
    r"iscriviti al canale",
    r"\[?musica\]?", r"\[?applausi\]?", r"\[?silenzio\]?",
]
_HALLU_ANY = [  # basta che compaia (firme di sottotitolatori presenti nei dati di addestramento)
    r"qtss", r"amara\.org", r"sottotitoli\b.*\ba cura\b", r"autore dei sottotitoli", r"sottotitoli creati",
]
_HALLU_RE = re.compile(r"^\W*(" + "|".join(_HALLU_FULL) + r")\W*$", re.IGNORECASE)
_HALLU_ANY_RE = re.compile("|".join(_HALLU_ANY), re.IGNORECASE)


@dataclass
class Line:
    start: float
    end: float
    speaker: str
    text: str


def is_hallucination(text: str) -> bool:
    t = text.strip()
    return bool(_HALLU_RE.match(t) or _HALLU_ANY_RE.search(t))


def drop_repeats(segs: list[transcribe.Segment], max_same: int = 2) -> list[transcribe.Segment]:
    """Whisper a volte entra in loop ripetendo la stessa frase: tiene al massimo `max_same` ripetizioni consecutive."""
    out, run = [], 0
    for s in segs:
        if out and s.text.strip().lower() == out[-1].text.strip().lower():
            run += 1
            if run >= max_same:
                continue
        else:
            run = 0
        out.append(s)
    return out


def fmt_ts(sec: float) -> str:
    s = int(max(0, sec))
    return f"{s // 3600:02d}:{s % 3600 // 60:02d}:{s % 60:02d}"


def merge_tracks(per_track: dict[str, list[transcribe.Segment]]) -> list[Line]:
    """Unisce le tracce in ordine di tempo; accorpa frasi consecutive dello stesso speaker vicine nel tempo."""
    lines = [Line(s.start, s.end, LABELS.get(t, t), s.text.strip())
             for t, segs in per_track.items() for s in drop_repeats(segs)
             if s.text.strip() and not is_hallucination(s.text)]
    lines.sort(key=lambda x: (x.start, x.speaker))
    out: list[Line] = []
    for ln in lines:
        prev = out[-1] if out else None
        if prev and prev.speaker == ln.speaker and ln.start - prev.end <= MERGE_GAP_S:
            prev.text = f"{prev.text} {ln.text}"
            prev.end = max(prev.end, ln.end)
        else:
            out.append(ln)
    return out


def render_txt(lines: list[Line]) -> str:
    return "".join(f"[{fmt_ts(l.start)}] {l.speaker}:\n{l.text}\n\n" for l in lines)


def render_md(md: dict, lines: list[Line]) -> str:
    head = (f"# Trascrizione — {md['title']}\n\n"
            f"- Data: {md.get('date')} {md.get('start_time')}\n"
            f"- Durata: {round((md.get('duration_seconds') or 0) / 60)} min\n"
            f"- Trascrizione locale: {md['whisper'].get('engine')} / {md['whisper'].get('model')}\n"
            f"- Speaker: \"Microfono locale\" = chi registrava; \"Partecipanti\" = audio della riunione "
            f"(più persone non distinte). Nessun nome viene dedotto.\n\n---\n\n")
    if not lines:
        return head + "_Nessun parlato riconosciuto._\n"
    return head + "".join(f"**[{fmt_ts(l.start)}] {l.speaker}:**  \n{l.text}\n\n" for l in lines)


def _peak_rss_mb() -> float:
    r = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss
    return round(r / 1024 / 1024 if sys.platform == "darwin" else r / 1024)


class Processor:
    def __init__(self, cfg: dict, dirs: dict, lock: threading.Lock):
        self.cfg, self.dirs, self.lock = cfg, dirs, lock
        self.q: queue.Queue[tuple[str, str]] = queue.Queue()
        self.current: dict | None = None
        self._queued: set[str] = set()
        self._thread: threading.Thread | None = None
        # sostituibile nei test
        self.llm_client_factory = lambda: llm.OllamaClient(
            cfg["llm"]["base_url"], dirs["models_dir"], keep_alive=cfg["llm"].get("keep_alive", "30s"))

    # ---------- coda ----------
    def enqueue(self, meeting_id: str, mode: str = "full") -> bool:
        """mode: "full" (conversione+trascrizione+sintesi) oppure "summary" (solo sintesi da trascrizione esistente)."""
        if meeting_id in self._queued or (self.current and self.current["id"] == meeting_id):
            return False
        self._queued.add(meeting_id)
        self.q.put((meeting_id, mode))
        return True

    def recover(self) -> list[str]:
        """Rimette in coda le riunioni chiuse ma non ancora elaborate (anche dopo un riavvio)."""
        d = self.dirs["meetings_dir"]
        found = []
        if d.is_dir():
            for f in sorted(d.iterdir()):
                if f.is_dir() and ID_RE.match(f.name):
                    md = _read_metadata(f)
                    if md and md.get("status") in PENDING:
                        only_summary = md["status"] == "summarizing" and (f / "transcript.txt").exists()
                        self.enqueue(f.name, "summary" if only_summary else "full")
                        found.append(f.name)
        return found

    def start_worker(self) -> None:
        if self._thread is None:
            self._thread = threading.Thread(target=self._loop, name="meetlocalai-processor", daemon=True)
            self._thread.start()

    def _loop(self) -> None:
        while True:
            mid, mode = self.q.get()
            self._queued.discard(mid)
            try:
                self.process(mid, mode)
            except MeetingNotFound:
                log.info("Riunione %s non più presente (eliminata): elaborazione saltata", mid)
            except Exception:  # noqa: BLE001 - il worker non deve mai morire
                log.exception("Errore inatteso elaborando %s", mid)

    def busy_with(self, meeting_id: str) -> bool:
        return meeting_id in self._queued or bool(self.current and self.current["id"] == meeting_id)

    def status(self) -> dict:
        return {"current": self.current, "queue_length": self.q.qsize()}

    # ---------- metadata ----------
    def _update(self, folder: Path, **changes) -> dict:
        with self.lock:
            md = _read_metadata(folder)
            if md is None:
                raise MeetingNotFound(folder.name)
            for k, v in changes.items():
                if isinstance(v, dict) and isinstance(md.get(k), dict):
                    md[k].update(v)
                else:
                    md[k] = v
            write_metadata(folder, md)
            return md

    def _fail(self, folder: Path, step: str, user_message: str) -> None:
        self._update(folder, status="error", error={"step": step, "user_message": user_message, "at": iso(now())})
        log.error("Elaborazione %s fallita al passo %s: %s", folder.name, step, user_message)

    # ---------- pipeline ----------
    def process(self, meeting_id: str, mode: str = "full") -> dict:
        folder = self.dirs["meetings_dir"] / meeting_id
        md = _read_metadata(folder)
        if md is None:
            raise MeetingNotFound(meeting_id)
        if md.get("status") in ("recording", "interrupted"):
            log.warning("Riunione %s ancora in registrazione: elaborazione saltata", meeting_id)
            return md
        if mode == "summary" and (folder / "transcript.txt").exists():
            self.current = {"id": meeting_id, "step": "summarizing", "started": iso(now())}
            try:
                return self._summarize(folder)
            finally:
                self.current = None
        work = self.dirs["temp_dir"] / meeting_id
        self.current = {"id": meeting_id, "step": "converting", "started": iso(now())}
        try:
            # 1) conversione
            self._update(folder, status="converting", error=None)
            t0 = time.perf_counter()
            try:
                prep = audio.prepare(folder, md["audio"].get("tracks") or ["tab"], work,
                                     self.cfg["audio"].get("wav_sample_rate", 16000))
            except audio.AudioError as e:
                self._fail(folder, "converting", e.user_message)
                return _read_metadata(folder)
            conv_s = round(time.perf_counter() - t0, 2)
            self._update(folder, audio={"size_bytes": prep["audio"].stat().st_size, "duration_seconds": round(prep["duration"], 1)},
                         files={"audio": "audio.wav"}, performance={"conversion_seconds": conv_s})

            # 2) trascrizione
            self.current["step"] = "transcribing"
            engine = transcribe.select_engine(self.cfg, self.dirs["models_dir"])
            if engine is None:
                self._fail(folder, "transcribing", messages.WHISPER_UNAVAILABLE)
                return _read_metadata(folder)
            self._update(folder, status="transcribing", whisper={"engine": engine.name, "model": engine.model})
            language = self.cfg["transcription"].get("language", "it")
            t0 = time.perf_counter()
            per_track: dict[str, list] = {}
            warnings = []
            try:
                for track, wav in prep["tracks"].items():
                    peak = audio.peak_db(wav)
                    if peak is not None and peak < SILENT_TRACK_DB:
                        warnings.append(f"Traccia \"{LABELS.get(track, track)}\" muta: non trascritta.")
                        log.warning("Riunione %s: traccia %s muta (picco %.1f dB), saltata", meeting_id, track, peak)
                        continue
                    per_track[track] = engine.transcribe(wav, language)
            except transcribe.TranscriptionError as e:
                self._fail(folder, "transcribing", e.user_message)
                return _read_metadata(folder)
            tr_s = round(time.perf_counter() - t0, 2)
            lines = merge_tracks(per_track)
            md = _read_metadata(folder)
            (folder / "transcript.txt").write_text(render_txt(lines), encoding="utf-8")
            (folder / "transcript.md").write_text(render_md(md, lines), encoding="utf-8")
            (folder / "transcript.json").write_text(json.dumps(
                [{"start": l.start, "end": l.end, "speaker": l.speaker, "text": l.text} for l in lines],
                ensure_ascii=False, indent=1), encoding="utf-8")
            dur = prep["duration"] or 0
            md = self._update(
                folder, status="transcribed", detected_language=language, warnings=warnings,
                files={"transcript_txt": "transcript.txt", "transcript_md": "transcript.md"},
                performance={"transcription_seconds": tr_s, "realtime_factor": round(tr_s / dur, 3) if dur else None,
                             "peak_rss_mb": _peak_rss_mb(),
                             "disk_bytes": sum(p.stat().st_size for p in folder.rglob("*") if p.is_file())})
            log.info("Riunione %s trascritta: audio %.0f s, trascrizione %.1f s, %d blocchi", meeting_id, dur, tr_s, len(lines))
            if not self.cfg["audio"].get("keep_raw_tracks", True):
                freed = files.remove_raw(folder)
                log.info("Riunione %s: tracce grezze rimosse (%d byte liberati)", meeting_id, freed)
            # 3) sintesi (un suo fallimento non invalida la trascrizione)
            self.current["step"] = "summarizing"
            return self._summarize(folder)
        finally:
            self.current = None
            shutil.rmtree(work, ignore_errors=True)

    def _summarize(self, folder: Path) -> dict:
        """transcribed → summarizing → completed. Se la sintesi non è possibile resta "transcribed" con un avviso."""
        md = _read_metadata(folder)
        keep = [w for w in (md.get("warnings") or []) if not w.startswith(NO_SUMMARY)]

        def skip(reason: str) -> dict:
            log.warning("Riunione %s: sintesi non generata (%s)", folder.name, reason)
            return self._update(folder, status="transcribed", warnings=keep + [NO_SUMMARY + reason])

        if not self.cfg.get("summary", {}).get("enabled", True):
            return self._update(folder, status="transcribed", warnings=keep)
        transcript = (folder / "transcript.txt").read_text(encoding="utf-8").strip()
        if not transcript:
            return skip("nessun parlato riconosciuto.")
        model = llm.resolve_model(self.cfg)
        if not health.check_llm(self.cfg, self.dirs["models_dir"])["available"]:
            return skip(messages.LLM_UNAVAILABLE)
        self._update(folder, status="summarizing", warnings=keep, llm={"provider": "ollama", "model": model})
        client = self.llm_client_factory()
        try:
            client.ensure_server()
            r = summarize.summarize(client, model, md["title"], transcript,
                                    temperature=self.cfg["llm"].get("temperature", 0.2),
                                    two_pass=self.cfg.get("summary", {}).get("two_pass", True))
        except (llm.LLMError, summarize.SummaryError) as e:
            log.error("Riunione %s: errore sintesi: %s", folder.name, getattr(e, "detail", "") or e.user_message)
            return skip(e.user_message)
        finally:
            client.stop_server()
        (folder / "summary.md").write_text(summarize.render_summary_file(md, r["markdown"], model), encoding="utf-8")
        st = r["stats"]
        out = self._update(
            folder, status="completed", files={"summary_md": "summary.md"},
            performance={"summary_seconds": st["seconds"], "summary_mode": st["mode"], "summary_calls": st["calls"],
                         "disk_bytes": sum(p.stat().st_size for p in folder.rglob("*") if p.is_file())},
            summary={"prompt_version": st["prompt_version"], "retries": st["retries"]})
        log.info("Riunione %s: sintesi pronta in %.1f s (%s, %d chiamate)", folder.name, st["seconds"], st["mode"], st["calls"])
        return out
