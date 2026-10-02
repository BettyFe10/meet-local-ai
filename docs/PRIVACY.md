# Privacy e sicurezza

## In breve
- Audio, trascrizioni e verbali restano **sul Mac**, in `~/MeetLocalAI/`. Non esiste alcun server del progetto, nessun account, nessuna telemetria.
- Trascrizione (whisper.cpp) e sintesi (Ollama) girano in locale; il backend rifiuta i modelli "cloud" di Ollama e accetta solo un indirizzo Ollama su questo computer.
- La rete serve **solo all'installazione** (Homebrew, pacchetti Python, download dei modelli) e ovviamente a Google Meet per la riunione stessa.

## Cosa viene salvato e dove
| Dato | Dove | Note |
|---|---|---|
| Audio, trascrizione, verbale, metadata | `~/MeetLocalAI/Meetings/<riunione>/` | file normali, non cifrati dall'app |
| Esportazioni | `~/MeetLocalAI/Exports/` e cartella Download di Chrome | |
| Configurazione | `~/MeetLocalAI/Config/config.json` | nessuna password o chiave API |
| Log | `~/MeetLocalAI/Logs/` | eventi tecnici; **mai** trascrizioni o verbali. Contengono il nome della cartella della riunione, che include il titolo |
| Stato dell'estensione | archivio locale di Chrome | porta, preferenza microfono, stato della registrazione |

I file non sono cifrati dall'app: la protezione è quella del Mac. Si consiglia **FileVault attivo** e un account macOS con password. Chiunque abbia accesso al tuo utente macOS può leggere le riunioni.

## Come è protetto il backend locale
- Ascolta solo su `127.0.0.1`: non è raggiungibile da altri computer.
- Accetta richieste solo dall'estensione ufficiale (ID fisso) e solo con un'intestazione dedicata: le pagine web aperte nel browser non possono interrogarlo.
- L'audio per il lettore si scarica con un codice temporaneo valido solo per quella riunione.
- Non espone pagine web né documentazione delle API.

## Permessi dell'estensione
| Permesso | Perché |
|---|---|
| `tabCapture` | catturare l'audio della scheda Meet, solo dopo il tuo clic su INIZIA |
| `offscreen` | tenere attiva la registrazione anche a popup chiuso |
| `storage` | ricordare le impostazioni |
| accesso a `meet.google.com` | riconoscere che la scheda è una riunione |
| accesso a `127.0.0.1` | parlare con il backend locale |
| microfono (facoltativo) | registrare la tua voce; lo abiliti tu dalle Impostazioni |

L'estensione non legge il contenuto delle pagine, non contiene script remoti e non contatta altri indirizzi.

## Consenso dei partecipanti
Registrare una riunione significa trattare la voce e le parole di altre persone. **Informa sempre i partecipanti prima di iniziare** e registra solo se è consentito dalle regole della tua azienda e dalla normativa applicabile (in Europa, il GDPR). L'app non avvisa gli altri al posto tuo: Meet non mostra alcun indicatore quando registri con questa estensione. Conserva le registrazioni solo per il tempo necessario ed elimina quelle che non servono più.

Questa pagina descrive il funzionamento tecnico; non è un parere legale. Per l'uso in azienda senti chi si occupa di privacy.

## Eliminare i dati
- Una riunione: pulsante **Elimina** → finisce nel Cestino del Mac; è cancellata davvero quando svuoti il Cestino.
- Tutto: cestinare `~/MeetLocalAI/Meetings` (e `Exports`, `Logs`).
- I backup che hai fatto altrove vanno eliminati a parte.

## Condivisione e assistenza
`diagnose.sh` produce un rapporto senza titoli né contenuti delle riunioni, adatto a essere inviato a chi dà assistenza. Il repository del codice non contiene mai dati: un controllo automatico nei test lo verifica.
