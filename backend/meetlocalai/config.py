"""Caricamento configurazione: default da config.example.json + override da config.json locale."""

from __future__ import annotations

import copy
import ipaddress
import json
import logging
import shutil
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from . import paths

log = logging.getLogger("meetlocalai.config")


class ConfigError(ValueError):
    """Configurazione non valida (messaggio comprensibile per l'utente)."""


def _deep_merge(base: dict, override: dict) -> dict:
    out = copy.deepcopy(base)
    for k, v in override.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def _is_loopback_host(host: str | None) -> bool:
    if not host:
        return False
    if host == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def validate(cfg: dict) -> dict:
    b = cfg.get("backend", {})
    if b.get("host") != "127.0.0.1":
        raise ConfigError("backend.host deve essere 127.0.0.1 (il backend non può essere esposto in rete).")
    port = b.get("port")
    if not isinstance(port, int) or not (1024 <= port <= 65535):
        raise ConfigError("backend.port deve essere un numero tra 1024 e 65535.")
    ids = b.get("allowed_extension_ids", [])
    if not isinstance(ids, list) or not all(isinstance(i, str) for i in ids):
        raise ConfigError("backend.allowed_extension_ids deve essere una lista di stringhe.")
    llm_url = cfg.get("llm", {}).get("base_url", "")
    if llm_url and not _is_loopback_host(urlparse(llm_url).hostname):
        raise ConfigError("llm.base_url deve puntare a questo computer (127.0.0.1 / localhost).")
    for key in ("data_root", "meetings_dir", "models_dir", "logs_dir", "exports_dir", "temp_dir"):
        if not isinstance(cfg.get("paths", {}).get(key), str):
            raise ConfigError(f"paths.{key} mancante o non valido.")
    return cfg


def load(path: Path | None = None, create_if_missing: bool = True) -> dict[str, Any]:
    """Carica e valida il config. Se manca il config locale, lo crea copiando l'esempio."""
    path = path or paths.config_path()
    defaults = json.loads(paths.EXAMPLE_CONFIG.read_text(encoding="utf-8"))
    if not path.exists():
        if create_if_missing:
            path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(paths.EXAMPLE_CONFIG, path)
            log.info("Creato config locale da esempio: %s", path)
        user: dict = {}
    else:
        try:
            user = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            raise ConfigError(f"Il file di configurazione non è un JSON valido ({path}, riga {e.lineno}).") from e
    cfg = validate(_deep_merge(defaults, user))
    cfg["_config_path"] = str(path)
    return cfg


def data_dirs(cfg: dict) -> dict[str, Path]:
    p = cfg["paths"]
    return {k: paths.expand(p[k]) for k in ("data_root", "meetings_dir", "models_dir", "logs_dir", "exports_dir", "temp_dir")}


def ensure_dirs(cfg: dict) -> None:
    for d in data_dirs(cfg).values():
        d.mkdir(parents=True, exist_ok=True)
