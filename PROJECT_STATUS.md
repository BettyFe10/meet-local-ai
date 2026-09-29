# PROJECT_STATUS — Meet Local AI

**Ultimo aggiornamento:** 2026-09-29
**Fase corrente:** FASE 3 — Backend minimo → ✅ COMPLETATA (verificata sul Mac)
**Prossima fase:** FASE 4 — Chrome Extension minima (NON ANCORA INIZIATA)

## Fase 3 — cosa è stato fatto
- `backend/meetlocalai/`: config (default da esempio + override locale, validazione host/porta/LLM loopback), log rotanti in `Logs/backend.log`, sicurezza (Host, Origin estensione, header `X-MeetLocalAI`), messaggi utente fissi, API `/api/v1/health` e `/api/v1/status`, CLI `python -m meetlocalai [--print-port|--print-dir|--check-config]`.
- Nessuna UI web esposta (docs/openapi disabilitati).
- Script: `installer/setup_backend.sh` (idempotente: venv + dipendenze + cartelle + test), `start_backend.sh`, `stop_backend.sh`.
- 31 test pytest in `tests/backend/`.
- Sul Mac: venv creato con Python 3.12.6 in `backend/.venv`; test superati; backend avviato, risponde, ascolta solo su 127.0.0.1:8765, fermato correttamente.

## Come si usa ora
```bash
cd ~/MeetLocalAI/app && ./start_backend.sh     # avvia
./stop_backend.sh                              # ferma
./installer/setup_backend.sh                   # (ri)prepara l'ambiente, rilanciabile
```

## Prossima attività (FASE 4 — Chrome Extension minima)
1. `extension/manifest.json` MV3 con `key` fissa (ID stabile), permessi `tabCapture`, `offscreen`, `storage`, host Meet + 127.0.0.1:8765.
2. popup/dashboard/meeting/settings minimi (HTML/CSS/JS vanilla), service worker, stato PRONTO/Backend offline.
3. Aggiungere l'ID estensione a `backend.allowed_extension_ids` (fine della modalità sviluppo).
4. **(U)** Caricare l'estensione in Chrome (`chrome://extensions` → Modalità sviluppatore → Carica non pacchettizzata → `extension/`).

## Percorsi
- Root progetto (repository codice): `~/MeetLocalAI/app/`
- Root dati (verrà popolata in Fase 2/12): `~/MeetLocalAI/` → `Meetings/ Models/ Logs/ Config/ Exports/ Temp/`
- Configurazione attiva: `~/MeetLocalAI/Config/config.json`
- Report ambiente Fase 1: `~/MeetLocalAI/Logs/env_report_fase1.txt` (fuori dal repo: contiene dati della macchina)
- Script diagnostico usato in Fase 1: `installer/phase1_env_check.sh`

## Fase 1 — lavoro completato
- Analisi completa di hardware, macOS, software, audio, Chrome, porte e spazio disco (dati sotto = Mac di sviluppo; il collega avrà hardware proprio).
- Creati: PROJECT_STATUS.md, TODO.md, ARCHITECTURE.md, DECISIONS.md, TEST_RESULTS.md.

## Ambiente rilevato sul Mac di sviluppo (28/09/2026)
| Voce | Valore |
|---|---|
| Mac | Mac mini (Mac16,10) — Apple M4 |
| CPU | 10 core (4 performance + 6 efficiency) |
| GPU | Apple M4 integrata, 10 core, Metal 4 |
| RAM | 16 GB (memoria unificata CPU/GPU) |
| macOS | 26.5.2 (build 25F84), arm64 |
| Disco | 228 GB, **29 GB liberi (85% usato)** ⚠️ |
| Homebrew | 6.0.22 (`/opt/homebrew`, nativo arm64) — nessun pacchetto rilevante installato |
| Python | 3.13.5 python.org (`/usr/local/bin/python3`); presenti anche 3.11 e 3.12 |
| pip | 26.1 |
| Xcode CLT | presenti (`/Library/Developer/CommandLineTools`) |
| Node / npm | v23.7.0 / 10.9.2 |
| git | 2.50.1 |
| FFmpeg | **NON INSTALLATO** |
| Ollama | **NON INSTALLATO** |
| Whisper (qualsiasi) | **NON INSTALLATO** |
| uv / conda / pyenv / docker | non installati (non necessari) |
| Pacchetti Python rilevanti | nessuno (whisper, mlx, torch, fastapi… assenti) |
| Chrome | 153.0.8010.53 |
| Driver audio virtuali | Microsoft Teams Audio, Parrot (ParrotAudioPlugin). **BlackHole NON presente** |
| Input predefinito | USB 2.0 Camera |
| Output predefinito | Altoparlanti Mac mini |
| Porte occupate rilevanti | 5000 e 7000 (ControlCenter/AirPlay), 3283, 27384, 51000, 55032 |
| Porta Ollama 11434 | libera |

## Test superati
- Esecuzione script diagnostico su macOS: OK (report generato).
- Accesso lettura/scrittura a `~/MeetLocalAI` da Claude: OK.

## Problemi aperti / rischi
1. **Spazio disco limitato (29 GB liberi).** Stima ingombro progetto: ~8–10 GB (FFmpeg, venv, Whisper, Ollama + un LLM ~5 GB). Audio: WAV 16 kHz mono ≈ 115 MB/ora di riunione. Consigliato liberare spazio o prevedere archiviazione esterna.
2. **16 GB RAM condivisi**: Whisper e LLM vanno eseguiti in sequenza (non in parallelo) e il modello LLM deve stare intorno a 7–9B quantizzato (Q4). Chrome + Meet occupano già RAM durante la riunione.
3. Python 3.13 è recente: la compatibilità di alcune librerie (es. mlx-whisper, eventuale diarizzazione) va verificata in Fase 3/7; in alternativa si usa 3.12 (già presente).
4. Le mie azioni sul Mac passano da una VM che vede solo `~/MeetLocalAI`: installazioni di sistema (brew, Ollama) e il caricamento dell'estensione in Chrome richiederanno che l'utente esegua comandi/script forniti.

## Operazioni che richiedono intervento dell'utente
- (Opzionale, quando vuoi) Pubblicare su GitHub privato seguendo `docs/GITHUB.md` (creare repo + `git push`).
- In Fase 4: caricare l'estensione in Chrome (istruzioni fornite).

## Punto esatto da cui riprendere
Dire: **"Riprendi il progetto Meet Local AI"** → leggere questo file e TODO.md → iniziare FASE 4.
- Nota: le operazioni git dalla VM di Claude richiedono il permesso di cancellazione su ~/MeetLocalAI (file temporanei/lock di git).
