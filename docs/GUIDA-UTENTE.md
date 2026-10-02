# Guida utente

## Prima volta
1. Installazione: vedi [SETUP-NEW-COMPUTER.md](../SETUP-NEW-COMPUTER.md).
2. Icona **Meet Local AI** in Chrome → **APRI DASHBOARD** → **Impostazioni** → **Abilita microfono** (una volta). Senza microfono viene registrata solo la voce degli altri.
3. Usa le **cuffie** quando puoi: con gli altoparlanti il microfono riprende anche gli altri e la trascrizione si sporca.

## Registrare una riunione
1. Entra nella riunione su `meet.google.com`.
2. **Avvisa i partecipanti** che stai registrando (vedi [PRIVACY.md](PRIVACY.md)).
3. Clicca l'icona dell'estensione: deve comparire **● PRONTO** e "Riunione rilevata". Scrivi un titolo se vuoi.
4. **🔴 INIZIA RIUNIONE**. Sull'icona compare **REC** e nel popup il cronometro. Puoi chiudere il popup.
5. Alla fine: icona → **■ TERMINA**. Se chiudi la scheda di Meet la registrazione si ferma da sola.

Durante la registrazione **non chiudere Chrome** e non ricaricare l'estensione.

## Dopo la riunione
L'elaborazione parte da sola: conversione → trascrizione → sintesi. Indicativamente un'ora di riunione richiede una decina di minuti di trascrizione più uno o due di sintesi (Mac con 16 GB). Puoi continuare a lavorare; il Mac può scaldarsi un po'.

Nella **dashboard** ogni riunione ha uno stato:

| Stato | Significato |
|---|---|
| ● In registrazione | la registrazione è in corso |
| In coda | registrazione chiusa, in attesa di elaborazione |
| Conversione audio… / Trascrizione… / Sintesi… | elaborazione in corso |
| ✓ Trascritta | trascrizione pronta, sintesi non (ancora) disponibile |
| ✓ Completata | trascrizione e verbale pronti |
| Errore | qualcosa non è andato: il motivo è scritto sotto; pulsante **Rielabora** |
| Interrotta | il backend o Chrome si sono chiusi durante la registrazione; l'audio già salvato resta |

## Pagina della riunione
| Pulsante | Cosa fa |
|---|---|
| ✎ Rinomina | cambia il titolo (la cartella su disco non cambia nome) |
| Trascrizione | mostra il testo con orari e chi parla |
| Audio | riascolta la registrazione |
| Apri cartella | apre la cartella della riunione nel Finder |
| Genera / Rigenera sintesi | riscrive il verbale (per esempio dopo aver cambiato modello) |
| Rielabora | rifà conversione, trascrizione e sintesi dall'audio |
| Esporta Markdown / TXT | scarica verbale + trascrizione; una copia va in `~/MeetLocalAI/Exports` |
| Stampa / PDF | apre la stampa di Chrome: scegli "Salva come PDF" |
| Elimina | sposta la riunione nel **Cestino del Mac** (recuperabile finché non lo svuoti) |

## Il verbale
Sezioni sempre presenti: TL;DR, DECISIONI, ACTION ITEMS, PROBLEMI / CRITICITÀ, INFORMAZIONI IMPORTANTI, DOMANDE APERTE, PROSSIMI PASSI. Quando nella riunione non c'è nulla per una sezione compare: *"Non chiaramente determinabile dalla trascrizione."*

Il verbale è scritto da un modello automatico: **rileggi sempre decisioni, nomi, numeri e scadenze** confrontandoli con la trascrizione o l'audio. I nomi delle persone non vengono dedotti: chi parla è indicato solo come "Microfono locale" (tu) o "Partecipanti".

## Impostazioni
- **Porta** del backend (di norma non va toccata).
- **Microfono**: permesso, interruttore "Registra anche il mio microfono", **scelta del microfono** e pulsante **Prova microfono** (mostra se la voce arriva). Se sul Mac ci sono microfoni "virtuali" di altre applicazioni, quello predefinito può essere muto: scegli dall'elenco quello vero.
- **Glossario**: nomi di persone, prodotti, sigle e termini che la trascrizione sbaglia spesso, uno per riga e scritti nel modo corretto. È un suggerimento per il riconoscimento, non una sostituzione automatica: aiuta, ma non garantisce. Vale dalla prossima trascrizione, o subito con **Rielabora** su una riunione già registrata. Metti in alto i più importanti: oltre un certo numero (circa 700 caratteri in tutto) gli ultimi non vengono usati.
- **Sintesi**: "Automatico" sceglie il modello adatto alla RAM del Mac; "Qualità massima" usa un modello più grande, più lento, da scaricare a parte (la pagina mostra il comando).

## Avvisi che puoi vedere
| Avviso | Cosa fare |
|---|---|
| Backend offline. | Terminale: `~/MeetLocalAI/app/start_backend.sh`. Se succede durante una registrazione l'audio resta in attesa nel browser e viene inviato quando il backend torna |
| Whisper locale non disponibile. | `~/MeetLocalAI/app/installer/setup_whisper.sh` |
| Modello locale non disponibile. | `~/MeetLocalAI/app/installer/setup_llm.sh` — nel frattempo le riunioni vengono solo trascritte |
| Nessun audio dalla riunione finora… | la scheda Meet è silenziata o nessuno ha ancora parlato: controlla l'icona dell'altoparlante sulla scheda |
| Microfono non disponibile… | abilitalo da Impostazioni; la registrazione prosegue con il solo audio della riunione |
| Spazio quasi esaurito | libera spazio o sposta le riunioni vecchie ([BACKUP.md](BACKUP.md)) |

Per qualsiasi altro problema: `~/MeetLocalAI/app/diagnose.sh`.

## Accendere e spegnere il backend
Il backend parte da solo a ogni accesso e a riposo consuma pochissimo. Se vuoi controllarlo tu, installa l'icona nella barra dei menu (una volta):
```bash
~/MeetLocalAI/app/installer/menubar.sh install
```
In alto a destra compare **MLA 🟢** (acceso) o **MLA ⚪️** (spento): cliccandola puoi accenderlo o spegnerlo. Se è spento l'estensione mostra "Backend offline." e non si può registrare. Dopo uno spegnimento manuale resta spento fino alla prossima accensione o al prossimo accesso al Mac.

## Dove sono i file
`~/MeetLocalAI/Meetings/AAAA-MM-GG_HH-MM_Titolo/` contiene `audio.wav`, `transcript.txt`, `transcript.md`, `summary.md`, `metadata.json` e `raw/` (tracce originali). Sono file normali: si possono aprire, copiare e archiviare a mano.
