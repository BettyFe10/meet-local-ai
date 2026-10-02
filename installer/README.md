# installer/

Script per singolo componente. Di norma non si lanciano a mano: li richiama `../install_mac.sh`.
Sono tutti rilanciabili (installano solo ciò che manca).

| Script | Cosa fa |
|---|---|
| `setup_backend.sh` | ambiente Python (`backend/.venv`), dipendenze, cartelle dati, test |
| `setup_whisper.sh [modello]` | FFmpeg, whisper.cpp e modello di trascrizione (predefinito `large-v3-turbo`) |
| `setup_llm.sh [modello]` | Ollama e modello di sintesi (predefinito: in base alla RAM; es. `setup_llm.sh gemma4:12b`) |
| `launchagent.sh install\|uninstall\|status` | avvio automatico del backend al login |
| `whisper_benchmark.sh`, `llm_benchmark.sh` | benchmark usati in sviluppo (scaricano modelli: non servono all'uso normale) |
| `phase1_env_check.sh` | rilevazione dell'ambiente usata nella Fase 1 |

Nella cartella principale: `install_mac.sh`, `uninstall_mac.sh`, `diagnose.sh`, `start_backend.sh`, `stop_backend.sh`.
