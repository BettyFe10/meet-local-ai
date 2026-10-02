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

## Fase 6 — 2026-10-01
| Test | Ambiente | Esito | Note |
|---|---|---|---|
| Suite completa (71 pytest; 31 test JS in 4 suite Node) | VM Linux | SUPERATO | session.test.mjs con MediaRecorder/AudioContext finti |
| Offscreen/session/http usano solo chrome.runtime | statico | SUPERATO | |
| Chiamata Meet reale (Mac + telefono), tracce tab+mic, 69 s | Mac + Chrome 153 | SUPERATO | tab.webm 556 KB, mic.webm 555 KB, 14 blocchi/traccia, ~68,5 s decodificati senza errori |
| Livelli audio registrazione reale | ffmpeg (VM, file locali) | SUPERATO | tab: media -21,2 dB; mic: media -29,8 dB; clipping trascurabile (0,03% / 0,001%) |
| Separazione tracce / eco del telefono nel microfono | analisi inviluppi | SUPERATO | attività tab 55%, mic 25%, sovrapposte 6%; correlazione inviluppi ≈ 0 |
| Audio della riunione udibile dall'utente durante la cattura | Mac | SUPERATO | nessun problema segnalato dall'utente |
| Prima prova (19-25): traccia scheda | Mac | ANOMALIA | silenzio digitale -91 dB per 57 s (mic con audio): causa da chiarire |
| Microfono negato → solo scheda con avviso | Node (fake) | SUPERATO | non provato in Chrome reale |
| Fine cattura / chiusura scheda durante registrazione reale | — | NON TESTATA | coperta da test unitari |

## Fase 7 — 2026-10-01
| Test | Ambiente | Esito | Note |
|---|---|---|---|
| Suite completa (85 test) | VM Linux | SUPERATO | conversione/mix reali con ffmpeg, whisper-cli finto, benchmark end-to-end |
| Installazione whisper.cpp 1.9.4 + modelli | Mac | SUPERATO | download modelli ~1 min ciascuno |
| Conversione 2 tracce (68,6 s) | Mac | SUPERATO | 0,25 s |
| Benchmark motori | Mac M4 | SUPERATO | tabella sotto |
| Riepilogo benchmark senza testo delle riunioni nei log | VM + Mac | SUPERATO | solo numeri in Logs/ |
| Velocità su riunioni lunghe (≥10 min) | — | NON TESTATA | Fase 8 |

## Fase 8 — 2026-10-01
| Test | Ambiente | Esito | Note |
|---|---|---|---|
| Suite completa (98 test) | VM Linux | SUPERATO | pipeline end-to-end con ffmpeg reale e whisper-cli finto; worker automatico + recupero al riavvio |
| Elaborazione automatica al riavvio delle 4 riunioni in coda | Mac | SUPERATO | 2 senza audio → errore "Nessun audio registrato…"; 2 → trascritte |
| RIUNIONE-DI-TEST (69 s) elaborata | Mac | SUPERATO | conversione 0,24 s, trascrizione 11,6 s (RTF 0,17 incl. caricamento modello), RAM ~1,9 GB |
| Trascrizione leggibile | Mac | SUPERATO | giudizio utente: "non perfetta ma leggibile" |
| Traccia muta saltata con avviso (riunione 19-25) | Mac | SUPERATO | picco -91 dB, nessuna frase inventata |
| Allucinazione "Autore dei sottotitoli… QTSS" | Mac | CORRETTO | comparsa nella prima elaborazione, ora filtrata |
| Velocità 10 min/traccia, senza VAD | Mac M4 | MISURATO | scheda 36,5 s (RTF 0,059), mic 69,1 s (RTF 0,112) → 1 h ≈ 10 min |
| Velocità 10 min/traccia, con VAD | Mac M4 | MISURATO | scheda 31,1 s (RTF 0,050), mic 16,2 s (RTF 0,026) |
| Qualità con VAD | Mac | PEGGIORE | frasi lontane accorpate, tempi spostati → ordine tra tracce errato; utente: "andava meglio prima" → VAD disattivato |
| Trascrizione dopo ritorno a senza VAD | — | NON TESTATA | richiede riavvio + rielabora |

## Fase 9 — 2026-10-01/02
| Test | Ambiente | Esito | Note |
|---|---|---|---|
| Suite completa (114 test) | VM Linux | SUPERATO | client Ollama con server finto: blocco cloud, think off, modello mancante, scelta per RAM, health |
| Benchmark 4 modelli (download → 3 prove → rimozione) | Mac M4 16 GB | SUPERATO | tabella sotto; un solo modello alla volta su disco |
| Nessun modello cloud utilizzabile | VM (test) | SUPERATO | nomi con "cloud" rifiutati prima di ogni chiamata |
| Installazione definitiva gemma4:e4b + health "Modello locale ✓" | Mac | NON TESTATA | in attesa dell'utente |
| RAM reale del modello | Mac | NON MISURATA | |
| Funzionamento su MacBook Pro M2 Pro 16 GB (collega) | — | NON TESTATA | atteso pari o migliore (GPU e banda di memoria superiori) |

## Benchmark
### LLM per la sintesi — 2026-10-01, Mac mini M4 16 GB, Ollama 0.35.0, prompt v1
Prove: A) riunione fittizia (657 parole, ~1900 token) con verità nota; C) testo lungo ~12.000 token (≈50 min di riunione), contesto 16k.

| Modello (licenza) | A: tempo | A: token/s | C: tempo | Decisioni (4) | Action item (4) | TikTok rimandato trattato bene | Invenzioni |
|---|---|---|---|---|---|---|---|
| **gemma4:e4b** (Apache 2.0) | **35 s** | 26 | **69 s** | 4/4 | 3/4 (manca "comunicare alla direzione"); un item senza campo Scadenza | sì (in Domande aperte) | nessuna |
| gemma4:12b (Apache 2.0) | 81 s | 11 | 171 s | 4/4 | **4/4** (attribuisce correttamente a "Microfono locale") | sì | nessuna |
| qwen3:8b (Apache 2.0) | 52 s | 18 | 147 s | 4 in 3 punti | 3/4 + 1 attività non assegnata nella riunione (fotografo) | omesso | lieve ("i fornitori") |
| qwen3:4b (Apache 2.0) | 197 s | 27 | 279 s | — | — | — | SCARTATO: ignora `think:false`, 5.000 token di ragionamento in inglese |

Prova B (chiamata reale di 69 s, trascrizione imperfetta): gemma4:e4b non inventa decisioni né attività ("Non chiaramente determinabile…"); gemma4:12b crea un action item interpretando male una frase.
Memoria: il valore di `/api/ps` per i modelli Gemma (≈0,3–1 GB) NON è attendibile → RAM reale NON MISURATA (da fare con `llm measure`); qwen3:8b ≈ 5,9–7,1 GB.
Valutazione umana (Claude) dei verbali confrontati con `tests/fixtures/riunione_fittizia_marketing.expected.json`.

### Whisper — 2026-10-01, Mac mini M4 16 GB, riunione di test 68,6 s (tracce: scheda + microfono), modello large-v3-turbo
| Motore | Traccia | Tempo | Rapporto realtime | RAM max* | Segmenti / caratteri |
|---|---|---|---|---|---|
| mlx-whisper 0.4.3 (mlx 0.32.3) | scheda | 33,8 s | 0,49 | 638 MB | 21 / 554 |
| mlx-whisper | microfono | 4,1 s | 0,06 | 1755 MB | 8 / 393 |
| whisper.cpp 1.9.4 (Metal) | scheda | 21,8 s | 0,32 | 1910 MB | 12 / 581 |
| whisper.cpp | microfono | 6,5 s | 0,10 | 1854 MB | 8 / 399 |

*RSS del processo (`/usr/bin/time -l`); con MLX parte della memoria GPU unificata può non essere conteggiata.
Note: tempi comprensivi del caricamento modello; mlx ha eseguito per primo (possibile costo di compilazione iniziale). Campione breve: non rappresentativo di riunioni di 1 ora.
Qualità (lettura delle trascrizioni di prova): molto simile; whisper.cpp produce frasi intere e punteggiatura più regolare, mlx frammenta di più e ha qualche errore grammaticale in più. Nessuna allucinazione sui silenzi lunghi del microfono con entrambi.
