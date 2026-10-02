import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from meetlocalai import config as config_mod
from meetlocalai.app import create_app

PORT = 8765
BASE = f"http://127.0.0.1:{PORT}"
HDR = {"X-MeetLocalAI": "1"}


def write_cfg(tmp_path: Path, override: dict | None = None) -> Path:
    root = tmp_path / "MLA"
    cfg = {
        "paths": {k: str(root / v) for k, v in {
            "data_root": "", "meetings_dir": "Meetings", "models_dir": "Models",
            "logs_dir": "Logs", "exports_dir": "Exports", "temp_dir": "Temp"}.items()},
        # porta chiusa: Ollama risulta non raggiungibile in modo deterministico
        "llm": {"base_url": "http://127.0.0.1:9"},
        # nei test l'elaborazione si lancia a mano (niente thread in background)
        "processing": {"enabled": False},
    }
    if override:
        cfg = config_mod._deep_merge(cfg, override)
    p = tmp_path / "config.json"
    p.write_text(json.dumps(cfg), encoding="utf-8")
    return p


@pytest.fixture(autouse=True)
def no_system_trash(monkeypatch):
    """I test non devono mai spostare nulla nel Cestino vero del Mac."""
    monkeypatch.setenv("MEETLOCALAI_NO_SYSTEM_TRASH", "1")


@pytest.fixture
def cfg_path(tmp_path, monkeypatch):
    p = write_cfg(tmp_path)
    monkeypatch.setenv("MEETLOCALAI_CONFIG", str(p))
    return p


@pytest.fixture
def client(cfg_path):
    app = create_app(config_mod.load())
    with TestClient(app, base_url=BASE) as c:
        yield c
