# ARCHITECTURE — Meet Local AI

> Stato: **definita in Fase 2 (2026-09-28)**. Nessun componente è ancora implementato: vedi TEST_RESULTS.md.
> Versione app: 0.1.0 (pre-release)

## 1. Flusso
```
Google Meet (scheda Chrome)
   │ chrome.tabCapture → audio della scheda (= altri partecipanti)
   │ getUserMedia      → microfono utente (traccia separata, opzionale)
   ▼
Chrome Extension MV3  (unica interfaccia utente)
   popup · dashboard · meeting · settings · service worker · offscreen document
   │ HTTP solo verso http://127.0.0.1:8765  (chunk audio ogni 5 s + comandi)
   ▼
Backend Python / FastAPI  (127.0.0.1:8765)
   FFmpeg → WAV 16 kHz mono → Whisper locale → LLM locale (Ollama 127.0.0.1:11434)
   ▼
~/MeetLocalAI/Meetings/YYYY-MM-DD_HH-MM_TITOLO/
```

## 2. Layout su disco
```
~/MeetLocalAI/                    ← data_root (configurabile)
  app/                            ← REPOSITORY (codice, copiabile su altro Mac)
    extension/  backend/  installer/  docs/  tests/  config/config.example.json
  Config/config.json              ← configurazione LOCALE attiva (non nel repo)
  Meetings/  Models/  Logs/  Exports/  Temp/
```
Il repository può essere clonato in **qualsiasi cartella** (convenzione consigliata: `~/MeetLocalAI/app`); script e backend ricavano il proprio percorso a runtime. Il repo è pubblicato su GitHub privato (vedi docs/GITHUB.md).
Tutti i percorsi in config usano `~` e sono espansi a runtime: nessun `/Users/<nome>` scritto nel codice.

Cartella riunione:
```
Meetings/2026-09-27_10-30_Riunione-commerciale/
  metadata.json        schema: docs/metadata.schema.json
  audio.wav            mix 16 kHz mono (per ascolto e Whisper)
  transcript.txt       [hh:mm:ss] Speaker: testo
  transcript.md        idem, formattato
  summary.md           struttura fissa (sez. 5)
  raw/tab.webm         traccia scheda (Opus) — conservata se audio.keep_raw_tracks
  raw/mic.webm         traccia microfono (se abilitata)
```
- **ID riunione = nome cartella** (niente database: la dashboard legge i `metadata.json`).
- Titolo sanitizzato: lettere/numeri/`-`/`_`, max 60 caratteri, accenti rimossi; collisione → suffisso `_2`, `_3`.
- Rinominare il titolo cambia solo `metadata.title`, non la cartella.

## 3. Chrome Extension (MV3)
| File | Ruolo |
|---|---|
| `manifest.json` | permessi: `tabCapture`, `offscreen`, `storage`; host: `https://meet.google.com/*`, `http://127.0.0.1:8765/*`; `key` fissa → ID estensione stabile su ogni computer |
| `popup.html/js` | stato (PRONTO / REGISTRAZIONE ATTIVA + timer), titolo opzionale, INIZIA / TERMINA, APRI DASHBOARD |
| `service_worker.js` | macchina a stati, badge "REC" sull'icona, crea/chiude l'offscreen document |
| `offscreen.html/js` | unico punto dove vive l'audio: MediaRecorder (webm/opus, timeslice 5 s), riproduce l'audio della scheda all'utente (tabCapture altrimenti lo silenzia), invia i chunk |
| `dashboard.html/js` | elenco riunioni (data, ora, titolo, durata, stato) |
| `meeting.html/js` | TL;DR, decisioni, action items, criticità, domande aperte, prossimi passi; Trascrizione / Audio / Apri cartella / Esporta |
| `settings.html/js` | impostazioni; pulsante "Abilita microfono" (concede il permesso una volta, l'offscreen non può chiederlo) |

Stato estensione (`chrome.storage.session`): `idle | starting | recording | stopping | error` + `meetingId`, `startedAt`.
Impostazioni leggere in `chrome.storage.local`; impostazioni di elaborazione nel `config.json` del backend (via API).

**Avvio:** click INIZIA nel popup (gesto utente) → verifica scheda attiva `meet.google.com/xxx-xxxx-xxx` → `POST /meetings` → `tabCapture.getMediaStreamId` → offscreen avvia registrazione → badge REC.
**Registrazione visibile sempre:** badge REC + indicatore di cattura nativo di Chrome + timer nel popup. Nessun avvio automatico.
**Backend irraggiungibile durante la registrazione:** i chunk restano in coda in memoria (limite configurabile) e vengono ritentati; oltre il limite si avvisa l'utente. Da implementare in Fase 6.

## 4. API backend (prefisso `/api/v1`, JSON salvo dove indicato)
| Metodo | Percorso | Descrizione |
|---|---|---|
| GET | `/health` | `{status, version, ffmpeg, whisper:{available,engine,model}, llm:{available,model}}` |
| GET | `/status` | registrazione/elaborazione in corso |
| GET / PUT | `/config` | legge / aggiorna (parziale) la configurazione non sensibile |
| POST | `/meetings` | `{title?, meet_code?, tracks:["tab","mic"]}` → `{id, status:"recording"}` |
| POST | `/meetings/{id}/chunks?track=tab\|mic&seq=N` | corpo binario `audio/webm`; append idempotente per `seq` |
| POST | `/meetings/{id}/stop` | `{client_duration_seconds}` → avvia pipeline in coda |
| GET | `/meetings?limit=&offset=` | elenco per dashboard (ordinato per data desc) |
| GET | `/meetings/{id}` | metadata |
| PATCH | `/meetings/{id}` | `{title}` |
| GET | `/meetings/{id}/summary` | `text/markdown` |
| GET | `/meetings/{id}/transcript?format=txt\|md` | testo |
| GET | `/meetings/{id}/audio` | `audio/wav`, supporta HTTP Range |
| GET | `/meetings/{id}/export?format=md\|txt` | download; copia anche in `Exports/` |
| POST | `/meetings/{id}/reprocess` | `{steps:["transcribe","summarize"]}` |
| POST | `/meetings/{id}/open-folder` | apre la cartella nel Finder |
| POST | `/open-data-root` | apre `~/MeetLocalAI` nel Finder |

Nessun endpoint di cancellazione nella v1 (le riunioni si eliminano dal Finder).

Errori: `{error_code, user_message, detail_logged:true}`. Messaggi utente fissi: "Backend offline.", "Whisper locale non disponibile.", "Modello locale non disponibile."; dettagli tecnici solo nei log.

## 5. Pipeline di elaborazione
Stati: `recording → stopped → converting → transcribing → summarizing → completed` · `error` (con `error.step`) · `interrupted` (backend riavviato durante la registrazione; l'audio ricevuto resta recuperabile con reprocess).
1. **converting** — FFmpeg: `raw/*.webm` → WAV 16 kHz mono per traccia + `audio.wav` mix.
2. **transcribing** — Whisper su ciascuna traccia; unione per timestamp. Etichette: traccia mic → "Microfono locale", traccia scheda → "Speaker 1..N" (o "Partecipanti" senza diarizzazione). Nessun nome inventato.
3. **summarizing** — Ollama, prompt vincolato al formato del brief; trascrizioni lunghe → sintesi a blocchi + unione. Sezioni non determinabili → "Non chiaramente determinabile dalla trascrizione."
- Una sola elaborazione alla volta (coda FIFO); Whisper e LLM mai contemporaneamente (RAM 16 GB).
- Tempi e risorse salvati in `metadata.performance`.

## 6. Sicurezza e privacy
- Bind **solo** su 127.0.0.1; rifiuto di `host` diversi in config.
- Controllo header `Host` (127.0.0.1/localhost:porta) contro DNS rebinding.
- CORS consentito solo a `chrome-extension://<ID stabile>`; richieste con `Origin` di siti web → 403. Header custom obbligatorio `X-MeetLocalAI: 1` (forza il preflight).
- `llm.base_url` accettato solo se loopback: impossibile inviare trascrizioni a un server remoto per errore.
- Log rotanti; nessun contenuto di trascrizioni nei log (`log_transcript_content:false`).
- Nessuna telemetria, nessuna API key.

## 7. Configurazione
`config/config.example.json` (nel repo) → copiato in `~/MeetLocalAI/Config/config.json` al primo avvio/installazione se assente. Il backend fonde i valori mancanti con i default dell'esempio (upgrade senza perdere modifiche).
Sezioni: `paths`, `backend`, `audio`, `transcription` (`engine/model: auto` = scelti dal benchmark), `llm`, `summary`, `logging`.

## 8. Rischi noti
- Se l'utente usa gli altoparlanti (non cuffie) il microfono ricapta gli altri partecipanti → frasi duplicate. Consigliate cuffie; eventuale deduplica in Fase 8.
- tabCapture silenzia la scheda: l'offscreen deve reinviare l'audio all'uscita (verifica in Fase 6).
- Il permesso microfono per l'offscreen document va concesso da una pagina dell'estensione (settings).
- Diarizzazione vera (più persone nella traccia scheda) potrebbe richiedere modelli pesanti: valutazione in Fase 8, non bloccante.
