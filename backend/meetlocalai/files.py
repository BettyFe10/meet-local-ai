"""Gestione dei file delle riunioni: eliminazione (nel Cestino), esportazione, spazio occupato, pulizia.

Le riunioni sono normali cartelle: tutto ciò che fa questo modulo si può fare anche a mano dal Finder.
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from .meetings import ID_RE

log = logging.getLogger("meetlocalai.files")

_JXA_TRASH = """
ObjC.import('Foundation');
function run(argv) {
  var url = $.NSURL.fileURLWithPath(argv[0]);
  var err = Ref();
  var ok = $.NSFileManager.defaultManager.trashItemAtURLResultingItemURLError(url, null, err);
  if (!ok) { throw new Error(ObjC.unwrap(err[0].localizedDescription)); }
  return 'ok';
}
"""


def trash(folder: Path, fallback_dir: Path) -> str:
    """Sposta la cartella nel Cestino del Mac (recuperabile). Se non è possibile, la sposta in
    <data_root>/Cestino. Ritorna "trash" oppure "fallback". Non cancella mai in modo definitivo."""
    # MEETLOCALAI_NO_SYSTEM_TRASH=1: usato dai test per non toccare il Cestino vero
    if sys.platform == "darwin" and not os.environ.get("MEETLOCALAI_NO_SYSTEM_TRASH"):
        try:
            r = subprocess.run(["/usr/bin/osascript", "-l", "JavaScript", "-e", _JXA_TRASH, str(folder)],
                               capture_output=True, text=True, timeout=30)
            if r.returncode == 0 and not folder.exists():
                return "trash"
            log.warning("Cestino di sistema non disponibile (%s): uso la cartella Cestino interna", r.stderr.strip()[:200])
        except Exception as e:  # noqa: BLE001
            log.warning("Cestino di sistema non disponibile (%s): uso la cartella Cestino interna", type(e).__name__)
    fallback_dir.mkdir(parents=True, exist_ok=True)
    dest = fallback_dir / folder.name
    n = 2
    while dest.exists():
        dest = fallback_dir / f"{folder.name}_{n}"
        n += 1
    shutil.move(str(folder), str(dest))
    return "fallback"


def build_export(folder: Path, md: dict, fmt: str) -> str:
    """Documento unico: verbale (se c'è) + trascrizione (se c'è)."""
    dur = round((md.get("duration_seconds") or 0) / 60)
    summary = folder / "summary.md"
    if fmt == "md":
        tr = folder / "transcript.md"
        parts = [summary.read_text(encoding="utf-8").rstrip() if summary.exists()
                 else f"# RIUNIONE — {md['title']}\n\n- Data: {md.get('date')} {md.get('start_time')} · Durata: {dur} min\n\n_Sintesi non disponibile._"]
        if tr.exists():
            parts.append("---\n\n" + tr.read_text(encoding="utf-8").rstrip())
        return "\n\n".join(parts) + "\n"
    tr = folder / "transcript.txt"
    head = f"RIUNIONE — {md['title']}\nData: {md.get('date')} {md.get('start_time')} · Durata: {dur} min\n"
    body = []
    if summary.exists():
        text = summary.read_text(encoding="utf-8")
        text = "\n".join(l for l in text.splitlines() if not l.startswith("# RIUNIONE") and not l.startswith("- Data:"))
        text = text.replace("## ", "").replace("**", "")
        body.append("=== VERBALE ===\n" + text.strip())
    if tr.exists():
        body.append("=== TRASCRIZIONE ===\n" + tr.read_text(encoding="utf-8").strip())
    if not body:
        body.append("Nessun contenuto disponibile.")
    return head + "\n" + "\n\n".join(body) + "\n"


def export(folder: Path, md: dict, fmt: str, exports_dir: Path) -> tuple[str, Path]:
    text = build_export(folder, md, fmt)
    exports_dir.mkdir(parents=True, exist_ok=True)
    out = exports_dir / f"{md['id']}.{fmt}"
    out.write_text(text, encoding="utf-8")
    return text, out


def dir_size(path: Path) -> int:
    if not path.exists():
        return 0
    return sum(p.stat().st_size for p in path.rglob("*") if p.is_file())


def storage(dirs: dict) -> dict:
    usage = shutil.disk_usage(dirs["data_root"] if dirs["data_root"].exists() else Path.home())
    meetings_dir = dirs["meetings_dir"]
    count = sum(1 for f in meetings_dir.iterdir() if f.is_dir() and ID_RE.match(f.name)) if meetings_dir.is_dir() else 0
    return {
        "meetings_bytes": dir_size(meetings_dir),
        "meetings_count": count,
        "models_bytes": dir_size(dirs["models_dir"]),
        "exports_bytes": dir_size(dirs["exports_dir"]),
        "free_bytes": usage.free,
        "total_bytes": usage.total,
        "low_space": usage.free < 5 * 1024**3,
    }


def cleanup_temp(temp_dir: Path) -> int:
    """All'avvio: rimuove le cartelle di lavoro lasciate da elaborazioni interrotte (WAV temporanei)."""
    n = 0
    if temp_dir.is_dir():
        for d in temp_dir.iterdir():
            if d.is_dir() and ID_RE.match(d.name):
                shutil.rmtree(d, ignore_errors=True)
                n += 1
    return n


def remove_raw(folder: Path) -> int:
    """Rimuove le tracce grezze (raw/*.webm) dopo un'elaborazione riuscita, se audio.keep_raw_tracks è false."""
    raw = folder / "raw"
    freed = dir_size(raw)
    shutil.rmtree(raw, ignore_errors=True)
    return freed


def stamp() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")
