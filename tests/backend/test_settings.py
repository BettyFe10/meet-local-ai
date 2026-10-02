import json

from meetlocalai import config as config_mod, llm

from .conftest import HDR
from .test_audio_whisper import fake_whispercpp  # noqa: F401 (fixture)


def test_settings_auto_and_max_quality_on_16gb(client, monkeypatch):
    monkeypatch.setattr(llm, "system_ram_gb", lambda: 16.0)
    s = client.get("/api/v1/settings", headers=HDR).json()
    assert s["ram_gb"] == 16.0 and s["llm"]["setting"] == "auto" and s["llm"]["model"] == "gemma4:e4b"
    auto, best = s["llm"]["choices"]
    assert (auto["value"], auto["model"], auto["note"]) == ("auto", "gemma4:e4b", None)
    assert best["value"] == "gemma4:12b" and "più lenta" in best["note"] and best["downloaded"] is False
    assert best["install_command"].endswith("setup_llm.sh gemma4:12b")


def test_on_24gb_auto_is_already_the_best(client, monkeypatch):
    monkeypatch.setattr(llm, "system_ram_gb", lambda: 32.0)
    s = client.get("/api/v1/settings", headers=HDR).json()
    assert [c["value"] for c in s["llm"]["choices"]] == ["auto"] and s["llm"]["model"] == "gemma4:12b"


def test_change_model_is_saved_and_used(client, cfg_path, monkeypatch):
    monkeypatch.setattr(llm, "system_ram_gb", lambda: 16.0)
    before = json.loads(cfg_path.read_text())
    r = client.patch("/api/v1/settings", headers=HDR, json={"llm_model": "gemma4:12b"})
    assert r.status_code == 200 and r.json()["llm"]["model"] == "gemma4:12b"
    saved = json.loads(cfg_path.read_text())
    assert saved["llm"]["model"] == "gemma4:12b" and saved["llm"]["base_url"] == before["llm"]["base_url"]
    assert saved["paths"] == before["paths"]                                  # il resto del config non cambia
    assert llm.resolve_model(client.app.state.processor.cfg) == "gemma4:12b"  # vale dalla prossima sintesi
    assert config_mod.load()["llm"]["model"] == "gemma4:12b"                  # e dopo un riavvio
    assert client.patch("/api/v1/settings", headers=HDR, json={"llm_model": "auto"}).json()["llm"]["model"] == "gemma4:e4b"


def test_invalid_or_cloud_models_are_refused(client, cfg_path):
    before = cfg_path.read_text()
    for bad in ("gpt-4o", "gemma4:12b-cloud", "", None, 5):
        r = client.patch("/api/v1/settings", headers=HDR, json={"llm_model": bad})
        assert r.status_code == 400, bad
    assert cfg_path.read_text() == before
    assert client.patch("/api/v1/settings", json={"llm_model": "auto"}).status_code == 403   # senza header


# ---------- glossario ----------
def test_glossary_saved_cleaned_and_passed_to_whisper(client, cfg_path, fake_whispercpp, tmp_path):
    from meetlocalai import transcribe
    from .test_audio_whisper import make_webm
    r = client.patch("/api/v1/settings", headers=HDR, json={"glossary": ["  WeCanRace ", "wecanrace", "Track, Days", "", "Mugello"]})
    assert r.status_code == 200
    g = r.json()["glossary"]
    assert g["terms"] == ["WeCanRace", "Track Days", "Mugello"] and g["used_terms"] == 3
    saved = json.loads(cfg_path.read_text())
    assert saved["transcription"]["glossary"] == g["terms"] and saved["llm"]["base_url"]      # resto del config intatto
    assert client.get("/api/v1/settings", headers=HDR).json()["llm"]["setting"] == "auto"
    # il motore riceve il suggerimento
    cfg = client.app.state.processor.cfg
    eng = transcribe.select_engine(cfg, config_mod.data_dirs(cfg)["models_dir"])
    assert eng.prompt == "Glossario: WeCanRace, Track Days, Mugello."
    wav = tmp_path / "a.wav"
    wav.write_bytes(b"x")
    eng.transcribe(wav)
    args = (fake_whispercpp.parent / "last_args.txt").read_text()
    assert "--prompt Glossario: WeCanRace, Track Days, Mugello." in args
    # svuotare il glossario toglie il suggerimento
    assert client.patch("/api/v1/settings", headers=HDR, json={"glossary": []}).json()["glossary"]["terms"] == []
    assert transcribe.select_engine(cfg, config_mod.data_dirs(cfg)["models_dir"]).prompt == ""
    # i termini non finiscono nei log
    log = (config_mod.data_dirs(cfg)["logs_dir"] / "backend.log").read_text()
    assert "Mugello" not in log and "Glossario aggiornato: 3 termini" in log


def test_glossary_limits_and_validation(client):
    from meetlocalai import transcribe
    many = [f"Termine numero {i:03d} abbastanza lungo" for i in range(200)]
    g = client.patch("/api/v1/settings", headers=HDR, json={"glossary": many}).json()["glossary"]
    assert len(g["terms"]) == transcribe.GLOSSARY_MAX_TERMS and 0 < g["used_terms"] < len(g["terms"])
    assert len(transcribe.glossary_prompt(many)) <= transcribe.GLOSSARY_PROMPT_MAX_CHARS
    for bad in ("testo", [1, 2], {"a": 1}, ["x"] * 501):
        assert client.patch("/api/v1/settings", headers=HDR, json={"glossary": bad}).status_code == 400
    assert client.patch("/api/v1/settings", headers=HDR, json={}).status_code == 400


def test_whisper_echo_of_glossary_is_dropped(tmp_path, monkeypatch):
    from meetlocalai import transcribe
    data = {"transcription": [{"offsets": {"from": 0, "to": 1000}, "text": " Glossario: Mugello, WeCanRace."},
                              {"offsets": {"from": 1000, "to": 2000}, "text": " Andiamo al Mugello."}]}
    segs = transcribe.parse_whispercpp_json(data)
    kept = [s for s in segs if not s.text.strip().lower().startswith(transcribe.GLOSSARY_PREFIX.strip().lower())]
    assert [s.text for s in kept] == ["Andiamo al Mugello."]
    assert transcribe.glossary_prompt([]) == "" and transcribe.glossary_prompt(None) == ""
