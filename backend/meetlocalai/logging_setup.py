"""Log rotanti in <logs_dir>/backend.log. Mai contenuto delle riunioni nei log."""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler

from .config import data_dirs

_FMT = "%(asctime)s %(levelname)s %(name)s: %(message)s"


def setup(cfg: dict) -> logging.Logger:
    lc = cfg.get("logging", {})
    logs_dir = data_dirs(cfg)["logs_dir"]
    logs_dir.mkdir(parents=True, exist_ok=True)
    root = logging.getLogger("meetlocalai")
    root.setLevel(getattr(logging, str(lc.get("level", "INFO")).upper(), logging.INFO))
    target = str(logs_dir / "backend.log")
    if not any(isinstance(h, RotatingFileHandler) and h.baseFilename == target for h in root.handlers):
        fh = RotatingFileHandler(target, maxBytes=int(lc.get("max_bytes", 5_242_880)),
                                 backupCount=int(lc.get("backup_count", 5)), encoding="utf-8")
        fh.setFormatter(logging.Formatter(_FMT))
        root.addHandler(fh)
    return root
