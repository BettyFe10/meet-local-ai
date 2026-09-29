"""Percorsi del progetto, ricavati a runtime (il repo può stare in qualsiasi cartella)."""

from __future__ import annotations

import os
from pathlib import Path

# backend/meetlocalai/paths.py -> radice del repository
REPO_ROOT = Path(__file__).resolve().parents[2]
EXAMPLE_CONFIG = REPO_ROOT / "config" / "config.example.json"
DEFAULT_CONFIG_PATH = Path("~/MeetLocalAI/Config/config.json")


def config_path() -> Path:
    """Percorso del config attivo. Sovrascrivibile con MEETLOCALAI_CONFIG (usato dai test)."""
    env = os.environ.get("MEETLOCALAI_CONFIG")
    return Path(env).expanduser() if env else DEFAULT_CONFIG_PATH.expanduser()


def expand(p: str) -> Path:
    return Path(os.path.expandvars(p)).expanduser()
