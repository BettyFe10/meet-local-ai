# Pubblicare e condividere il repository (GitHub privato)

## Regole
- Il repository contiene **solo codice e documentazione**. Mai: audio, trascrizioni, riassunti, modelli, `config.json` locale, log, report diagnostici (`env_report*.txt`). Il `.gitignore` li esclude già.
- Nessuna API key o password: il progetto non ne usa.
- Prima di ogni push: `git status` e controllare che non compaiano file inattesi.

## Prima pubblicazione (una volta sola)
1. Su github.com → **New repository** → nome `meet-local-ai` → **Private** → *non* aggiungere README/.gitignore/licenza (esistono già).
2. Nel Terminale del Mac:
   ```bash
   cd ~/MeetLocalAI/app
   git remote add origin https://github.com/<UTENTE-O-ORGANIZZAZIONE>/meet-local-ai.git
   git push -u origin main
   ```
   Autenticazione: al primo push GitHub chiede le credenziali. Con HTTPS serve un *Personal Access Token* (non la password) oppure si usa GitHub CLI (`brew install gh` → `gh auth login`).
3. GitHub → repository → **Settings → Collaborators** → invitare il collega.

## Aggiornamenti successivi
```bash
cd ~/MeetLocalAI/app && git status && git push
```
(I commit li crea Claude alla fine di ogni fase; il push lo fai tu.)

## Il collega (Mac Apple Silicon)
```bash
git clone https://github.com/<UTENTE-O-ORGANIZZAZIONE>/meet-local-ai.git ~/MeetLocalAI/app
cd ~/MeetLocalAI/app && ./install_mac.sh      # disponibile dalla Fase 14
```
Per aggiornare: `cd ~/MeetLocalAI/app && git pull` e poi rilanciare l'installer (installa solo ciò che manca).
