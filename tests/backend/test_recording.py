import json

from fastapi.testclient import TestClient

from meetlocalai import config as config_mod, recording
from meetlocalai.app import create_app

from .conftest import BASE, HDR

AUDIO = {**HDR, "Content-Type": "audio/webm"}


def start(client, **payload):
    r = client.post("/api/v1/meetings", headers=HDR, json=payload)
    assert r.status_code == 201, r.text
    return r.json()


def folder_of(md):
    return config_mod.data_dirs(config_mod.load())["meetings_dir"] / md["id"]


def test_slugify():
    assert recording.slugify_title("Riunione commerciale: Q4 / più è città") == "Riunione-commerciale-Q4-piu-e-citta"
    assert recording.slugify_title("") == "Riunione"
    assert recording.slugify_title("../../etc") == "etc"
    assert len(recording.slugify_title("x" * 300)) == 60


def test_start_creates_folder_and_valid_metadata(client):
    md = start(client, title="Riunione commerciale", meet_code="abc-defg-hij", tracks=["tab", "mic"])
    f = folder_of(md)
    assert (f / "raw").is_dir()
    disk = json.loads((f / "metadata.json").read_text(encoding="utf-8"))
    assert disk["status"] == "recording" and disk["title"] == "Riunione commerciale"
    assert disk["source"]["meet_code"] == "abc-defg-hij"
    assert md["id"].endswith("_Riunione-commerciale")
    st = client.get("/api/v1/status", headers=HDR).json()["recording"]
    assert st["id"] == md["id"]


def test_metadata_matches_schema(client):
    import jsonschema  # noqa: PLC0415 - opzionale
    from meetlocalai import paths
    schema = json.loads((paths.REPO_ROOT / "docs" / "metadata.schema.json").read_text(encoding="utf-8"))
    md = start(client, title="Schema")
    jsonschema.validate(md, schema)
    client.post(f"/api/v1/meetings/{md['id']}/stop", headers=HDR, json={})
    jsonschema.validate(client.get(f"/api/v1/meetings/{md['id']}", headers=HDR).json(), schema)


def test_default_title_uses_meet_code(client):
    md = start(client, meet_code="abc-defg-hij")
    assert md["title"] == "Riunione abc-defg-hij"


def test_invalid_meet_code_is_dropped(client):
    md = start(client, title="x", meet_code="<script>")
    assert md["source"]["meet_code"] is None


def test_only_one_active_recording(client):
    md = start(client, title="Prima")
    r = client.post("/api/v1/meetings", headers=HDR, json={"title": "Seconda"})
    assert r.status_code == 409 and r.json()["error_code"] == "already_recording"
    assert r.json()["meeting_id"] == md["id"]


def test_same_minute_same_title_gets_suffix(client):
    a = start(client, title="Daily")
    client.post(f"/api/v1/meetings/{a['id']}/stop", headers=HDR, json={})
    b = start(client, title="Daily")
    assert b["id"] != a["id"]


def test_chunks_appended_in_order_duplicates_ignored_gaps_rejected(client):
    md = start(client, title="Chunk", tracks=["tab", "mic"])
    url = f"/api/v1/meetings/{md['id']}/chunks"
    assert client.post(url + "?track=tab&seq=0", headers=AUDIO, content=b"AAA").json()["accepted"]
    assert client.post(url + "?track=tab&seq=1", headers=AUDIO, content=b"BBB").json()["next_seq"] == 2
    dup = client.post(url + "?track=tab&seq=1", headers=AUDIO, content=b"BBB").json()
    assert dup["duplicate"] is True
    gap = client.post(url + "?track=tab&seq=5", headers=AUDIO, content=b"X")
    assert gap.status_code == 409 and gap.json()["next_seq"] == 2
    client.post(url + "?track=mic&seq=0", headers=AUDIO, content=b"MMM")
    raw = folder_of(md) / "raw"
    assert (raw / "tab.webm").read_bytes() == b"AAABBB"
    assert (raw / "mic.webm").read_bytes() == b"MMM"


def test_chunk_validation(client):
    md = start(client, title="V", tracks=["tab"])
    url = f"/api/v1/meetings/{md['id']}/chunks"
    assert client.post(url + "?track=video&seq=0", headers=AUDIO, content=b"x").status_code == 422
    assert client.post(url + "?track=mic&seq=0", headers=AUDIO, content=b"x").status_code == 422
    assert client.post(url + "?track=tab&seq=-1", headers=AUDIO, content=b"x").status_code == 422
    big = b"0" * (recording.MAX_CHUNK_BYTES + 1)
    assert client.post(url + "?track=tab&seq=0", headers=AUDIO, content=big).status_code == 413
    assert client.post("/api/v1/meetings/2026-01-01_00-00_Nessuna/chunks?track=tab&seq=0", headers=AUDIO, content=b"x").status_code == 404


def test_stop_sets_duration_status_and_is_idempotent(client):
    md = start(client, title="Stop")
    url = f"/api/v1/meetings/{md['id']}"
    client.post(url + "/chunks?track=tab&seq=0", headers=AUDIO, content=b"1234")
    r = client.post(url + "/stop", headers=HDR, json={"client_duration_seconds": 12.4})
    body = r.json()
    assert r.status_code == 200 and body["status"] == "stopped"
    assert body["duration_seconds"] >= 0 and body["ended_at"]
    assert body["performance"]["client_duration_seconds"] == 12
    assert body["audio"]["raw_bytes"] == {"tab": 4}
    assert client.post(url + "/stop", headers=HDR, json={}).json()["status"] == "stopped"
    assert client.get("/api/v1/status", headers=HDR).json()["recording"] is None
    late = client.post(url + "/chunks?track=tab&seq=1", headers=AUDIO, content=b"x")
    assert late.status_code == 409 and late.json()["error_code"] == "not_recording"


def test_rename(client):
    md = start(client, title="Vecchio")
    r = client.patch(f"/api/v1/meetings/{md['id']}", headers=HDR, json={"title": "  Nuovo   titolo "})
    assert r.json()["title"] == "Nuovo titolo"
    assert client.patch(f"/api/v1/meetings/{md['id']}", headers=HDR, json={"title": "  "}).status_code == 422


def test_restart_marks_interrupted_and_recording_can_resume(client, cfg_path):
    md = start(client, title="Crash")
    url = f"/api/v1/meetings/{md['id']}"
    client.post(url + "/chunks?track=tab&seq=0", headers=AUDIO, content=b"AA")
    # nuovo processo backend sugli stessi dati
    with TestClient(create_app(config_mod.load()), base_url=BASE) as c2:
        assert c2.get(url, headers=HDR).json()["status"] == "interrupted"
        r = c2.post(url + "/chunks?track=tab&seq=1", headers=AUDIO, content=b"BB")
        assert r.json()["accepted"]
        assert c2.get(url, headers=HDR).json()["status"] == "recording"
        assert c2.post(url + "/stop", headers=HDR, json={}).json()["status"] == "stopped"
    assert (folder_of(md) / "raw" / "tab.webm").read_bytes() == b"AABB"


def test_extension_can_post_chunks_cross_origin(client):
    ext = "chrome-extension://" + config_mod.load()["backend"]["allowed_extension_ids"][0]
    pre = client.options("/api/v1/meetings/x/chunks", headers={"Origin": ext, "Access-Control-Request-Method": "POST",
                                                                 "Access-Control-Request-Headers": "content-type,x-meetlocalai"})
    assert pre.status_code == 204 and "POST" in pre.headers["access-control-allow-methods"]
