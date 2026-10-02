# Meet Local AI

Registra, trascrive e sintetizza le riunioni **Google Meet** interamente **sul proprio Mac**: estensione Chrome + backend locale + Whisper e modello linguistico locali. Audio, trascrizioni e verbali non vengono mai inviati a servizi cloud. Gratuito: nessun abbonamento, nessuna API key.

```
Google Meet → estensione Chrome → backend su 127.0.0.1 → Whisper locale → modello locale → ~/MeetLocalAI/Meetings/
```

## Cosa fa
- **INIZIA / TERMINA** dal popup dell'estensione mentre sei in una riunione Meet
- Registra l'audio della riunione e, se abilitato, il tuo microfono (tracce separate)
- Trascrive in italiano con orari e due etichette: "Microfono locale" (tu) e "Partecipanti" (gli altri)
- Scrive un verbale con sezioni fisse: TL;DR, Decisioni, Action items, Problemi / criticità, Informazioni importanti, Domande aperte, Prossimi passi
- Dashboard: ricerca, ascolto dell'audio, rinomina, esportazione (Markdown, TXT, stampa/PDF), eliminazione (nel Cestino)

## Requisiti
- Mac con Apple Silicon (M1 o successivi), 16 GB di RAM consigliati
- Google Chrome, Homebrew
- ~12 GB liberi per strumenti e modelli + ~170 MB per ora di riunione

## Installazione
```bash
git clone <URL-del-repository> ~/MeetLocalAI/app
cd ~/MeetLocalAI/app && ./install_mac.sh
```
Senza git: scarica lo ZIP e apri `Installa Meet Local AI.command` (clic destro → Apri).

Poi si carica l'estensione in Chrome (cartella `extension/`). Passo passo: **[SETUP-NEW-COMPUTER.md](SETUP-NEW-COMPUTER.md)**.

## Documentazione
| Per chi usa l'app | |
|---|---|
| [docs/GUIDA-UTENTE.md](docs/GUIDA-UTENTE.md) | come si registra, cosa si trova dopo, pulsanti e avvisi |
| [docs/PRIVACY.md](docs/PRIVACY.md) | dove stanno i dati, cosa usa la rete, consenso dei partecipanti |
| [docs/LIMITI-NOTI.md](docs/LIMITI-NOTI.md) | cosa non fa, cosa non è stato ancora provato |
| [docs/BACKUP.md](docs/BACKUP.md) | backup e spostamento delle riunioni |
| [SETUP-NEW-COMPUTER.md](SETUP-NEW-COMPUTER.md) | installazione, aggiornamento, disinstallazione, problemi |

| Per chi lo mantiene | |
|---|---|
| [ARCHITECTURE.md](ARCHITECTURE.md) | componenti, API, flusso di elaborazione |
| [DECISIONS.md](DECISIONS.md) | scelte tecniche e motivazioni |
| [TEST_RESULTS.md](TEST_RESULTS.md) | cosa è stato provato, dove, con quale esito (incluso ciò che è NON TESTATO) |
| [PROJECT_STATUS.md](PROJECT_STATUS.md) · [TODO.md](TODO.md) | stato e attività aperte |
| [THIRD_PARTY.md](THIRD_PARTY.md) | componenti di terze parti e licenze |
| [docs/GITHUB.md](docs/GITHUB.md) | pubblicazione sul repository privato |

## Comandi utili
```bash
./diagnose.sh          # stato dei componenti (nessun contenuto delle riunioni nel rapporto)
./start_backend.sh     # avvia il backend (di norma parte da solo al login)
./stop_backend.sh      # lo ferma fino al prossimo login
./uninstall_mac.sh     # disinstalla senza toccare le riunioni
backend/.venv/bin/python -m pytest   # test automatici
```

## Struttura
| Cartella | Contenuto |
|---|---|
| `extension/` | Estensione Chrome MV3 (unica interfaccia utente) |
| `backend/` | Backend Python/FastAPI, solo su 127.0.0.1 |
| `installer/` | Script per componente (richiamati da `install_mac.sh`) e benchmark |
| `config/` | `config.example.json` (la configurazione attiva è in `~/MeetLocalAI/Config/`) |
| `docs/` | Guide e schema dei metadata |
| `tests/` | Test automatici (backend, estensione, repository) |

I dati (riunioni, modelli, log, configurazione) stanno **fuori dal repository**, in `~/MeetLocalAI/`.

## Stato
Versione 0.1.0, completa e in uso. Prove effettuate e limiti: [TEST_RESULTS.md](TEST_RESULTS.md), [docs/LIMITI-NOTI.md](docs/LIMITI-NOTI.md).

Licenza: uso interno, nessuna licenza open source assegnata (vedi DECISIONS D-020).
