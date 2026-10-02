"""LLM locale tramite Ollama (solo su questo computer).

Garanzie:
- l'indirizzo di Ollama deve essere loopback (validato anche nel config);
- i modelli "cloud" di Ollama (che girerebbero su server esterni) sono rifiutati;
- se Ollama non è già in esecuzione, il backend avvia `ollama serve` solo per il tempo della sintesi
  e poi lo ferma: nessun processo resta acceso inutilmente;
- i modelli stanno in <models_dir>/ollama (OLLAMA_MODELS), copiabili/rimovibili con il resto dei dati.
"""

from __future__ import annotations

import json
import logging
import os
import re
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import urlparse

from . import health

log = logging.getLogger("meetlocalai.llm")

# Modelli consigliati per fascia di RAM (D-019). Valori confermati/aggiornati dal benchmark di Fase 9.
RAM_TIERS = [  # (RAM minima in GB, modello) — vedi DECISIONS D-037 e TEST_RESULTS (benchmark Fase 9)
    (24, "gemma4:12b"),   # qualità migliore nel benchmark, ma più lento e pesante
    (12, "gemma4:e4b"),   # riferimento per i Mac da 16 GB: veloce, nessuna invenzione nel benchmark
    (0, "gemma4:e2b"),    # Mac da 8 GB — NON TESTATO
]
_CLOUD_RE = re.compile(r"(^|[:\-_])cloud($|[:\-_])", re.IGNORECASE)


class LLMError(Exception):
    def __init__(self, user_message: str, detail: str = ""):
        super().__init__(user_message)
        self.user_message = user_message
        self.detail = detail


def is_cloud_model(name: str) -> bool:
    return bool(_CLOUD_RE.search(name or ""))


def recommended_model(ram_gb: float) -> str:
    for min_gb, model in RAM_TIERS:
        if ram_gb >= min_gb:
            return model
    return RAM_TIERS[-1][1]


def resolve_model(cfg: dict) -> str:
    """Modello configurato, oppure ("auto"/vuoto) quello consigliato per la RAM di questo Mac."""
    m = (cfg.get("llm", {}).get("model") or "auto").strip()
    return recommended_model(system_ram_gb()) if m == "auto" else m


def model_on_disk(models_dir: Path, model: str) -> bool:
    """Verifica senza avviare Ollama: esiste il manifest del modello in <models_dir>/ollama."""
    name, _, tag = model.partition(":")
    return (models_dir / "ollama" / "manifests" / "registry.ollama.ai" / "library" / name / (tag or "latest")).exists()


def ollama_rss_mb() -> int:
    """Memoria residente totale dei processi Ollama (server + runner del modello), in MB."""
    try:
        out = subprocess.run(["ps", "-axo", "rss=,command="], capture_output=True, text=True, timeout=5).stdout
        return round(sum(int(l.split(None, 1)[0]) for l in out.splitlines() if "ollama" in l.lower()) / 1024)
    except Exception:  # noqa: BLE001
        return 0


def system_ram_gb() -> float:
    try:
        if os.uname().sysname == "Darwin":
            out = subprocess.run(["sysctl", "-n", "hw.memsize"], capture_output=True, text=True, timeout=5).stdout
            return int(out.strip()) / 1024**3
        with open("/proc/meminfo") as f:
            return int(f.readline().split()[1]) / 1024**2
    except Exception:  # noqa: BLE001
        return 0.0


class OllamaClient:
    def __init__(self, base_url: str, models_dir: Path, keep_alive: str = "30s"):
        host = urlparse(base_url).hostname
        if host not in ("127.0.0.1", "localhost", "::1"):
            raise LLMError("Configurazione LLM non valida.", f"host non locale: {host}")
        self.base = base_url.rstrip("/")
        self.models_dir = models_dir
        self.keep_alive = keep_alive
        self._proc: subprocess.Popen | None = None

    # ---------- HTTP ----------
    def _req(self, path: str, payload: dict | None = None, timeout: float = 5.0) -> dict:
        data = json.dumps(payload).encode() if payload is not None else None
        req = urllib.request.Request(self.base + path, data=data, method="POST" if data else "GET",
                                     headers={"Content-Type": "application/json"} if data else {})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8"))

    def running(self) -> bool:
        try:
            self._req("/api/version", timeout=1.5)
            return True
        except Exception:  # noqa: BLE001
            return False

    def installed_models(self) -> list[str]:
        try:
            return [m["name"] for m in self._req("/api/tags").get("models", [])]
        except Exception:  # noqa: BLE001
            return []

    # ---------- ciclo di vita del server ----------
    def ensure_server(self, wait_s: float = 20.0) -> None:
        if self.running():
            return
        binary = health.which("ollama")
        if not binary:
            raise LLMError("Modello locale non disponibile.", "ollama non installato")
        env = {**os.environ, "OLLAMA_HOST": urlparse(self.base).netloc,
               "OLLAMA_MODELS": str(self.models_dir / "ollama"), "OLLAMA_KEEP_ALIVE": self.keep_alive}
        (self.models_dir / "ollama").mkdir(parents=True, exist_ok=True)
        self._proc = subprocess.Popen([binary, "serve"], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        deadline = time.time() + wait_s
        while time.time() < deadline:
            if self.running():
                log.info("ollama serve avviato su richiesta (PID %s)", self._proc.pid)
                return
            time.sleep(0.3)
        self.stop_server()
        raise LLMError("Modello locale non disponibile.", "ollama serve non risponde")

    def stop_server(self) -> None:
        """Ferma solo il server avviato da noi (non un Ollama già in uso dall'utente)."""
        if self._proc and self._proc.poll() is None:
            self._proc.terminate()
            try:
                self._proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self._proc.kill()
            log.info("ollama serve fermato")
        self._proc = None

    # ---------- generazione ----------
    def chat(self, model: str, system: str, user: str, *, num_ctx: int = 8192, temperature: float = 0.2,
             timeout: float = 1800.0) -> dict:
        if is_cloud_model(model):
            raise LLMError("Modello non consentito: solo modelli locali.", f"modello cloud rifiutato: {model}")
        payload = {
            "model": model, "stream": False, "think": False, "keep_alive": self.keep_alive,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "options": {"temperature": temperature, "num_ctx": num_ctx},
        }
        try:
            r = self._req("/api/chat", payload, timeout=timeout)
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", "replace")[:300]
            if "think" in body.lower():  # modello senza supporto al parametro "think"
                payload.pop("think")
                r = self._req("/api/chat", payload, timeout=timeout)
            elif e.code == 404:
                raise LLMError("Modello locale non disponibile.", f"modello non scaricato: {model}") from e
            else:
                raise LLMError("Errore del modello locale.", body) from e
        except (urllib.error.URLError, TimeoutError) as e:
            raise LLMError("Modello locale non disponibile.", str(e)) from e
        content = r.get("message", {}).get("content", "")
        content = re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL).strip()
        ns = 1e9
        stats = {
            "total_s": round(r.get("total_duration", 0) / ns, 2),
            "load_s": round(r.get("load_duration", 0) / ns, 2),
            "prompt_tokens": r.get("prompt_eval_count"),
            "prompt_tps": round(r["prompt_eval_count"] / (r["prompt_eval_duration"] / ns), 1) if r.get("prompt_eval_duration") else None,
            "output_tokens": r.get("eval_count"),
            "output_tps": round(r["eval_count"] / (r["eval_duration"] / ns), 1) if r.get("eval_duration") else None,
        }
        return {"content": content, "stats": stats}

    def pull(self, model: str, timeout: float = 7200.0) -> None:
        """Scarica un modello (unica operazione che usa la rete, solo in installazione)."""
        if is_cloud_model(model):
            raise LLMError("Modello non consentito: solo modelli locali.", model)
        r = self._req("/api/pull", {"model": model, "stream": False}, timeout=timeout)
        if r.get("status") != "success":
            raise LLMError("Download del modello non riuscito.", str(r)[:300])

    def delete(self, model: str) -> None:
        req = urllib.request.Request(self.base + "/api/delete", data=json.dumps({"model": model}).encode(),
                                     headers={"Content-Type": "application/json"}, method="DELETE")
        urllib.request.urlopen(req, timeout=60).read()

    def loaded_size_mb(self) -> dict:
        try:
            ps = self._req("/api/ps").get("models", [])
            return {m["name"]: {"size_mb": round(m.get("size", 0) / 1024**2), "vram_mb": round(m.get("size_vram", 0) / 1024**2)} for m in ps}
        except Exception:  # noqa: BLE001
            return {}


def main(argv: list[str]) -> int:
    """python -m meetlocalai.llm install [modello] | which | measure"""
    import sys  # noqa: PLC0415

    from . import config as config_mod, summary_prompt  # noqa: PLC0415

    cfg = config_mod.load()
    dirs = config_mod.data_dirs(cfg)
    cmd = argv[0] if argv else "which"
    model = argv[1] if len(argv) > 1 else resolve_model(cfg)
    if cmd == "which":
        print(model)
        return 0
    client = OllamaClient(cfg["llm"]["base_url"], dirs["models_dir"], keep_alive="1m")
    try:
        client.ensure_server()
        if cmd == "install":
            if model in client.installed_models():
                print(f"Modello già presente: {model}")
            else:
                print(f"Scarico {model} in {dirs['models_dir'] / 'ollama'} …", flush=True)
                client.pull(model)
            r = client.chat(model, "Rispondi solo con: OK", "Test", num_ctx=2048)
            print(f"Modello pronto: {model} (risposta di prova in {r['stats']['total_s']} s)")
            return 0
        if cmd == "measure":
            fixture = (paths_fixture()).read_text(encoding="utf-8")
            for label, text, ctx in (("breve", fixture, 8192), ("lungo", "\n".join([fixture] * 8), 16384)):
                r = client.chat(model, summary_prompt.SYSTEM, summary_prompt.user_message("Prova", text), num_ctx=ctx)
                print(f"{model} [{label}]: {r['stats']['total_s']} s, prompt {r['stats']['prompt_tokens']} tok, "
                      f"{r['stats']['output_tps']} tok/s — memoria processi Ollama: {ollama_rss_mb()} MB", flush=True)
            return 0
        print("Uso: python -m meetlocalai.llm install [modello] | which | measure [modello]", file=sys.stderr)
        return 2
    except LLMError as e:
        print(f"{e.user_message} ({e.detail})", file=sys.stderr)
        return 1
    finally:
        client.stop_server()


def paths_fixture() -> Path:
    from . import paths  # noqa: PLC0415
    return paths.REPO_ROOT / "tests" / "fixtures" / "riunione_fittizia_marketing.txt"


if __name__ == "__main__":
    import sys
    sys.exit(main(sys.argv[1:]))
