# THIRD_PARTY — componenti di terze parti

Aggiornato: 2026-09-29. Licenze da riverificare prima di ogni distribuzione.
Obblighi generali per licenze MIT/BSD: mantenere l'avviso di copyright e il testo della licenza se si ridistribuisce il componente (es. in un futuro .dmg che include il venv).

## Backend (installati in `backend/.venv`, non inclusi nel repository)
| Componente | Versione | Progetto | Licenza | Uso |
|---|---|---|---|---|
| FastAPI | 0.141.1 | github.com/fastapi/fastapi | MIT | framework API |
| Starlette | 1.7.0 | github.com/encode/starlette | BSD-3-Clause | base di FastAPI |
| Pydantic | 2.13.5 | github.com/pydantic/pydantic | MIT | validazione dati |
| pydantic-core | 2.46.5 | github.com/pydantic/pydantic-core | MIT | dipendenza di Pydantic |
| Uvicorn | 0.54.0 | github.com/encode/uvicorn | BSD-3-Clause | server ASGI |

## Solo sviluppo/test
| Componente | Versione | Progetto | Licenza |
|---|---|---|---|
| pytest | 9.1.1 | github.com/pytest-dev/pytest | MIT |
| HTTPX | 0.28.1 | github.com/encode/httpx | BSD-3-Clause |
| jsonschema | 4.26.0 | github.com/python-jsonschema/jsonschema | MIT |

## Programmi esterni (installati con Homebrew, non inclusi nel repository)
| Componente | Versione | Progetto | Licenza | Uso / obblighi |
|---|---|---|---|---|
| FFmpeg | 9.0.2 | ffmpeg.org | LGPL-2.1+ / GPL (build Homebrew con componenti GPL) | eseguito come programma separato; non incorporato né ridistribuito |
| whisper.cpp (`whisper-cli`) | 1.9.4 | github.com/ggml-org/whisper.cpp | MIT | trascrizione; se ridistribuito, includere la licenza |
| ggml / llama.cpp / libomp | 0.25.3 / 0.5.0 / 23.1.2 | dipendenze Homebrew di whisper.cpp | MIT / MIT / Apache-2.0 con eccezione LLVM | |

## Modelli
| Modello | File | Origine | Licenza |
|---|---|---|---|
| Whisper large-v3-turbo (OpenAI), formato ggml | ggml-large-v3-turbo.bin (1,5 GB) | huggingface.co/ggerganov/whisper.cpp | MIT (pesi Whisper) |

| Gemma 4 E4B (Google), via Ollama `gemma4:e4b` | ~6 GB | ollama.com/library/gemma4 | Apache 2.0 |
| Gemma 4 12B (opzionale, ≥24 GB) `gemma4:12b` | ~8 GB | ollama.com/library/gemma4 | Apache 2.0 |

Ollama 0.35.0 (github.com/ollama/ollama, MIT) è installato con Homebrew ed eseguito come programma separato.

## Opzionali (non installati di default)
| Componente | Versione provata | Licenza | Nota |
|---|---|---|---|
| mlx-whisper | 0.4.3 | MIT | usato solo nel benchmark; richiede mlx (MIT) e torch (BSD-3) |

## Previsti (non ancora installati)
| Componente | Fase | Nota licenza da verificare |
|---|---|---|
| — | — | — |
