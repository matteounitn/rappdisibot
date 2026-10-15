# RappDisiBot

Bot Telegram per **contattare i rappresentanti DISI UniTN**: ogni studente apre
una conversazione privata con il bot, i rappresentanti rispondono da un gruppo
di lavoro e tutto resta in un unico posto.

## Come funziona

- Ogni richiesta di uno studente diventa un **topic** nella supergruppo degli
  operatori: `Nome Cognome · <user id>`.
- La conversazione è **bidirezionale**: i messaggi dello studente arrivano nel
  topic, le risposte scritte nel topic tornano allo studente in privato.
- Una sola richiesta aperta per utente: i messaggi successivi finiscono nella
  stessa conversazione.
- Un ticket si chiude con `/close` (dallo studente o dall'operatore nel topic);
  il topic viene chiuso e lo studente può aprirne uno nuovo.
- Utenti, ticket e admin sono salvati in `rappdisibot.db` (SQLite): un riavvio
  non perde nulla.

## Requisiti

- Python **≥ 3.10**
- Un bot creato con [@BotFather](https://t.me/BotFather)
- Una supergruppo con i **Topic** attivi per gli operatori

## Installazione

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Configurazione

```bash
cp .env.example .env      # segreti (api_id, api_hash, bot_token)
cp config.ini.example config.ini
```

I **segreti** stanno in `.env` (che è in `.gitignore`, quindi non finisce nel
repository) e hanno la precedenza su `config.ini`; le variabili d'ambiente reali
(`RAPPDISIBOT_BOT_TOKEN`, …) vincono su `.env`, comodo per systemd o Docker.
In `config.ini` restano le impostazioni non segrete:

```ini
[bot]
operators_chat_id = -1001234567890
admins = 11111111, 22222222
```

Se preferisci, i segreti si possono ancora mettere in `config.ini` sotto
`[pyrogram]`: vengono usati solo se `.env` e l'ambiente non li definiscono.

- **api_id / api_hash**: da <https://my.telegram.org/auth?to=apps> (crea una app,
  i valori non dipendono dal bot).
- **bot_token**: da @BotFather, in `.env` (`RAPPDISIBOT_BOT_TOKEN`). Il vecchio
  token è stato versionato in chiaro per anni (e il repository è pubblico):
  **revocalo con `/revoke` su @BotFather** e usa quello nuovo.
- **operators_chat_id**: id della supergruppo operatori (formato `-100…`). È il
  valore di partenza: un admin può sovrascriverlo a runtime con `/setgroup`
  dentro il gruppo (vedi sotto).
- **admins**: user ID Telegram degli admin iniziali, separati da virgola. Vengono
  reinseriti a ogni avvio e **non sono rimovibili** dal menu `/admin`.

`.env` e `config.ini` sono in `.gitignore`: non finiscono nel repository.

### Gruppo operatori

1. Crea una supergruppo e attiva **Topic** nelle impostazioni.
2. Aggiungi il bot come **amministratore** con il diritto **Gestisci argomenti**
   (`can_manage_topics`): serve per creare e chiudere i topic. Da amministratore
   il bot riceve anche tutti i messaggi del gruppo, indipendentemente dalla
   privacy mode di @BotFather.
3. Imposta l'id in `operators_chat_id` (valore di partenza), **oppure** — senza
   toccare il file — esegui `/setgroup` **dentro** il gruppo da parte di un
   admin: il bot verifica di essere amministratore con «Gestisci argomenti» e
   salva l'id nel database, con effetto immediato e senza riavvio.

`/setgroup` in privato mostra il gruppo attivo e da dove arriva (`da /setgroup`
o `da config.ini`); `/setgroup reset` rimuove l'override e torna al valore di
`config.ini`.

## Avvio

```bash
python bot.py
```

## Uso

**Studente** (in privato al bot)

1. `/start` → pulsante **⚠️ Chiedi aiuto ⚠️**
2. Premi il pulsante e scrivi il messaggio (testo, foto, documenti, …).
3. `/close` chiude la conversazione e libera il topic.
4. Se un messaggio non è inoltrabile (tipo di contenuto non supportato) il bot
   te lo segnala: la conversazione resta aperta, basta inviarne un altro.

**Operatori** (nella supergruppo)

- Ogni richiesta apre un topic con il nome dello studente.
- Rispondi nel topic: il messaggio arriva allo studente in privato.
- `/close` dentro il topic chiude la conversazione e avvisa lo studente.
- Se lo studente ha bloccato il bot, nel topic appare un avviso di mancata
  consegna; lo stesso vale se il messaggio non è inoltrabile.
- Alla chiusura di una conversazione compare nel topic un avviso con il pulsante
  **🚫 Allontana l'utente**; per allontanare puoi anche scrivere `/allontana`
  **dentro il topic** (funziona solo lì) oppure `/allontana <id|@username>` da
  qualunque topic. Il pulsante è utile perché dopo la chiusura solo gli admin
  possono scrivere nei topic, mentre i pulsanti restano premibili.
- L'allontanamento chiede conferma con due tasti (**🚫 Allontana** /
  **↩️ Ho cambiato idea**); dopo il blocco restano il tasto **✅ Sblocca utente**
  e il comando precompilato `/riammetti …` scritto nel messaggio.
- L'utente allontanato non può più inviare richieste (se scrive riceve un
  avviso) e viene escluso dai broadcast.
- Un utente si può indicare per **id** o per **@username**, ma l'username
  funziona solo se il bot l'ha già visto almeno una volta (Telegram non permette
  di risalire da un username mai incontrato): altrimenti usa l'id numerico.

**Operatori non admin**

Chi può rispondere agli studenti è deciso dalla whitelist operatori:

- **whitelist vuota** (default): chiunque possa scrivere nel gruppo può
  rispondere nei topic e usare `/close`;
- **whitelist con almeno un id**: solo quegli id possono farlo.

Gli **admin possono sempre** rispondere, anche se non sono in whitelist.
Gestisci la lista da `/admin` → **👥 Gestisci operatori** (➕ aggiungi, ❌ rimuovi);
nella stessa schermata vedi il gruppo attivo e la modalità in corso. Un operatore
non può toccare broadcast, statistiche o la gestione di admin e operatori:
quelle restano funzioni riservate agli admin.

**Admin** (in privato al bot, `/admin`)

| Voce | Cosa fa |
| --- | --- |
| 📢 Broadcast | Inoltri un messaggio (testo o media) a tutti gli utenti raggiungibili, esclusi i bannati; prima chiede conferma e alla fine mostra inviati/falliti |
| 📊 Statistiche | Utenti totali, ticket aperti, ticket totali, utenti bannati |
| 🎫 Ticket aperti | Elenco degli user ID con ticket aperto e data di apertura |
| 👤 Gestisci admin | Aggiunge o rimuove admin a runtime (gli admin da `config.ini` restano, con 🔒) |
| 👥 Gestisci operatori | Whitelist di chi può rispondere agli studenti + gruppo attivo e modalità (whitelist / chiunque nel gruppo) |

`/annulla` annulla un broadcast o un'aggiunta di admin/operatore in attesa.
`/help` elenca i comandi: in privato mostra anche la sezione admin se sei admin,
nel gruppo le istruzioni per rispondere. Ogni schermata del pannello ha il
pulsante **⬅️ Menu** per tornare indietro.

## Verifiche

```bash
python tests/offline.py
```

Gira **senza rete e senza Telegram**: client finto, database temporaneo, e
`config.ini` (oppure `config.ini.example`, quindi funziona anche da un clone
appena scaricato). Copre il caricamento dei plugin, la scelta dell'handler da
parte del dispatcher, la coerenza fra pulsanti e handler, l'arrivo delle
schermate del pannello e il ciclo dei ticket. Esce con codice 1 se qualcosa
fallisce.

Controllo statico opzionale (non è una dipendenza del progetto):

```bash
pip install ruff
ruff check --select F821,F811,F401 bot.py config.py core.py db.py plugins/ tests/
```
