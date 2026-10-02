#!/bin/bash
# Meet Local AI — disinstallazione. NON cancella mai le riunioni né la configurazione.
#
# Uso: ./uninstall_mac.sh [--models] [--yes]
#   (senza opzioni)  ferma il backend, rimuove l'avvio automatico e l'ambiente Python del progetto
#   --models         rimuove anche i modelli scaricati (~/MeetLocalAI/Models, circa 8 GB)
#   --yes            non chiede conferma
#
# Restano sempre al loro posto: ~/MeetLocalAI/Meetings, Exports, Config, Logs e la cartella del codice.
# I programmi installati con Homebrew non vengono toccati (potrebbero servire ad altro): i comandi per
# rimuoverli sono stampati alla fine.
set -euo pipefail
REPO="$(cd "$(dirname "$0")" && pwd)"
export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"
MODELS=0; YES=0
for a in "$@"; do
  case "$a" in
    --models) MODELS=1 ;; --yes) YES=1 ;;
    -h|--help) sed -n '2,12p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "Opzione sconosciuta: $a (usa --help)"; exit 2 ;;
  esac
done
VENV="$REPO/backend/.venv"
MODELS_DIR="$HOME/MeetLocalAI/Models"
if [ -x "$VENV/bin/python" ]; then
  MODELS_DIR="$(cd "$REPO/backend" && "$VENV/bin/python" -m meetlocalai --print-dir models_dir 2>/dev/null || echo "$MODELS_DIR")"
fi

echo "Verranno rimossi:"
echo "  - avvio automatico del backend (LaunchAgent)"
echo "  - ambiente Python del progetto ($VENV)"
[ "$MODELS" = 1 ] && echo "  - modelli scaricati ($MODELS_DIR)"
echo "NON verranno toccati: riunioni, esportazioni, configurazione, codice, programmi Homebrew."
if [ "$YES" = 0 ]; then
  read -r -p "Procedo? [s/N] " R
  case "$R" in s|S|si|SI|sì|y|Y) ;; *) echo "Annullato."; exit 0 ;; esac
fi

"$REPO/stop_backend.sh" 2>/dev/null || true
"$REPO/installer/launchagent.sh" uninstall 2>/dev/null || true
"$REPO/installer/menubar.sh" uninstall 2>/dev/null || true
pkill -f "ollama serve" 2>/dev/null || true

case "$VENV" in
  */backend/.venv) [ -d "$VENV" ] && rm -rf "$VENV" && echo "Ambiente Python rimosso." ;;
esac
if [ "$MODELS" = 1 ]; then
  case "$MODELS_DIR" in
    */MeetLocalAI/Models) [ -d "$MODELS_DIR" ] && rm -rf "$MODELS_DIR" && echo "Modelli rimossi." ;;
    *) echo "[AVVISO] Cartella modelli inattesa ($MODELS_DIR): non la tocco." ;;
  esac
fi

cat <<TXT

Fatto. Restano da fare a mano, se vuoi togliere tutto:
  - Chrome → chrome://extensions → "Meet Local AI" → Rimuovi
  - Programmi Homebrew (solo se non ti servono per altro):
      brew uninstall whisper-cpp ollama ffmpeg
  - Riunioni e dati: cartella ~/MeetLocalAI (controlla prima di cestinarla: contiene le tue riunioni)
Per reinstallare: $REPO/install_mac.sh
TXT
