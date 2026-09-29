#!/bin/bash
# Meet Local AI — ferma il backend avviato con start_backend.sh.
set -euo pipefail
REPO="$(cd "$(dirname "$0")" && pwd)"
VENV_PY="$REPO/backend/.venv/bin/python"
[ -x "$VENV_PY" ] || { echo "Ambiente non installato: niente da fermare."; exit 0; }
cd "$REPO/backend"
PIDFILE="$("$VENV_PY" -m meetlocalai --print-dir temp_dir)/backend.pid"

if [ ! -f "$PIDFILE" ]; then echo "Backend non attivo."; exit 0; fi
PID="$(cat "$PIDFILE")"
if ! kill -0 "$PID" 2>/dev/null; then echo "Backend non attivo (PID file obsoleto rimosso)."; rm -f "$PIDFILE"; exit 0; fi
# sicurezza: termina solo se il processo è davvero il nostro backend
if ! ps -p "$PID" -o command= | grep -q "meetlocalai"; then
  echo "[AVVISO] Il PID $PID non appartiene a Meet Local AI: non lo termino. PID file rimosso."; rm -f "$PIDFILE"; exit 1
fi
kill "$PID"
for _ in $(seq 1 20); do kill -0 "$PID" 2>/dev/null || break; sleep 0.25; done
kill -0 "$PID" 2>/dev/null && kill -9 "$PID" 2>/dev/null || true
rm -f "$PIDFILE"
echo "Backend fermato."
