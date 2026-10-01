#!/bin/bash
# Meet Local AI — avvia il backend locale in background (solo 127.0.0.1).
set -euo pipefail
REPO="$(cd "$(dirname "$0")" && pwd)"
VENV_PY="$REPO/backend/.venv/bin/python"
export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"

[ -x "$VENV_PY" ] || { echo "Ambiente non installato. Esegui prima: $REPO/installer/setup_backend.sh"; exit 1; }
cd "$REPO/backend"
PORT="$("$VENV_PY" -m meetlocalai --print-port)" || exit 2
TEMP_DIR="$("$VENV_PY" -m meetlocalai --print-dir temp_dir)"
LOGS_DIR="$("$VENV_PY" -m meetlocalai --print-dir logs_dir)"
mkdir -p "$TEMP_DIR" "$LOGS_DIR"
PIDFILE="$TEMP_DIR/backend.pid"

LABEL="local.meetlocalai.backend"
if [ "$(uname -s)" = "Darwin" ] && launchctl print "gui/$(id -u)/$LABEL" >/dev/null 2>&1; then
  # avvio automatico installato: si avvia tramite launchd (stessa gestione dei crash)
  if [ -f "$PIDFILE" ] && kill -0 "$(cat "$PIDFILE")" 2>/dev/null; then
    echo "Backend già attivo (PID $(cat "$PIDFILE"), avvio automatico) su http://127.0.0.1:$PORT"; exit 0
  fi
  launchctl kickstart "gui/$(id -u)/$LABEL"
  for _ in $(seq 1 30); do
    curl -s -m 1 -H 'X-MeetLocalAI: 1' "http://127.0.0.1:$PORT/api/v1/health" >/dev/null 2>&1 && { echo "Backend attivo (avvio automatico) su http://127.0.0.1:$PORT"; exit 0; }
    sleep 0.5
  done
  echo "[ERRORE] Il backend non risponde. Vedi $LOGS_DIR/backend.stdout.log"; exit 1
fi

if [ -f "$PIDFILE" ] && kill -0 "$(cat "$PIDFILE")" 2>/dev/null; then
  echo "Backend già attivo (PID $(cat "$PIDFILE")) su http://127.0.0.1:$PORT"; exit 0
fi
rm -f "$PIDFILE"

if lsof -nP -iTCP:"$PORT" -sTCP:LISTEN >/dev/null 2>&1; then
  echo "[ERRORE] La porta $PORT è già usata da: $(lsof -nP -iTCP:"$PORT" -sTCP:LISTEN | awk 'NR==2{print $1" (PID "$2")"}')"
  echo "Chiudi quel programma oppure cambia backend.port in $("$VENV_PY" -m meetlocalai --check-config | sed 's/^OK: //')"
  exit 1
fi

nohup "$VENV_PY" -m meetlocalai >> "$LOGS_DIR/backend.stdout.log" 2>&1 &
echo $! > "$PIDFILE"

for _ in $(seq 1 30); do
  if curl -s -m 1 -H 'X-MeetLocalAI: 1' "http://127.0.0.1:$PORT/api/v1/health" >/dev/null 2>&1; then
    echo "Backend attivo (PID $(cat "$PIDFILE")) su http://127.0.0.1:$PORT"
    exit 0
  fi
  if ! kill -0 "$(cat "$PIDFILE")" 2>/dev/null; then break; fi
  sleep 0.5
done
echo "[ERRORE] Il backend non risponde. Ultime righe di log:"
tail -n 20 "$LOGS_DIR/backend.stdout.log" "$LOGS_DIR/backend.log" 2>/dev/null || true
exit 1
