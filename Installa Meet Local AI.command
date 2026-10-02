#!/bin/bash
# Meet Local AI — installazione con doppio clic.
# Copia il progetto in ~/MeetLocalAI/app (se è stato scaricato altrove), installa Homebrew se manca
# (chiedendo conferma) e avvia install_mac.sh. Rilanciabile: serve anche per aggiornare.
set -uo pipefail
SRC="$(cd "$(dirname "$0")" && pwd)"
DEST="$HOME/MeetLocalAI/app"
finish(){ echo; read -r -p "Premi Invio per chiudere questa finestra. " _; exit "${1:-0}"; }

echo "Meet Local AI — installazione"
echo
[ "$(uname -s)" = "Darwin" ] || { echo "Questo installer funziona solo su macOS."; finish 1; }
[ "$(uname -m)" = "arm64" ] || { echo "Serve un Mac con Apple Silicon (M1 o successivi)."; finish 1; }

if [ "$SRC" != "$DEST" ]; then
  echo "Copio il programma in $DEST …"
  mkdir -p "$DEST" || finish 1
  # le riunioni e la configurazione stanno in ~/MeetLocalAI, fuori da questa cartella: non vengono toccate
  rsync -a --exclude '.venv' --exclude '.git' --exclude '__pycache__' "$SRC"/ "$DEST"/ || { echo "Copia non riuscita."; finish 1; }
  xattr -dr com.apple.quarantine "$DEST" 2>/dev/null || true
fi
chmod +x "$DEST"/*.sh "$DEST"/installer/*.sh 2>/dev/null || true

export PATH="/opt/homebrew/bin:$PATH"
if ! command -v brew >/dev/null 2>&1; then
  echo
  echo "Serve Homebrew (il gestore di programmi per Mac usato dall'installazione)."
  echo "Verrà scaricato dal sito ufficiale e chiederà la password del Mac."
  read -r -p "Lo installo ora? [s/N] " R
  case "$R" in s|S|si|SI|sì|y|Y) ;; *) echo "Annullato."; finish 0 ;; esac
  /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)" || { echo "Installazione di Homebrew non riuscita."; finish 1; }
  [ -x /opt/homebrew/bin/brew ] && eval "$(/opt/homebrew/bin/brew shellenv)"
  command -v brew >/dev/null 2>&1 || { echo "Homebrew non trovato dopo l'installazione: chiudi, riapri e rilancia."; finish 1; }
fi

"$DEST/install_mac.sh"
finish $?
