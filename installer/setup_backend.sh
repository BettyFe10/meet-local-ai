#!/bin/bash
# Meet Local AI — prepara l'ambiente Python del backend (idempotente: rilanciabile senza danni).
# Crea backend/.venv, installa le dipendenze, crea cartelle dati e config locale, esegue i test.
# Rete usata SOLO per scaricare i pacchetti Python da PyPI.
set -euo pipefail
REPO="$(cd "$(dirname "$0")/.." && pwd)"
VENV="$REPO/backend/.venv"
export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"

say(){ printf "\n==> %s\n" "$1"; }
fail(){ printf "\n[ERRORE] %s\n" "$1" >&2; exit 1; }

say "Sistema"
OS="$(uname -s)"; ARCH="$(uname -m)"
echo "$OS $ARCH"
[ "$OS" = "Darwin" ] || echo "[AVVISO] Sistema non macOS: supportato solo per sviluppo/test."

say "Scelta interprete Python (3.10–3.13, preferito 3.12)"
PY=""
for c in python3.12 python3.13 python3.11 python3.10 python3; do
  if command -v "$c" >/dev/null 2>&1; then
    if "$c" -c 'import sys; sys.exit(0 if (3,10)<=sys.version_info[:2]<=(3,13) else 1)' 2>/dev/null; then
      if [ "$OS" = "Darwin" ] && [ "$ARCH" = "arm64" ] && [ "$("$c" -c 'import platform;print(platform.machine())')" != "arm64" ]; then
        continue   # evita interpreti Intel/Rosetta su Apple Silicon
      fi
      PY="$(command -v "$c")"; break
    fi
  fi
done
[ -n "$PY" ] || fail "Nessun Python 3.10–3.13 nativo trovato. Installa Python 3.12 da python.org o con 'brew install python@3.12'."
echo "Uso: $PY ($("$PY" --version))"

say "Ambiente virtuale: $VENV"
if [ -x "$VENV/bin/python" ] && "$VENV/bin/python" -c 'import sys' 2>/dev/null; then
  echo "Già presente, lo riuso."
else
  "$PY" -m venv "$VENV"
  echo "Creato."
fi

say "Dipendenze (backend/requirements-dev.txt)"
"$VENV/bin/python" -m pip install --quiet --upgrade pip
"$VENV/bin/python" -m pip install --quiet -r "$REPO/backend/requirements-dev.txt"
"$VENV/bin/python" -m pip list 2>/dev/null | grep -iE "^(fastapi|uvicorn|pydantic|starlette|pytest|httpx) " || true

say "Configurazione e cartelle dati"
( cd "$REPO/backend" && "$VENV/bin/python" -m meetlocalai --check-config ) || fail "Configurazione non valida (vedi messaggio sopra)."
DATA_ROOT="$(cd "$REPO/backend" && "$VENV/bin/python" -m meetlocalai --print-dir data_root)"
for d in Meetings Models Logs Config Exports Temp; do mkdir -p "$DATA_ROOT/$d"; done
echo "Dati in: $DATA_ROOT"

say "Test automatici"
if ( cd "$REPO" && "$VENV/bin/python" -m pytest -q -p no:cacheprovider ); then
  echo "TEST: SUPERATI"
else
  fail "Alcuni test sono falliti (output sopra)."
fi

say "FATTO. Avvio backend: $REPO/start_backend.sh"
