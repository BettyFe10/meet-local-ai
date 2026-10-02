# Meet Local AI

Registra, trascrive e sintetizza le riunioni **Google Meet** interamente **sul proprio Mac**: estensione Chrome + backend locale + Whisper e LLM locali. Nessun audio, trascrizione o riassunto viene inviato a servizi cloud.

> **Stato: IN SVILUPPO — non ancora utilizzabile.** Avanzamento in [PROJECT_STATUS.md](PROJECT_STATUS.md), attività in [TODO.md](TODO.md).

## Requisiti
- Mac con Apple Silicon (M1 o successivi), 16 GB di RAM consigliati
- Google Chrome, Homebrew
- ~12 GB liberi per strumenti e modelli + ~170 MB per ora di riunione

## Installazione
```bash
git clone <URL-del-repository> ~/MeetLocalAI/app
cd ~/MeetLocalAI/app && ./install_mac.sh
```
Poi si carica l'estensione in Chrome (cartella `extension/`). Guida passo passo: [SETUP-NEW-COMPUTER.md](SETUP-NEW-COMPUTER.md).
Diagnostica: `./diagnose.sh` · Disinstallazione: `./uninstall_mac.sh`

I dati (riunioni, modelli, log, configurazione) vivono **fuori dal repository** in `~/MeetLocalAI/` e non vengono mai committati.

## Struttura
| Cartella | Contenuto |
|---|---|
| `extension/` | Estensione Chrome MV3 (unica interfaccia utente) |
| `backend/` | Backend Python/FastAPI su 127.0.0.1 |
| `installer/` | Script di installazione e diagnostica |
| `config/` | `config.example.json` (la config attiva è in `~/MeetLocalAI/Config/`) |
| `docs/` | Schema metadata, guide |
| `tests/` | Test automatici |

Documentazione di progetto: [ARCHITECTURE.md](ARCHITECTURE.md) · [DECISIONS.md](DECISIONS.md) · [TEST_RESULTS.md](TEST_RESULTS.md)
