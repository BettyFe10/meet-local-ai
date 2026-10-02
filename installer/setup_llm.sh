#!/bin/bash
# Meet Local AI — installa il modello locale per i riassunti (Ollama), scelto in base alla RAM del Mac.
# Idempotente. Rete usata solo per Homebrew e per scaricare il modello (in ~/MeetLocalAI/Models/ollama).
# Uso: installer/setup_llm.sh [modello]      es. installer/setup_llm.sh gemma4:12b
set -euo pipefail
REPO="$(cd "$(dirname "$0")/.." && pwd)"
VENV_PY="$REPO/backend/.venv/bin/python"
export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"
fail(){ printf "\n[ERRORE] %s\n" "$1" >&2; exit 1; }

[ -x "$VENV_PY" ] || fail "Esegui prima installer/setup_backend.sh"
if ! command -v ollama >/dev/null; then
  command -v brew >/dev/null || fail "Homebrew non trovato (https://brew.sh)."
  brew install ollama
fi
cd "$REPO/backend"
MODEL="${1:-$("$VENV_PY" -m meetlocalai.llm which)}"
echo "RAM: $(( $(sysctl -n hw.memsize) / 1073741824 )) GB → modello: $MODEL"
MODELS="$("$VENV_PY" -m meetlocalai --print-dir models_dir)"
# pulizia di eventuali download interrotti
find "$MODELS/ollama/blobs" -name '*-partial*' -delete 2>/dev/null || true
"$VENV_PY" -m meetlocalai.llm install "$MODEL"
du -sh "$MODELS/ollama" | awk '{print "Spazio occupato dai modelli LLM:", $1}'
