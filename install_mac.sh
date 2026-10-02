#!/bin/bash
# Meet Local AI — installazione completa su un Mac (Apple Silicon). Rilanciabile: installa solo ciò che manca.
#
# Uso: ./install_mac.sh [--check] [--yes] [--no-llm] [--no-autostart]
#   --check         controlla soltanto i requisiti, non installa nulla
#   --yes           non chiede conferma prima dei download
#   --no-llm        salta il modello per le sintesi (resta la sola trascrizione)
#   --no-autostart  non installa l'avvio automatico del backend
#
# Cosa fa: 1) controlla il Mac  2) ambiente Python + test  3) FFmpeg, whisper.cpp e modello di trascrizione
#          4) Ollama e modello di sintesi scelto in base alla RAM  5) avvio automatico  6) diagnostica finale.
# La rete serve solo qui (Homebrew, PyPI, download dei modelli). Non servono permessi di amministratore.
set -euo pipefail
REPO="$(cd "$(dirname "$0")" && pwd)"
export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"
CHECK=0; YES=0; LLM=1; AUTOSTART=1
for a in "$@"; do
  case "$a" in
    --check) CHECK=1 ;; --yes) YES=1 ;; --no-llm) LLM=0 ;; --no-autostart) AUTOSTART=0 ;;
    -h|--help) sed -n '2,12p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "Opzione sconosciuta: $a (usa --help)"; exit 2 ;;
  esac
done
say(){ printf "\n\033[1m==> %s\033[0m\n" "$1"; }
ok(){ echo "  ✓ $1"; }
warn(){ echo "  ! $1"; }
fail(){ printf "\n[ERRORE] %s\n" "$1" >&2; exit 1; }

say "1/6 Controllo del Mac"
[ "$(uname -s)" = "Darwin" ] || fail "Questo installer funziona solo su macOS."
ARCH="$(uname -m)"
[ "$ARCH" = "arm64" ] || fail "Serve un Mac con Apple Silicon (M1 o successivi). Rilevato: $ARCH. Se il Terminale è in modalità Rosetta, disattivala."
ok "macOS $(sw_vers -productVersion) · $(sysctl -n machdep.cpu.brand_string)"
RAM_GB=$(( $(sysctl -n hw.memsize) / 1073741824 ))
if   [ "$RAM_GB" -ge 24 ]; then LLM_MODEL="gemma4:12b"; LLM_GB=9
elif [ "$RAM_GB" -ge 12 ]; then LLM_MODEL="gemma4:e4b"; LLM_GB=7
else LLM_MODEL="gemma4:e2b"; LLM_GB=5; fi
ok "RAM ${RAM_GB} GB → modello di sintesi previsto: $LLM_MODEL"
[ "$RAM_GB" -ge 12 ] || warn "Meno di 12 GB di RAM: configurazione NON testata, le sintesi saranno meno accurate e più lente."
case "$REPO" in
  "$HOME/Desktop"*|"$HOME/Documents"*|"$HOME/Downloads"*|"$HOME/Library/Mobile Documents"*)
    fail "Il progetto è in una cartella protetta da macOS ($REPO). Spostalo in ~/MeetLocalAI/app e rilancia." ;;
esac
case "$REPO" in *" "*) fail "Il percorso del progetto contiene spazi ($REPO). Usa ~/MeetLocalAI/app." ;; esac
[ "$REPO" = "$HOME/MeetLocalAI/app" ] || warn "Posizione consigliata: ~/MeetLocalAI/app (ora: $REPO). Funziona comunque."
FREE_GB=$(( $(df -k "$HOME" | awk 'NR==2{print $4}') / 1048576 ))
NEED_GB=3
[ -s "$HOME/MeetLocalAI/Models/whispercpp/ggml-large-v3-turbo.bin" ] || NEED_GB=$(( NEED_GB + 2 ))
if [ "$LLM" = 1 ] && [ ! -d "$HOME/MeetLocalAI/Models/ollama/manifests" ]; then NEED_GB=$(( NEED_GB + LLM_GB )); fi
if [ "$FREE_GB" -ge "$NEED_GB" ]; then ok "Spazio libero ${FREE_GB} GB (servono circa ${NEED_GB} GB)"
else fail "Spazio insufficiente: ${FREE_GB} GB liberi, ne servono circa ${NEED_GB}."; fi
if command -v brew >/dev/null; then ok "Homebrew presente"; else
  echo
  echo "  Homebrew non è installato. Installalo (chiede la password del Mac), poi rilancia questo script:"
  echo '    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"'
  exit 1
fi
[ -d "/Applications/Google Chrome.app" ] && ok "Google Chrome presente" || warn "Google Chrome non trovato in /Applications: installalo prima di caricare l'estensione."
if lsof -nP -iTCP:8765 -sTCP:LISTEN 2>/dev/null | awk 'NR>1' | grep -qv -i python; then
  warn "La porta 8765 è usata da un altro programma: andrà cambiata in ~/MeetLocalAI/Config/config.json (backend.port) e nelle Impostazioni dell'estensione."
fi
PYOK=0
for c in python3.12 python3.13 python3.11 python3.10 python3; do
  if command -v "$c" >/dev/null 2>&1 && "$c" -c 'import sys,platform; sys.exit(0 if (3,10)<=sys.version_info[:2]<=(3,13) and platform.machine()=="arm64" else 1)' 2>/dev/null; then PYOK=1; ok "Python: $("$c" --version)"; break; fi
done
[ "$PYOK" = 1 ] || warn "Nessun Python 3.10–3.13 nativo: verrà installato python@3.12 con Homebrew."

if [ "$CHECK" = 1 ]; then say "Controllo terminato (nessuna modifica eseguita)."; exit 0; fi

echo
echo "Verranno installati, se mancanti: FFmpeg, whisper.cpp, modello di trascrizione (1,5 GB)$( [ "$LLM" = 1 ] && echo ", Ollama, modello $LLM_MODEL" )."
echo "Tutto resta in ~/MeetLocalAI e in Homebrew. Durata tipica: 10–30 minuti secondo la connessione."
if [ "$YES" = 0 ]; then
  read -r -p "Procedo? [s/N] " R
  case "$R" in s|S|si|SI|sì|y|Y) ;; *) echo "Annullato."; exit 0 ;; esac
fi

say "2/6 Ambiente Python e test"
[ "$PYOK" = 1 ] || brew install python@3.12
"$REPO/installer/setup_backend.sh"

say "3/6 Trascrizione locale (FFmpeg, whisper.cpp, modello)"
"$REPO/installer/setup_whisper.sh"

if [ "$LLM" = 1 ]; then
  say "4/6 Sintesi locale (Ollama, modello $LLM_MODEL)"
  "$REPO/installer/setup_llm.sh"
else
  say "4/6 Sintesi locale: SALTATA (--no-llm). Per aggiungerla dopo: installer/setup_llm.sh"
fi

if [ "$AUTOSTART" = 1 ]; then
  say "5/6 Avvio automatico del backend"
  "$REPO/installer/launchagent.sh" install
else
  say "5/6 Avvio automatico: SALTATO (--no-autostart). Avvio manuale: ./start_backend.sh"
  "$REPO/start_backend.sh" || true
fi

say "6/6 Diagnostica"
"$REPO/diagnose.sh" || warn "La diagnostica segnala qualcosa da sistemare (vedi sopra)."

cat <<TXT

────────────────────────────────────────────────────────
ULTIMO PASSO (a mano, una volta sola): caricare l'estensione in Chrome
  1. Apri Chrome e vai su   chrome://extensions
  2. Attiva "Modalità sviluppatore" (in alto a destra)
  3. Clicca "Carica estensione non pacchettizzata" e scegli la cartella:
       $REPO/extension
  4. Fissa l'icona "Meet Local AI" nella barra; aprila → Impostazioni → "Abilita microfono"
Guida completa: $REPO/SETUP-NEW-COMPUTER.md
────────────────────────────────────────────────────────
TXT
