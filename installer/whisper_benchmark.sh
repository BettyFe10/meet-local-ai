#!/bin/bash
# Meet Local AI — Fase 7: installa i due candidati Whisper e li confronta su una riunione registrata.
# Rete usata SOLO per: Homebrew (ffmpeg, whisper-cpp), PyPI (mlx-whisper), Hugging Face (modelli).
# Dopo la scelta, il motore scartato e il suo modello verranno rimossi.
# Uso: installer/whisper_benchmark.sh [ID_RIUNIONE]
set -euo pipefail
REPO="$(cd "$(dirname "$0")/.." && pwd)"
VENV_PY="$REPO/backend/.venv/bin/python"
export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"
say(){ printf "\n==> %s\n" "$1"; }
fail(){ printf "\n[ERRORE] %s\n" "$1" >&2; exit 1; }

[ "$(uname -s)" = "Darwin" ] && [ "$(uname -m)" = "arm64" ] || fail "Serve un Mac Apple Silicon."
[ -x "$VENV_PY" ] || fail "Ambiente non installato: esegui prima installer/setup_backend.sh"
command -v brew >/dev/null || fail "Homebrew non trovato (https://brew.sh)."
MODELS="$(cd "$REPO/backend" && "$VENV_PY" -m meetlocalai --print-dir models_dir)"
mkdir -p "$MODELS/hf" "$MODELS/whispercpp"

say "Spazio disco"
FREE_GB=$(( $(df -k "$MODELS" | awk 'NR==2{print $4}') / 1024 / 1024 ))
echo "Liberi: ${FREE_GB} GB (servono ~6 GB per il benchmark)"
[ "$FREE_GB" -ge 6 ] || fail "Spazio insufficiente."

say "FFmpeg e whisper.cpp (Homebrew, solo se mancano)"
for f in ffmpeg whisper-cpp; do
  if brew list --formula "$f" >/dev/null 2>&1; then echo "$f: già installato"; else brew install "$f"; fi
done
command -v whisper-cli >/dev/null || fail "whisper-cli non trovato dopo l'installazione di whisper-cpp."
echo "ffmpeg: $(ffmpeg -version | head -1)"; echo "whisper-cli: $(command -v whisper-cli)"

say "mlx-whisper (nell'ambiente Python del progetto)"
"$VENV_PY" -m pip install --quiet -r "$REPO/backend/requirements-mlx.txt"
"$VENV_PY" -m pip show mlx-whisper mlx | grep -E "^(Name|Version)" | paste - -

say "Modello MLX: mlx-community/whisper-large-v3-turbo"
HF_HOME="$MODELS/hf" HF_HUB_DISABLE_TELEMETRY=1 "$VENV_PY" -c \
  "from huggingface_hub import snapshot_download as d; print(d('mlx-community/whisper-large-v3-turbo'))"

say "Modello whisper.cpp: ggml-large-v3-turbo.bin"
GG="$MODELS/whispercpp/ggml-large-v3-turbo.bin"
if [ -s "$GG" ]; then echo "già presente"; else
  curl -L --fail -C - -o "$GG.part" "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-large-v3-turbo.bin"
  mv "$GG.part" "$GG"
fi
ls -lh "$GG" | awk '{print $5, $9}'

say "Benchmark (rete NON usata da qui in poi)"
cd "$REPO/backend"
"$VENV_PY" -m meetlocalai.bench ${1:+--meeting "$1"}
du -sh "$MODELS"/* 2>/dev/null
say "FATTO"
