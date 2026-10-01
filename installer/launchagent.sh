#!/bin/bash
# Meet Local AI — avvio automatico del backend all'accesso (LaunchAgent dell'utente, nessun permesso admin).
# Uso: installer/launchagent.sh install | uninstall | status | print-plist
# - install: crea ~/Library/LaunchAgents/<LABEL>.plist e avvia subito il backend
# - uninstall: ferma il backend e rimuove il plist (configurazione precedente ripristinata)
# Comportamento: parte al login, riparte da solo se va in crash, NON riparte se fermato con stop_backend.sh.
set -euo pipefail
LABEL="local.meetlocalai.backend"
REPO="$(cd "$(dirname "$0")/.." && pwd)"
VENV_PY="$REPO/backend/.venv/bin/python"
PLIST="${MEETLOCALAI_LAUNCHAGENTS_DIR:-$HOME/Library/LaunchAgents}/$LABEL.plist"
DOMAIN="gui/$(id -u)"

need_venv(){ [ -x "$VENV_PY" ] || { echo "Ambiente non installato. Esegui prima: $REPO/installer/setup_backend.sh"; exit 1; }; }

gen_plist(){
  need_venv
  local logs; logs="$(cd "$REPO/backend" && "$VENV_PY" -m meetlocalai --print-dir logs_dir)"
  mkdir -p "$logs"
  "$VENV_PY" - "$LABEL" "$VENV_PY" "$REPO/backend" "$logs" <<'PY'
import plistlib, sys
label, py, workdir, logs = sys.argv[1:5]
plist = {
    "Label": label,
    "ProgramArguments": [py, "-m", "meetlocalai"],
    "WorkingDirectory": workdir,
    "RunAtLoad": True,
    "KeepAlive": {"SuccessfulExit": False},   # riavvio solo dopo un crash
    "ThrottleInterval": 30,
    "ProcessType": "Standard",                # non "Background": la trascrizione non deve essere rallentata
    "StandardOutPath": f"{logs}/backend.stdout.log",
    "StandardErrorPath": f"{logs}/backend.stdout.log",
    "EnvironmentVariables": {"PATH": "/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"},
}
sys.stdout.write(plistlib.dumps(plist).decode())
PY
}

is_loaded(){ launchctl print "$DOMAIN/$LABEL" >/dev/null 2>&1; }

case "${1:-}" in
  print-plist)
    gen_plist ;;
  install)
    [ "$(uname -s)" = "Darwin" ] || { echo "Solo macOS."; exit 1; }
    case "$REPO" in
      "$HOME/Desktop"*|"$HOME/Documents"*|"$HOME/Downloads"*|"$HOME/Library/Mobile Documents"*)
        echo "[ATTENZIONE] Il progetto è in una cartella protetta da macOS ($REPO)."
        echo "I servizi avviati al login potrebbero non poterla leggere. Consigliato: ~/MeetLocalAI/app"; exit 1 ;;
    esac
    # ferma un eventuale backend avviato a mano, per liberare la porta
    "$REPO/stop_backend.sh" >/dev/null 2>&1 || true
    is_loaded && launchctl bootout "$DOMAIN/$LABEL" 2>/dev/null || true
    mkdir -p "$(dirname "$PLIST")"
    gen_plist > "$PLIST.tmp" && mv "$PLIST.tmp" "$PLIST"
    plutil -lint "$PLIST" >/dev/null
    launchctl bootstrap "$DOMAIN" "$PLIST"
    echo "Avvio automatico installato: $PLIST"
    PORT="$(cd "$REPO/backend" && "$VENV_PY" -m meetlocalai --print-port)"
    for _ in $(seq 1 30); do
      curl -s -m 1 -H 'X-MeetLocalAI: 1' "http://127.0.0.1:$PORT/api/v1/health" >/dev/null 2>&1 && { echo "Backend attivo su http://127.0.0.1:$PORT"; exit 0; }
      sleep 0.5
    done
    echo "[AVVISO] Il backend non risponde ancora. Controlla ~/MeetLocalAI/Logs/backend.stdout.log"; exit 1 ;;
  uninstall)
    if is_loaded; then launchctl bootout "$DOMAIN/$LABEL" 2>/dev/null || true; fi
    if [ -f "$PLIST" ]; then rm -f "$PLIST"; echo "Avvio automatico rimosso ($PLIST)."; else echo "Avvio automatico non installato."; fi ;;
  status)
    if [ -f "$PLIST" ]; then echo "Plist: $PLIST"; else echo "Avvio automatico: NON installato"; exit 0; fi
    if is_loaded; then
      launchctl print "$DOMAIN/$LABEL" | grep -E "^\s*(state|pid|last exit code|runs) =" || true
    else
      echo "Plist presente ma non caricato (verrà caricato al prossimo login)."
    fi
    grep -q "$VENV_PY" "$PLIST" || echo "[AVVISO] Il plist punta a un'altra cartella del progetto: riesegui 'install'." ;;
  *)
    echo "Uso: $0 install | uninstall | status | print-plist"; exit 2 ;;
esac
