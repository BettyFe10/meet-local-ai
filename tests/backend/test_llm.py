import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from meetlocalai import bench_llm, health, llm, summary_prompt


class FakeOllama(BaseHTTPRequestHandler):
    reject_think = False
    calls: list = []

    def log_message(self, *a):
        pass

    def _send(self, code, obj):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/api/version":
            return self._send(200, {"version": "0.0-test"})
        if self.path == "/api/tags":
            return self._send(200, {"models": [{"name": "qwen3:8b"}]})
        if self.path == "/api/ps":
            return self._send(200, {"models": [{"name": "qwen3:8b", "size": 6 * 1024**3, "size_vram": 6 * 1024**3}]})
        self._send(404, {"error": "not found"})

    def do_POST(self):
        p = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        FakeOllama.calls.append(p)
        if self.path == "/api/chat":
            if p["model"] == "missing:1b":
                return self._send(404, {"error": "model not found"})
            if FakeOllama.reject_think and "think" in p:
                return self._send(400, {"error": "model does not support thinking"})
            return self._send(200, {"message": {"content": "<think>ragiono</think>## TL;DR\n- ok"},
                                    "total_duration": 3e9, "load_duration": 1e9, "prompt_eval_count": 500,
                                    "prompt_eval_duration": 0.5e9, "eval_count": 100, "eval_duration": 2e9})
        self._send(404, {"error": "?"})


@pytest.fixture
def ollama(tmp_path):
    FakeOllama.calls = []
    FakeOllama.reject_think = False
    srv = HTTPServer(("127.0.0.1", 0), FakeOllama)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    yield llm.OllamaClient(f"http://127.0.0.1:{srv.server_port}", tmp_path)
    srv.shutdown()


def test_rejects_non_local_host(tmp_path):
    with pytest.raises(llm.LLMError):
        llm.OllamaClient("http://example.com:11434", tmp_path)


@pytest.mark.parametrize("name", ["gemma4:cloud", "gpt-oss:120b-cloud", "qwen3-cloud:latest"])
def test_cloud_models_are_refused(ollama, name):
    assert llm.is_cloud_model(name)
    with pytest.raises(llm.LLMError, match="solo modelli locali"):
        ollama.chat(name, "s", "u")
    assert FakeOllama.calls == []


def test_local_model_names_are_not_cloud():
    for n in ["qwen3:8b", "gemma4:12b", "gemma4:e4b", "qwen3:4b"]:
        assert not llm.is_cloud_model(n)


def test_chat_strips_thinking_and_reports_stats(ollama):
    r = ollama.chat("qwen3:8b", "sys", "user", num_ctx=4096)
    assert r["content"] == "## TL;DR\n- ok"
    assert r["stats"]["output_tps"] == 50.0 and r["stats"]["prompt_tps"] == 1000.0
    sent = FakeOllama.calls[0]
    assert sent["think"] is False and sent["options"]["num_ctx"] == 4096 and sent["stream"] is False


def test_chat_retries_without_think_param(ollama):
    FakeOllama.reject_think = True
    assert ollama.chat("gemma4:12b", "s", "u")["content"]
    assert "think" not in FakeOllama.calls[-1]


def test_missing_model_gives_user_message(ollama):
    with pytest.raises(llm.LLMError, match="Modello locale non disponibile"):
        ollama.chat("missing:1b", "s", "u")


def test_running_tags_ps(ollama):
    assert ollama.running() and ollama.installed_models() == ["qwen3:8b"]
    assert ollama.loaded_size_mb()["qwen3:8b"]["size_mb"] == 6144


def test_ensure_server_without_ollama_binary(tmp_path, monkeypatch):
    monkeypatch.setattr(health, "which", lambda c: None)
    c = llm.OllamaClient("http://127.0.0.1:9", tmp_path)
    with pytest.raises(llm.LLMError, match="Modello locale non disponibile"):
        c.ensure_server(wait_s=0.5)


def test_recommended_model_by_ram():
    assert llm.recommended_model(32) == "gemma4:12b"
    assert llm.recommended_model(16) == "gemma4:e4b"      # il Mac di sviluppo e quello del collega (16 GB)
    assert llm.recommended_model(8) == "gemma4:e2b"
    assert all(not llm.is_cloud_model(m) for _, m in llm.RAM_TIERS)


def test_resolve_model_auto_and_explicit(monkeypatch):
    monkeypatch.setattr(llm, "system_ram_gb", lambda: 16.0)
    assert llm.resolve_model({"llm": {"model": "auto"}}) == "gemma4:e4b"
    assert llm.resolve_model({"llm": {"model": ""}}) == "gemma4:e4b"
    assert llm.resolve_model({"llm": {"model": "gemma4:12b"}}) == "gemma4:12b"


def test_model_on_disk_and_health(tmp_path, monkeypatch):
    assert not llm.model_on_disk(tmp_path, "gemma4:e4b")
    m = tmp_path / "ollama" / "manifests" / "registry.ollama.ai" / "library" / "gemma4"
    m.mkdir(parents=True)
    (m / "e4b").write_text("{}")
    assert llm.model_on_disk(tmp_path, "gemma4:e4b") and not llm.model_on_disk(tmp_path, "gemma4:12b")
    monkeypatch.setattr(llm, "system_ram_gb", lambda: 16.0)
    monkeypatch.setattr(health, "which", lambda c: "/x/ollama" if c == "ollama" else None)
    h = health.check_llm({"llm": {"model": "auto"}}, tmp_path)
    assert h["available"] and h["model"] == "gemma4:e4b"
    monkeypatch.setattr(health, "which", lambda c: None)
    assert not health.check_llm({"llm": {"model": "auto"}}, tmp_path)["available"]


def test_prompt_contains_rules_and_sections():
    for s in bench_llm.SECTIONS:
        assert f"## {s}" in summary_prompt.SYSTEM
    assert summary_prompt.ND in summary_prompt.SYSTEM and "Non inventare" in summary_prompt.SYSTEM


def test_auto_checks_on_good_and_bad_summary():
    good = """## TL;DR\n- x\n## DECISIONI\n- Lancio spostato al 22 ottobre\n- Budget social 4.000 euro\n- Non rinnovare l'agenzia\n- TikTok: rimandato a gennaio
## ACTION ITEMS\n- Descrizione video maker — Responsabile: Giulia — Scadenza: venerdì prossimo
## PROBLEMI / CRITICITÀ\n## INFORMAZIONI IMPORTANTI\n## DOMANDE APERTE\n## PROSSIMI PASSI\n"""
    c = bench_llm.auto_checks(good)
    assert c["sezioni_presenti"] == 7 and c["decisione_22_ottobre"] and c["decisione_budget_4000"]
    assert c["giulia_venerdi"] and not c["tiktok_tra_le_decisioni"]
    bad = good.replace("- TikTok: rimandato a gennaio", "- Aprire il profilo TikTok")
    assert bench_llm.auto_checks(bad)["tiktok_tra_le_decisioni"]


def test_fixture_exists_and_has_expected():
    assert bench_llm.FIXTURE.exists()
    exp = json.loads(bench_llm.FIXTURE.with_suffix(".expected.json").read_text())
    assert len(exp["decisioni_attese"]) == 4


# ---------- Ollama già presente sul Mac (modelli nella cartella standard) ----------
def _manifest(store, model="gemma4:12b"):
    name, tag = model.split(":")
    p = store / "manifests" / "registry.ollama.ai" / "library" / name
    p.mkdir(parents=True)
    (p / tag).write_text("{}")


def test_model_found_in_standard_ollama_dir(tmp_path, monkeypatch):
    std = tmp_path / "std"
    monkeypatch.setenv("OLLAMA_MODELS", str(std))
    models = tmp_path / "Models"
    assert llm.model_on_disk(models, "gemma4:12b") is False
    _manifest(std)
    assert llm.model_on_disk(models, "gemma4:12b") is True
    assert llm.find_model_store(models, "gemma4:12b") == std
    assert llm.model_on_disk(models, "gemma4:e4b") is False
    assert llm.server_store(models) == std                     # cartella del progetto vuota → si usa quella standard


def test_project_dir_wins_when_it_has_models(tmp_path, monkeypatch):
    std = tmp_path / "std"
    monkeypatch.setenv("OLLAMA_MODELS", str(std))
    models = tmp_path / "Models"
    _manifest(std)
    _manifest(models / "ollama", "gemma4:e4b")
    assert llm.server_store(models) == models / "ollama"
    assert llm.find_model_store(models, "gemma4:e4b") == models / "ollama"
    assert llm.server_store(tmp_path / "vuoto" ) == std
    monkeypatch.setenv("OLLAMA_MODELS", str(tmp_path / "niente"))
    assert llm.server_store(tmp_path / "vuoto") == tmp_path / "vuoto" / "ollama"
