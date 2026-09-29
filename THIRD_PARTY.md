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

## Previsti (non ancora installati)
| Componente | Fase | Nota licenza da verificare |
|---|---|---|
| FFmpeg (Homebrew) | 6/7 | LGPL/GPL a seconda della build: usato come programma esterno, non incorporato |
| Motore Whisper (mlx-whisper o whisper.cpp) | 7 | entrambi MIT (da confermare alla versione scelta) |
| Modelli Whisper (OpenAI) | 7 | MIT |
| Ollama | 9 | MIT |
| Modello LLM | 9 | **dipende dal modello**: preferire licenze permissive (es. Apache-2.0) per l'uso aziendale |
