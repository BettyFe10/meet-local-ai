# TEST_RESULTS — Meet Local AI

Regola: ogni voce è **SUPERATO**, **FALLITO** o **NON TESTATA**. Nulla è dichiarato funzionante senza verifica.

## Fase 1 — 2026-09-28
| Test | Esito | Note |
|---|---|---|
| Script diagnostico ambiente eseguito su macOS | SUPERATO | Output in `~/MeetLocalAI/Logs/env_report_fase1.txt` |
| Cartella `~/MeetLocalAI` accessibile in lettura/scrittura da Claude | SUPERATO | |
| Porta 8765 libera | SUPERATO (al 28/09) | Da riverificare all'avvio backend |
| Porta 11434 (Ollama) libera | SUPERATO (al 28/09) | |
| Backend | NON TESTATA | Non ancora creato |
| Chrome Extension | NON TESTATA | Non ancora creata |
| Cattura audio tabCapture | NON TESTATA | Fase 6 |
| Whisper | NON TESTATA | Non installato |
| LLM / Ollama | NON TESTATA | Non installato |

## Fase 2 — 2026-09-28
| Test | Esito | Note |
|---|---|---|
| `config.example.json` e `Config/config.json` sono JSON validi | SUPERATO | Python json |
| host backend = 127.0.0.1 e llm.base_url loopback nel config di default | SUPERATO | |
| `metadata.example.json` valido contro `metadata.schema.json` | SUPERATO | jsonschema |
| Cartelle dati create in `~/MeetLocalAI` | SUPERATO | |
| Commit git iniziale senza file audio/config locale | SUPERATO | verificato con `git ls-files` |
| Nessun dato personale/macchina nei file tracciati da git (grep utente, dispositivi, /Users/) | SUPERATO | unico `/Users/utente` nell'esempio metadata (fittizio) |
| Push su GitHub | NON TESTATA | Da eseguire dall'utente |
| Backend / Extension / Audio / Whisper / LLM | NON TESTATA | Non ancora implementati |

## Fase 3 — 2026-09-28/29
| Test | Ambiente | Esito | Note |
|---|---|---|---|
| Suite pytest `tests/backend` (31 test: config, API, sicurezza, CLI) | VM Linux, Python 3.10 | SUPERATO | |
| Suite pytest `tests/backend` (31 test) | **Mac M4, Python 3.12.6** | SUPERATO | eseguita da setup_backend.sh |
| setup_backend.sh prima esecuzione + riesecuzione (idempotenza) | VM Linux | SUPERATO | |
| setup_backend.sh prima esecuzione | Mac | SUPERATO | venv creato, dipendenze installate |
| start_backend.sh / avvio doppio ("già attivo") / stop / stop doppio | VM Linux | SUPERATO | |
| start_backend.sh → health risponde | Mac | SUPERATO | |
| Richiesta senza header X-MeetLocalAI → 403 | Mac | SUPERATO | |
| Backend in ascolto SOLO su 127.0.0.1:8765 | Mac (lsof) | SUPERATO | |
| stop_backend.sh | Mac | SUPERATO | |
| health: FFmpeg / Whisper / LLM segnalati non disponibili con messaggio utente | Mac | SUPERATO | corretto: non ancora installati |
| Porta 8765 occupata da altro programma → messaggio chiaro | — | NON TESTATA | logica presente in start_backend.sh |
| Chrome Extension | — | NON TESTATA | Fase 4 |

## Fase 4 — 2026-09-29 / 10-01
| Test | Ambiente | Esito | Note |
|---|---|---|---|
| Suite pytest completa (49 test: backend + statici estensione) | VM Linux | SUPERATO | inclusi sintassi JS (node --check), assenza script inline/URL remoti, ID = allowlist |
| Endpoint /meetings e /meetings/{id} (lista ordinata, metadata corrotti ignorati, ID non validi/traversal → 404) | VM Linux | SUPERATO | |
| Estensione caricata in Chrome 153 (non pacchettizzata) con ID atteso | Mac | SUPERATO | confermato dall'utente |
| Popup / dashboard / impostazioni contattano il backend | Mac | SUPERATO | 3 richieste health dall'estensione nel log, nessun rifiuto di Origin |
| Allowlist estensione attiva (nessun avviso "modalità sviluppo" all'avvio) | Mac | SUPERATO | log 2026-10-01 |
| Popup "Backend offline." a backend fermo; "Riunione rilevata" su scheda Meet | Mac | SUPERATO | prova manuale dell'utente ("fatto"), non verificabile dai log |
| Consumo backend a riposo | Mac M4 | MISURATO | ps: 0,1% CPU, 33,5 MB RSS dopo 60 s; top: 0,2% CPU, 36 MB |
| Port personalizzata da Impostazioni | — | NON TESTATA | |

## Fase 5 — 2026-10-01
| Test | Ambiente | Esito | Note |
|---|---|---|---|
| Suite pytest completa (65: backend, registrazione, statici, 3 suite Node) | VM Linux | SUPERATO | |
| setup_backend.sh con nuova dipendenza (jsonschema) + suite | Mac | SUPERATO | dipendenza installata, backend riavviato |
| API registrazione: start/chunk/dup/gap/limite/stop/rename/riavvio→interrupted→ripresa | VM Linux | SUPERATO | test_recording.py |
| Metadata generati conformi a metadata.schema.json (start e stop) | VM Linux | SUPERATO | |
| Controller estensione (start, doppio start, offline, stop, chiusura scheda, resync) | Node 22 | SUPERATO | controller.test.mjs |
| Uploader chunk (ordine, ritentativi offline, seq_gap, not_recording, limite coda) | Node 22 | SUPERATO | uploader.test.mjs |
| INIZIA → cartella + metadata `recording` → TERMINA → `stopped` con durata | Mac + Chrome 153 | SUPERATO | 2026-10-01_19-09_Riunione-pcm-iaqh-vds (10 s) |
| Stop automatico alla chiusura della scheda Meet | Mac + Chrome | SUPERATO | 2ª riunione chiusa senza popup aperto (log) |
| Badge REC, timer persistente alla riapertura del popup, "Apri" riunione, dashboard | Mac + Chrome | SUPERATO | prova manuale dell'utente |
| Invio chunk reali dall'estensione | — | NON TESTATA | nessuna sorgente audio fino alla Fase 6 |
| Backend offline durante la registrazione (coda) in Chrome reale | — | NON TESTATA | coperto solo da test unitari |
| Durate < 1 min mostrate come "0 min" | — | CORRETTO | ora "10 s" (ui.test.mjs) |

## Avvio automatico (LaunchAgent) — 2026-10-01
| Test | Ambiente | Esito | Note |
|---|---|---|---|
| Plist generato valido (chiavi, percorsi con spazi, ProcessType ≠ Background) | VM Linux | SUPERATO | test_launchagent.py |
| install: plist creato, `plutil -lint` ok, backend risponde | Mac | SUPERATO | state=running, runs=1 |
| Crash simulato (kill -9) → riavvio automatico | Mac | SUPERATO | runs=2, PID 58344 → 58432 (entro 35 s) |
| stop_backend.sh con LaunchAgent → resta spento | Mac | SUPERATO | health non risponde |
| start_backend.sh con LaunchAgent (kickstart) | Mac | SUPERATO | "Backend attivo (avvio automatico)" |
| Avvio al login / dopo riavvio del Mac | — | NON TESTATA | da verificare al prossimo riavvio |
| uninstall | — | NON TESTATA | |
| Suite completa | VM Linux | SUPERATO | 68 test |

## Benchmark
Nessun benchmark ancora eseguito (previsto in Fase 7 per Whisper e Fase 9 per LLM).
