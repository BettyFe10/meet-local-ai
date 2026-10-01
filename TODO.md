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

## FASE 3 — Backend minimo ✅
- [x] (U) Eseguire script di setup Python (venv con python3.12 o 3.13)
- [x] FastAPI su 127.0.0.1:8765 con /api/v1/health e /api/v1/status
- [x] Caricamento config con merge sui default + validazione (host loopback, llm.base_url loopback)
- [x] Middleware sicurezza: Host check, CORS estensione, header X-MeetLocalAI
- [x] Test pytest backend
- [x] Logging rotante in ~/MeetLocalAI/Logs
- [x] start_backend.sh / stop_backend.sh

## FASE 4 — Chrome Extension minima ✅
- [x] manifest.json MV3 con key fissa, permessi minimi
- [x] popup (PRONTO / Backend offline), dashboard, meeting, settings (vuoti ma navigabili)
- [x] service worker con macchina a stati
- [x] ID estensione in backend.allowed_extension_ids
- [x] (U) Caricare l'estensione in Chrome

## FASE 5 — Comunicazione Extension → Backend ✅
- [x] API backend: POST /meetings (crea cartella + metadata), POST /meetings/{id}/chunks, POST /meetings/{id}/stop, PATCH titolo, GET /status con registrazione attiva
- [x] Service worker: macchina a stati idle → starting → recording → stopping, badge REC, timer
- [x] Popup: INIZIA / TERMINA attivi (senza audio reale), stato persistente se si chiude il popup
- [x] Gestione backend offline durante la registrazione (coda + messaggio)
- [x] Test API e messaggistica

## Dopo la Fase 5 ✅
- [x] Avvio automatico backend con LaunchAgent (D-024): install/uninstall reversibili, start/stop_backend.sh compatibili

## FASE 6 — Cattura audio ✅
- [ ] (U) Verificare che dopo un riavvio/login del Mac il popup mostri PRONTO senza Terminale
- [x] Permessi tabCapture + offscreen; offscreen document con MediaRecorder (webm/opus, 5 s) + ChunkUploader
- [x] Riproduzione dell'audio della scheda all'utente (tabCapture la silenzia)
- [x] Microfono come traccia separata (permesso da settings.html), fallback solo scheda
- [x] Stop: flush della coda prima di chiudere la riunione
- [x] (U) Test con una vera chiamata Meet

- [ ] Chiarire la prima prova con traccia scheda muta (2026-10-01_19-25)
- [ ] Rilevare automaticamente una traccia della scheda completamente muta e avvisare l'utente durante la registrazione
- [ ] Backend offline durante una registrazione reale (coda) — NON TESTATA in Chrome

## FASE 7 — Whisper locale (PROSSIMA)
- [ ] (U) Installare FFmpeg (`brew install ffmpeg`)
- [ ] Conversione raw/*.webm → WAV 16 kHz mono per traccia + audio.wav mix
- [ ] Benchmark mlx-whisper vs whisper.cpp (large-v3-turbo; fallback small/medium) su audio italiano: velocità, RAM, qualità
- [ ] Scaricare solo il modello scelto in ~/MeetLocalAI/Models
- [ ] Integrare nel backend + health "Whisper disponibile"

## FASE 8–16
- [ ] Vedi ordine fasi nel brief (Trascrizione completa → Trascrizione → LLM → Summary → Dashboard → File → Test → Installer → UI → Documentazione)

## Installazioni previste (NON ancora eseguite)
- [ ] (U) `brew install ffmpeg` — Fase 6/7
- [ ] (U) Ollama — Fase 9
- [ ] Motore Whisper (scelta dopo benchmark) — Fase 7
- [ ] Modello Whisper scelto — Fase 7
- [ ] Modello LLM scelto — Fase 9

## Debito tecnico / note
- [ ] Starlette segnala che `httpx` per TestClient è deprecato (suggerisce `httpx2`): solo test, nessun impatto runtime. Rivalutare quando si aggiornano le dipendenze.
- [ ] Ollama: keep_alive breve per liberare la RAM dopo la sintesi (Fase 9)
- [ ] Dipendenze transitive (es. rpds-py) non fissate: valutare un lock file completo in Fase 14.
