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

## Benchmark
Nessun benchmark ancora eseguito (previsto in Fase 7 per Whisper e Fase 9 per LLM).
