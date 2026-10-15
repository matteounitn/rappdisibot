"""Testi e tastiere: unico posto per le stringhe mostrate all'utente."""

from __future__ import annotations

from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup

START_TEXT = (
    "Ciao!\n"
    "Questo bot ha come scopo **contattare i rappresentanti** DISI **UniTN**!\n"
    "Come posso aiutarti?"
)
PROMPT_TEXT = "Scrivi ora il messaggio che vuoi inviare ai rappresentanti."
NO_TICKET_TEXT = (
    "Nessuna richiesta aperta. Premi il pulsante qui sotto per contattare i rappresentanti."
)
TICKET_CLOSED_USER_TEXT = (
    "La conversazione con i rappresentanti è stata chiusa. "
    "Premi il pulsante per aprirne una nuova."
)
TICKET_LOST_TEXT = (
    "La conversazione precedente non è più disponibile. "
    "Premi il pulsante per aprirne una nuova."
)
USER_BLOCKED_TEXT = "⚠️ Messaggio non consegnato: l'utente ha bloccato il bot."
BANNED_USER_TEXT = (
    "🚫 La conversazione con i rappresentanti è bloccata. "
    "Se pensi sia un errore, contatta i rappresentanti per altri canali."
)
CLOSE_NOTICE_TEXT = (
    "Se la conversazione non è andata bene, puoi allontanare l'utente. "
    "Per farlo, scrivi /allontana"
)
BAN_CANCELLED_TEXT = "Operazione annullata: nessun blocco applicato."
ALLONTANA_USAGE_TEXT = (
    "Usa /allontana dentro il topic della conversazione, oppure "
    "/allontana <id|@username> per scegliere l'utente."
)
UNBAN_USAGE_TEXT = "Usa /riammetti <id|@username>."
TARGET_NOT_FOUND_TEXT = (
    "Non ho mai visto questo utente, quindi dall'username non riesco a risalire: usa l'id numerico."
)
NOT_BANNED_TEXT = "Questo utente non è allontanato."
ALREADY_BANNED_TEXT = "Questo utente è già allontanato."
NO_TICKET_IN_TOPIC_TEXT = (
    "Nessuna conversazione associata a questo topic: usa /allontana <id|@username>."
)
UNBANNED_TEXT = "✅ Blocco rimosso: l'utente può di nuovo scrivere ai rappresentanti."
OPEN_FAILED_TEXT = (
    "⚠️ Non riesco ad aprire la richiesta in questo momento. Riprova tra poco."
)
USER_UNSUPPORTED_TEXT = (
    "⚠️ Questo messaggio non è stato inoltrato ai rappresentanti: "
    "il tipo di contenuto non è supportato. Prova con testo, foto o un file."
)
OPERATOR_UNSUPPORTED_TEXT = (
    "⚠️ Questo messaggio non è stato inoltrato all'utente: "
    "il tipo di contenuto non è supportato."
)
OPERATORS_TITLE = "Gestione operatori"
OPERATOR_ADD_PROMPT = "Invia l'user ID numerico del nuovo operatore."

ADMIN_PANEL_TEXT = (
    "Pannello di amministrazione:\n\n"
    "/help elenca i comandi · /annulla annulla l'operazione in attesa"
)

HELP_STUDENT_TEXT = (
    "ℹ️ **Comandi**\n\n"
    "/start — mostra il pulsante per contattare i rappresentanti\n"
    "/close — chiude la conversazione aperta\n"
    "/help — questo messaggio"
)
HELP_ADMIN_EXTRA_TEXT = (
    "\n\n**Admin**\n"
    "/admin — apre il pannello di amministrazione\n"
    "/annulla — annulla l'operazione in attesa (broadcast, aggiunta admin/operatore)\n"
    "/setgroup — imposta il gruppo operatori: eseguilo **dentro** il gruppo\n"
    "/setgroup reset — torna al gruppo di config.ini"
)


def help_text(is_admin: bool) -> str:
    return HELP_STUDENT_TEXT + (HELP_ADMIN_EXTRA_TEXT if is_admin else "")


OPERATOR_HELP_TEXT = (
    "ℹ️ **Come si risponde**\n\n"
    "Ogni richiesta di uno studente apre un topic qui: rispondi nel topic e il "
    "messaggio arriva allo studente in privato.\n"
    "/close — chiude il ticket del topic in cui lo scrivi\n"
    "/allontana — allontana l'utente del topic (chiede conferma)\n"
    "/riammetti <id|@username> — toglie il blocco a un utente\n"
    "/help — questo messaggio"
)


def topic_title(user) -> str:
    """Titolo del topic: nome e cognome (se presenti) più l'user ID."""
    name = f"{user.first_name or ''} {user.last_name or ''}".strip() or "utente"
    return f"{name} · {user.id}"[:120]


def topic_intro(user) -> str:
    """Messaggio di apertura del topic, con il riferimento all'utente."""
    return f"📩 Nuova richiesta da {user.mention} (ID <code>{user.id}</code>)"


def close_notice_keyboard(uid: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton("🚫 Allontana l'utente", callback_data=f"ban:ask:{uid}")]]
    )


def ban_confirm_text(uid: int) -> str:
    return (
        f"Vuoi allontanare l'utente <code>{uid}</code>?\n\n"
        "Non potrà più inviare richieste ai rappresentanti e sarà escluso dai broadcast. "
        f"Se scriverà al bot vedrà: <i>{BANNED_USER_TEXT}</i>"
    )


def ban_confirm_keyboard(uid: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("🚫 Allontana", callback_data=f"ban:yes:{uid}"),
                InlineKeyboardButton("↩️ Ho cambiato idea", callback_data=f"ban:no:{uid}"),
            ]
        ]
    )


def banned_notice_text(uid: int, target: str) -> str:
    return (
        f"🚫 Utente <code>{uid}</code> allontanato: non potrà più inviare richieste.\n\n"
        f"Puoi togliere il blocco con <code>/riammetti {target}</code> oppure premendo il tasto qui sotto."
    )


def unban_keyboard(uid: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton("✅ Sblocca utente", callback_data=f"unban:{uid}")]]
    )

def start_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton("⚠️ Chiedi aiuto ⚠️", callback_data="helpme")]]
    )


def admin_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("📢 Broadcast", callback_data="admin:broadcast")],
            [InlineKeyboardButton("📊 Statistiche", callback_data="admin:stats")],
            [InlineKeyboardButton("🎫 Ticket aperti", callback_data="admin:tickets")],
            [InlineKeyboardButton("👤 Gestisci admin", callback_data="admin:admins")],
            [InlineKeyboardButton("👥 Gestisci operatori", callback_data="admin:ops")],
        ]
    )


def broadcast_confirm_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("✅ Conferma", callback_data="broadcast:confirm"),
                InlineKeyboardButton("❌ Annulla", callback_data="broadcast:cancel"),
            ]
        ]
    )

def broadcast_prompt_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton("❌ Annulla", callback_data="broadcast:cancel")]]
    )



def admins_keyboard(runtime_admins: list[int]) -> InlineKeyboardMarkup:
    """Un pulsante di rimozione per ogni admin aggiunto a runtime."""
    rows = [
        [InlineKeyboardButton(f"❌ {uid}", callback_data=f"admin:del:{uid}")]
        for uid in runtime_admins
    ]
    rows.append([InlineKeyboardButton("➕ Aggiungi admin", callback_data="admin:add")])
    rows.append([InlineKeyboardButton("⬅️ Menu", callback_data="admin:menu")])
    return InlineKeyboardMarkup(rows)


def operators_keyboard(operators: list[int]) -> InlineKeyboardMarkup:
    """Un pulsante di rimozione per ogni operatore registrato."""
    rows = [
        [InlineKeyboardButton(f"❌ {uid}", callback_data=f"admin:opdel:{uid}")]
        for uid in operators
    ]
    rows.append([InlineKeyboardButton("➕ Aggiungi operatore", callback_data="admin:opadd")])
    rows.append([InlineKeyboardButton("⬅️ Menu", callback_data="admin:menu")])
    return InlineKeyboardMarkup(rows)
