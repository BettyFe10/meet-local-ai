import json
import time

import pytest
from fastapi.testclient import TestClient

from meetlocalai import config as config_mod, processing
from meetlocalai.app import create_app
from meetlocalai.transcribe import Segment

from .conftest import BASE, HDR, write_cfg
from .test_audio_whisper import fake_whispercpp, make_webm, needs_ffmpeg  # noqa: F401 (fixture)


def test_hallucination_filter():
    for t in ["Sottotitoli creati dalla comunità Amara.org", "Sottotitoli a cura di QTSS", "Grazie per la visione!",
              "[Musica]", "  amara.org ", "Autore dei sottotitoli e revisione a cura di QTSS"]:
        assert processing.is_hallucination(t), t
    for t in ["Grazie per la visione del documento che ti ho mandato", "Iniziamo la riunione."]:
        assert not processing.is_hallucination(t), t


def test_merge_tracks_orders_labels_and_groups():
    lines = processing.merge_tracks({
        "tab": [Segment(0.0, 2.0, "Ciao."), Segment(2.5, 4.0, "Come va?"), Segment(10.0, 11.0, "Bene.")],
        "mic": [Segment(5.0, 7.0, "Tutto bene."), Segment(7.5, 8.0, "Sottotitoli a cura di QTSS")],
    })
    assert [(l.speaker, l.text) for l in lines] == [
        ("Partecipanti", "Ciao. Come va?"), ("Microfono locale", "Tutto bene."), ("Partecipanti", "Bene.")]
    txt = processing.render_txt(lines)
    assert txt.startswith("[00:00:00] Partecipanti:\nCiao. Come va?\n\n[00:00:05] Microfono locale:")


def test_render_md_has_no_invented_names():
    md = {"title": "T", "date": "2026-10-01", "start_time": "10:00", "duration_seconds": 600,
          "whisper": {"engine": "whispercpp", "model": "large-v3-turbo"}}
    out = processing.render_md(md, [])
    assert "Nessun parlato" in out and "Nessun nome viene dedotto" in out


@pytest.fixture
def meeting_with_audio(client):
    r = client.post("/api/v1/meetings", headers=HDR, json={"title": "Pipeline", "tracks": ["tab", "mic"]})
    md = r.json()
    folder = config_mod.data_dirs(config_mod.load())["meetings_dir"] / md["id"]
    make_webm(folder / "raw" / "tab.webm", 4.0, 440)
    make_webm(folder / "raw" / "mic.webm", 4.0, 880)
    client.post(f"/api/v1/meetings/{md['id']}/stop", headers=HDR, json={})
    return md["id"], folder


@needs_ffmpeg
def test_full_pipeline_with_fake_whisper(fake_whispercpp, client, meeting_with_audio):
    mid, folder = meeting_with_audio
    md = client.app.state.processor.process(mid)
    assert md["status"] == "transcribed", md.get("error")
    for f in ("audio.wav", "transcript.txt", "transcript.md", "transcript.json"):
        assert (folder / f).exists(), f
    txt = (folder / "transcript.txt").read_text()
    assert "Microfono locale:" in txt and "Partecipanti:" in txt
    assert md["whisper"] == {"engine": "whispercpp", "model": "large-v3-turbo"}
    assert md["performance"]["transcription_seconds"] >= 0 and md["performance"]["realtime_factor"] is not None
    assert md["files"]["transcript_txt"] == "transcript.txt"
    assert not (config_mod.data_dirs(config_mod.load())["temp_dir"] / mid).exists()   # WAV temporanei rimossi
    r = client.get(f"/api/v1/meetings/{mid}/transcript?format=md", headers=HDR)
    assert r.status_code == 200 and r.text.startswith("# Trascrizione")
    # nessun testo trascritto nei log
    log = (config_mod.data_dirs(config_mod.load())["logs_dir"] / "backend.log").read_text()
    assert "Buongiorno" not in log


@needs_ffmpeg
def test_pipeline_without_whisper_fails_cleanly(client, meeting_with_audio):
    mid, folder = meeting_with_audio
    md = client.app.state.processor.process(mid)
    assert md["status"] == "error"
    assert md["error"] == {**md["error"], "step": "transcribing", "user_message": "Whisper locale non disponibile."}
    assert (folder / "audio.wav").exists()


def test_pipeline_without_audio_fails_cleanly(client):
    md = client.post("/api/v1/meetings", headers=HDR, json={"title": "Muta"}).json()
    client.post(f"/api/v1/meetings/{md['id']}/stop", headers=HDR, json={})
    out = client.app.state.processor.process(md["id"])
    assert out["status"] == "error" and out["error"]["step"] == "converting"
    assert out["error"]["user_message"] == "Nessun audio registrato per questa riunione."


def test_transcript_not_ready_and_reprocess(client):
    md = client.post("/api/v1/meetings", headers=HDR, json={"title": "R"}).json()
    url = f"/api/v1/meetings/{md['id']}"
    assert client.post(url + "/reprocess", headers=HDR).status_code == 409          # ancora in registrazione
    client.post(url + "/stop", headers=HDR, json={})
    assert client.get(url + "/transcript", headers=HDR).status_code == 404
    # lo stop la mette già in coda: un reprocess immediato non la duplica
    r = client.post(url + "/reprocess", headers=HDR).json()
    assert r == {"queued": False, "queue_length": 1}
    assert client.get("/api/v1/status", headers=HDR).json()["queue_length"] == 1
    assert client.get(url + "/transcript?format=pdf", headers=HDR).status_code == 422


@needs_ffmpeg
def test_worker_processes_automatically_after_stop_and_recovers_on_restart(fake_whispercpp, tmp_path, monkeypatch, cfg_path):
    p = write_cfg(tmp_path, {"processing": {"enabled": True}})
    monkeypatch.setenv("MEETLOCALAI_CONFIG", str(p))
    # riunione chiusa ma non elaborata, lasciata da un "processo precedente"
    with TestClient(create_app(config_mod.load() | {"processing": {"enabled": False}}), base_url=BASE) as c:
        md = c.post("/api/v1/meetings", headers=HDR, json={"title": "Auto"}).json()
        folder = config_mod.data_dirs(config_mod.load())["meetings_dir"] / md["id"]
        make_webm(folder / "raw" / "tab.webm", 3.0)
        c.post(f"/api/v1/meetings/{md['id']}/stop", headers=HDR, json={})
    with TestClient(create_app(config_mod.load()), base_url=BASE) as c:
        for _ in range(100):
            st = json.loads((folder / "metadata.json").read_text())["status"]
            if st in ("transcribed", "error"):
                break
            time.sleep(0.1)
        assert st == "transcribed"


def test_drop_repeats_limits_loops():
    segs = [Segment(i, i + 1, "Grazie.") for i in range(10)] + [Segment(20, 21, "Fine."), Segment(22, 23, "Grazie.")]
    out = processing.drop_repeats(segs)
    assert [s.text for s in out] == ["Grazie.", "Grazie.", "Fine.", "Grazie."]


@needs_ffmpeg
def test_silent_track_is_skipped_with_warning(fake_whispercpp, client):
    md = client.post("/api/v1/meetings", headers=HDR, json={"title": "Muta", "tracks": ["tab", "mic"]}).json()
    folder = config_mod.data_dirs(config_mod.load())["meetings_dir"] / md["id"]
    make_webm(folder / "raw" / "tab.webm", 3.0, silent=True)
    make_webm(folder / "raw" / "mic.webm", 3.0, 880)
    client.post(f"/api/v1/meetings/{md['id']}/stop", headers=HDR, json={})
    out = client.app.state.processor.process(md["id"])
    assert out["status"] == "transcribed"
    assert out["warnings"] == ['Traccia "Partecipanti" muta: non trascritta.']
    txt = (folder / "transcript.txt").read_text()
    assert "Partecipanti:" not in txt and "Microfono locale:" in txt
