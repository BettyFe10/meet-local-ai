#!/bin/bash
# Meet Local AI — Fase 1: diagnostica ambiente (SOLA LETTURA).
# Uso: bash installer/phase1_env_check.sh > ~/MeetLocalAI/Logs/env_report.txt 2>&1
# Il report contiene dati del computer (nomi dispositivi, porte): NON va nel repository.
export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"
s(){ echo; echo "===== $1 ====="; }
v(){ printf "%-14s" "$1:"; if command -v "$1" >/dev/null 2>&1; then echo "$(command -v $1) | $($1 ${2:---version} 2>&1 | head -1)"; else echo "NON INSTALLATO"; fi; }
s DATA; date
s MACOS; sw_vers; uname -m
s HARDWARE; sysctl -n hw.model machdep.cpu.brand_string hw.ncpu hw.perflevel0.physicalcpu hw.perflevel1.physicalcpu 2>/dev/null; echo "RAM_GB: $(( $(sysctl -n hw.memsize)/1073741824 ))"
system_profiler SPHardwareDataType SPDisplaysDataType 2>/dev/null | grep -E "Model Name|Model Identifier|Chip|Total Number of Cores|Memory|Chipset Model|Metal|Cores:"
s DISCO; df -h ~ /
s TOOLS
v brew; v python3; v pip3; v ffmpeg -version; v node; v npm; v git; v ollama; v whisper-cli -h; v uv; v conda; v pyenv; v docker
ls -1 /opt/homebrew/bin/python3* /usr/local/bin/python3* 2>/dev/null
xcode-select -p 2>&1
s PY_PKGS; python3 -m pip list 2>/dev/null | grep -iE "whisper|mlx|torch|fastapi|uvicorn|ctranslate|pyannote|sounddevice" || echo "nessuno"
s OLLAMA; command -v ollama >/dev/null && (ollama list 2>&1; curl -s -m 3 http://127.0.0.1:11434/api/version) || echo "ollama assente"
s BREW_PKGS; command -v brew >/dev/null && brew list --formula 2>/dev/null | grep -iE "ffmpeg|python|node|whisper|ollama|blackhole|switchaudio|portaudio|sox"; command -v brew >/dev/null && brew list --cask 2>/dev/null | grep -iE "blackhole|loopback|soundflower|ollama|chrome"
s AUDIO; ls -1 /Library/Audio/Plug-Ins/HAL 2>/dev/null; system_profiler SPAudioDataType 2>/dev/null | grep -E "^        [A-Za-z].*:$|Default (Input|Output|System Output) Device|Transport"
s CHROME; for a in "/Applications/Google Chrome.app" "$HOME/Applications/Google Chrome.app"; do [ -d "$a" ] && defaults read "$a/Contents/Info" CFBundleShortVersionString; done
s PORTE_LOCALI; lsof -nP -iTCP -sTCP:LISTEN 2>/dev/null | awk 'NR>1{print $1, $9}' | sort -u | head -40
s MEETLOCALAI; ls -la ~/MeetLocalAI 2>&1
