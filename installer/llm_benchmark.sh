#!/bin/bash
# Meet Local AI — Fase 9: confronta modelli LLM locali (Ollama) per la sintesi.
# Rete usata SOLO per installare Ollama (Homebrew) e scaricare i modelli. Un modello alla volta su disco.
# Uso: installer/llm_benchmark.sh [modello1,modello2,...]
set -euo pipefail
REPO="$(cd "$(dirname "$0")/.." && pwd)"
VENV_PY="$REPO/backend/.venv/bin/python"
export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"
MODELS_LIST="${1:-qwen3:4b,qwen3:8b,gemma4:e4b,gemma4:12b}"
fail(){ printf "\n[ERRORE] %s\n" "$1" >&2; exit 1; }

[ -x "$VENV_PY" ] || fail "Esegui prima installer/setup_backend.sh"
command -v brew >/dev/null || fail "Homebrew non trovato."
if command -v ollama >/dev/null; then echo "Ollama già installato: $(ollama --version 2>/dev/null | tail -1)"; else brew install ollama; fi
MODELS="$(cd "$REPO/backend" && "$VENV_PY" -m meetlocalai --print-dir models_dir)"
FREE_GB=$(( $(df -k "$MODELS" | awk 'NR==2{print $4}') / 1024 / 1024 ))
echo "Spazio libero: ${FREE_GB} GB (serve ~12 GB: un modello alla volta)"
[ "$FREE_GB" -ge 12 ] || fail "Spazio insufficiente."
cd "$REPO/backend"
"$VENV_PY" -m meetlocalai.bench_llm --models "$MODELS_LIST" --remove-after
echo FATTO
