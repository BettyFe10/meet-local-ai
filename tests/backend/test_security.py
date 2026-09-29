from fastapi.testclient import TestClient

from meetlocalai import config as config_mod
from meetlocalai.app import create_app

from .conftest import BASE, HDR, write_cfg

EXT = "chrome-extension://abcdefghijklmnopabcdefghijklmnop"


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


def test_allowlist_restricts_extension_ids(tmp_path, monkeypatch):
    p = write_cfg(tmp_path, {"backend": {"allowed_extension_ids": ["abcdefghijklmnopabcdefghijklmnop"]}})
    monkeypatch.setenv("MEETLOCALAI_CONFIG", str(p))
    app = create_app(config_mod.load())
    with TestClient(app, base_url=BASE) as c:
        assert c.get("/api/v1/health", headers={**HDR, "Origin": EXT}).status_code == 200
        other = "chrome-extension://zzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzz"
        assert c.get("/api/v1/health", headers={**HDR, "Origin": other}).status_code == 403
