#!/bin/bash
# Meet Local AI — confronto tra motori di trascrizione sulla STESSA riunione (strumento di valutazione).
# Trascrive audio.wav di una riunione con: 1) Whisper large-v3-turbo (attuale)  2) Whisper large-v3  3) Parakeet v3
# e salva i tre testi affiancabili in ~/MeetLocalAI/Exports/confronto-trascrizione/<riunione>/.
# Scarica i modelli uno alla volta e li cancella dopo l'uso (picco di spazio: circa 3,5 GB). Tutto resta sul Mac.
# Uso: installer/transcription_compare.sh [nome-cartella-riunione]     (predefinita: la riunione più recente)
#      KEEP=1 … per non cancellare i modelli scaricati
set -uo pipefail
REPO="$(cd "$(dirname "$0")/.." && pwd)"
VENV_PY="$REPO/backend/.venv/bin/python"
export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"
[ "$(uname -s)" = "Darwin" ] || { echo "Solo macOS."; exit 1; }
[ -x "$VENV_PY" ] || { echo "Esegui prima install_mac.sh"; exit 1; }
cd "$REPO/backend"
MEETINGS="$("$VENV_PY" -m meetlocalai --print-dir meetings_dir)"
MODELS="$("$VENV_PY" -m meetlocalai --print-dir models_dir)/whispercpp"
TEMP="$("$VENV_PY" -m meetlocalai --print-dir temp_dir)/confronto"
EXPORTS="$("$VENV_PY" -m meetlocalai --print-dir exports_dir)"
ID="${1:-$(ls -1 "$MEETINGS" | grep -E '^[0-9]{4}-' | sort | tail -1)}"
WAV="$MEETINGS/$ID/audio.wav"
[ -f "$WAV" ] || { echo "audio.wav non trovato per la riunione: $ID"; exit 1; }
OUT="$EXPORTS/confronto-trascrizione/$ID"
mkdir -p "$OUT" "$TEMP"
TIMES="$OUT/tempi.txt"
DUR="$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$WAV" 2>/dev/null | cut -d. -f1)"
echo "Riunione: durata audio ${DUR:-?} s — $(date '+%Y-%m-%d %H:%M')" > "$TIMES"
free_gb(){ echo $(( $(df -k "$HOME" | awk 'NR==2{print $4}') / 1048576 )); }
echo "Riunione: $ID (${DUR:-?} s) · spazio libero: $(free_gb) GB"
echo "Risultati in: $OUT"

whisper_run(){  # $1 = nome modello, $2 = file di uscita (senza estensione)
  local t0=$SECONDS
  if whisper-cli -m "$MODELS/ggml-$1.bin" -f "$WAV" -l it -t 4 -otxt -of "$2" -np >/dev/null 2>"$TEMP/whisper-$1.err"; then
    echo "Whisper $1: $((SECONDS - t0)) s" | tee -a "$TIMES"
  else
    echo "Whisper $1: FALLITO (vedi $TEMP/whisper-$1.err)" | tee -a "$TIMES"
  fi
}

echo; echo "== 1/3 Whisper large-v3-turbo (attuale) =="
if [ -s "$MODELS/ggml-large-v3-turbo.bin" ]; then whisper_run large-v3-turbo "$OUT/1-whisper-turbo"
else echo "Whisper large-v3-turbo: modello non presente" | tee -a "$TIMES"; fi

echo; echo "== 2/3 Whisper large-v3 (download ~3,1 GB) =="
L3="$MODELS/ggml-large-v3.bin"; HAD_L3=0; [ -s "$L3" ] && HAD_L3=1
if [ "$HAD_L3" = 0 ] && [ "$(free_gb)" -lt 5 ]; then
  echo "Whisper large-v3: SALTATO, spazio insufficiente ($(free_gb) GB liberi, ne servono almeno 5)" | tee -a "$TIMES"
else
  if [ "$HAD_L3" = 0 ]; then
    curl -L --fail -C - -o "$L3.part" "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-large-v3.bin" && mv "$L3.part" "$L3"
  fi
  if [ -s "$L3" ]; then whisper_run large-v3 "$OUT/2-whisper-large-v3"
  else echo "Whisper large-v3: download non riuscito" | tee -a "$TIMES"; fi
  if [ "$HAD_L3" = 0 ] && [ "${KEEP:-0}" != 1 ]; then rm -f "$L3" "$L3.part"; fi
fi

echo; echo "== 3/3 Parakeet v3 (ambiente temporaneo + download ~2,5 GB) =="
if [ "$(free_gb)" -lt 5 ]; then
  echo "Parakeet v3: SALTATO, spazio insufficiente ($(free_gb) GB liberi)" | tee -a "$TIMES"
else
  PY=""; for c in python3.12 python3.13 python3.11 python3.10; do command -v "$c" >/dev/null 2>&1 && { PY="$c"; break; }; done
  if [ -z "$PY" ]; then echo "Parakeet v3: SALTATO, Python non trovato" | tee -a "$TIMES"
  else
    "$PY" -m venv "$TEMP/venv" && "$TEMP/venv/bin/python" -m pip install --quiet --upgrade pip && \
      "$TEMP/venv/bin/python" -m pip install --quiet parakeet-mlx
    if [ $? -ne 0 ]; then echo "Parakeet v3: installazione non riuscita" | tee -a "$TIMES"
    else
      HF_HOME="$TEMP/hf" "$TEMP/venv/bin/python" - "$WAV" "$OUT/3-parakeet-v3.txt" <<'PY' 2>"$TEMP/parakeet.err" | tee -a "$TIMES"
import sys, time
wav, out = sys.argv[1], sys.argv[2]
from parakeet_mlx import from_pretrained
t0 = time.time()
model = from_pretrained("mlx-community/parakeet-tdt-0.6b-v3")
t1 = time.time()
r = model.transcribe(wav, chunk_duration=120.0, overlap_duration=15.0)
t2 = time.time()
sents = getattr(r, "sentences", None) or []
text = "\n".join(s.text.strip() for s in sents if s.text.strip()) or r.text
open(out, "w", encoding="utf-8").write(text.strip() + "\n")
print(f"Parakeet v3: {t2 - t1:.0f} s (caricamento/download modello {t1 - t0:.0f} s)")
PY
      [ -s "$OUT/3-parakeet-v3.txt" ] || echo "Parakeet v3: FALLITO (vedi $TEMP/parakeet.err: $(tail -1 "$TEMP/parakeet.err" 2>/dev/null | cut -c1-200))" | tee -a "$TIMES"
    fi
  fi
fi
if [ "${KEEP:-0}" != 1 ]; then
  case "$TEMP" in */Temp/confronto) rm -rf "$TEMP/venv" "$TEMP/hf" ;; esac
fi

echo; echo "== Fatto =="; cat "$TIMES"
echo "Apri la cartella e confronta i tre testi:"; echo "  open \"$OUT\""
open "$OUT" 2>/dev/null || true
