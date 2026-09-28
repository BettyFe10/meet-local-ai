# TODO — Meet Local AI

Legenda: [x] fatto · [ ] da fare · (U) richiede azione dell'utente

## FASE 1 — Analisi hardware e ambiente ✅
- [x] Rilevare modello Mac, CPU, GPU, RAM, macOS
- [x] Verificare spazio disco
- [x] Verificare Python, pip, Homebrew, FFmpeg, Node, git
- [x] Verificare Ollama / Whisper
- [x] Verificare strumenti audio e dispositivi
- [x] Verificare versione Chrome
- [x] Verificare porte locali occupate
- [x] Creare file di checkpoint

## FASE 2 — Architettura e struttura progetto ✅
- [x] Decisioni D-001, D-007 confermate; D-010…D-016 aggiunte
- [x] Creare struttura cartelle: extension/ backend/ installer/ docs/ tests/ config/
- [x] Creare struttura dati `~/MeetLocalAI/{Meetings,Models,Logs,Config,Exports,Temp}`
- [x] config.example.json + config.json (senza segreti)
- [x] Definire contratto API backend (endpoint, formati) in ARCHITECTURE.md
- [x] Definire schema metadata.json
- [x] .gitignore (esclude audio, modelli, config.json locale, venv)
- [x] Inizializzare repository git locale

## Pubblicazione
- [ ] (U) Creare repo privato `meet-local-ai` su GitHub e fare il primo push (docs/GITHUB.md)
- [ ] (U) Invitare il collega come collaboratore
- [ ] Decidere la licenza prima di un'eventuale apertura (D-020)
- [ ] Fase 13: controllo automatico "nessun dato personale nei file tracciati" nei test

## FASE 3 — Backend minimo (PROSSIMA)
- [ ] (U) Eseguire script di setup Python (venv con python3.12 o 3.13)
- [ ] FastAPI su 127.0.0.1:8765 con /api/v1/health e /api/v1/status
- [ ] Caricamento config con merge sui default + validazione (host loopback, llm.base_url loopback)
- [ ] Middleware sicurezza: Host check, CORS estensione, header X-MeetLocalAI
- [ ] Test pytest backend
- [ ] Logging rotante in ~/MeetLocalAI/Logs
- [ ] start_backend.sh / stop_backend.sh

## FASE 4–16
- [ ] Vedi ordine fasi nel brief (Extension minima → Comunicazione → Audio → Whisper → Trascrizione → LLM → Summary → Dashboard → File → Test → Installer → UI → Documentazione)

## Installazioni previste (NON ancora eseguite)
- [ ] (U) `brew install ffmpeg` — Fase 6/7
- [ ] (U) Ollama — Fase 9
- [ ] Motore Whisper (scelta dopo benchmark) — Fase 7
- [ ] Modello Whisper scelto — Fase 7
- [ ] Modello LLM scelto — Fase 9
