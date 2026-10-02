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

## FASE 7 — Whisper locale ✅
- [x] (U) Installare FFmpeg (`brew install ffmpeg`)
- [x] Conversione raw/*.webm → WAV 16 kHz mono per traccia + audio.wav mix
- [x] Benchmark mlx-whisper vs whisper.cpp (large-v3-turbo; fallback small/medium) su audio italiano: velocità, RAM, qualità
- [x] Scaricare solo il modello scelto in ~/MeetLocalAI/Models
- [x] Integrare nel backend + health "Whisper disponibile"

- [x] (U) Ricreare il venv senza mlx/torch

## FASE 8 — Trascrizione completa ✅
- [x] Pipeline automatica dopo TERMINA: converting → transcribing (coda FIFO, una alla volta)
- [x] Trascrizione per traccia e unione per timestamp; etichette "Microfono locale" / "Partecipanti" (D-015), nessun nome inventato
- [x] transcript.txt + transcript.md con [hh:mm:ss]; metadata (motore, modello, tempi, RTF)
- [x] Misurare velocità su ≥10 min (RTF ~0,06–0,11; 1 h ≈ 10 min)
- [ ] Ottimizzazioni facoltative: beam size, VAD con parametri diversi (tempi più fini) — solo se servirà
- [x] Filtrare allucinazioni tipiche su silenzio; pulizia WAV temporanei
- [x] Riprocessare riunioni già registrate (endpoint reprocess)

- [ ] (U) Confermare che dopo il ritorno a "senza VAD" la trascrizione di RIUNIONE-DI-TEST è tornata come prima
- [ ] Avviso in tempo reale durante la registrazione se la traccia della riunione resta muta (oggi solo a posteriori)

## FASE 9 — LLM locale ✅
- [x] Ricerca modelli multilingue con licenza permissiva (Apache 2.0) per 16 GB
- [x] Client Ollama locale, blocco modelli cloud, server su richiesta
- [x] Benchmark su riunione fittizia con verità nota + riunione reale + testo lungo
- [x] Scelta: gemma4:e4b per 16 GB (D-037)
- [x] (U) Modello definitivo installato (gemma4:e4b)
- [x] RAM reale dei processi Ollama misurata: ~4,3–6,4 GB
- [ ] Fascia 8 GB (gemma4:e2b) NON TESTATA; qwen3:4b scartato (non rispetta think:false, output in inglese)

## FASE 10 — Summary ✅
- [x] Passo `summarizing` → `summary.md`, stato `completed`; fallimento LLM non blocca la trascrizione
- [x] Prompt v3 a due passaggi: impegni in prima persona, formato action item con etichette
- [x] Controllo dell'output + un nuovo tentativo; normalizzazione sezioni
- [x] Riunioni lunghe: sintesi a blocchi + unione
- [x] Endpoint summary + sezioni nella pagina riunione + "Rigenera sintesi"
- [ ] Opzione "qualità massima" (gemma4:12b) nelle impostazioni, con avviso su RAM/tempi — Fase 15
- [ ] Qualità: temi rimandati a volte omessi; impegni impliciti a volte promossi ad attività → valutare ancora il prompt o gemma4:12b
- [ ] Provare la sintesi su una riunione reale lunga (≥30 min) — NON TESTATA

## FASE 11 — Dashboard (PROSSIMA)
- [ ] Elenco riunioni rifinito: ricerca, ordinamento, stato/avanzamento in tempo reale, avvisi
- [ ] Pagina riunione: player audio (`GET /meetings/{id}/audio` con Range), rinomina titolo, Apri cartella
- [ ] Indicatore di elaborazione in corso (coda) anche nel popup

## FASE 12–16
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
