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

## Benchmark
Nessun benchmark ancora eseguito (previsto in Fase 7 per Whisper e Fase 9 per LLM).
