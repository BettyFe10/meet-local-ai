import json

from fastapi.testclient import TestClient

from meetlocalai import config as config_mod, paths
from meetlocalai.app import create_app

from .conftest import BASE, HDR, write_cfg

OFFICIAL_ID = json.loads(paths.EXAMPLE_CONFIG.read_text())["backend"]["allowed_extension_ids"][0]
EXT = f"chrome-extension://{OFFICIAL_ID}"
OTHER_EXT = "chrome-extension://zzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzz"


def test_missing_client_header_is_rejected(client):
    r = client.get("/api/v1/health")
    assert r.status_code == 403 and r.json()["error_code"] == "missing_client_header"


def test_website_origin_is_rejected(client):
    r = client.get("/api/v1/health", headers={**HDR, "Origin": "https://evil.example"})
    assert r.status_code == 403 and r.json()["error_code"] == "forbidden_origin"


def test_meet_origin_is_rejected(client):
    r = client.get("/api/v1/health", headers={**HDR, "Origin": "https://meet.google.com"})
    assert r.status_code == 403


def test_foreign_host_is_rejected(cfg_path):
    app = create_app(config_mod.load())
    with TestClient(app, base_url="http://attacker.example:8765") as c:
        r = c.get("/api/v1/health", headers=HDR)
    assert r.status_code == 403 and r.json()["error_code"] == "forbidden_host"


def test_localhost_host_is_accepted(cfg_path):
    app = create_app(config_mod.load())
    with TestClient(app, base_url="http://localhost:8765") as c:
        assert c.get("/api/v1/health", headers=HDR).status_code == 200


def test_extension_origin_allowed_with_cors_headers(client):
    r = client.get("/api/v1/health", headers={**HDR, "Origin": EXT})
    assert r.status_code == 200
    assert r.headers["access-control-allow-origin"] == EXT


def test_preflight_from_extension(client):
    r = client.options("/api/v1/health", headers={"Origin": EXT, "Access-Control-Request-Method": "GET",
                                                   "Access-Control-Request-Headers": "x-meetlocalai"})
    assert r.status_code == 204
    assert "X-MeetLocalAI" in r.headers["access-control-allow-headers"]


def test_default_config_allows_only_official_extension(client):
    assert client.get("/api/v1/health", headers={**HDR, "Origin": EXT}).status_code == 200
    r = client.get("/api/v1/health", headers={**HDR, "Origin": OTHER_EXT})
    assert r.status_code == 403 and r.json()["error_code"] == "forbidden_origin"


def test_empty_allowlist_is_dev_mode_any_extension(tmp_path, monkeypatch):
    p = write_cfg(tmp_path, {"backend": {"allowed_extension_ids": []}})
    monkeypatch.setenv("MEETLOCALAI_CONFIG", str(p))
    with TestClient(create_app(config_mod.load()), base_url=BASE) as c:
        assert c.get("/api/v1/health", headers={**HDR, "Origin": OTHER_EXT}).status_code == 200
        assert c.get("/api/v1/health", headers={**HDR, "Origin": "https://evil.example"}).status_code == 403
