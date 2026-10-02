#!/bin/bash
# Meet Local AI — diagnostica. Non modifica nulla e non stampa contenuti delle riunioni
# (né titoli, né trascrizioni, né sintesi). Il rapporto viene salvato anche in Logs/diagnose_report.txt.
set -uo pipefail
REPO="$(cd "$(dirname "$0")" && pwd)"
VENV_PY="$REPO/backend/.venv/bin/python"
export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"
LABEL="local.meetlocalai.backend"

if [ ! -x "$VENV_PY" ]; then
  echo "✗ Ambiente Python non installato ($REPO/backend/.venv)."
  echo "  Esegui: $REPO/installer/setup_backend.sh"
  exit 1
fi
cd "$REPO/backend"
LOGS_DIR="$("$VENV_PY" -m meetlocalai --print-dir logs_dir 2>/dev/null)" || {
  echo "✗ Configurazione non valida:"; "$VENV_PY" -m meetlocalai --check-config; exit 2; }
mkdir -p "$LOGS_DIR"
REPORT="$LOGS_DIR/diagnose_report.txt"

{
  echo "Data: $(date '+%Y-%m-%d %H:%M')"
  "$VENV_PY" -m meetlocalai.diagnose; RC=$?
  echo
  echo "[Mac]"
  if [ "$(uname -s)" = "Darwin" ]; then
    echo "  modello: $(sysctl -n hw.model 2>/dev/null) · chip: $(sysctl -n machdep.cpu.brand_string 2>/dev/null) · macOS $(sw_vers -productVersion 2>/dev/null)"
    if launchctl print "gui/$(id -u)/$LABEL" >/dev/null 2>&1; then
      echo "  avvio automatico (LaunchAgent): installato"
    else
      echo "  avvio automatico (LaunchAgent): NON installato → $REPO/installer/launchagent.sh install"
    fi
    CHROME="/Applications/Google Chrome.app/Contents/Info.plist"
    [ -f "$CHROME" ] && echo "  Chrome: $(/usr/libexec/PlistBuddy -c 'Print CFBundleShortVersionString' "$CHROME" 2>/dev/null)" || echo "  Chrome: non trovato in /Applications"
  else
    echo "  (non macOS: controlli di sistema saltati)"
  fi
  echo "[Programmi]"
  for c in ffmpeg whisper-cli ollama git; do
    if command -v "$c" >/dev/null 2>&1; then echo "  $c: presente"; else echo "  $c: MANCANTE"; fi
  done
  echo "[Codice]"
  echo "  versione git: $(git -C "$REPO" rev-parse --short HEAD 2>/dev/null || echo 'n/d') · modifiche locali: $(git -C "$REPO" status --porcelain 2>/dev/null | wc -l | tr -d ' ')"
  exit $RC
} 2>&1 | sed "s|$HOME|~|g" | tee "$REPORT"
RC=${PIPESTATUS[0]}
echo
echo "Rapporto salvato in: ${REPORT/#$HOME/~}"
exit "$RC"
