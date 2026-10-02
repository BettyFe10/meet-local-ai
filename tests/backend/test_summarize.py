import json

import pytest

from meetlocalai import config as config_mod, health, llm, summarize, summary_prompt as sp

from .conftest import HDR
from .test_audio_whisper import fake_whispercpp, make_webm, needs_ffmpeg  # noqa: F401

GOOD = "\n".join(f"## {s}\n- punto {i}" for i, s in enumerate(sp.SECTIONS))


class FakeClient:
    """Sostituisce OllamaClient: risponde con una sequenza di testi e registra le chiamate."""

    def __init__(self, replies):
        self.replies, self.calls, self.started, self.stopped = list(replies), [], 0, 0

    def ensure_server(self):
        self.started += 1

    def stop_server(self):
        self.stopped += 1

    def chat(self, model, system, user, *, num_ctx=8192, temperature=0.2, timeout=0):
        self.calls.append({"model": model, "system": system, "user": user, "num_ctx": num_ctx})
        r = self.replies.pop(0) if self.replies else GOOD
        if isinstance(r, Exception):
            raise r
        return {"content": r, "stats": {"output_tokens": 10}}


def test_parse_sections_is_tolerant():
    md = "Ecco il verbale:\n### **TL;DR**\n- a\n## decisioni:\n- b\n## Action Items\n- c\n"
    s = summarize.parse_sections(md)
    assert s["TL;DR"] == "- a" and s["DECISIONI"] == "- b" and s["ACTION ITEMS"] == "- c"


def test_normalize_orders_fills_and_strips_preamble():
    md = "Certo! Ecco:\n## DECISIONI\n- x\n## TL;DR\n- y\n"
    out = summarize.normalize(md)
    assert out.startswith("## TL;DR\n- y\n\n## DECISIONI\n- x")
    assert "Certo" not in out
    assert out.count(sp.ND) == 5 and all(f"## {s}" in out for s in sp.SECTIONS)


def test_normalize_collapses_sections_that_only_say_not_determinable():
    nd = sp.ND
    md = (f"## TL;DR\n- ok\n## ACTION ITEMS\n- {nd} — Responsabile: {nd} — Scadenza: {nd}\n"
          f"## DOMANDE APERTE\n* {nd}\n## DECISIONI\n- Fare X — Responsabile: {nd}\n")
    secs = summarize.parse_sections(summarize.normalize(md))
    assert secs["ACTION ITEMS"] == nd and secs["DOMANDE APERTE"] == nd
    assert secs["DECISIONI"].startswith("- Fare X")


def test_single_pass_for_normal_meeting():
    c = FakeClient([GOOD])
    r = summarize.summarize(c, "gemma4:e4b", "T", "[00:00:01] Microfono locale:\nCiao a tutti.", two_pass=False)
    assert r["stats"]["mode"] == "single" and r["stats"]["calls"] == 1 and r["stats"]["retries"] == 0
    assert c.calls[0]["system"] == sp.SYSTEM and c.calls[0]["num_ctx"] == 4096
    assert list(r["sections"]) == sp.SECTIONS


def test_invalid_output_is_retried_once_then_accepted():
    c = FakeClient(["Okay, let's tackle this. First I need to...", GOOD])
    r = summarize.summarize(c, "m", "T", "testo", two_pass=False)
    assert r["stats"]["retries"] == 1 and len(c.calls) == 2
    assert "ATTENZIONE" in c.calls[1]["user"]


def test_invalid_twice_raises():
    c = FakeClient(["boh", "ancora boh"])
    with pytest.raises(summarize.SummaryError, match="verbale valido"):
        summarize.summarize(c, "m", "T", "testo", two_pass=False)


def test_two_pass_is_default_for_normal_meetings():
    c = FakeClient(["### Impegni presi\n- Microfono locale comunica alla direzione", GOOD])
    r = summarize.summarize(c, "m", "T", "[00:00:01] Microfono locale:\nLo comunico io alla direzione.")
    assert r["stats"]["mode"] == "two_pass" and r["stats"]["calls"] == 2 and r["stats"]["blocks"] == 1
    assert c.calls[0]["system"] == sp.SYSTEM_CHUNK and c.calls[1]["system"] == sp.SYSTEM_MERGE
    assert "comunica alla direzione" in c.calls[1]["user"]            # gli appunti arrivano al secondo passaggio
    assert "Lo comunico io" not in c.calls[1]["user"]                 # ...al posto della trascrizione


def test_empty_transcript_raises():
    with pytest.raises(summarize.SummaryError):
        summarize.summarize(FakeClient([]), "m", "T", "   ")


def test_long_meeting_uses_blocks_then_merge():
    para = "[00:00:01] Partecipanti:\n" + ("Parliamo del budget e delle scadenze del progetto. " * 40)
    transcript = "\n\n".join([para] * 40)      # ~80k caratteri ≈ 29k token stimati
    assert summarize.estimate_tokens(transcript) > summarize.SINGLE_PASS_MAX_TOKENS
    c = FakeClient(["### Decisioni\n- nota"] * 10 + [GOOD])
    blocks = summarize.split_blocks(transcript)
    c.replies = ["### Decisioni\n- nota"] * len(blocks) + [GOOD]
    r = summarize.summarize(c, "m", "T", transcript)
    assert r["stats"]["mode"] == "blocks" and r["stats"]["blocks"] == len(blocks) >= 3
    assert r["stats"]["calls"] == len(blocks) + 1
    assert all(call["system"] == sp.SYSTEM_CHUNK for call in c.calls[:-1]) and c.calls[-1]["system"] == sp.SYSTEM_MERGE
    assert all(summarize.estimate_tokens(b) <= summarize.CHUNK_TOKENS for b in blocks)
    assert "".join(blocks).count("Partecipanti:") == 40          # nessun intervento perso


def test_split_handles_single_huge_paragraph():
    blocks = summarize.split_blocks("Frase molto lunga. " * 5000, max_tokens=1000)
    assert len(blocks) > 5 and all(summarize.estimate_tokens(b) <= 1100 for b in blocks)


def test_prompt_v2_rules():
    assert "prima persona" in sp.SYSTEM and "Microfono locale (chi ha registrato)" in sp.SYSTEM
    assert sp.PROMPT_VERSION == "v3" and "Responsabile: <chi>" in sp.SYSTEM_MERGE
    for s in sp.SECTIONS:
        assert f"## {s}" in sp.SYSTEM and f"## {s}" in sp.SYSTEM_MERGE


# ---------- pipeline ----------
@pytest.fixture
def llm_ready(monkeypatch):
    monkeypatch.setattr(health, "check_llm", lambda cfg, d: {"available": True, "model": "gemma4:e4b"})
    monkeypatch.setattr(llm, "resolve_model", lambda cfg: "gemma4:e4b")


def _transcribed_meeting(client, fake=True):
    md = client.post("/api/v1/meetings", headers=HDR, json={"title": "Sintesi", "tracks": ["tab"]}).json()
    folder = config_mod.data_dirs(config_mod.load())["meetings_dir"] / md["id"]
    make_webm(folder / "raw" / "tab.webm", 3.0)
    client.post(f"/api/v1/meetings/{md['id']}/stop", headers=HDR, json={})
    return md["id"], folder


@needs_ffmpeg
def test_pipeline_reaches_completed_with_summary(fake_whispercpp, client, llm_ready):
    mid, folder = _transcribed_meeting(client)
    fc = FakeClient([GOOD])
    client.app.state.processor.llm_client_factory = lambda: fc
    md = client.app.state.processor.process(mid)
    assert md["status"] == "completed", md
    assert md["files"]["summary_md"] == "summary.md" and md["llm"]["model"] == "gemma4:e4b"
    assert md["performance"]["summary_seconds"] >= 0 and md["summary"]["prompt_version"] == "v3"
    text = (folder / "summary.md").read_text()
    assert text.startswith("# RIUNIONE — Sintesi") and "## TL;DR" in text and "verificare i punti importanti" in text
    assert fc.started == 1 and fc.stopped == 1                       # Ollama acceso solo per la sintesi
    assert "Buongiorno" in fc.calls[0]["user"]                        # la trascrizione arriva al modello locale
    r = client.get(f"/api/v1/meetings/{mid}/summary", headers=HDR).json()
    assert list(r["sections"]) == sp.SECTIONS and r["model"] == "gemma4:e4b"
    log = (config_mod.data_dirs(config_mod.load())["logs_dir"] / "backend.log").read_text()
    assert "Buongiorno" not in log and "punto 1" not in log           # né trascrizione né sintesi nei log


@needs_ffmpeg
def test_llm_missing_keeps_transcript_with_warning(fake_whispercpp, client):
    mid, folder = _transcribed_meeting(client)
    md = client.app.state.processor.process(mid)
    assert md["status"] == "transcribed"
    assert md["warnings"] == ["Sintesi non generata: Modello locale non disponibile."]
    assert (folder / "transcript.txt").exists() and not (folder / "summary.md").exists()
    assert client.get(f"/api/v1/meetings/{mid}/summary", headers=HDR).status_code == 404


@needs_ffmpeg
def test_llm_error_keeps_transcript_then_summary_only_reprocess_works(fake_whispercpp, client, llm_ready):
    mid, folder = _transcribed_meeting(client)
    proc = client.app.state.processor
    bad = FakeClient([llm.LLMError("Errore del modello locale.", "boom")])
    proc.llm_client_factory = lambda: bad
    md = proc.process(mid)
    assert md["status"] == "transcribed" and md["warnings"] == ["Sintesi non generata: Errore del modello locale."]
    assert bad.stopped == 1                                           # server fermato anche in caso di errore
    # rifaccio solo la sintesi
    r = client.post(f"/api/v1/meetings/{mid}/reprocess", headers=HDR, json={"steps": ["summarize"]})
    assert r.status_code == 200          # (nei test la coda non viene consumata: lancio a mano qui sotto)
    good = FakeClient([GOOD])
    proc.llm_client_factory = lambda: good
    mtime = (folder / "transcript.txt").stat().st_mtime_ns
    md = proc.process(mid, "summary")
    assert md["status"] == "completed" and md["warnings"] == []
    assert (folder / "transcript.txt").stat().st_mtime_ns == mtime     # trascrizione non rifatta


def test_summary_only_reprocess_requires_transcript(client):
    md = client.post("/api/v1/meetings", headers=HDR, json={"title": "X"}).json()
    client.post(f"/api/v1/meetings/{md['id']}/stop", headers=HDR, json={})
    r = client.post(f"/api/v1/meetings/{md['id']}/reprocess", headers=HDR, json={"steps": ["summarize"]})
    assert r.status_code == 409 and r.json()["error_code"] == "transcript_not_ready"
