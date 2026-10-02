import json

from meetlocalai import config as config_mod, llm

from .conftest import HDR


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
