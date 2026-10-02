"""Benchmark dei modelli LLM locali (Ollama) per la sintesi delle riunioni.

  python -m meetlocalai.bench_llm --models qwen3:8b,gemma4:12b [--remove-after] [--meeting ID]

Per ogni modello: download (se manca) → 3 prove → (facoltativo) rimozione, così su disco c'è un solo modello alla volta.
Prove: A) riunione FITTIZIA con verità nota (tests/fixtures), B) una riunione reale trascritta, C) testo lungo
(~10k token) per misurare velocità e memoria. Verbali in <temp_dir>/llm_bench/, numeri in <logs_dir>/llm_benchmark_*.json.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from datetime import datetime

from . import config as config_mod, llm, paths, summary_prompt

FIXTURE = paths.REPO_ROOT / "tests" / "fixtures" / "riunione_fittizia_marketing.txt"
SECTIONS = ["TL;DR", "DECISIONI", "ACTION ITEMS", "PROBLEMI / CRITICITÀ", "INFORMAZIONI IMPORTANTI", "DOMANDE APERTE", "PROSSIMI PASSI"]


def section(md: str, name: str) -> str:
    m = re.search(rf"^##\s*{re.escape(name)}\s*$(.*?)(?=^##\s|\Z)", md, flags=re.M | re.S | re.I)
    return m.group(1).strip() if m else ""


def auto_checks(md: str) -> dict:
    """Controlli automatici sulla riunione fittizia (la valutazione completa resta umana)."""
    dec = section(md, "DECISIONI").lower()
    act = section(md, "ACTION ITEMS").lower()
    names = set(re.findall(r"\b[A-Z][a-zà-ù]{2,}\b", md)) - {
        "Giulia", "Marco", "Genova", "TikTok", "Non", "Microfono", "Partecipanti", "Responsabile", "Scadenza", "Attività",
        "Decisioni", "Problemi", "Informazioni", "Domande", "Prossimi", "Lancio", "Budget", "Il", "La", "Le", "Lo", "Gli",
        "Un", "Una", "Per", "Da", "Dal", "Si", "Se", "Con", "In", "Nessuna", "Riunione", "Campagna", "Ottobre", "Novembre",
        "Dicembre", "Gennaio", "Giovedì", "Venerdì", "Ricapitolando", "Sintesi", "Verbale", "Titolo", "Contratto", "Agenzia"}
    return {
        "sezioni_presenti": sum(1 for s in SECTIONS if re.search(rf"^##\s*{re.escape(s)}\s*$", md, re.M | re.I)),
        "decisione_22_ottobre": "22" in dec,
        "decisione_budget_4000": bool(re.search(r"4[.\s]?000|quattromila", dec)),
        "decisione_agenzia": "agenzia" in dec,
        "tiktok_tra_le_decisioni": "tiktok" in dec and not re.search(r"riman|gennaio|non .*decis", dec),
        "giulia_venerdi": "giulia" in act and "venerd" in act,
        "maiuscole_sospette": sorted(names)[:15],
    }


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="python -m meetlocalai.bench_llm")
    ap.add_argument("--models", required=True)
    ap.add_argument("--meeting", help="riunione reale trascritta da usare per la prova B (default: la più recente)")
    ap.add_argument("--remove-after", action="store_true")
    a = ap.parse_args(argv)

    cfg = config_mod.load()
    dirs = config_mod.data_dirs(cfg)
    client = llm.OllamaClient(cfg["llm"]["base_url"], dirs["models_dir"], keep_alive="2m")
    out_dir = dirs["temp_dir"] / "llm_bench"
    out_dir.mkdir(parents=True, exist_ok=True)

    real = None
    cands = sorted((p for p in dirs["meetings_dir"].glob("*/transcript.txt") if p.stat().st_size > 200),
                   key=lambda p: p.parent.name, reverse=True)
    if a.meeting:
        cands = [dirs["meetings_dir"] / a.meeting / "transcript.txt"]
    if cands and cands[0].exists():
        real = cands[0]
    fixture = FIXTURE.read_text(encoding="utf-8")
    long_text = "\n".join([fixture] * 8)

    client.ensure_server()
    ram = llm.system_ram_gb()
    print(f"RAM del Mac: {ram:.0f} GB — modello consigliato oggi per questa fascia: {llm.recommended_model(ram)}")
    try:
        for model in [m.strip() for m in a.models.split(",") if m.strip()]:
            res = {"model": model, "date": datetime.now().astimezone().isoformat(timespec="seconds"),
                   "ram_gb": round(ram), "prompt_version": summary_prompt.PROMPT_VERSION}
            safe = re.sub(r"[^A-Za-z0-9._-]", "_", model)
            try:
                if model not in client.installed_models():
                    print(f"\n[{model}] download…", flush=True)
                    t0 = time.time()
                    client.pull(model)
                    res["pull_seconds"] = round(time.time() - t0, 1)
                print(f"[{model}] A) riunione fittizia", flush=True)
                r = client.chat(model, summary_prompt.SYSTEM, summary_prompt.user_message("Riunione marketing (fittizia)", fixture))
                (out_dir / f"{safe}_A_fittizia.md").write_text(r["content"], encoding="utf-8")
                res["A"] = {**r["stats"], "checks": auto_checks(r["content"])}
                res["memory"] = client.loaded_size_mb()
                res["ollama_rss_mb"] = llm.ollama_rss_mb()
                if real:
                    print(f"[{model}] B) riunione reale ({real.parent.name})", flush=True)
                    r = client.chat(model, summary_prompt.SYSTEM, summary_prompt.user_message("Riunione di test", real.read_text(encoding="utf-8")))
                    (out_dir / f"{safe}_B_reale.md").write_text(r["content"], encoding="utf-8")
                    res["B"] = r["stats"]
                print(f"[{model}] C) testo lungo (~10k token)", flush=True)
                r = client.chat(model, summary_prompt.SYSTEM, summary_prompt.user_message("Lunga", long_text), num_ctx=16384)
                res["C"] = r["stats"]
                res["memory_long"] = client.loaded_size_mb()
                res["ollama_rss_mb_long"] = llm.ollama_rss_mb()
                a_ = res["A"]
                print(f"[{model}] A: {a_['total_s']} s (caricamento {a_['load_s']} s, {a_['output_tps']} tok/s) — "
                      f"C: {res['C']['total_s']} s, prompt {res['C']['prompt_tps']} tok/s — memoria {res['memory_long']}")
                print(f"[{model}] controlli: {res['A']['checks']}")
            except Exception as e:  # noqa: BLE001
                res["error"] = str(getattr(e, "detail", "") or e)[:300]
                print(f"[{model}] ERRORE: {res['error']}")
            finally:
                if a.remove_after:
                    try:
                        client.delete(model)
                        print(f"[{model}] rimosso dal disco")
                    except Exception:  # noqa: BLE001
                        pass
            (dirs["logs_dir"] / f"llm_benchmark_{safe}_{datetime.now():%Y%m%d_%H%M%S}.json").write_text(
                json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8")
    finally:
        client.stop_server()
    print(f"\nVerbali di prova: {out_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
