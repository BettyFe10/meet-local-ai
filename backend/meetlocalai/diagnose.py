"""Diagnostica: stato dei componenti e prestazioni, SENZA contenuti delle riunioni.

Uso: python -m meetlocalai.diagnose [--json]
Non stampa titoli, nomi di cartelle delle riunioni, trascrizioni o sintesi; il percorso della home è sostituito da "~".
"""

from __future__ import annotations

import json
import platform
import re
import shutil
import sys
import urllib.request
from collections import Counter
from pathlib import Path

from . import __version__, config as config_mod, files, health, llm
from .security import CLIENT_HEADER

MEETING_ID_RE = re.compile(r"\d{4}-\d{2}-\d{2}_\d{2}-\d{2}_[A-Za-z0-9_-]+")
_LEVEL_RE = re.compile(r"^\S+ \S+ (DEBUG|INFO|WARNING|ERROR|CRITICAL) ")


def redact(text: str) -> str:
    """Toglie identificativi delle riunioni (contengono il titolo) e il percorso della home."""
    text = MEETING_ID_RE.sub("<riunione>", text)
    return text.replace(str(Path.home()), "~")


def ram_gb() -> float | None:
    gb = llm.system_ram_gb()
    return round(gb, 1) if gb else None


def backend_state(port: int, timeout: float = 1.5) -> dict:
    req = urllib.request.Request(f"http://127.0.0.1:{port}/api/v1/health", headers={CLIENT_HEADER: "1"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return {"running": True, "health": json.loads(r.read().decode("utf-8"))}
    except Exception as e:  # noqa: BLE001
        return {"running": False, "reason": type(e).__name__}


def meetings_stats(meetings_dir: Path) -> dict:
    """Conteggi e medie dalle metadata.json: nessun titolo, nessun ID."""
    by_status: Counter = Counter()
    unreadable = 0
    rtf, summ, conv, rss, hours = [], [], [], [], 0.0
    if meetings_dir.is_dir():
        for folder in meetings_dir.iterdir():
            mdp = folder / "metadata.json"
            if not mdp.is_file():
                continue
            try:
                md = json.loads(mdp.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                unreadable += 1
                continue
            by_status[str(md.get("status"))] += 1
            hours += float(md.get("duration_seconds") or 0) / 3600
            p = md.get("performance") or {}
            for key, dst in (("realtime_factor", rtf), ("summary_seconds", summ), ("conversion_seconds", conv), ("peak_rss_mb", rss)):
                if isinstance(p.get(key), (int, float)):
                    dst.append(float(p[key]))

    def avg(xs):
        return round(sum(xs) / len(xs), 3) if xs else None

    return {"total": sum(by_status.values()), "by_status": dict(sorted(by_status.items())), "unreadable_metadata": unreadable,
            "recorded_hours": round(hours, 2),
            "performance": {"transcription_realtime_factor_avg": avg(rtf), "transcription_realtime_factor_max": max(rtf) if rtf else None,
                            "summary_seconds_avg": avg(summ), "summary_seconds_max": max(summ) if summ else None,
                            "conversion_seconds_avg": avg(conv), "whisper_peak_rss_mb_max": max(rss) if rss else None,
                            "samples": len(rtf)}}


def log_stats(logs_dir: Path, last_errors: int = 5) -> dict:
    p = logs_dir / "backend.log"
    out = {"present": p.is_file(), "size_bytes": 0, "rotated_files": 0, "levels": {}, "last_errors": []}
    if not p.is_file():
        return out
    out["size_bytes"] = p.stat().st_size
    out["rotated_files"] = len(list(logs_dir.glob("backend.log.*")))
    levels: Counter = Counter()
    errors: list[str] = []
    with p.open(encoding="utf-8", errors="replace") as fh:
        for line in fh:
            m = _LEVEL_RE.match(line)
            if not m:
                continue
            levels[m.group(1)] += 1
            if m.group(1) in ("ERROR", "CRITICAL"):
                errors.append(redact(line.rstrip())[:300])
    out["levels"] = dict(levels)
    out["last_errors"] = errors[-last_errors:]
    return out


def collect(cfg: dict) -> dict:
    dirs = config_mod.data_dirs(cfg)
    port = cfg["backend"]["port"]
    whisper = health.check_whisper(cfg, dirs["models_dir"])
    lm = health.check_llm(cfg, dirs["models_dir"])
    try:
        free = shutil.disk_usage(dirs["data_root"] if dirs["data_root"].exists() else Path.home()).free
    except OSError:
        free = None
    try:
        storage = files.storage(dirs)
    except Exception:  # noqa: BLE001
        storage = None
    return {
        "app_version": __version__,
        "system": {"os": platform.system(), "os_version": platform.mac_ver()[0] or platform.release(),
                   "machine": platform.machine(), "python": platform.python_version(), "ram_gb": ram_gb(),
                   "disk_free_gb": round(free / 1e9, 1) if free is not None else None},
        "config": {"path": redact(str(cfg.get("_config_path"))), "port": port,
                   "extension_ids": len(cfg["backend"].get("allowed_extension_ids") or []),
                   "llm_model_setting": cfg["llm"].get("model"), "keep_raw_tracks": cfg["audio"].get("keep_raw_tracks", True)},
        "dirs": {k: {"path": redact(str(v)), "exists": v.is_dir()} for k, v in dirs.items()},
        "components": {"ffmpeg": {"available": health.check_ffmpeg()["available"]}, "whisper": whisper, "llm": lm},
        "backend": backend_state(port),
        "storage": storage,
        "meetings": meetings_stats(dirs["meetings_dir"]),
        "log": log_stats(dirs["logs_dir"]),
    }


def problems(d: dict) -> list[str]:
    out = []
    c = d["components"]
    if not d["backend"]["running"]:
        out.append("Backend offline. → ~/MeetLocalAI/app/start_backend.sh")
    if not c["ffmpeg"]["available"]:
        out.append("FFmpeg non installato. → brew install ffmpeg")
    if not c["whisper"]["available"]:
        out.append("Whisper locale non disponibile. → ~/MeetLocalAI/app/installer/setup_whisper.sh")
    if not c["llm"]["available"]:
        out.append("Modello locale non disponibile. → ~/MeetLocalAI/app/installer/setup_llm.sh")
    if d["config"]["extension_ids"] == 0:
        out.append("Nessuna estensione autorizzata nel config (modalità sviluppo).")
    free = d["system"]["disk_free_gb"]
    if free is not None and free < 5:
        out.append(f"Poco spazio libero su disco ({free} GB).")
    ram = d["system"]["ram_gb"]
    if ram is not None and ram < 12:
        out.append(f"RAM {ram} GB: fascia non testata (modello di sintesi ridotto).")
    for k, v in d["dirs"].items():
        if not v["exists"]:
            out.append(f"Cartella mancante: {v['path']} ({k})")
    st = d["meetings"]["by_status"]
    if st.get("error"):
        out.append(f"Riunioni in errore: {st['error']} (pulsante Rielabora nella pagina della riunione).")
    if d["meetings"]["unreadable_metadata"]:
        out.append(f"metadata.json illeggibili: {d['meetings']['unreadable_metadata']}")
    return out


def render(d: dict) -> str:
    def yn(b):
        return "OK" if b else "MANCANTE"
    s, c, m, lg = d["system"], d["components"], d["meetings"], d["log"]
    perf = m["performance"]
    L = [f"Meet Local AI {d['app_version']} — diagnostica",
         "(nessun contenuto delle riunioni in questo rapporto)", "",
         "[Sistema]",
         f"  {s['os']} {s['os_version']} {s['machine']} · Python {s['python']} · RAM {s['ram_gb']} GB · disco libero {s['disk_free_gb']} GB",
         "[Configurazione]",
         f"  file: {d['config']['path']} · porta {d['config']['port']} · estensioni autorizzate: {d['config']['extension_ids']} · modello sintesi: {d['config']['llm_model_setting']}",
         "[Componenti]",
         f"  Backend : {'attivo' if d['backend']['running'] else 'OFFLINE'}",
         f"  FFmpeg  : {yn(c['ffmpeg']['available'])}",
         f"  Whisper : {yn(c['whisper']['available'])} ({c['whisper'].get('engine')}, {c['whisper'].get('model')})",
         f"  LLM     : {yn(c['llm']['available'])} (ollama installato: {c['llm'].get('ollama_installed')}, modello {c['llm'].get('model')}, scaricato: {c['llm'].get('model_downloaded')})",
         "[Cartelle]"]
    L += [f"  {k:13s} {yn(v['exists']):9s} {v['path']}" for k, v in d["dirs"].items()]
    L += ["[Riunioni]",
          f"  totale {m['total']} · ore registrate {m['recorded_hours']} · per stato: {m['by_status'] or '-'}",
          "[Prestazioni (medie dalle riunioni elaborate)]",
          f"  trascrizione: fattore tempo reale medio {perf['transcription_realtime_factor_avg']} (max {perf['transcription_realtime_factor_max']}), campioni {perf['samples']}",
          f"  sintesi: {perf['summary_seconds_avg']} s in media (max {perf['summary_seconds_max']}) · conversione {perf['conversion_seconds_avg']} s · RAM Whisper max {perf['whisper_peak_rss_mb_max']} MB",
          "[Log]",
          f"  backend.log: {lg['size_bytes']} byte, file ruotati {lg['rotated_files']}, righe per livello {lg['levels'] or '-'}"]
    L += [f"  ! {e}" for e in lg["last_errors"]]
    pr = problems(d)
    L += ["", "[Esito]"] + ([f"  ✗ {p}" for p in pr] if pr else ["  ✓ Nessun problema rilevato."])
    return "\n".join(L) + "\n"


def main(argv: list[str]) -> int:
    try:
        cfg = config_mod.load()
    except config_mod.ConfigError as e:
        print(f"Configurazione non valida: {e}", file=sys.stderr)
        return 2
    d = collect(cfg)
    print(json.dumps(d, ensure_ascii=False, indent=2) if "--json" in argv else render(d), end="")
    return 1 if problems(d) else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
