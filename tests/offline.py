"""Verifiche offline di RappDisiBot: nessuna rete, nessun pytest.

    python tests/offline.py

Usa un client finto, un database temporaneo e la config locale (o
`config.ini.example` se `config.ini` non c'è, così gira anche da un clone
pulito). Esce con codice 1 al primo gruppo di controlli falliti.

Copre le invarianti nate da bug reali:
- caricamento dei plugin e registrazione degli handler;
- **competizione fra handler**: kurigram esegue un solo handler per gruppo
  (esce al primo match), quindi i filtri non devono sovrapporsi;
- ogni `callback_data` di ogni tastiera deve avere un handler registrato;
- ogni messaggio che invita a premere il pulsante deve allegare la tastiera;
- una schermata del pannello deve comparire anche se l'edit fallisce, e un tap
  su una schermata già aggiornata deve comunque essere confermato;
- `/setgroup`: override efficace (senza accesso al db nei filtri), avviso sui
  ticket orfani solo se il gruppo cambia davvero.
"""

from __future__ import annotations

import asyncio
import atexit
import os
import re
import shutil
import sqlite3
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

from pyrogram import Client  # noqa: E402
from pyrogram.enums import ChatMemberStatus, ChatType, MessageMediaType, ParseMode  # noqa: E402
from pyrogram.errors import MessageNotModified, QueryIdInvalid, RPCError  # noqa: E402
from pyrogram.handlers import CallbackQueryHandler, MessageHandler  # noqa: E402
from pyrogram.types import (  # noqa: E402
    CallbackQuery,
    Chat,
    ChatMember,
    ChatPrivileges,
    ForumTopicCreated,
    Message,
    User,
)

import config  # noqa: E402
import core  # noqa: E402
import db  # noqa: E402
from plugins import structures as S  # noqa: E402

NEW_GROUP = -1009998887770
# Identificativi sintetici: nel test non entrano mai dati reali.
BOT_ID = 123456789
BOT_USERNAME = "testbot"
MEMBER_X = 777001
STUDENT = 555001
USERNAME = "mario_rossi"
STUDENT_KO = 555002
STUDENT_INTRO = 555003
RESULTS = []


def check(label: str, cond, detail: str = "") -> None:
    RESULTS.append((label, bool(cond)))
    print(("PASS  " if cond else "FAIL  ") + label + (f"   -> {detail}" if detail else ""))


class FakeRPC(RPCError):
    def __init__(self, msg="simulated failure"):
        super().__init__(msg)


class FakeClient:
    """Client finto: registra le chiamate e simula i rifiuti di Telegram."""

    def __init__(self):
        self.me = User(id=BOT_ID, is_bot=True, first_name="Bot", username=BOT_USERNAME)
        self.parse_mode = ParseMode.HTML
        self._next = 100
        self.created_topics: list[tuple[int, str]] = []
        self.sent: list[tuple[int, str, int | None]] = []
        self.markups: list[tuple[int, str, object]] = []
        self.cached: list[tuple[int, str, int | None]] = []
        self.copied: list[tuple[int, int, int]] = []
        self.closed: list[tuple[int, int]] = []
        self.answered: list[tuple[str, str | None]] = []
        self.answer_attempts: list[tuple[str, str | None]] = []
        self.edited: list[tuple[int, int, str, object]] = []
        self.topics: dict[int, set[int]] = {}
        self.fail_send_to: set[int] = set()
        self.fail_copy_to: set[int] = set()
        self.fail_edit = False
        self.fail_not_modified = False
        self.fail_create_topic = False
        self.fail_intro = False
        self.member_status = ChatMemberStatus.ADMINISTRATOR
        self.member_privileges = ChatPrivileges(can_manage_topics=True)

    async def create_forum_topic(self, chat_id, title, **kw):
        if self.fail_create_topic:
            raise FakeRPC("Telegram says: [400 CHANNEL_INVALID] - The provided channel is invalid.")
        self._next += 1
        self.created_topics.append((chat_id, title))
        self.topics.setdefault(chat_id, set()).add(self._next)
        return ForumTopicCreated(id=self._next, title=title, icon_color=0)

    def _check_thread(self, chat_id, thread):
        """Telegram rifiuta un topic che non esiste in quel chat."""
        if thread is not None and thread not in self.topics.get(chat_id, set()):
            raise FakeRPC(f"topic {thread} inesistente in {chat_id}")

    async def send_message(self, chat_id, text, **kw):
        if self.fail_send_to and chat_id in self.fail_send_to:
            raise FakeRPC("send failed")
        if self.fail_intro and text.startswith("📩"):
            raise FakeRPC("intro failed")
        self._check_thread(chat_id, kw.get("message_thread_id"))
        self.sent.append((chat_id, text, kw.get("message_thread_id")))
        self.markups.append((chat_id, text, kw.get("reply_markup")))
        return Message(id=1, chat=Chat(id=chat_id, type=ChatType.PRIVATE), text=text, client=self)

    async def send_cached_media(self, chat_id, file_id, **kw):
        self._check_thread(chat_id, kw.get("message_thread_id"))
        self.cached.append((chat_id, file_id, kw.get("message_thread_id")))
        return Message(id=1, chat=Chat(id=chat_id, type=ChatType.PRIVATE), client=self)

    async def copy_message(self, chat_id, from_chat_id, message_id, **kw):
        if chat_id in self.fail_copy_to:
            raise FakeRPC("user unreachable")
        self._check_thread(chat_id, kw.get("message_thread_id"))
        self.copied.append((chat_id, from_chat_id, message_id))
        return None

    async def close_forum_topic(self, chat_id, topic_id):
        self.closed.append((chat_id, topic_id))
        return True

    async def get_chat_member(self, chat_id, user_id):
        return ChatMember(
            status=self.member_status, user=self.me, privileges=self.member_privileges
        )

    async def answer_callback_query(self, callback_query_id, **kw):
        # Telegram accetta una sola risposta per query: la seconda è QueryIdInvalid.
        self.answer_attempts.append((callback_query_id, kw.get("text")))
        if any(qid == callback_query_id for qid, _t in self.answered):
            raise QueryIdInvalid("query is too old and response timeout expired")
        self.answered.append((callback_query_id, kw.get("text")))
        return True

    async def edit_message_text(self, chat_id, message_id, text, **kw):
        if self.fail_not_modified:
            raise MessageNotModified("message is not modified")
        if self.fail_edit:
            raise FakeRPC("message can't be edited")
        self.edited.append((chat_id, message_id, text, kw.get("reply_markup")))
        return Message(id=message_id, chat=Chat(id=chat_id, type=ChatType.PRIVATE), text=text, client=self)


CLIENT = FakeClient()
ADMIN = 0
OPS_CHAT = 0


def dm_msg(uid, text, mid=1, command=None, media=None):
    m = Message(
        id=mid,
        chat=Chat(id=uid, type=ChatType.PRIVATE),
        from_user=User(
            id=uid,
            is_bot=False,
            first_name="Mario",
            last_name="Rossi",
            # STUDENT ha un username: serve per provare ban/unban per @username.
            username=USERNAME if uid == STUDENT else None,
            client=CLIENT,
        ),
        text=text,
        client=CLIENT,
    )
    if command is not None:
        m.command = command
    if media:
        m.media = media
    return m


def ops_msg(text, thread, mid=500, uid=999, chat_id=None, is_forum=True, command=None):
    m = Message(
        id=mid,
        chat=Chat(
            id=chat_id if chat_id is not None else OPS_CHAT,
            type=ChatType.SUPERGROUP,
            title="Rappresentanti DISI",
            is_forum=is_forum,
        ),
        from_user=User(id=uid, is_bot=False, first_name="Operatore", client=CLIENT),
        text=text,
        message_thread_id=thread,
        client=CLIENT,
    )
    if command is not None:
        m.command = command
    return m


def cq(data, uid, mid=900, chat_id=None):
    chat = (
        Chat(id=chat_id, type=ChatType.SUPERGROUP, title="Rappresentanti DISI", is_forum=True)
        if chat_id is not None
        else Chat(id=uid, type=ChatType.PRIVATE)
    )
    m = Message(id=mid, chat=chat, text="pannello", client=CLIENT)
    # Il filtro regex popola da sé `matches` quando l'update passa da
    # Handler.check; questo serve solo se un test chiama l'handler diretto.
    match = re.match(r"^(?:admin:(?:del|opdel)|ban:(?:ask|yes|no)|unban):(\d+)$", data)
    return CallbackQuery(
        id=str(mid),
        from_user=User(id=uid, is_bot=False, first_name="Adm", client=CLIENT),
        message=m,
        data=data,
        matches=[match] if match else None,
        client=CLIENT,
    )


def texts(chat_id=None):
    return [t for c, t, _thr in CLIENT.sent if chat_id is None or c == chat_id]


def kb_data(markup):
    if markup is None:
        return []
    return [b.callback_data for row in markup.inline_keyboard for b in row]


async def dispatch(app, update):
    """Replica Dispatcher.handler_worker: tipo di handler e un handler per gruppo."""
    ran = []
    atteso = CallbackQueryHandler if isinstance(update, CallbackQuery) else MessageHandler
    for group in app.dispatcher.groups.values():
        for handler in group:
            if not isinstance(handler, atteso):
                continue
            try:
                matched = await handler.check(app, update)
            except Exception:
                continue
            if matched:
                ran.append(f"{handler.callback.__module__}.{handler.callback.__name__}")
                await handler.callback(CLIENT, update)
                break
    return ran


async def handler_for(app, handlers, update):
    for h in handlers.values():
        try:
            if await h.check(app, update):
                return h
        except Exception:
            continue
    return None


async def main() -> None:
    global ADMIN, OPS_CHAT

    # Tutti i file temporanei del test (db, .env, sessioni) finiscono in una
    # cartella sola, rimossa a fine esecuzione anche in caso di uscita con errore.
    tmpdir = tempfile.mkdtemp(prefix="rappdisibot-test-")
    atexit.register(shutil.rmtree, tmpdir, ignore_errors=True)
    tempfile.tempdir = tmpdir

    cfg_path = "config.ini" if Path("config.ini").is_file() else "config.ini.example"
    # I segreti arrivano da .env; da un clone pulito non esiste, quindi il test
    # se ne crea uno sintetico (nessun dato reale entra mai nella suite).
    env_path = ".env" if Path(".env").is_file() else tempfile.mktemp(suffix=".env")
    if env_path != ".env":
        Path(env_path).write_text(
            "RAPPDISIBOT_API_ID=12345\n"
            "RAPPDISIBOT_API_HASH=0123456789abcdef0123456789abcdef\n"
            "RAPPDISIBOT_BOT_TOKEN=123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11\n",
            encoding="utf-8",
        )
    cfg = config.load_config(cfg_path, env_path=env_path)
    ADMIN = cfg.seed_admins[0]
    OPS_CHAT = cfg.operators_chat_id
    print(f"config: {cfg_path} | admin: {ADMIN} | gruppo: {OPS_CHAT}\n")

    db.init(tempfile.mktemp(suffix=".db"))
    db.seed_admins(cfg.seed_admins)
    core.load_admins()
    core.load_operators()
    core.load_ops_chat()

    workdir = tempfile.mkdtemp(prefix="sessione-")
    app = Client(
        "offline_test",
        api_id=cfg.api_id,
        api_hash=cfg.api_hash,
        bot_token=cfg.bot_token,
        plugins=dict(root="plugins"),
        workdir=workdir,
    )
    app.me = User(id=BOT_ID, is_bot=True, first_name="Bot", username=BOT_USERNAME)
    app.load_plugins()
    await asyncio.sleep(0.2)

    handlers = {}
    for group in app.dispatcher.groups.values():
        for h in group:
            handlers[f"{h.callback.__module__}.{h.callback.__name__}"] = h
    check("plugin caricati (>= 24 handler)", len(handlers) >= 24, str(len(handlers)))

    # --- ogni pulsante ha un handler --------------------------------------
    tastiere = {
        "start": S.start_keyboard(),
        "admin": S.admin_keyboard(),
        "broadcast_confirm": S.broadcast_confirm_keyboard(),
        "broadcast_prompt": S.broadcast_prompt_keyboard(),
        "admins": S.admins_keyboard([42]),
        "operators": S.operators_keyboard([42]),
    }
    tutti = sorted({d for kb in tastiere.values() for d in kb_data(kb)})
    scoperti = [d for d in tutti if await handler_for(app, handlers, cq(d, ADMIN)) is None]
    check("ogni callback_data ha un handler registrato", not scoperti, str(scoperti))

    # --- competizione fra handler (un handler per gruppo) ------------------
    CLIENT.sent.clear()
    ran = await dispatch(app, dm_msg(ADMIN, "/help", mid=10, command=["help"]))
    check(
        "dispatch: /help di un admin risponde (non inghiottito)",
        ran == ["plugins.user.help_command"] and texts(ADMIN)[-1] == S.help_text(True),
        str(ran),
    )
    CLIENT.sent.clear()
    ran = await dispatch(app, dm_msg(ADMIN, "/admin", mid=11, command=["admin"]))
    check("dispatch: /admin apre il pannello", ran == ["plugins.admin.panel"], str(ran))
    CLIENT.sent.clear()
    ran = await dispatch(app, dm_msg(ADMIN, "messaggio senza ticket", mid=12))
    check(
        "dispatch: messaggio di un admin inoltrato al relay",
        ran == ["plugins.user.relay_to_operators"] and texts(ADMIN)[-1] == S.NO_TICKET_TEXT,
        str(ran),
    )

    h_admin_in = handlers["plugins.admin.admin_input"]
    h_relay = handlers["plugins.user.relay_to_operators"]
    for label, upd in [
        ("admin, testo", dm_msg(ADMIN, "x")),
        ("admin, comando", dm_msg(ADMIN, "/start", command=["start"])),
        ("studente, testo", dm_msg(STUDENT, "x")),
        ("admin, media", dm_msg(ADMIN, None, media=MessageMediaType.PHOTO)),
    ]:
        a = await h_admin_in.check(app, upd)
        r = await h_relay.check(app, upd)
        check(f"filtri disgiunti: {label}", not (a and r), f"admin_input={a} relay={r}")
    core.broadcast_wait.add(ADMIN)
    a = await h_admin_in.check(app, dm_msg(ADMIN, "x"))
    r = await h_relay.check(app, dm_msg(ADMIN, "x"))
    check("filtri disgiunti: admin con input in attesa", a and not r, f"admin_input={a} relay={r}")
    core.broadcast_wait.discard(ADMIN)

    # --- flusso studente: il pulsante c'è sempre --------------------------
    await dispatch(app, cq("helpme", STUDENT, mid=20))
    await dispatch(app, dm_msg(STUDENT, "ciao", mid=21))
    topic_u = db.get_open_topic(STUDENT)
    check("studente: ticket creato", topic_u is not None)

    CLIENT.sent.clear()
    ran = await dispatch(app, ops_msg("/close", topic_u, mid=22, uid=MEMBER_X, command=["close"]))
    avviso = [(c, t, m) for c, t, m in CLIENT.markups if c == STUDENT and "chiusa" in t]
    check(
        "operatore /close: avviso allo studente con il pulsante",
        ran == ["plugins.operators.close"] and bool(avviso) and kb_data(avviso[0][2]) == ["helpme"],
        str(avviso),
    )

    core.pending_first.add(STUDENT)
    await dispatch(app, dm_msg(STUDENT, "primo", mid=23))
    CLIENT.fail_send_to.add(OPS_CHAT)
    CLIENT.sent.clear()
    await dispatch(app, dm_msg(STUDENT, "secondo", mid=24))
    check(
        "ticket perso: avviso con il pulsante",
        texts(STUDENT) == [S.TICKET_LOST_TEXT] and kb_data(CLIENT.markups[-1][2]) == ["helpme"],
        str(CLIENT.markups[-1]),
    )
    CLIENT.fail_send_to.clear()

    promesse = [(c, t, m) for c, t, m in CLIENT.markups if "premi il pulsante" in t.lower()]
    senza = [(t, kb_data(m)) for _c, t, m in promesse if kb_data(m) != ["helpme"]]
    check("chi invita a premere il pulsante allega la tastiera", promesse and not senza, str(senza))

    # --- pannello: schermate, edit fallito, tap ripetuto -------------------
    CLIENT.edited.clear()
    ran = await dispatch(app, cq("admin:stats", ADMIN, mid=30))
    check(
        "statistiche: schermata con conteggi e orario",
        ran == ["plugins.admin.stats"]
        and CLIENT.edited[-1][2].startswith("👥 Utenti:")
        and "Aggiornato alle" in CLIENT.edited[-1][2],
        CLIENT.edited[-1][2],
    )

    CLIENT.edited.clear()
    CLIENT.sent.clear()
    CLIENT.fail_edit = True
    await dispatch(app, cq("admin:stats", ADMIN, mid=31))
    CLIENT.fail_edit = False
    check(
        "edit fallito: la schermata arriva comunque (nuovo messaggio)",
        texts(ADMIN)[-1].startswith("👥 Utenti:"),
        str(texts(ADMIN)),
    )

    CLIENT.answered.clear()
    CLIENT.answer_attempts.clear()
    CLIENT.sent.clear()
    CLIENT.fail_not_modified = True
    await dispatch(app, cq("admin:stats", ADMIN, mid=32))
    CLIENT.fail_not_modified = False
    check(
        "schermata già aggiornata: nessun messaggio extra, una sola risposta alla callback",
        texts(ADMIN) == [] and len(CLIENT.answer_attempts) == 1,
        f"messaggi={texts(ADMIN)} risposte={CLIENT.answer_attempts}",
    )

    # --- /setgroup --------------------------------------------------------
    core.pending_first.add(STUDENT)
    await dispatch(app, dm_msg(STUDENT, "ticket aperto", mid=40))
    CLIENT.sent.clear()
    await dispatch(app, ops_msg("/setgroup", None, mid=41, uid=ADMIN, command=["setgroup"]))
    conferma = texts(OPS_CHAT)[-1]
    check(
        "setgroup nello stesso gruppo: nessun avviso",
        "⚠️" not in conferma and "✅ Gruppo operatori impostato" in conferma,
        conferma,
    )

    aperti = db.count_open_tickets()
    CLIENT.sent.clear()
    await dispatch(app, ops_msg("/setgroup", None, mid=42, uid=ADMIN, chat_id=NEW_GROUP, command=["setgroup"]))
    conferma = texts(NEW_GROUP)[-1]
    atteso = "⚠️ 1 ticket resta aperto" if aperti == 1 else f"⚠️ {aperti} ticket restano aperti"
    check("setgroup su un altro gruppo: avviso sui ticket orfani", atteso in conferma, conferma)
    check("setgroup: override efficace", core.ops_chat_id() == NEW_GROUP, str(core.ops_chat_id()))

    h_ops_relay = handlers["plugins.operators.relay_to_user"]
    check(
        "setgroup: il gruppo nuovo passa dal filtro reale (worker thread)",
        await h_ops_relay.check(app, ops_msg("ciao", None, uid=MEMBER_X, chat_id=NEW_GROUP)),
    )
    check(
        "setgroup: il vecchio gruppo non passa più",
        not await h_ops_relay.check(app, ops_msg("ciao", None, uid=MEMBER_X)),
    )

    CLIENT.sent.clear()
    await dispatch(app, dm_msg(STUDENT, "dopo il cambio", mid=43))
    check(
        "ticket orfano: chiuso con avviso e pulsante",
        db.get_open_topic(STUDENT) is None
        and texts(STUDENT) == [S.TICKET_LOST_TEXT]
        and kb_data(CLIENT.markups[-1][2]) == ["helpme"],
        str(CLIENT.markups[-1]),
    )

    CLIENT.sent.clear()
    await dispatch(app, dm_msg(ADMIN, "/setgroup reset", mid=44, command=["setgroup", "reset"]))
    check(
        "setgroup reset: torna al gruppo di config",
        core.ops_chat_id() == OPS_CHAT and "torno al valore di config.ini" in texts(ADMIN)[-1],
        str(texts(ADMIN)),
    )

    # --- broadcast --------------------------------------------------------
    await dispatch(app, cq("admin:broadcast", ADMIN, mid=50))
    CLIENT.sent.clear()
    await dispatch(app, dm_msg(ADMIN, "Annuncio", mid=51))
    check(
        "broadcast: chiede conferma con il numero di utenti in db",
        texts(ADMIN)[-1].startswith(f"Confermi l'invio a {db.count_users()} utenti"),
        str(texts(ADMIN)),
    )
    CLIENT.copied.clear()
    await dispatch(app, cq("broadcast:confirm", ADMIN, mid=52))
    check(
        "broadcast: inviato esattamente agli utenti raggiungibili",
        {c for c, _f, _m in CLIENT.copied} == set(db.broadcast_user_ids()),
        str(CLIENT.copied),
    )

    CLIENT.fail_copy_to.add(STUDENT)
    core.broadcast_msg[ADMIN] = (ADMIN, 51)
    CLIENT.edited.clear()
    await dispatch(app, cq("broadcast:confirm", ADMIN, mid=53))
    CLIENT.fail_copy_to.clear()
    check(
        "broadcast: i falliti sono contati e spiegati",
        CLIENT.edited[-1][2].startswith("✅ Inviato a")
        and "falliti: 1" in CLIENT.edited[-1][2]
        and "hanno bloccato il bot" in CLIENT.edited[-1][2],
        CLIENT.edited[-1][2],
    )

    # --- fallimento nell'apertura del topic (es. gruppo non configurato) --
    core.pending_first.add(STUDENT_KO)
    CLIENT.fail_create_topic = True
    CLIENT.created_topics.clear()
    CLIENT.sent.clear()
    ran = await dispatch(app, dm_msg(STUDENT_KO, "primo messaggio", mid=90))
    CLIENT.fail_create_topic = False
    check(
        "topic non creabile: lo studente viene avvisato (niente silenzio)",
        ran == ["plugins.user.relay_to_operators"] and texts(STUDENT_KO) == [S.OPEN_FAILED_TEXT],
        str(texts(STUDENT_KO)),
    )
    check("topic non creabile: nessun ticket creato", db.get_open_topic(STUDENT_KO) is None)
    check(
        "topic non creabile: l'attesa resta attiva per riprovare",
        STUDENT_KO in core.pending_first,
    )

    CLIENT.sent.clear()
    await dispatch(app, dm_msg(STUDENT_KO, "riprovo", mid=91))
    check(
        "topic non creabile: il messaggio successivo riprova e riesce",
        db.get_open_topic(STUDENT_KO) is not None and len(CLIENT.created_topics) == 1,
        f"topic={db.get_open_topic(STUDENT_KO)} creati={CLIENT.created_topics}",
    )

    core.pending_first.add(STUDENT_INTRO)
    CLIENT.fail_intro = True
    await dispatch(app, dm_msg(STUDENT_INTRO, "ciao", mid=92))
    CLIENT.fail_intro = False
    topic_intro = db.get_open_topic(STUDENT_INTRO)
    check("intro non inviata: il ticket resta valido", topic_intro is not None)
    CLIENT.sent.clear()
    await dispatch(app, ops_msg("risposta", topic_intro, mid=93, uid=MEMBER_X))
    check(
        "intro non inviata: l'inoltro verso lo studente funziona lo stesso",
        (STUDENT_INTRO, "risposta", None) in CLIENT.sent,
        str(CLIENT.sent),
    )

    # --- allontanamento in due passi --------------------------------------
    check("allontana: utente non bloccato all'inizio", not db.is_banned(STUDENT))

    core.pending_first.add(STUDENT)
    await dispatch(app, dm_msg(STUDENT, "richiesta da chiudere", mid=60))
    topic_ban = db.get_open_topic(STUDENT)
    CLIENT.sent.clear()
    CLIENT.markups.clear()
    await dispatch(app, ops_msg("/close", topic_ban, mid=61, uid=MEMBER_X, command=["close"]))
    avviso_ops = [
        (c, t, m) for c, t, m in CLIENT.markups if c == OPS_CHAT and f"ban:ask:{STUDENT}" in kb_data(m)
    ]
    check(
        "close operatore: avviso con testo e pulsante di allontanamento",
        len(avviso_ops) == 1 and avviso_ops[0][1] == S.CLOSE_NOTICE_TEXT,
        str(avviso_ops),
    )

    core.pending_first.add(STUDENT)
    await dispatch(app, dm_msg(STUDENT, "richiesta da chiudere 2", mid=62))
    topic_attivo = db.get_open_topic(STUDENT)
    CLIENT.sent.clear()
    CLIENT.markups.clear()
    await dispatch(app, dm_msg(STUDENT, "/close", mid=63, command=["close"]))
    avviso_studente = [
        (c, t, m) for c, t, m in CLIENT.markups if c == OPS_CHAT and f"ban:ask:{STUDENT}" in kb_data(m)
    ]
    check(
        "close studente: avviso con pulsante di allontanamento",
        len(avviso_studente) == 1,
        str(avviso_studente),
    )

    CLIENT.sent.clear()
    await dispatch(app, ops_msg("/allontana", None, mid=64, uid=MEMBER_X, command=["allontana"]))
    check(
        "/allontana fuori da un topic: spiega come usarlo",
        texts(OPS_CHAT)[-1] == S.ALLONTANA_USAGE_TEXT,
        str(texts(OPS_CHAT)),
    )

    CLIENT.sent.clear()
    CLIENT.markups.clear()
    await dispatch(app, ops_msg("/allontana", topic_attivo, mid=65, uid=MEMBER_X, command=["allontana"]))
    conferme = [
        (c, t, m) for c, t, m in CLIENT.markups if c == OPS_CHAT and f"ban:yes:{STUDENT}" in kb_data(m)
    ]
    check(
        "/allontana nel topic (ticket appena chiuso): conferma a due tasti",
        len(conferme) == 1
        and conferme[0][1] == S.ban_confirm_text(STUDENT)
        and kb_data(conferme[0][2]) == [f"ban:yes:{STUDENT}", f"ban:no:{STUDENT}"],
        str(conferme),
    )
    check("conferma mostrata: l'utente non è ancora bloccato", not db.is_banned(STUDENT))

    # in un topic ormai "vecchio" (lo studente ha riaperto) il comando non risolve:
    # resta il pulsante dell'avviso, che porta con sé l'id
    CLIENT.sent.clear()
    await dispatch(app, ops_msg("/allontana", topic_ban, mid=69, uid=MEMBER_X, command=["allontana"]))
    check(
        "/allontana in un topic senza conversazione: suggerisce id/username",
        texts(OPS_CHAT)[-1] == S.NO_TICKET_IN_TOPIC_TEXT,
        str(texts(OPS_CHAT)),
    )

    # "Ho cambiato idea"
    CLIENT.edited.clear()
    await dispatch(app, cq(f"ban:no:{STUDENT}", MEMBER_X, mid=66, chat_id=OPS_CHAT))
    check(
        "ho cambiato idea: nessun blocco e messaggio aggiornato",
        not db.is_banned(STUDENT)
        and CLIENT.edited[-1][2] == S.BAN_CANCELLED_TEXT
        and kb_data(CLIENT.edited[-1][3]) == [],
        str(CLIENT.edited[-1:]),
    )

    # conferma dell'allontanamento
    CLIENT.answered.clear()
    CLIENT.edited.clear()
    await dispatch(app, cq(f"ban:yes:{STUDENT}", MEMBER_X, mid=67, chat_id=OPS_CHAT))
    check("allontana: l'utente è bloccato", db.is_banned(STUDENT))
    check(
        "allontana: toast di conferma",
        [t for _i, t in CLIENT.answered][-1] == "🚫 Utente allontanato",
        str(CLIENT.answered),
    )
    check(
        "allontana: messaggio con comando precompilato e tasto di sblocco",
        CLIENT.edited[-1][2] == S.banned_notice_text(STUDENT, f"@{USERNAME}")
        and kb_data(CLIENT.edited[-1][3]) == [f"unban:{STUDENT}"],
        str(CLIENT.edited[-1:]),
    )

    # sblocco dal tasto
    CLIENT.edited.clear()
    await dispatch(app, cq(f"unban:{STUDENT}", MEMBER_X, mid=68, chat_id=OPS_CHAT))
    check(
        "sblocca utente dal tasto: blocco rimosso e avviso ripristinato",
        not db.is_banned(STUDENT) and CLIENT.edited[-1][2] == S.CLOSE_NOTICE_TEXT,
        str(CLIENT.edited[-1:]),
    )

    # comandi con argomento
    CLIENT.sent.clear()
    CLIENT.markups.clear()
    await dispatch(
        app, ops_msg(f"/allontana {STUDENT}", None, mid=70, uid=MEMBER_X, command=["allontana", str(STUDENT)])
    )
    check(
        "/allontana <id>: conferma a due tasti",
        any(f"ban:yes:{STUDENT}" in kb_data(m) for _c, _t, m in CLIENT.markups),
        str(CLIENT.markups),
    )

    CLIENT.sent.clear()
    CLIENT.markups.clear()
    await dispatch(
        app,
        ops_msg(f"/allontana @{USERNAME}", None, mid=71, uid=MEMBER_X, command=["allontana", f"@{USERNAME}"]),
    )
    check(
        "/allontana @username (utente già visto): conferma a due tasti",
        any(f"ban:yes:{STUDENT}" in kb_data(m) for _c, _t, m in CLIENT.markups),
        str(CLIENT.markups),
    )

    CLIENT.sent.clear()
    await dispatch(
        app,
        ops_msg("/allontana @mai_visto", None, mid=72, uid=MEMBER_X, command=["allontana", "@mai_visto"]),
    )
    check(
        "/allontana con username sconosciuto: spiega il limite",
        texts(OPS_CHAT)[-1] == S.TARGET_NOT_FOUND_TEXT,
        str(texts(OPS_CHAT)),
    )

    db.set_banned(STUDENT, True)
    CLIENT.sent.clear()
    await dispatch(
        app, ops_msg(f"/riammetti {STUDENT}", None, mid=73, uid=MEMBER_X, command=["riammetti", str(STUDENT)])
    )
    check(
        "/riammetti <id>: rimuove il blocco",
        not db.is_banned(STUDENT) and texts(OPS_CHAT)[-1] == S.UNBANNED_TEXT,
        str(texts(OPS_CHAT)),
    )
    CLIENT.sent.clear()
    await dispatch(app, ops_msg("/riammetti", None, mid=74, uid=MEMBER_X, command=["riammetti"]))
    check("/riammetti senza argomento: spiega l'uso", texts(OPS_CHAT)[-1] == S.UNBAN_USAGE_TEXT, str(texts(OPS_CHAT)))
    CLIENT.sent.clear()
    await dispatch(
        app, ops_msg(f"/riammetti {STUDENT}", None, mid=75, uid=MEMBER_X, command=["riammetti", str(STUDENT)])
    )
    check(
        "/riammetti su utente non bloccato",
        texts(OPS_CHAT)[-1] == S.NOT_BANNED_TEXT,
        str(texts(OPS_CHAT)),
    )

    # gating: qualunque operatore, ma non estranei
    h_allontana = await handler_for(
        app, handlers, ops_msg("/allontana", None, uid=MEMBER_X, command=["allontana"])
    )
    check("allontana: handler registrato", h_allontana is not None)
    check(
        "allontana: non raggiungibile da un messaggio privato",
        not await h_allontana.check(app, dm_msg(MEMBER_X, "/allontana", command=["allontana"])),
    )
    core.operator_ids.add(MEMBER_X)
    check(
        "allontana: con whitelist attiva un estraneo è escluso",
        not await h_allontana.check(
            app, ops_msg("/allontana", None, uid=777999, command=["allontana"])
        ),
    )
    check(
        "allontana: l'operatore in whitelist passa",
        await h_allontana.check(app, ops_msg("/allontana", None, uid=MEMBER_X, command=["allontana"])),
    )
    core.operator_ids.discard(MEMBER_X)
    check(
        "username salvato nel db per gli utenti già visti",
        db.find_user_by_username(f"@{USERNAME}") == STUDENT and db.get_username(STUDENT) == USERNAME,
    )

    # --- pulsanti rimasti da versioni precedenti --------------------------
    # La prima versione usava `ban:<id>`: nei messaggi già inviati quel pulsante
    # non ha più un handler, quindi senza il catch-all non farebbe nulla.
    ran = await dispatch(app, cq(f"ban:{STUDENT}", MEMBER_X, mid=99, chat_id=OPS_CHAT))
    check(
        "pulsante di una versione precedente: viene gestito, non ignorato",
        ran == ["plugins.user.callback_sconosciuta"],
        str(ran),
    )
    CLIENT.answered.clear()
    await dispatch(app, cq(f"ban:{STUDENT}", MEMBER_X, mid=98, chat_id=OPS_CHAT))
    check(
        "pulsante vecchio: l'operatore riceve un avviso",
        "non è più attivo" in ([t for _i, t in CLIENT.answered][-1] or ""),
        str(CLIENT.answered),
    )
    check(
        "pulsante valido (pannello): non intercettato dal catch-all",
        await dispatch(app, cq("admin:stats", ADMIN, mid=97)) == ["plugins.admin.stats"],
    )
    check(
        "pulsante valido (allontana): non intercettato dal catch-all",
        await dispatch(app, cq(f"ban:ask:{STUDENT}", MEMBER_X, mid=96, chat_id=OPS_CHAT))
        == ["plugins.operators.ban_ask_callback"],
    )

    # Un estraneo preme un pulsante valido: il filtro dell'handler lo scarta, quindi
    # risponde il catch-all — e deve dire "permessi", non "non più attivo".
    stato_prima = db.is_banned(STUDENT)
    core.operator_ids.add(MEMBER_X)  # whitelist attiva: 777999 non è operatore
    CLIENT.answered.clear()
    ran = await dispatch(app, cq(f"ban:yes:{STUDENT}", 777999, mid=95, chat_id=OPS_CHAT))
    core.operator_ids.discard(MEMBER_X)
    check(
        "pulsante valido premuto da un estraneo: avviso sui permessi",
        ran == ["plugins.user.callback_sconosciuta"]
        and "permessi" in ([t for _i, t in CLIENT.answered][-1] or "")
        and db.is_banned(STUDENT) == stato_prima,
        f"{ran} {CLIENT.answered}",
    )

    db.set_banned(STUDENT, True)
    CLIENT.created_topics.clear()
    CLIENT.sent.clear()
    ran = await dispatch(app, dm_msg(STUDENT, "ci sei?", mid=72))
    check(
        "utente bannato: messaggio rifiutato, nessun topic nuovo",
        ran == ["plugins.user.relay_to_operators"]
        and texts(STUDENT) == [S.BANNED_USER_TEXT]
        and not CLIENT.created_topics,
        f"{ran} {texts(STUDENT)}",
    )

    core.pending_first.discard(STUDENT)
    CLIENT.edited.clear()
    await dispatch(app, cq("helpme", STUDENT, mid=73))
    check(
        "utente bannato: il pulsante non apre una richiesta",
        STUDENT not in core.pending_first and CLIENT.edited[-1][2] == S.BANNED_USER_TEXT,
        str(CLIENT.edited[-1:]),
    )

    check("broadcast: i bannati sono esclusi dai destinatari", STUDENT not in db.broadcast_user_ids())
    await dispatch(app, cq("admin:broadcast", ADMIN, mid=80))
    CLIENT.sent.clear()
    await dispatch(app, dm_msg(ADMIN, "Annuncio 2", mid=81))
    check(
        "broadcast: la conferma conta i non bannati",
        texts(ADMIN)[-1].startswith(f"Confermi l'invio a {len(db.broadcast_user_ids())} utenti"),
        str(texts(ADMIN)),
    )
    CLIENT.copied.clear()
    CLIENT.edited.clear()
    await dispatch(app, cq("broadcast:confirm", ADMIN, mid=82))
    destinatari = {c for c, _f, _m in CLIENT.copied}
    check(
        "broadcast: inviato solo ai non bannati",
        destinatari == set(db.broadcast_user_ids()) and STUDENT not in destinatari,
        str(CLIENT.copied),
    )
    CLIENT.edited.clear()
    await dispatch(app, cq("admin:stats", ADMIN, mid=83))
    check(
        "statistiche: mostra quanti sono bannati",
        "🚫 Bannati: 1" in CLIENT.edited[-1][2],
        CLIENT.edited[-1][2],
    )
    db.set_banned(STUDENT, False)

    # --- migrazione di un db creato prima della colonna `banned` ----------
    # (per ultimo: cambia la connessione del modulo)
    vecchio_db = tempfile.mktemp(suffix=".db")
    conn = sqlite3.connect(vecchio_db)
    conn.executescript(
        "CREATE TABLE users(user_id INTEGER PRIMARY KEY, first_seen TEXT DEFAULT CURRENT_TIMESTAMP);"
        "INSERT INTO users(user_id) VALUES(999);"
    )
    conn.commit()
    conn.close()
    db.init(vecchio_db)
    check(
        "migrazione: db senza colonna banned viene aggiornato",
        db.is_banned(999) is False and db.count_banned() == 0 and db.broadcast_user_ids() == [999],
    )
    db.set_banned(999, True)
    check(
        "migrazione: il ban funziona sul db migrato",
        db.is_banned(999) and db.count_banned() == 1 and db.broadcast_user_ids() == [],
    )
    db.upsert_user(999, "Tizio")
    check(
        "migrazione: la colonna username c'è ed è ricercabile (con o senza @, case-insensitive)",
        db.get_username(999) == "tizio" and db.find_user_by_username("@Tizio") == 999,
    )

    # --- segreti: precedenza ambiente > .env > config.ini -----------------
    # Tutto con file sintetici: la suite non legge né stampa segreti reali.
    ini_prova = Path(tempfile.mktemp(suffix=".ini"))
    ini_prova.write_text(
        "[pyrogram]\napi_id = 77\napi_hash = aa\nbot_token = 77:bb\n\n"
        "[bot]\noperators_chat_id = -100999\nadmins = 1\n",
        encoding="utf-8",
    )
    env_prova = Path(tempfile.mktemp(suffix=".env"))
    env_prova.write_text(
        "RAPPDISIBOT_BOT_TOKEN=111:da-file-env\nRAPPDISIBOT_API_ID=4242\n", encoding="utf-8"
    )

    cfg_ini = config.load_config(str(ini_prova), env_path=tempfile.mktemp(suffix=".env"))
    check(
        "segreti: senza .env si usano quelli di config.ini (compatibilità)",
        cfg_ini.bot_token == "77:bb" and cfg_ini.api_id == 77 and cfg_ini.operators_chat_id == -100999,
        f"api_id={cfg_ini.api_id}",
    )

    cfg_env = config.load_config(str(ini_prova), env_path=str(env_prova))
    check(
        "segreti: .env vince su config.ini, il resto resta da config.ini",
        cfg_env.bot_token == "111:da-file-env"
        and cfg_env.api_id == 4242
        and cfg_env.api_hash == "aa"
        and cfg_env.operators_chat_id == -100999
        and cfg_env.seed_admins == (1,),
        f"api_id={cfg_env.api_id} token_da_env={cfg_env.bot_token == '111:da-file-env'}",
    )

    os.environ["RAPPDISIBOT_BOT_TOKEN"] = "222:da-ambiente"
    cfg_amb = config.load_config(str(ini_prova), env_path=str(env_prova))
    os.environ.pop("RAPPDISIBOT_BOT_TOKEN", None)
    check(
        "segreti: la variabile d'ambiente vince sul .env",
        cfg_amb.bot_token == "222:da-ambiente",
        f"da_ambiente={cfg_amb.bot_token == '222:da-ambiente'}",
    )

    ini_senza = Path(tempfile.mktemp(suffix=".ini"))
    ini_senza.write_text("[bot]\noperators_chat_id = -100\nadmins = 1\n", encoding="utf-8")
    try:
        config.load_config(str(ini_senza), env_path=tempfile.mktemp(suffix=".env"))
    except SystemExit as e:
        messaggio = str(e)
    else:
        messaggio = ""
    check(
        "segreto mancante: messaggio chiaro che indica .env e config.ini",
        "RAPPDISIBOT_" in messaggio and ".env.example" in messaggio and "[pyrogram]" in messaggio,
        messaggio,
    )

    config.load_config(cfg_path, env_path=env_path)  # ripristina CFG

    failed = [label for label, ok in RESULTS if not ok]
    print(f"\n{len(RESULTS) - len(failed)}/{len(RESULTS)} controlli superati")
    if failed:
        print("FALLITI:")
        for label in failed:
            print("  -", label)
        sys.exit(1)
    print("OFFLINE-OK")


if __name__ == "__main__":
    asyncio.run(main())
