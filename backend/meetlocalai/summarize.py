"""Sintesi di una trascrizione con il modello locale.

- riunioni normali: un solo passaggio;
- riunioni lunghe (trascrizione oltre il contesto): appunti per blocchi + verbale finale dagli appunti;
- l'output viene controllato (deve essere il verbale in 7 sezioni): preamboli rimossi, un nuovo tentativo se non valido,
  sezioni mancanti completate con il testo standard. Nessun testo delle riunioni nei log.

CLI di prova:  python -m meetlocalai.summarize --fixture | --meeting ID   (stampa il verbale e i tempi)
"""

from __future__ import annotations

import logging
import re
import sys
import time
from pathlib import Path

from . import llm
from . import summary_prompt as sp

log = logging.getLogger("meetlocalai.summarize")

CHARS_PER_TOKEN = 2.8          # stima prudente per l'italiano (misurato ≈2,9 nel benchmark)
SINGLE_PASS_MAX_TOKENS = 12000  # oltre: sintesi a blocchi
CHUNK_TOKENS = 8000
OUTPUT_RESERVE = 1800           # token riservati a prompt di sistema + risposta


class SummaryError(Exception):
    def __init__(self, user_message: str, detail: str = ""):
        super().__init__(user_message)
        self.user_message = user_message
        self.detail = detail


def estimate_tokens(text: str) -> int:
    return int(len(text) / CHARS_PER_TOKEN) + 1


def ctx_for(tokens: int) -> int:
    need = tokens + OUTPUT_RESERVE
    for size in (4096, 8192, 16384):
        if need <= size:
            return size
    return 16384


def split_blocks(transcript: str, max_tokens: int = CHUNK_TOKENS) -> list[str]:
    """Divide ai confini dei paragrafi ([hh:mm:ss] Speaker:\\n testo), senza spezzare un intervento se possibile."""
    paras = [p for p in re.split(r"\n\s*\n", transcript.strip()) if p.strip()]
    blocks, cur, cur_tok = [], [], 0
    for p in paras:
        t = estimate_tokens(p)
        if t > max_tokens:  # intervento enorme: lo spezzo a frasi
            for piece in _split_long(p, max_tokens):
                if cur:
                    blocks.append("\n\n".join(cur)); cur, cur_tok = [], 0
                blocks.append(piece)
            continue
        if cur and cur_tok + t > max_tokens:
            blocks.append("\n\n".join(cur)); cur, cur_tok = [], 0
        cur.append(p); cur_tok += t
    if cur:
        blocks.append("\n\n".join(cur))
    return blocks


def _split_long(p: str, max_tokens: int) -> list[str]:
    max_chars = int(max_tokens * CHARS_PER_TOKEN)
    out, cur = [], ""
    for sent in re.split(r"(?<=[.!?])\s+", p):
        while len(sent) > max_chars:
            out.append(sent[:max_chars]); sent = sent[max_chars:]
        if len(cur) + len(sent) + 1 > max_chars and cur:
            out.append(cur); cur = sent
        else:
            cur = f"{cur} {sent}".strip()
    if cur:
        out.append(cur)
    return out


# ---------- controllo e normalizzazione dell'output ----------
_HEAD_RE = {s: re.compile(rf"^\s*#{{1,4}}\s*\**\s*{re.escape(s)}\s*\**\s*:?\s*$", re.I | re.M) for s in sp.SECTIONS}


def parse_sections(md: str) -> dict[str, str]:
    """{sezione: testo}. Tollerante su livello del titolo, grassetto e maiuscole."""
    found = []
    for name, rx in _HEAD_RE.items():
        m = rx.search(md)
        if m:
            found.append((m.start(), m.end(), name))
    found.sort()
    out = {}
    for i, (_, end, name) in enumerate(found):
        nxt = found[i + 1][0] if i + 1 < len(found) else len(md)
        out[name] = md[end:nxt].strip()
    return out


def is_valid(md: str) -> bool:
    secs = parse_sections(md)
    return "TL;DR" in secs and len(secs) >= 5 and bool(secs["TL;DR"].strip())


def _only_nd(body: str) -> bool:
    """True se la sezione contiene solo il testo standard (anche ripetuto dentro il formato degli action item)."""
    rest = body.replace(sp.ND, "").replace(sp.ND.rstrip("."), "")
    rest = re.sub(r"Responsabile:|Scadenza:|Attività:", "", rest, flags=re.I)
    return not re.search(r"[A-Za-zÀ-ÿ0-9]", rest)


def normalize(md: str) -> str:
    """Verbale pulito: solo le 7 sezioni, nell'ordine previsto; quelle mancanti o vuote → testo standard."""
    secs = parse_sections(md)
    parts = []
    for name in sp.SECTIONS:
        body = secs.get(name, "").strip() or sp.ND
        if _only_nd(body):
            body = sp.ND
        parts.append(f"## {name}\n{body}")
    return "\n\n".join(parts) + "\n"


# ---------- sintesi ----------
def summarize(client: llm.OllamaClient, model: str, title: str, transcript: str, *, temperature: float = 0.2,
              two_pass: bool = True) -> dict:
    """Ritorna {"markdown", "sections", "stats"}. Solleva SummaryError / llm.LLMError.

    two_pass=True (default, D-040): prima appunti fedeli (per blocchi se la riunione è lunga), poi il verbale dagli appunti.
    two_pass=False: un solo passaggio (più veloce, meno completo), usato solo se la trascrizione sta nel contesto."""
    transcript = transcript.strip()
    if not transcript:
        raise SummaryError("Nessun parlato da riassumere.")
    t0 = time.perf_counter()
    stats = {"model": model, "prompt_version": sp.PROMPT_VERSION, "calls": 0, "output_tokens": 0, "mode": "single", "retries": 0}

    def call(system: str, user: str, num_ctx: int) -> str:
        r = client.chat(model, system, user, num_ctx=num_ctx, temperature=temperature)
        stats["calls"] += 1
        stats["output_tokens"] += r["stats"].get("output_tokens") or 0
        return r["content"]

    tokens = estimate_tokens(transcript)
    if not two_pass and tokens <= SINGLE_PASS_MAX_TOKENS:
        system, user, ctx = sp.SYSTEM, sp.user_message(title, transcript), ctx_for(tokens)
    else:
        blocks = split_blocks(transcript, CHUNK_TOKENS if tokens > SINGLE_PASS_MAX_TOKENS else SINGLE_PASS_MAX_TOKENS)
        stats["mode"], stats["blocks"] = ("blocks" if len(blocks) > 1 else "two_pass"), len(blocks)
        notes = [call(sp.SYSTEM_CHUNK, sp.chunk_message(title, b, i, len(blocks)), ctx_for(estimate_tokens(b)))
                 for i, b in enumerate(blocks, 1)]
        system, user = sp.SYSTEM_MERGE, sp.merge_message(title, notes)
        ctx = ctx_for(estimate_tokens(user))

    out = call(system, user, ctx)
    if not is_valid(out):
        stats["retries"] = 1
        log.warning("Sintesi non conforme al formato (tentativo 1): riprovo")
        out = call(system, user + sp.RETRY_SUFFIX, ctx)
        if not is_valid(out):
            raise SummaryError("Il modello locale non ha prodotto un verbale valido.", "formato non rispettato dopo 2 tentativi")
    md = normalize(out)
    stats["seconds"] = round(time.perf_counter() - t0, 2)
    stats["transcript_tokens_est"] = tokens
    return {"markdown": md, "sections": parse_sections(md), "stats": stats}


def render_summary_file(md_meta: dict, body: str, model: str) -> str:
    dur = round((md_meta.get("duration_seconds") or 0) / 60)
    return (f"# RIUNIONE — {md_meta['title']}\n\n"
            f"- Data: {md_meta.get('date')} {md_meta.get('start_time')} · Durata: {dur} min\n"
            f"- Sintesi generata in locale con {model} dalla trascrizione automatica: verificare i punti importanti.\n\n"
            f"{body}")


def main(argv: list[str]) -> int:
    from . import config as config_mod, paths  # noqa: PLC0415

    cfg = config_mod.load()
    dirs = config_mod.data_dirs(cfg)
    if "--fixture" in argv:
        title, text = "Riunione marketing (fittizia)", (paths.REPO_ROOT / "tests" / "fixtures" / "riunione_fittizia_marketing.txt").read_text(encoding="utf-8")
    elif "--meeting" in argv:
        mid = argv[argv.index("--meeting") + 1]
        title, text = mid, (dirs["meetings_dir"] / mid / "transcript.txt").read_text(encoding="utf-8")
    else:
        print("Uso: python -m meetlocalai.summarize --fixture | --meeting ID [--model M] [--long] [--single]", file=sys.stderr)
        return 2
    if "--long" in argv:  # forza la modalità a blocchi ripetendo il testo
        text = "\n\n".join([text] * 10)
    model = argv[argv.index("--model") + 1] if "--model" in argv else llm.resolve_model(cfg)
    client = llm.OllamaClient(cfg["llm"]["base_url"], dirs["models_dir"], keep_alive=cfg["llm"].get("keep_alive", "30s"))
    try:
        client.ensure_server()
        r = summarize(client, model, title, text, temperature=cfg["llm"].get("temperature", 0.2),
                      two_pass="--single" not in argv and cfg.get("summary", {}).get("two_pass", True))
        print(r["markdown"])
        print(f"--- {r['stats']} — memoria Ollama {llm.ollama_rss_mb()} MB", file=sys.stderr)
        return 0
    except (SummaryError, llm.LLMError) as e:
        print(f"ERRORE: {e.user_message} ({e.detail})", file=sys.stderr)
        return 1
    finally:
        client.stop_server()


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
