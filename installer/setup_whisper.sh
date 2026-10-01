#!/bin/bash
# Meet Local AI — installa la trascrizione locale scelta in Fase 7: whisper.cpp (Metal) + modello large-v3-turbo.
# Idempotente: installa/scarica solo ciò che manca. Rete usata solo per Homebrew e per il download del modello.
set -euo pipefail
REPO="$(cd "$(dirname "$0")/.." && pwd)"
VENV_PY="$REPO/backend/.venv/bin/python"
export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"
MODEL="${1:-large-v3-turbo}"
fail(){ printf "\n[ERRORE] %s\n" "$1" >&2; exit 1; }

[ "$(uname -s)" = "Darwin" ] || fail "Solo macOS."
command -v brew >/dev/null || fail "Homebrew non trovato (https://brew.sh)."
[ -x "$VENV_PY" ] || fail "Esegui prima installer/setup_backend.sh"
for f in ffmpeg whisper-cpp; do
  brew list --formula "$f" >/dev/null 2>&1 && echo "$f: già installato" || brew install "$f"
done
command -v whisper-cli >/dev/null || fail "whisper-cli non trovato."

MODELS="$(cd "$REPO/backend" && "$VENV_PY" -m meetlocalai --print-dir models_dir)/whispercpp"
mkdir -p "$MODELS"
GG="$MODELS/ggml-$MODEL.bin"
if [ -s "$GG" ] && [ "$(stat -f%z "$GG")" -gt 100000000 ]; then
  echo "Modello già presente: $GG"
else
  FREE_GB=$(( $(df -k "$MODELS" | awk 'NR==2{print $4}') / 1024 / 1024 ))
  [ "$FREE_GB" -ge 3 ] || fail "Spazio insufficiente (${FREE_GB} GB liberi, servono ~3 GB)."
  curl -L --fail -C - -o "$GG.part" "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-$MODEL.bin"
  mv "$GG.part" "$GG"
fi
ls -lh "$GG" | awk '{print "Modello:", $5, $9}'
echo "Trascrizione locale pronta (whisper.cpp, $MODEL)."
