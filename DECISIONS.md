# DECISIONS — Meet Local AI

Nota Fase 2: l'utente ha dato il via libera alla Fase 2 senza obiezioni alle decisioni proposte → D-001 e D-007 confermate; le altre restano da validare con test nelle fasi indicate.

Stato: **CONFERMATA** = attiva · **PROVVISORIA** = da confermare/validare nella fase indicata.

| ID | Data | Decisione | Motivazione | Stato |
|---|---|---|---|---|
| D-001 | 2026-09-28 | Repository codice in `~/MeetLocalAI/app`, dati in `~/MeetLocalAI/{Meetings,Models,Logs,Config,Exports,Temp}` | Un'unica cartella da concedere a Claude e da fare backup; codice e dati restano separati e il repo è copiabile. Percorso dati configurabile in config.json | CONFERMATA (Fase 2) |
| D-002 | 2026-09-28 | Cattura audio con `chrome.tabCapture` + offscreen document, **senza BlackHole** come prima scelta | Cattura l'audio della scheda Meet senza toccare l'output audio del Mac; nessun driver da installare; più portabile. BlackHole resta piano B documentato | PROVVISORIA (Fase 6) |
| D-003 | 2026-09-28 | Microfono utente registrato come traccia separata via getUserMedia; se inaffidabile → solo mix | Permette di distinguere "microfono locale" da "altri partecipanti" senza diarizzazione pesante | PROVVISORIA (Fase 6) |
| D-004 | 2026-09-28 | Motore Whisper: benchmark tra **mlx-whisper** e **whisper.cpp** (Metal), non faster-whisper | Su Apple Silicon faster-whisper non usa la GPU; mlx e whisper.cpp sì. Modelli candidati: large-v3-turbo, fallback small/medium. Nessun download prima del benchmark | PROVVISORIA (Fase 7) |
| D-005 | 2026-09-28 | LLM via **Ollama**, modello multilingue ~7–9B quantizzato Q4 (≈5 GB) | 16 GB RAM condivisi + 29 GB disco liberi: modelli ≥14B sconsigliati. Modello specifico scelto e testato sull'italiano in Fase 9 | PROVVISORIA (Fase 9) |
| D-006 | 2026-09-28 | Python dedicato in venv (`app/backend/.venv`), interprete 3.12 o 3.13 già presenti | Nessuna installazione aggiuntiva di Python; 3.12 come ripiego se 3.13 dà problemi di compatibilità | PROVVISORIA (Fase 3) |
| D-007 | 2026-09-28 | Porta backend predefinita **8765** su 127.0.0.1, configurabile | 5000/7000 occupate da ControlCenter (AirPlay); 8765 libera al 28/09 | CONFERMATA (Fase 2) |
| D-008 | 2026-09-28 | audio.wav salvato a 16 kHz mono (formato Whisper); eventuale originale compresso opzionale | ~115 MB/ora contro ~660 MB/ora a 48 kHz stereo: essenziale con 29 GB liberi | PROVVISORIA (Fase 6/12) |
| D-009 | 2026-09-28 | Le installazioni di sistema (brew, Ollama) saranno eseguite dall'utente tramite script forniti | Claude accede al Mac solo via cartella `~/MeetLocalAI` (VM isolata) e non può digitare nel Terminale | CONFERMATA |
| D-010 | 2026-09-28 | `config.json` attivo in `~/MeetLocalAI/Config/`, nel repo solo `config/config.example.json`; percorsi con `~` | Il repo resta copiabile senza impostazioni locali; stesso file su ogni Mac | CONFERMATA |
| D-011 | 2026-09-28 | ID riunione = nome cartella; nessun database | File normali, facili da copiare/backup; la dashboard legge i metadata.json | CONFERMATA |
| D-012 | 2026-09-28 | Registrazione a chunk di 5 s (webm/opus) inviati subito al backend e salvati in `raw/` | In caso di crash si perdono al massimo pochi secondi; niente audio grande in memoria o in chrome.storage | CONFERMATA |
| D-013 | 2026-09-28 | Sicurezza API locale: Host check, CORS solo sull'ID estensione (fissato con `key` nel manifest), header custom obbligatorio | Impedisce a siti web aperti nel browser di usare il backend su 127.0.0.1 | CONFERMATA |
| D-014 | 2026-09-28 | `llm.base_url` accettato solo se loopback | Garanzia tecnica che la sintesi non esca dal Mac | CONFERMATA |
| D-015 | 2026-09-28 | Etichette speaker per traccia: mic → "Microfono locale", scheda → "Speaker N"/"Partecipanti" | Separazione affidabile senza inventare nomi; diarizzazione avanzata valutata in Fase 8 | PROVVISORIA (Fase 8) |
| D-016 | 2026-09-28 | Nessun endpoint di cancellazione nella v1 | Riduce il rischio di perdita dati; si elimina dal Finder | CONFERMATA |
| D-017 | 2026-09-28 | Il repository funziona da **qualsiasi cartella** di clone: script e backend ricavano il proprio percorso a runtime; i dati stanno sempre in `paths.data_root` (default `~/MeetLocalAI`) | Il progetto sarà pubblicato su GitHub e clonato dai colleghi; nessun percorso della macchina di sviluppo nel codice | CONFERMATA |
| D-018 | 2026-09-28 | Pubblicazione su **GitHub privato**; nel repo solo codice/documentazione, mai dati di riunioni né report diagnostici della macchina | Richiesta utente; il report di Fase 1 (nomi dispositivi, utente) è stato spostato in `~/MeetLocalAI/Logs/` e rimosso dalla cronologia git prima del primo push | CONFERMATA |
| D-019 | 2026-09-28 | Target: **Mac Apple Silicon** (sviluppo su M4 16 GB; collega su Apple Silicon). Scelta modelli automatica in base alla RAM rilevata dall'installer (es. 8 GB → modelli più piccoli) | Il collega può avere hardware diverso; niente modelli fissi | CONFERMATA (soglie in Fase 7/9) |
| D-020 | 2026-09-28 | Licenza: nessuna licenza open-source per ora (repo privato, uso interno); da decidere prima di un'eventuale apertura. THIRD_PARTY.md resta obbligatorio | Evita impegni prematuri; le licenze dei componenti vanno comunque verificate per la distribuzione ai colleghi | PROVVISORIA |
