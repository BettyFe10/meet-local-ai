import subprocess
import sys

from meetlocalai import config as config_mod, messages, paths

from .conftest import HDR


def test_health_ok(client):
    r = client.get("/api/v1/health", headers=HDR)
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["version"]
    assert set(body) >= {"ffmpeg", "whisper", "llm"}


def test_health_reports_missing_components_with_user_messages(client):
    body = client.get("/api/v1/health", headers=HDR).json()
    assert body["whisper"]["available"] is False
    assert body["whisper"]["user_message"] == messages.WHISPER_UNAVAILABLE
    assert body["llm"]["available"] is False            # Ollama su porta chiusa
    assert body["llm"]["user_message"] == messages.LLM_UNAVAILABLE


def test_status(client):
    body = client.get("/api/v1/status", headers=HDR).json()
    assert body["recording"] is None and body["queue_length"] == 0


def test_unknown_route_returns_user_friendly_404(client):
    r = client.get("/api/v1/nope", headers=HDR)
    assert r.status_code == 404
    assert r.json()["user_message"] == messages.NOT_FOUND


def test_no_docs_or_web_ui_exposed(client):
    for path in ("/docs", "/redoc", "/openapi.json", "/"):
        assert client.get(path, headers=HDR).status_code == 404


def test_data_dirs_and_log_created(client, cfg_path):
    cfg = config_mod.load()
    dirs = config_mod.data_dirs(cfg)
    for d in dirs.values():
        assert d.is_dir()
    assert (dirs["logs_dir"] / "backend.log").exists()


def test_cli_print_port(cfg_path):
    out = subprocess.run([sys.executable, "-m", "meetlocalai", "--print-port"], capture_output=True, text=True,
                         cwd=paths.REPO_ROOT / "backend")
    assert out.returncode == 0 and out.stdout.strip() == "8765"


def test_cli_rejects_invalid_config(tmp_path, monkeypatch):
    p = tmp_path / "config.json"
    p.write_text('{"backend": {"host": "0.0.0.0"}}', encoding="utf-8")
    monkeypatch.setenv("MEETLOCALAI_CONFIG", str(p))
    out = subprocess.run([sys.executable, "-m", "meetlocalai", "--check-config"], capture_output=True, text=True,
                         cwd=paths.REPO_ROOT / "backend")
    assert out.returncode == 2 and "127.0.0.1" in out.stderr


def test_cli_print_dir(cfg_path):
    out = subprocess.run([sys.executable, "-m", "meetlocalai", "--print-dir", "temp_dir"], capture_output=True, text=True,
                         cwd=paths.REPO_ROOT / "backend")
    assert out.returncode == 0 and out.stdout.strip().endswith("Temp")
    bad = subprocess.run([sys.executable, "-m", "meetlocalai", "--print-dir", "nope"], capture_output=True, text=True,
                         cwd=paths.REPO_ROOT / "backend")
    assert bad.returncode == 2
