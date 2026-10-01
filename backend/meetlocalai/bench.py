"""Benchmark dei motori Whisper su una riunione registrata (tempo, rapporto realtime, RAM).

  python -m meetlocalai.bench [--meeting ID] [--engines mlx,whispercpp]

Le trascrizioni di prova vanno in <temp_dir>/bench/<ID>/ (file locali, non nei log).
Il riepilogo (solo numeri) va in <logs_dir>/whisper_benchmark_<data>.json.
"""

from __future__ import annotations

import argparse
import json
import platform
import re
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

from . import audio, config as config_mod, transcribe


def pick_meeting(meetings_dir: Path, meeting_id: str | None) -> Path:
    if meeting_id:
        f = meetings_dir / meeting_id
        if not f.is_dir():
            raise SystemExit(f"Riunione non trovata: {meeting_id}")
        return f
    cands = [d for d in meetings_dir.iterdir() if d.is_dir() and any(
        p.stat().st_size > 100_000 for p in (d / "raw").glob("*.webm"))] if meetings_dir.is_dir() else []
    if not cands:
        raise SystemExit("Nessuna riunione con audio da usare per il benchmark.")
    return max(cands, key=lambda d: d.name)


def parse_max_rss(stderr: str) -> int | None:
    """macOS `/usr/bin/time -l`: '  123456789  maximum resident set size' (byte)."""
    m = re.search(r"(\d+)\s+maximum resident set size", stderr)
    return int(m.group(1)) if m else None


def fmt_ts(sec: float) -> str:
    s = int(sec)
    return f"{s // 3600:02d}:{s % 3600 // 60:02d}:{s % 60:02d}"


def run_one(engine: str, wav: Path, out_json: Path, language: str) -> dict:
    cmd = [sys.executable, "-m", "meetlocalai.transcribe", "--engine", engine, "--wav", str(wav), "--out", str(out_json),
           "--language", language]
    if sys.platform == "darwin":
        cmd = ["/usr/bin/time", "-l"] + cmd
    t0 = time.perf_counter()
    r = subprocess.run(cmd, capture_output=True, text=True, cwd=Path(__file__).resolve().parents[1])
    elapsed = time.perf_counter() - t0
    res = {"ok": r.returncode == 0, "seconds": round(elapsed, 2), "max_rss_mb": None}
    rss = parse_max_rss(r.stderr)
    if rss:
        res["max_rss_mb"] = round(rss / 1024 / 1024)
    if not res["ok"]:
        res["error"] = r.stderr.strip().splitlines()[-1][:300] if r.stderr.strip() else f"exit {r.returncode}"
    return res


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="python -m meetlocalai.bench")
    ap.add_argument("--meeting")
    ap.add_argument("--engines", default="mlx,whispercpp")
    a = ap.parse_args(argv)

    cfg = config_mod.load()
    dirs = config_mod.data_dirs(cfg)
    language = cfg["transcription"].get("language", "it")
    folder = pick_meeting(dirs["meetings_dir"], a.meeting)
    work = dirs["temp_dir"] / "bench" / folder.name
    print(f"Riunione: {folder.name}")
    t0 = time.perf_counter()
    prep = audio.prepare(folder, ["tab", "mic"], work)
    conv = time.perf_counter() - t0
    print(f"Conversione: {conv:.1f} s, durata audio {prep['duration']:.1f} s, tracce {list(prep['tracks'])}")

    results = {"meeting": folder.name, "date": datetime.now().astimezone().isoformat(timespec="seconds"),
               "machine": {"platform": platform.platform(), "machine": platform.machine(), "python": platform.python_version()},
               "audio_seconds": round(prep["duration"], 1), "conversion_seconds": round(conv, 2), "engines": {}}
    for name in [e.strip() for e in a.engines.split(",") if e.strip()]:
        eng = transcribe.make_engine(name, "auto", dirs["models_dir"])
        ok, why = eng.available()
        if not ok:
            print(f"- {name}: NON DISPONIBILE ({why})")
            results["engines"][name] = {"available": False, "reason": why}
            continue
        er = {"available": True, "model": eng.model, "tracks": {}}
        for track, wav in prep["tracks"].items():
            out_json = work / f"{name}_{track}.json"
            r = run_one(name, wav, out_json, language)
            dur = audio.wav_duration(wav)
            if r["ok"]:
                segs = json.loads(out_json.read_text(encoding="utf-8"))["segments"]
                r["segments"] = len(segs)
                r["characters"] = sum(len(s["text"]) for s in segs)
                (work / f"{name}_{track}.txt").write_text(
                    "\n".join(f"[{fmt_ts(s['start'])}] {s['text']}" for s in segs) + "\n", encoding="utf-8")
            r["track_seconds"] = round(dur, 1)
            r["realtime_factor"] = round(r["seconds"] / dur, 3) if dur else None
            er["tracks"][track] = r
            print(f"- {name} [{track}]: {'ok' if r['ok'] else 'ERRORE'} {r['seconds']} s "
                  f"(RTF {r['realtime_factor']}), RAM max {r['max_rss_mb']} MB" + ("" if r["ok"] else f" — {r.get('error')}"))
        results["engines"][name] = er

    dirs["logs_dir"].mkdir(parents=True, exist_ok=True)
    out = dirs["logs_dir"] / f"whisper_benchmark_{datetime.now():%Y%m%d_%H%M%S}.json"
    out.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Riepilogo: {out}\nTrascrizioni di prova: {work}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
