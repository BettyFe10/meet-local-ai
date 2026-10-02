# Backup e spostamento delle riunioni

Tutti i dati sono file normali dentro `~/MeetLocalAI/` (pulsante **Apri cartella MeetLocalAI** nella dashboard).

| Cartella | Contenuto | Va nel backup? |
|---|---|---|
| `Meetings/` | una cartella per riunione: `metadata.json`, `audio.wav`, `transcript.*`, `summary.md`, `raw/` | **Sì** — è l'archivio |
| `Exports/` | copie dei file esportati dall'interfaccia | facoltativo |
| `Config/` | `config.json` e la chiave di firma dell'estensione (`extension-signing-key.pem`) | **Sì** |
| `Models/` | modelli Whisper e LLM (≈8 GB) | No: si riscaricano con gli script in `app/installer/` |
| `Logs/`, `Temp/` | log e file temporanei | No |
| `Cestino/` | riunioni eliminate quando il Cestino del Mac non era disponibile | No |
| `app/` | il codice (repository git) | È su GitHub quando verrà pubblicato |

## Fare un backup
Copiare `~/MeetLocalAI/Meetings` (e `Config`) su disco esterno, NAS o cloud personale, ad esempio:
```bash
rsync -a --delete ~/MeetLocalAI/Meetings/ /Volumes/DISCO/MeetLocalAI-backup/Meetings/
cp -R ~/MeetLocalAI/Config /Volumes/DISCO/MeetLocalAI-backup/
```
`--delete` rende il backup uguale all'originale (rimuove dal backup le riunioni eliminate): toglierlo per conservare tutto.
Anche Time Machine include già queste cartelle.

## Ripristinare o spostare su un altro Mac
1. Installare l'app sul nuovo Mac (vedi `SETUP-NEW-COMPUTER.md`).
2. Copiare le cartelle delle riunioni dentro `~/MeetLocalAI/Meetings/`.
3. Aprire la dashboard: le riunioni compaiono da sole (non c'è un database: l'elenco si legge dai `metadata.json`).

## Liberare spazio
- La parte pesante è `audio.wav` (~115 MB per ora). Spostare su disco esterno le cartelle delle riunioni vecchie:
  basta rimetterle in `Meetings/` per rivederle.
- **Elimina** nella pagina della riunione sposta la cartella nel Cestino del Mac: lo spazio si libera svuotando il Cestino.
- `audio.keep_raw_tracks: false` in `Config/config.json` fa eliminare le tracce grezze (`raw/`, ~30 MB/ora per traccia)
  dopo ogni elaborazione riuscita (poi non sarà più possibile ritrascrivere con le tracce separate).
