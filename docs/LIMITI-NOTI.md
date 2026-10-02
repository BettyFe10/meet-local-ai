# Limiti noti

Aggiornato: 2026-10-02. Il dettaglio delle prove è in [TEST_RESULTS.md](../TEST_RESULTS.md).

## Cosa non fa
- **Solo Mac con Apple Silicon** e **solo Google Meet in Chrome**. Niente Windows, Intel, Zoom, Teams, app Meet per telefono.
- **Non riconosce le persone.** Distingue solo "Microfono locale" (chi registra) e "Partecipanti" (tutti gli altri insieme). I nomi non vengono dedotti.
- **Non trascrive in tempo reale**: la trascrizione parte dopo TERMINA.
- **Una registrazione alla volta.**
- **Lingua**: impostata sull'italiano. Riunioni in altre lingue o miste non sono state provate.
- **Non avvisa i partecipanti** della registrazione: va fatto a voce (vedi [PRIVACY.md](PRIVACY.md)).
- **I file non sono cifrati** dall'app.
- L'estensione si installa a mano in "Modalità sviluppatore" (non è sul Chrome Web Store) e Chrome può ricordarlo all'avvio.
- Per avviare o riparare i componenti serve ogni tanto il Terminale.

## Qualità
- **Trascrizione**: leggibile ma non perfetta; peggiora con audio scadente, voci sovrapposte, nomi propri e sigle. Sui silenzi Whisper può inventare brevi frasi: i casi tipici sono filtrati, altri possono sfuggire.
- **Senza cuffie** il microfono riprende anche gli altri: frasi duplicate tra le due etichette.
- **Ordine delle battute**: le due tracce sono trascritte separatamente e unite per orario; in scambi molto rapidi l'ordine può risultare leggermente sfalsato.
- **Verbale** (modello `gemma4:e4b` sui Mac da 16 GB): nelle prove non ha inventato fatti, ma può **omettere un tema rimandato** e può **trasformare in attività un impegno solo accennato**. Va sempre riletto. Il modello più grande (`gemma4:12b`) è più completo ma 2–3 volte più lento sui 16 GB.
- Le riunioni molto lunghe vengono sintetizzate a blocchi e poi unite: qualche dettaglio può perdersi.

## Non ancora provato dal vivo (NON TESTATO)
- Installazione su un **secondo Mac** (in particolare MacBook Pro M2 Pro 16 GB) e su un Mac senza Homebrew/Python.
- **Riunione reale di 30 minuti o più** (provate solo registrazioni brevi e testi lunghi simulati).
- **Backend che si ferma durante una registrazione** (coperto solo da test automatici).
- **Avvio automatico dopo il riavvio** del Mac.
- Mac con **meno di 12 GB** di RAM (modello `gemma4:e2b`) e con **24 GB o più** (`gemma4:12b` automatico).
- Opzione **"Qualità massima"** usata davvero; **avviso di scheda muta** in una riunione reale; **Stampa / PDF**; ripristino di una riunione dal Cestino.
- Opzioni secondarie degli script (`--models`, `--no-llm`, `--no-autostart`).

## Tecnici
- Se sul Mac c'era già Ollama, i modelli di sintesi vengono cercati anche nella sua cartella standard (`~/.ollama/models`). Se un Ollama già aperto usa una cartella modelli diversa da quella in cui si trova il modello scelto, la sintesi fallisce e la riunione resta "Trascritta".
- Mac senza microfono integrato (Mac mini, Mac Studio): senza un microfono esterno si registra solo l'audio degli altri partecipanti.
- I log contengono il nome della cartella della riunione (che include il titolo), mai il contenuto.
- Se Chrome si chiude o l'estensione viene ricaricata durante la registrazione, la riunione risulta "Interrotta": l'audio già inviato resta, il resto è perso.
- La prima registrazione fatta in sviluppo aveva la traccia della riunione muta per cause non chiarite; da allora c'è l'avviso di scheda muta.
- Le dipendenze Python indirette non hanno versione bloccata (solo quelle dirette).
- Aggiornamenti di Chrome, macOS, Homebrew, whisper.cpp od Ollama possono richiedere adeguamenti: dopo un aggiornamento eseguire `./diagnose.sh` e i test.
