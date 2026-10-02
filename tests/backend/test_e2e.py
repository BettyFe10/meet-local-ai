"""Flusso completo attraverso l'API: registra → blocchi → stop → trascrizione → sintesi → export → elimina.
Whisper e LLM sono sostituiti da finti; FFmpeg è reale."""

import json
import logging
from pathlib import Path

import jsonschema
import pytest

from meetlocalai import config as config_mod, logging_setup, messages

from .conftest import HDR
from .test_audio_whisper import fake_whispercpp, make_webm, needs_ffmpeg  # noqa: F401 (fixture)
from .test_summarize import GOOD, FakeClient, llm_ready  # noqa: F401 (fixture)

REPO = Path(__file__).resolve().parents[2]
SCHEMA = json.loads((REPO / "docs" / "metadata.schema.json").read_text(encoding="utf-8"))
TITLE = "Budget riservato Zanzibar"


def check_schema(md):
    jsonschema.validate(md, SCHEMA)


def test_metadata_example_matches_schema():
    check_schema(json.loads((REPO / "docs" / "metadata.example.json").read_text(encoding="utf-8")))


@needs_ffmpeg
def test_end_to_end(fake_whispercpp, client, llm_ready, tmp_path):
    dirs = config_mod.data_dirs(config_mod.load())
    api = "/api/v1"
    # 1. avvio
    md = client.post(f"{api}/meetings", headers=HDR, json={"title": TITLE, "meet_code": "abc-defg-hij", "tracks": ["tab", "mic"]}).json()
    mid = md["id"]
    check_schema(md)
    assert md["status"] == "recording" and client.get(f"{api}/status", headers=HDR).json()["recording"]["id"] == mid
    # una sola registrazione alla volta
    assert client.post(f"{api}/meetings", headers=HDR, json={"tracks": ["tab"]}).status_code == 409
    # 2. blocchi audio veri (webm spezzato in due), con un duplicato e un buco
    for track, freq in (("tab", 440), ("mic", 880)):
        src = tmp_path / f"{track}.webm"
        make_webm(src, 4.0, freq)
        data = src.read_bytes()
        half = len(data) // 2
        bh = {**HDR, "Content-Type": "audio/webm"}
        assert client.post(f"{api}/meetings/{mid}/chunks?track={track}&seq=0", headers=bh, content=data[:half]).status_code == 200
        assert client.post(f"{api}/meetings/{mid}/chunks?track={track}&seq=0", headers=bh, content=data[:half]).status_code == 200  # duplicato ignorato
        gap = client.post(f"{api}/meetings/{mid}/chunks?track={track}&seq=5", headers=bh, content=b"x")
        assert gap.status_code == 409 and gap.json()["next_seq"] == 1
        assert client.post(f"{api}/meetings/{mid}/chunks?track={track}&seq=1", headers=bh, content=data[half:]).status_code == 200
        assert (dirs["meetings_dir"] / mid / "raw" / f"{track}.webm").read_bytes() == data
    # non si elimina durante la registrazione
    assert client.delete(f"{api}/meetings/{mid}", headers=HDR).status_code == 409
    # 3. stop
    md = client.post(f"{api}/meetings/{mid}/stop", headers=HDR, json={"client_duration_seconds": 4}).json()
    assert md["status"] == "stopped"
    check_schema(md)
    # 4. elaborazione
    fc = FakeClient([GOOD, GOOD])
    client.app.state.processor.llm_client_factory = lambda: fc
    md = client.app.state.processor.process(mid)
    assert md["status"] == "completed", md.get("error")
    check_schema(md)
    folder = dirs["meetings_dir"] / mid
    assert json.loads((folder / "metadata.json").read_text(encoding="utf-8")) == md
    for f in ("audio.wav", "transcript.txt", "transcript.md", "transcript.json", "summary.md"):
        assert (folder / f).stat().st_size > 0, f
    perf = md["performance"]
    for k in ("conversion_seconds", "transcription_seconds", "realtime_factor", "summary_seconds", "disk_bytes"):
        assert isinstance(perf.get(k), (int, float)), k
    # 5. lettura
    lst = client.get(f"{api}/meetings", headers=HDR).json()
    item = next(m for m in lst["meetings"] if m["id"] == mid)
    assert item["has_transcript"] and item["has_summary"] and item["title"] == TITLE
    summ = client.get(f"{api}/meetings/{mid}/summary", headers=HDR).json()
    assert len(summ["sections"]) == 7
    tr = client.get(f"{api}/meetings/{mid}/transcript?format=txt", headers=HDR).text
    assert "Partecipanti:" in tr and "Microfono locale:" in tr
    # 6. export
    ex = client.get(f"{api}/meetings/{mid}/export?format=md", headers=HDR)
    assert ex.status_code == 200 and TITLE in ex.text and "TL;DR" in ex.text and "Partecipanti" in ex.text
    assert any(dirs["exports_dir"].glob("*.md"))
    # 7. i log non contengono né il titolo né il testo della riunione
    log = (dirs["logs_dir"] / "backend.log").read_text(encoding="utf-8")
    assert mid.split("_", 2)[0] in log                      # la riunione compare (per ID)…
    for secret in (TITLE, "Buongiorno", "abc-defg-hij"):
        assert secret not in log, secret
    for line in (folder / "summary.md").read_text(encoding="utf-8").splitlines():
        if len(line) > 25 and not line.startswith("#"):
            assert line.strip("- ") not in log
    # 8. elimina (Cestino simulato → cartella interna)
    r = client.delete(f"{api}/meetings/{mid}", headers=HDR)
    assert r.status_code == 200 and not folder.exists()
    assert client.get(f"{api}/meetings/{mid}", headers=HDR).status_code == 404
    assert all(m["id"] != mid for m in client.get(f"{api}/meetings", headers=HDR).json()["meetings"])


def test_fixed_user_messages():
    assert messages.BACKEND_OFFLINE == "Backend offline."
    assert messages.WHISPER_UNAVAILABLE == "Whisper locale non disponibile."
    assert messages.LLM_UNAVAILABLE == "Modello locale non disponibile."
    ext = "".join(p.read_text(encoding="utf-8") for p in (REPO / "extension").rglob("*.js"))
    assert "Backend offline." in ext


def test_errors_never_leak_details(client):
    r = client.get("/api/v1/meetings/../../etc/passwd", headers=HDR)
    assert r.status_code in (400, 404)
    r = client.get("/api/v1/meetings/2026-01-01_10-00_Inesistente", headers=HDR)
    assert r.status_code == 404 and r.json()["user_message"].endswith("non trovata.")
    r = client.post("/api/v1/meetings", headers=HDR, content=b"{non json", )
    assert r.status_code in (400, 422) and "Traceback" not in r.text
    assert client.get("/api/v1/health").status_code == 403           # senza header


def test_log_rotation(tmp_path):
    cfg = {"paths": {k: str(tmp_path / k) for k in ("data_root", "meetings_dir", "models_dir", "logs_dir", "exports_dir", "temp_dir")},
           "logging": {"level": "INFO", "max_bytes": 2000, "backup_count": 2}}
    root = logging_setup.setup(cfg)
    try:
        lg = logging.getLogger("meetlocalai.rotazione")
        for i in range(400):
            lg.info("riga di prova numero %04d ........................................", i)
        logs = sorted(p.name for p in (tmp_path / "logs_dir").iterdir())
        assert logs == ["backend.log", "backend.log.1", "backend.log.2"]
        assert all((tmp_path / "logs_dir" / n).stat().st_size <= 2200 for n in logs)
    finally:
        for h in list(root.handlers):
            if getattr(h, "baseFilename", "").startswith(str(tmp_path)):
                root.removeHandler(h)
                h.close()
