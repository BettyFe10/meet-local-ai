"""Controlli di disponibilità dei componenti locali (senza dipendenze esterne)."""

from __future__ import annotations

import json
import logging
import os
import shutil
import urllib.request

log = logging.getLogger("meetlocalai.health")

_EXTRA_PATHS = ["/opt/homebrew/bin", "/usr/local/bin"]


def which(cmd: str) -> str | None:
    search = os.pathsep.join([os.environ.get("PATH", "")] + _EXTRA_PATHS)
    return shutil.which(cmd, path=search)


def check_ffmpeg() -> dict:
    p = which("ffmpeg")
    return {"available": p is not None, "path": p}


def check_ollama(base_url: str, timeout: float = 1.5) -> dict:
    try:
        with urllib.request.urlopen(base_url.rstrip("/") + "/api/version", timeout=timeout) as r:
            version = json.loads(r.read().decode("utf-8")).get("version")
        return {"available": True, "version": version}
    except Exception as e:  # noqa: BLE001 - qualsiasi errore = non disponibile
        log.info("Ollama non raggiungibile su %s: %s", base_url, type(e).__name__)
        return {"available": False, "version": None}


def check_whisper(cfg: dict, models_dir) -> dict:
    from . import transcribe  # noqa: PLC0415
    eng = transcribe.select_engine(cfg, models_dir)
    if eng is None:
        return {"available": False, "engine": None, "model": None}
    return {"available": True, "engine": eng.name, "model": eng.model}


def check_llm(cfg: dict, models_dir) -> dict:
    """LLM utilizzabile = Ollama installato + modello presente su disco (il server parte solo quando serve)."""
    from . import llm  # noqa: PLC0415
    model = llm.resolve_model(cfg)
    binary = which("ollama") is not None
    present = llm.model_on_disk(models_dir, model)
    return {"available": binary and present and not llm.is_cloud_model(model), "provider": "ollama",
            "ollama_installed": binary, "model": model, "model_downloaded": present}
