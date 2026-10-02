import json
import sys
import wave

from meetlocalai import config as config_mod

from .conftest import HDR


def meeting_with_wav(client, seconds=2):
    md = client.post("/api/v1/meetings", headers=HDR, json={"title": "Audio"}).json()
    client.post(f"/api/v1/meetings/{md['id']}/stop", headers=HDR, json={})
    folder = config_mod.data_dirs(config_mod.load())["meetings_dir"] / md["id"]
    with wave.open(str(folder / "audio.wav"), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(16000)
        w.writeframes(b"\x01\x02" * 16000 * seconds)
    return md["id"], folder


def test_audio_requires_header_or_valid_token(client):
    mid, _ = meeting_with_wav(client)
    url = f"/api/v1/meetings/{mid}/audio"
    assert client.get(url).status_code == 403                                   # niente header, niente token
    assert client.get(url + "?token=sbagliato").status_code == 403
    tok = client.post(f"/api/v1/meetings/{mid}/audio-token", headers=HDR).json()["token"]
    r = client.get(url + f"?token={tok}")                                       # come farebbe il tag <audio>
    assert r.status_code == 200 and r.headers["content-type"] == "audio/wav"
    assert len(r.content) == 44 + 64000
    assert client.get(url, headers=HDR).status_code == 200                      # con header va comunque


def test_audio_token_is_bound_to_its_meeting(client):
    a, _ = meeting_with_wav(client)
    b, _ = meeting_with_wav(client)
    tok = client.post(f"/api/v1/meetings/{a}/audio-token", headers=HDR).json()["token"]
    assert client.get(f"/api/v1/meetings/{b}/audio?token={tok}").status_code == 403


def test_token_does_not_unlock_other_endpoints(client):
    mid, _ = meeting_with_wav(client)
    tok = client.post(f"/api/v1/meetings/{mid}/audio-token", headers=HDR).json()["token"]
    assert client.get(f"/api/v1/meetings/{mid}?token={tok}").status_code == 403
    assert client.get(f"/api/v1/meetings?token={tok}").status_code == 403
    assert client.post(f"/api/v1/meetings/{mid}/audio-token").status_code == 403   # il token si ottiene solo con header


def test_audio_supports_range_requests(client):
    mid, _ = meeting_with_wav(client)
    r = client.get(f"/api/v1/meetings/{mid}/audio", headers={**HDR, "Range": "bytes=0-99"})
    assert r.status_code == 206 and len(r.content) == 100
    assert r.headers["content-range"].startswith("bytes 0-99/")


def test_audio_not_ready(client):
    md = client.post("/api/v1/meetings", headers=HDR, json={"title": "No"}).json()
    assert client.post(f"/api/v1/meetings/{md['id']}/audio-token", headers=HDR).status_code == 404
    assert client.get(f"/api/v1/meetings/{md['id']}/audio", headers=HDR).status_code == 404


def test_open_folder(client, monkeypatch):
    import subprocess
    mid, folder = meeting_with_wav(client)
    calls = []
    monkeypatch.setattr(subprocess, "Popen", lambda cmd, **k: calls.append(cmd))
    monkeypatch.setattr(sys, "platform", "darwin")
    assert client.post(f"/api/v1/meetings/{mid}/open-folder", headers=HDR).json() == {"opened": True}
    assert calls == [["/usr/bin/open", str(folder)]]
    assert client.post("/api/v1/open-data-root", headers=HDR).json() == {"opened": True}
    assert client.post("/api/v1/meetings/2026-01-01_00-00_Nessuna/open-folder", headers=HDR).status_code == 404
    assert len(calls) == 2
    monkeypatch.setattr(sys, "platform", "linux")
    assert client.post("/api/v1/open-data-root", headers=HDR).status_code == 501


def test_list_has_dashboard_fields(client):
    mid, folder = meeting_with_wav(client)
    md = json.loads((folder / "metadata.json").read_text())
    md.update(status="error", error={"step": "converting", "user_message": "Conversione audio non riuscita."}, warnings=["a", "b"])
    (folder / "metadata.json").write_text(json.dumps(md))
    item = client.get("/api/v1/meetings", headers=HDR).json()["meetings"][0]
    assert item["has_transcript"] is False and item["has_summary"] is False and item["warnings"] == 2
    assert item["error_message"] == "Conversione audio non riuscita."
