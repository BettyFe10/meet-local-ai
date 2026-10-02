# Installare Meet Local AI su un nuovo Mac

Tempo: 15–40 minuti (quasi tutto download). Dopo l'installazione l'app funziona **senza Internet** (a parte Google Meet stesso).

## Requisiti
| | Minimo | Note |
|---|---|---|
| Mac | Apple Silicon (M1 o successivi) | i Mac Intel non sono supportati |
| RAM | 16 GB consigliati | 12–23 GB → modello `gemma4:e4b`; da 24 GB → `gemma4:12b`; sotto 12 GB → `gemma4:e2b` (**non testato**) |
| Disco | ~12 GB liberi | ~3 GB programmi, 1,5 GB trascrizione, 6–9 GB modello di sintesi; poi ~170 MB per ora di riunione |
| Software | Google Chrome, Homebrew | Homebrew: https://brew.sh |

Provato su: Mac mini M4 16 GB (macOS 26). **Non ancora provato** su altri Mac: vedi TEST_RESULTS.md.

## 1. Scaricare il progetto
```bash
mkdir -p ~/MeetLocalAI
git clone <URL-del-repository-privato> ~/MeetLocalAI/app
```
La cartella deve essere `~/MeetLocalAI/app` (non Scrivania/Documenti/Download: macOS le protegge e l'avvio automatico non funzionerebbe).

## 2. Installare
```bash
cd ~/MeetLocalAI/app && ./install_mac.sh
```
Lo script controlla il Mac, chiede conferma, poi installa: ambiente Python, FFmpeg, whisper.cpp con il modello di trascrizione, Ollama con il modello di sintesi adatto alla RAM, avvio automatico del backend. Alla fine esegue la diagnostica: deve comparire **"✓ Nessun problema rilevato."**

Si può rilanciare in qualsiasi momento: riprende da dove si era fermato (anche i download). Solo controllo, senza installare: `./install_mac.sh --check`.

## 3. Caricare l'estensione in Chrome (a mano, una volta)
1. Chrome → `chrome://extensions`
2. Attivare **Modalità sviluppatore** (in alto a destra)
3. **Carica estensione non pacchettizzata** → scegliere `~/MeetLocalAI/app/extension`
4. Fissare l'icona **Meet Local AI** nella barra
5. Icona → **Impostazioni** → **Abilita microfono** (Chrome chiede il permesso una volta)

L'ID dell'estensione deve essere `lpdaoidkipjcdboiepcogiopcnhohiaa` (è fisso: se è diverso, è stata caricata la cartella sbagliata).

## 4. Prova
1. Aprire una riunione su `meet.google.com`
2. Icona dell'estensione → deve mostrare **PRONTO** → **INIZIA**
3. Parlare per un minuto → **TERMINA**
4. Dopo poco la riunione compare nella dashboard con trascrizione e sintesi

## Se qualcosa non va
```bash
~/MeetLocalAI/app/diagnose.sh
```
Indica cosa manca e il comando per sistemarlo. Il rapporto (`~/MeetLocalAI/Logs/diagnose_report.txt`) non contiene titoli né contenuti delle riunioni e si può inviare a chi dà assistenza.

| Messaggio | Cosa fare |
|---|---|
| Backend offline. | `~/MeetLocalAI/app/start_backend.sh` |
| Whisper locale non disponibile. | `~/MeetLocalAI/app/installer/setup_whisper.sh` |
| Modello locale non disponibile. | `~/MeetLocalAI/app/installer/setup_llm.sh` |
| Porta 8765 occupata | cambiare `backend.port` in `~/MeetLocalAI/Config/config.json`, riavviare il backend e mettere la stessa porta nelle Impostazioni dell'estensione |

## Aggiornare
```bash
cd ~/MeetLocalAI/app && git pull && ./install_mac.sh --yes
```
Poi `chrome://extensions` → icona di ricarica sull'estensione.

## Portare le riunioni da un altro Mac
Copiare la cartella `~/MeetLocalAI/Meetings` (vedi [docs/BACKUP.md](docs/BACKUP.md)). I modelli non vanno copiati: li scarica l'installer.

## Disinstallare
```bash
~/MeetLocalAI/app/uninstall_mac.sh            # lascia riunioni, configurazione e modelli
~/MeetLocalAI/app/uninstall_mac.sh --models   # toglie anche i modelli (~8 GB)
```
Le riunioni non vengono mai cancellate dallo script.

## Cosa viene installato e dove
| Cosa | Dove |
|---|---|
| Codice | `~/MeetLocalAI/app` |
| Ambiente Python | `~/MeetLocalAI/app/backend/.venv` |
| Riunioni, modelli, log, configurazione | `~/MeetLocalAI/{Meetings,Models,Logs,Config,Exports,Temp}` |
| FFmpeg, whisper.cpp, Ollama | Homebrew (`/opt/homebrew`) |
| Avvio automatico | `~/Library/LaunchAgents/local.meetlocalai.backend.plist` |

Nessun permesso di amministratore, nessun driver audio, nessun servizio cloud.
