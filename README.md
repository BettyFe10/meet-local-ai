# Meet Local AI

Registra, trascrive e sintetizza le riunioni **Google Meet** interamente **sul proprio Mac**: estensione Chrome + backend locale + Whisper e LLM locali. Nessun audio, trascrizione o riassunto viene inviato a servizi cloud.

> **Stato: IN SVILUPPO — non ancora utilizzabile.** Avanzamento in [PROJECT_STATUS.md](PROJECT_STATUS.md), attività in [TODO.md](TODO.md).

## Requisiti (previsti)
- Mac con Apple Silicon (M1 o successivi), macOS recente
- Google Chrome
- ~10 GB liberi per strumenti e modelli + spazio per le registrazioni (~115 MB per ora di audio)
- Homebrew

## Installazione su un nuovo Mac
Verrà descritta in `SETUP-NEW-COMPUTER.md` (Fase 14). In sintesi sarà:
```bash
git clone <URL-del-repository> ~/MeetLocalAI/app   # la cartella può essere qualsiasi
cd ~/MeetLocalAI/app && ./install_mac.sh
```
Poi: Chrome → `chrome://extensions` → Modalità sviluppatore → "Carica estensione non pacchettizzata" → cartella `extension/`.

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
