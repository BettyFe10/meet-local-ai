#!/bin/bash
# Meet Local AI — icona nella barra dei menu per accendere/spegnere il backend e vederne lo stato.
# Uso: installer/menubar.sh install | uninstall | status
# install: compila una piccola app (serve il compilatore Swift degli strumenti da riga di comando di Apple),
#          la mette in ~/Applications e la fa partire a ogni login. Nessun permesso di amministratore.
set -euo pipefail
LABEL="local.meetlocalai.menubar"
REPO="$(cd "$(dirname "$0")/.." && pwd)"
APP="$HOME/Applications/Meet Local AI Backend.app"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
DOMAIN="gui/$(id -u)"
VENV_PY="$REPO/backend/.venv/bin/python"

stop_agent(){ launchctl bootout "$DOMAIN/$LABEL" 2>/dev/null || true; }

case "${1:-}" in
  install)
    [ "$(uname -s)" = "Darwin" ] || { echo "Solo macOS."; exit 1; }
    SWIFTC="$(xcrun -f swiftc 2>/dev/null || true)"
    if [ -z "$SWIFTC" ]; then
      echo "Manca il compilatore Swift. Installa gli strumenti di Apple con:  xcode-select --install"
      echo "poi rilancia questo comando."; exit 1
    fi
    [ -x "$VENV_PY" ] || { echo "Esegui prima: $REPO/install_mac.sh"; exit 1; }
    PORT="$(cd "$REPO/backend" && "$VENV_PY" -m meetlocalai --print-port)"
    stop_agent
    BUILD="$(mktemp -d)"
    sed -e "s|__REPO__|$REPO|g" -e "s|__PORT__|$PORT|g" "$REPO/installer/menubar/main.swift" > "$BUILD/main.swift"
    echo "Compilo l'icona…"
    SDK="$(xcrun --sdk macosx --show-sdk-path 2>/dev/null || true)"
    if [ -z "$SDK" ] || ! xcrun --sdk macosx swiftc -O -sdk "$SDK" -o "$BUILD/MeetLocalAIBackend" "$BUILD/main.swift" -framework AppKit; then
      echo
      echo "Compilazione non riuscita. Di solito gli strumenti da riga di comando di Apple sono vecchi rispetto a macOS."
      echo "Aggiornali da Impostazioni di Sistema → Generali → Aggiornamento Software, oppure reinstallali con:"
      echo "  sudo rm -rf /Library/Developer/CommandLineTools && xcode-select --install"
      echo "Versione attuale: $(pkgutil --pkg-info=com.apple.pkg.CLTools_Executables 2>/dev/null | awk '/version/{print $2}') · SDK: ${SDK:-non trovato}"
      exit 1
    fi
    mkdir -p "$APP/Contents/MacOS"
    cp "$BUILD/MeetLocalAIBackend" "$APP/Contents/MacOS/MeetLocalAIBackend"
    cat > "$APP/Contents/Info.plist" <<PL
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>CFBundleName</key><string>Meet Local AI Backend</string>
  <key>CFBundleIdentifier</key><string>$LABEL</string>
  <key>CFBundleExecutable</key><string>MeetLocalAIBackend</string>
  <key>CFBundlePackageType</key><string>APPL</string>
  <key>CFBundleShortVersionString</key><string>1.0</string>
  <key>LSUIElement</key><true/>
</dict></plist>
PL
    codesign --force -s - "$APP" >/dev/null 2>&1 || true
    mkdir -p "$(dirname "$PLIST")"
    cat > "$PLIST" <<PL
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>$LABEL</string>
  <key>ProgramArguments</key><array><string>$APP/Contents/MacOS/MeetLocalAIBackend</string></array>
  <key>RunAtLoad</key><true/>
  <key>ProcessType</key><string>Interactive</string>
</dict></plist>
PL
    plutil -lint "$PLIST" >/dev/null
    launchctl bootstrap "$DOMAIN" "$PLIST"
    echo "Fatto: in alto a destra nella barra dei menu compare \"MLA 🟢\" (acceso) o \"MLA ⚪️\" (spento)."
    echo "Partirà da sola a ogni accesso. Per toglierla: $REPO/installer/menubar.sh uninstall" ;;
  uninstall)
    stop_agent
    [ -f "$PLIST" ] && rm -f "$PLIST"
    case "$APP" in "$HOME/Applications/Meet Local AI Backend.app") [ -d "$APP" ] && rm -rf "$APP" ;; esac
    echo "Icona della barra dei menu rimossa." ;;
  status)
    launchctl print "$DOMAIN/$LABEL" >/dev/null 2>&1 && echo "Icona attiva." || echo "Icona non attiva." ;;
  *) echo "Uso: $0 install | uninstall | status"; exit 2 ;;
esac
