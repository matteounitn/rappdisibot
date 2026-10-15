"""Stato effimero, lock per-utente e filtri condivisi.

Tutto ciò che è in memoria qui è volutamente non persistente: se il bot riparte
le attese in corso (broadcast, aggiunta admin) vengono semplicemente perse,
mentre ticket e admin restano nel database.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Awaitable, Callable

from pyrogram import filters
from pyrogram.errors import FloodWait, RPCError

import config
import db
from plugins import structures

log = logging.getLogger(__name__)

# --- lock per-utente ------------------------------------------------------

_locks: dict[int, asyncio.Lock] = {}


def lock_for(uid: int) -> asyncio.Lock:
    """Lock dedicato all'utente.

    ``setdefault`` non contiene await, quindi è atomico sull'event loop: due
    handler concorrenti ottengono sempre lo stesso lock.
    """
    return _locks.setdefault(uid, asyncio.Lock())


# --- stato delle attese ---------------------------------------------------

# Utenti che hanno premuto "chiedi aiuto" e devono ancora inviare il primo messaggio.
pending_first: set[int] = set()
# Admin che hanno premuto "Broadcast" e devono inviare il messaggio da inoltrare.
broadcast_wait: set[int] = set()
# Admin -> (chat_id, message_id) del messaggio in attesa di conferma.
broadcast_msg: dict[int, tuple[int, int]] = {}
# Admin che devono inviare l'user ID del nuovo admin.
admin_add_wait: set[int] = set()
# Admin che devono inviare l'user ID del nuovo operatore.
operator_add_wait: set[int] = set()
# Serializza i broadcast: due invii non possono sovrapporsi.
broadcast_lock = asyncio.Lock()


def _awaiting_admin_input(_, __, update) -> bool:
    """True se l'admin ha un input in attesa (broadcast, aggiunta admin/operatore).

    Serve a rendere i filtri **mutuamente esclusivi**: il dispatcher esegue un
    solo handler per gruppo (esce dal ciclo al primo match), quindi la scelta
    dell'handler non può dipendere dall'ordine di registrazione.
    """
    user = getattr(update, "from_user", None)
    if user is None:
        return False
    return (
        user.id in broadcast_wait
        or user.id in admin_add_wait
        or user.id in operator_add_wait
    )


pending_input_filter = filters.create(_awaiting_admin_input)


# --- admin ----------------------------------------------------------------

admin_ids: set[int] = set()


def load_admins() -> None:
    """Ricarica la cache degli admin dal database."""
    admin_ids.clear()
    admin_ids.update(db.list_admins())


def _is_admin(_, __, update) -> bool:
    user = getattr(update, "from_user", None)
    return bool(user and user.id in admin_ids)


admin_filter = filters.create(_is_admin)


# --- operatori ------------------------------------------------------------

operator_ids: set[int] = set()


def load_operators() -> None:
    """Ricarica la cache degli operatori dal database."""
    operator_ids.clear()
    operator_ids.update(db.list_operators())


def _is_operator(_, __, update) -> bool:
    user = getattr(update, "from_user", None)
    if user is None:
        return False
    if user.id in admin_ids:
        return True
    if operator_ids:
        return user.id in operator_ids
    return True


operator_filter = filters.create(_is_operator)


# --- filtro gruppo operatori ---------------------------------------------

SETTING_OPS_CHAT = "operators_chat_id"

# Override impostato con /setgroup, tenuto in memoria. I filtri creati con
# filters.create(sync_fn) hanno __call__ sincrono, quindi Handler.check li esegue
# in un worker thread (run_in_executor) e la connessione SQLite non è
# condivisibile fra thread: qui non si legge mai il database.
ops_chat_override: int | None = None


def load_ops_chat() -> None:
    """Carica l'override del gruppo operatori dal database (una volta, all'avvio)."""
    global ops_chat_override
    raw = db.get_setting(SETTING_OPS_CHAT)
    if raw is None:
        ops_chat_override = None
        return
    try:
        ops_chat_override = int(raw)
    except ValueError:
        log.warning("Valore non numerico per '%s' nel database: %r", SETTING_OPS_CHAT, raw)
        ops_chat_override = None


def set_ops_chat_override(value: int | None) -> None:
    """Imposta (o azzera) l'override: aggiorna database e cache insieme."""
    global ops_chat_override
    if value is None:
        db.delete_setting(SETTING_OPS_CHAT)
    else:
        db.set_setting(SETTING_OPS_CHAT, str(value))
    ops_chat_override = value


def ops_chat_id() -> int | None:
    """Gruppo operatori effettivo: override di /setgroup, altrimenti config.ini."""
    if ops_chat_override is not None:
        return ops_chat_override
    return config.CFG.operators_chat_id if config.CFG else None


def _ops(_, __, message) -> bool:
    cid = ops_chat_id()
    chat = getattr(message, "chat", None)
    return bool(cid is not None and chat and chat.id == cid)


ops_chat_filter = filters.create(_ops)

# --- helper ---------------------------------------------------------------

async def call_with_flood(
    coro_fn: Callable[..., Awaitable[Any]], *args: Any, **kwargs: Any
) -> Any:
    """Chiama una coroutine API ritentando sugli attesi FloodWait brevi."""
    while True:
        try:
            return await coro_fn(*args, **kwargs)
        except FloodWait as e:
            if e.value > 300:
                raise
            await asyncio.sleep(e.value)


async def try_copy(message, chat_id: int, **kwargs: Any) -> bool:
    """Inoltra ``message`` in ``chat_id``; False se il tipo non è inoltrabile.

    ``Message.copy`` non è un wrapper di ``copy_message``: per i testi usa
    ``send_message``, per i media ``send_cached_media``, e per i tipi che non
    gestisce solleva ``ValueError`` ("Unknown media type" per media come
    checklist o tipi non supportati) oppure non invia nulla e ritorna ``None``
    (messaggi vuoti). In entrambi i casi il messaggio non è stato recapitato e
    chi lo ha scritto va avvisato. Gli errori di rete/API restano ``RPCError``
    e vengono propagati: quelli significano "conversazione non più disponibile".
    """
    try:
        sent = await call_with_flood(message.copy, chat_id, **kwargs)
    except ValueError as e:
        log.warning("Messaggio non inoltrabile (%s): %s", type(e).__name__, e)
        return False

    if sent is None:
        log.warning("Messaggio non inoltrato: nessun contenuto copiabile (id=%s)", message.id)
        return False

    return True


async def send_ban_notice(client, chat_id: int, topic_id: int, uid: int) -> None:
    """Messaggio nel topic con il pulsante di ban/sblocco (best-effort)."""
    try:
        await call_with_flood(
            client.send_message,
            chat_id,
            structures.CLOSE_NOTICE_TEXT,
            reply_markup=structures.close_notice_keyboard(uid),
            message_thread_id=topic_id,
        )
    except RPCError as e:
        log.warning(
            "Invio avviso ban non riuscito (chat=%s, topic=%s, uid=%s): %s",
            chat_id,
            topic_id,
            uid,
            e,
        )
    except Exception as e:
        # Un errore imprevisto qui è un bug nostro, non un rifiuto di Telegram:
        # lo si logga come errore con traceback, ma non deve far fallire la
        # chiusura del ticket (il resto del flusso è già stato eseguito).
        log.error(
            "Errore imprevisto invio avviso ban (chat=%s, topic=%s, uid=%s): %s",
            chat_id,
            topic_id,
            uid,
            e,
            exc_info=True,
        )


def resolve_target(arg: str) -> int | None:
    """id numerico -> int; @username/username -> utente già visto (dal db), altrimenti None."""
    raw = arg.strip()
    if not raw:
        return None
    try:
        return int(raw)
    except ValueError:
        return db.find_user_by_username(raw)
