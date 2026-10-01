"""Conversione audio con FFmpeg (programma esterno): webm/opus → WAV 16 kHz mono, mix delle tracce."""

from __future__ import annotations

import logging
import shutil
import subprocess
from pathlib import Path

from . import health

log = logging.getLogger("meetlocalai.audio")


class AudioError(Exception):
    """Errore di conversione (messaggio per l'utente in .user_message)."""

    def __init__(self, user_message: str, detail: str = ""):
        super().__init__(user_message)
        self.user_message = user_message
        self.detail = detail


def _ffmpeg() -> str:
    p = health.which("ffmpeg")
    if not p:
        raise AudioError("FFmpeg non installato.")
    return p


def _run(cmd: list[str], timeout: int = 3600) -> None:
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    if r.returncode != 0:
        log.error("ffmpeg fallito (%s): %s", r.returncode, r.stderr[-800:])
        raise AudioError("Conversione audio non riuscita.", r.stderr[-800:])


def wav_duration(path: Path) -> float:
    """Durata di un WAV PCM 16 bit mono prodotto da noi (header 44 byte)."""
    import wave
    with wave.open(str(path), "rb") as w:
        return w.getnframes() / float(w.getframerate())


def to_wav(src: Path, dst: Path, sample_rate: int = 16000) -> float:
    dst.parent.mkdir(parents=True, exist_ok=True)
    _run([_ffmpeg(), "-nostdin", "-y", "-v", "error", "-i", str(src), "-ac", "1", "-ar", str(sample_rate),
          "-c:a", "pcm_s16le", str(dst)])
    return wav_duration(dst)


def mix(wavs: list[Path], dst: Path) -> float:
    if not wavs:
        raise AudioError("Nessuna traccia audio da unire.")
    dst.parent.mkdir(parents=True, exist_ok=True)
    if len(wavs) == 1:
        shutil.copyfile(wavs[0], dst)
        return wav_duration(dst)
    cmd = [_ffmpeg(), "-nostdin", "-y", "-v", "error"]
    for w in wavs:
        cmd += ["-i", str(w)]
    cmd += ["-filter_complex", f"amix=inputs={len(wavs)}:duration=longest:normalize=0,alimiter=limit=0.95",
            "-ac", "1", "-c:a", "pcm_s16le", str(dst)]
    _run(cmd)
    return wav_duration(dst)


def prepare(meeting_folder: Path, tracks: list[str], work_dir: Path, sample_rate: int = 16000) -> dict:
    """Converte le tracce grezze presenti; crea audio.wav (mix) nella cartella della riunione.
    Ritorna {"tracks": {track: wav_path}, "audio": path, "duration": s}. Tracce vuote/assenti saltate."""
    out: dict[str, Path] = {}
    for t in tracks:
        raw = meeting_folder / "raw" / f"{t}.webm"
        if raw.exists() and raw.stat().st_size > 0:
            out[t] = work_dir / f"{t}.wav"
            to_wav(raw, out[t], sample_rate)
    if not out:
        raise AudioError("Nessun audio registrato per questa riunione.")
    audio = meeting_folder / "audio.wav"
    duration = mix(list(out.values()), audio)
    return {"tracks": out, "audio": audio, "duration": duration}


def peak_db(wav: Path) -> float | None:
    """Picco del segnale in dB (FFmpeg volumedetect). None se non misurabile."""
    import re  # noqa: PLC0415
    r = subprocess.run([_ffmpeg(), "-nostdin", "-hide_banner", "-nostats", "-i", str(wav), "-af", "volumedetect",
                        "-f", "null", "-"], capture_output=True, text=True, timeout=600)
    m = re.search(r"max_volume:\s*(-?[\d.]+|-inf) dB", r.stderr)
    if not m:
        return None
    return -120.0 if m.group(1) == "-inf" else float(m.group(1))
