"""Motori Whisper locali. Nessuna rete durante la trascrizione (HF_HUB_OFFLINE=1).

- "mlx":        mlx-whisper (Apple Silicon, GPU via MLX), modello Hugging Face in <models_dir>/hf
- "whispercpp": whisper.cpp (`whisper-cli`, Metal), modello ggml in <models_dir>/whispercpp

Uso da riga di comando (usato dal benchmark per misurare tempo e RAM in un processo separato):
  python -m meetlocalai.transcribe --engine mlx|whispercpp --wav file.wav --out segments.json [--language it]
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import logging
import os
import platform
import subprocess
import sys
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path

from . import health

log = logging.getLogger("meetlocalai.transcribe")

DEFAULT_MODELS = {"mlx": "mlx-community/whisper-large-v3-turbo", "whispercpp": "large-v3-turbo"}
ENGINE_ORDER = ("mlx", "whispercpp")


@dataclass
class Segment:
    start: float
    end: float
    text: str


class TranscriptionError(Exception):
    def __init__(self, user_message: str, detail: str = ""):
        super().__init__(user_message)
        self.user_message = user_message
        self.detail = detail


def _offline_env(models_dir: Path) -> dict:
    return {"HF_HOME": str(models_dir / "hf"), "HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1",
            "HF_HUB_DISABLE_TELEMETRY": "1"}


class MlxEngine:
    name = "mlx"

    def __init__(self, model: str, models_dir: Path):
        self.model = model if model and model != "auto" else DEFAULT_MODELS["mlx"]
        self.models_dir = models_dir

    def model_path(self) -> Path:
        return self.models_dir / "hf" / "hub" / ("models--" + self.model.replace("/", "--"))

    def available(self) -> tuple[bool, str]:
        if not (sys.platform == "darwin" and platform.machine() == "arm64"):
            return False, "mlx richiede un Mac Apple Silicon"
        if importlib.util.find_spec("mlx_whisper") is None:
            return False, "mlx-whisper non installato"
        if not self.model_path().exists():
            return False, f"modello non scaricato ({self.model})"
        return True, ""

    def transcribe(self, wav: Path, language: str = "it") -> list[Segment]:
        os.environ.update(_offline_env(self.models_dir))
        import mlx_whisper  # noqa: PLC0415 - import pesante solo quando serve
        r = mlx_whisper.transcribe(str(wav), path_or_hf_repo=self.model, language=language or None,
                                   condition_on_previous_text=False, verbose=None)
        return [Segment(float(s["start"]), float(s["end"]), s["text"].strip()) for s in r.get("segments", []) if s["text"].strip()]


class WhisperCppEngine:
    name = "whispercpp"

    def __init__(self, model: str, models_dir: Path, threads: int = 4):
        self.model = model if model and model != "auto" else DEFAULT_MODELS["whispercpp"]
        self.models_dir = models_dir
        self.threads = threads

    def model_path(self) -> Path:
        return self.models_dir / "whispercpp" / f"ggml-{self.model}.bin"

    def binary(self) -> str | None:
        return health.which("whisper-cli")

    def available(self) -> tuple[bool, str]:
        if not self.binary():
            return False, "whisper-cli non installato"
        if not self.model_path().exists():
            return False, f"modello non scaricato ({self.model_path().name})"
        return True, ""

    def transcribe(self, wav: Path, language: str = "it") -> list[Segment]:
        with tempfile.TemporaryDirectory() as td:
            prefix = Path(td) / "out"
            cmd = [self.binary(), "-m", str(self.model_path()), "-f", str(wav), "-l", language or "auto",
                   "-t", str(self.threads), "-oj", "-of", str(prefix), "-np"]
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=6 * 3600)
            if r.returncode != 0:
                log.error("whisper-cli fallito (%s): %s", r.returncode, r.stderr[-800:])
                raise TranscriptionError("Trascrizione non riuscita.", r.stderr[-800:])
            return parse_whispercpp_json(json.loads(Path(str(prefix) + ".json").read_text(encoding="utf-8")))


def parse_whispercpp_json(data: dict) -> list[Segment]:
    out = []
    for item in data.get("transcription", []):
        text = item.get("text", "").strip()
        if text:
            off = item.get("offsets", {})
            out.append(Segment(off.get("from", 0) / 1000.0, off.get("to", 0) / 1000.0, text))
    return out


def make_engine(name: str, model: str, models_dir: Path):
    if name == "mlx":
        return MlxEngine(model, models_dir)
    if name == "whispercpp":
        return WhisperCppEngine(model, models_dir)
    raise ValueError(f"motore sconosciuto: {name}")


def select_engine(cfg: dict, models_dir: Path):
    """Motore configurato, oppure ('auto') il primo disponibile. None se nessuno è pronto."""
    tc = cfg.get("transcription", {})
    name, model = tc.get("engine", "auto"), tc.get("model", "auto")
    names = ENGINE_ORDER if name == "auto" else (name,)
    for n in names:
        eng = make_engine(n, model if name != "auto" else "auto", models_dir)
        ok, why = eng.available()
        if ok:
            return eng
        log.info("Motore %s non disponibile: %s", n, why)
    return None


def main(argv: list[str]) -> int:
    from . import config as config_mod

    ap = argparse.ArgumentParser(prog="python -m meetlocalai.transcribe")
    ap.add_argument("--engine", required=True, choices=ENGINE_ORDER)
    ap.add_argument("--model", default="auto")
    ap.add_argument("--wav", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--language", default="it")
    a = ap.parse_args(argv)
    cfg = config_mod.load()
    eng = make_engine(a.engine, a.model, config_mod.data_dirs(cfg)["models_dir"])
    ok, why = eng.available()
    if not ok:
        print(f"Motore non disponibile: {why}", file=sys.stderr)
        return 3
    segs = eng.transcribe(a.wav, a.language)
    a.out.write_text(json.dumps({"engine": eng.name, "model": eng.model, "segments": [asdict(s) for s in segs]},
                                ensure_ascii=False, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
