"""Pannello admin: /admin, statistiche, ticket aperti, broadcast e gestione admin."""

from __future__ import annotations

import logging
from datetime import datetime

from pyrogram import Client, filters
from pyrogram.enums import ChatMemberStatus, ChatType
from pyrogram.errors import MessageNotModified, RPCError
from pyrogram.types import CallbackQuery, Message

import config
import core
import db
from . import structures

log = logging.getLogger(__name__)


async def _answer(cq: CallbackQuery, *args, **kwargs):
    """Risponde alla callback; una query scaduta non deve bloccare la schermata."""
    try:
        await core.call_with_flood(cq.answer, *args, **kwargs)
    except RPCError as e:
        log.warning("Callback non rispondibile (%s): %s", type(e).__name__, e)


async def _edit(client: Client, cq: CallbackQuery, text: str, **kwargs):
    """Aggiorna la schermata del pannello.

    Un errore di Telegram (FloodWait lungo, messaggio non modificabile, query
    scaduta) non deve lasciare il pulsante senza risposta: in quel caso la
    schermata viene rimandata come nuovo messaggio.
    """
    try:
        await core.call_with_flood(cq.edit_message_text, text, **kwargs)
    except MessageNotModified:
        # Il testo è già quello giusto. Non si risponde qui: l'handler ha già
        # risposto alla callback e Telegram rifiuta una seconda risposta sulla
        # stessa query (QueryIdInvalid).
        pass
    except RPCError as e:
        log.warning(
            "Modifica della schermata non riuscita (%s): %s — la rimando come nuovo messaggio",
            type(e).__name__,
            e,
        )
        try:
            await core.call_with_flood(
                client.send_message, cq.message.chat.id, text, **kwargs
            )
        except RPCError as e2:
            log.error("Invio della schermata non riuscito: %s", e2)


def _admins_view() -> tuple[str, list[int]]:
    """Testo della schermata admin e lista dei soli admin aggiunti a runtime."""
    seeds = set(config.CFG.seed_admins)
    runtime = [a for a in db.list_admins() if a not in seeds]

    lines = ["Admin da config.ini (🔒 non rimovibili):"]
    lines += [f"🔒 <code>{a}</code>" for a in config.CFG.seed_admins] or ["—"]
    lines += ["", "Admin aggiunti a runtime:"]
    lines += [f"<code>{a}</code>" for a in runtime] or ["—"]
    return "\n".join(lines), runtime

def _operators_view() -> tuple[str, list[int]]:
    """Testo della schermata operatori e lista degli operatori."""
    cid = core.ops_chat_id()
    if cid is None:
        first_line = "Gruppo operatori: non configurato."
    else:
        origine = (
            "da /setgroup"
            if core.ops_chat_override is not None
            else "da config.ini"
        )
        first_line = f"Gruppo operatori: <code>{cid}</code> ({origine})"

    if not core.operator_ids:
        mode_line = "Modalità: chiunque nel gruppo (whitelist vuota)"
    else:
        mode_line = f"Modalità: solo whitelist ({len(core.operator_ids)})"

    ops = db.list_operators()
    lines = [first_line, mode_line, "", "Operatori:"]
    if ops:
        lines.extend(f"• <code>{uid}</code>" for uid in ops)
    else:
        lines.append("—")

    return "\n".join(lines), ops



@Client.on_message(filters.command("admin") & filters.private & core.admin_filter)
async def panel(client: Client, message: Message):
    await message.reply_text(
        structures.ADMIN_PANEL_TEXT, reply_markup=structures.admin_keyboard()
    )


@Client.on_callback_query(filters.regex(r"^admin:menu$") & core.admin_filter)
async def admin_menu(client: Client, cq: CallbackQuery):
    await _answer(cq)
    await _edit(
        client,
        cq, structures.ADMIN_PANEL_TEXT, reply_markup=structures.admin_keyboard()
    )


@Client.on_message(filters.command("setgroup") & core.admin_filter)
async def setgroup(client: Client, message: Message):
    cmd_args = [arg.lower() for arg in (message.command or [])[1:]]
    if "reset" in cmd_args:
        cfg_chat = config.CFG.operators_chat_id if config.CFG else None
        if core.ops_chat_override is None:
            await message.reply_text(
                f"Nessun override attivo: il gruppo è già quello di config.ini ({cfg_chat})."
            )
        else:
            core.set_ops_chat_override(None)
            await message.reply_text(
                f"✅ Override rimosso: torno al valore di config.ini ({cfg_chat})."
            )
        return

    if message.chat.type == ChatType.PRIVATE:
        cid = core.ops_chat_id()
        if cid is None:
            await message.reply_text("Gruppo operatori: non configurato.")
        else:
            origine = (
                "da /setgroup"
                if core.ops_chat_override is not None
                else "da config.ini"
            )
            await message.reply_text(
                f"Gruppo operatori: <code>{cid}</code> ({origine})\n"
                "Esegui /setgroup nel gruppo per cambiarlo, oppure /setgroup reset per tornare a config.ini."
            )
        return

    # Validazione gruppo
    if (
        (message.chat.type != ChatType.SUPERGROUP and message.chat.type != getattr(ChatType, "FORUM", None))
        or not getattr(message.chat, "is_forum", False)
    ):
        await message.reply_text("⚠️ Questo gruppo non ha i Topic attivi: attivali e riprova.")
        return

    try:
        member = await client.get_chat_member(message.chat.id, "me")
    except RPCError as e:
        await message.reply_text(
            f"⚠️ Non riesco a verificare i miei permessi in questo gruppo: {e}"
        )
        return

    ok = member.status == ChatMemberStatus.OWNER or (
        member.status == ChatMemberStatus.ADMINISTRATOR
        and getattr(member.privileges, "can_manage_topics", False)
    )
    if not ok:
        await message.reply_text(
            "⚠️ Non sono amministratore di questo gruppo con il diritto «Gestisci argomenti»: aggiungilo e riprova."
        )
        return

    precedente = core.ops_chat_id()
    core.set_ops_chat_override(message.chat.id)
    testo = (
        f"✅ Gruppo operatori impostato: <code>{message.chat.id}</code> "
        f"({message.chat.title}). I ticket verranno aperti qui."
    )
    # I ticket aperti puntano a topic del gruppo precedente: lì le risposte degli
    # operatori non vengono più inoltrate e lo studente le perde. Vale solo se il
    # gruppo cambia davvero.
    aperti = db.count_open_tickets() if precedente != message.chat.id else 0
    if aperti == 1:
        testo += (
            "\n\n⚠️ 1 ticket resta aperto in un topic del gruppo precedente: le risposte "
            "scritte lì non vengono più inoltrate. Si chiuderà al prossimo messaggio dello "
            "studente, che potrà aprire una nuova richiesta qui."
        )
    elif aperti > 1:
        testo += (
            f"\n\n⚠️ {aperti} ticket restano aperti in topic del gruppo precedente: le "
            "risposte scritte lì non vengono più inoltrate. Si chiuderanno al prossimo "
            "messaggio degli studenti, che potranno aprire nuove richieste qui."
        )
    await message.reply_text(testo)


@Client.on_callback_query(filters.regex(r"^admin:stats$") & core.admin_filter)
async def stats(client: Client, cq: CallbackQuery):
    await _answer(cq)
    await _edit(
        client,
        cq,
        f"👥 Utenti: {db.count_users()}\n"
        f"🎫 Ticket aperti: {db.count_open_tickets()}\n"
        f"📨 Ticket totali: {db.count_tickets()}\n"
        f"🚫 Bannati: {db.count_banned()}\n\n"
        f"🕒 Aggiornato alle {datetime.now():%H:%M:%S}",
        reply_markup=structures.admin_keyboard(),
    )


@Client.on_callback_query(filters.regex(r"^admin:tickets$") & core.admin_filter)
async def tickets(client: Client, cq: CallbackQuery):
    await _answer(cq)
    rows = db.list_open_tickets()
    text = (
        "\n".join(f"• <code>{uid}</code> — {created_at}" for uid, _tid, created_at in rows)
        if rows
        else "Nessun ticket aperto."
    )
    await _edit(client, cq, text, reply_markup=structures.admin_keyboard())


@Client.on_callback_query(filters.regex(r"^admin:broadcast$") & core.admin_filter)
async def broadcast_start(client: Client, cq: CallbackQuery):
    core.broadcast_wait.add(cq.from_user.id)
    await _answer(cq)
    await _edit(
        client,
        cq,
        "Invia ora il messaggio da inoltrare a tutti gli utenti (testo o media).",
        reply_markup=structures.broadcast_prompt_keyboard(),
    )


@Client.on_callback_query(filters.regex(r"^admin:admins$") & core.admin_filter)
async def admins_view(client: Client, cq: CallbackQuery):
    await _answer(cq)
    text, runtime = _admins_view()
    await _edit(client, cq, text, reply_markup=structures.admins_keyboard(runtime))


@Client.on_callback_query(filters.regex(r"^admin:add$") & core.admin_filter)
async def admin_add_start(client: Client, cq: CallbackQuery):
    core.admin_add_wait.add(cq.from_user.id)
    await _answer(cq)
    await _edit(client, cq, "Invia l'user ID numerico del nuovo admin.")


@Client.on_callback_query(filters.regex(r"^admin:del:(\d+)$") & core.admin_filter)
async def admin_del(client: Client, cq: CallbackQuery):
    uid = cq.from_user.id
    target = int(cq.matches[0].group(1))

    if target == uid:
        await _answer(cq, "Non puoi rimuovere te stesso.", show_alert=True)
        return
    if target in config.CFG.seed_admins:
        await _answer(cq, "Admin da config: non rimovibile.", show_alert=True)
        return

    db.remove_admin(target)
    core.admin_ids.discard(target)
    await _answer(cq, "Rimosso.")

    text, runtime = _admins_view()
    await _edit(client, cq, text, reply_markup=structures.admins_keyboard(runtime))



@Client.on_callback_query(filters.regex(r"^admin:ops$") & core.admin_filter)
async def operators_view(client: Client, cq: CallbackQuery):
    await _answer(cq)
    text, ops = _operators_view()
    await _edit(client, cq, text, reply_markup=structures.operators_keyboard(ops))


@Client.on_callback_query(filters.regex(r"^admin:opadd$") & core.admin_filter)
async def operator_add_start(client: Client, cq: CallbackQuery):
    core.operator_add_wait.add(cq.from_user.id)
    await _answer(cq)
    await _edit(client, cq, structures.OPERATOR_ADD_PROMPT)


@Client.on_callback_query(filters.regex(r"^admin:opdel:(\d+)$") & core.admin_filter)
async def operator_del(client: Client, cq: CallbackQuery):
    target = int(cq.matches[0].group(1))
    db.remove_operator(target)
    core.operator_ids.discard(target)
    await _answer(cq, "Rimosso.")

    text, ops = _operators_view()
    await _edit(client, cq, text, reply_markup=structures.operators_keyboard(ops))

@Client.on_callback_query(filters.regex(r"^broadcast:confirm$") & core.admin_filter)
async def broadcast_confirm(client: Client, cq: CallbackQuery):
    uid = cq.from_user.id

    if core.broadcast_lock.locked():
        await _answer(cq, "Broadcast già in corso.", show_alert=True)
        return

    src = core.broadcast_msg.pop(uid, None)
    if src is None:
        await _answer(cq, "Nessun messaggio in attesa di conferma.", show_alert=True)
        return

    await _answer(cq)

    targets = db.broadcast_user_ids()
    total = len(targets)
    ok = fail = 0

    async with core.broadcast_lock:
        for i, target in enumerate(targets, start=1):
            try:
                await core.call_with_flood(client.copy_message, target, src[0], src[1])
                ok += 1
            except RPCError:
                fail += 1

            if i % 10 == 0:
                await _edit(client, cq, f"Invio… {i}/{total}")

        testo = f"✅ Inviato a {ok} utenti, falliti: {fail}."
        if fail:
            testo += (
                "\n\nℹ️ I falliti sono utenti che hanno bloccato il bot o che non "
                "l'hanno mai avviato: non è possibile raggiungerli."
            )
        await _edit(
            client,
            cq,
            testo,
            reply_markup=structures.admin_keyboard(),
        )


@Client.on_callback_query(filters.regex(r"^broadcast:cancel$") & core.admin_filter)
async def broadcast_cancel(client: Client, cq: CallbackQuery):
    core.broadcast_wait.discard(cq.from_user.id)
    core.broadcast_msg.pop(cq.from_user.id, None)
    await _answer(cq)
    await _edit(client, cq, "❌ Annullato.", reply_markup=structures.admin_keyboard())


@Client.on_message(
    filters.private
    & filters.incoming
    & ~filters.service
    & ~filters.regex(r"^/")
    & core.admin_filter
    & core.pending_input_filter
)
async def admin_input(client: Client, message: Message):
    uid = message.from_user.id

    # I comandi (/admin, /annulla, /start, /close) sono gestiti altrove.
    if (message.text or "").startswith("/"):
        return

    if uid in core.broadcast_wait:
        core.broadcast_wait.discard(uid)
        core.broadcast_msg[uid] = (message.chat.id, message.id)
        destinatari = db.broadcast_user_ids()
        await message.reply_text(
            f"Confermi l'invio a {len(destinatari)} utenti?",
            reply_markup=structures.broadcast_confirm_keyboard(),
        )
        return

    if uid in core.admin_add_wait:
        core.admin_add_wait.discard(uid)
        try:
            new_id = int((message.text or "").strip())
        except (TypeError, ValueError):
            core.admin_add_wait.add(uid)
            await message.reply_text("ID non valido. Invia l'user ID numerico.")
            return

        db.add_admin(new_id)
        core.admin_ids.add(new_id)
        await message.reply_text(f"✅ Admin {new_id} aggiunto.")

    if uid in core.operator_add_wait:
        core.operator_add_wait.discard(uid)
        try:
            new_id = int((message.text or "").strip())
        except (TypeError, ValueError):
            core.operator_add_wait.add(uid)
            await message.reply_text("ID non valido. Invia l'user ID numerico.")
            return

        if db.is_admin(new_id):
            await message.reply_text(
                f"{new_id} è admin: può già rispondere agli studenti."
            )
            return

        db.add_operator(new_id)
        core.operator_ids.add(new_id)
        await message.reply_text(f"✅ Operatore {new_id} aggiunto.")
        return


@Client.on_message(filters.command("annulla") & filters.private & core.admin_filter)
async def annulla(client: Client, message: Message):
    uid = message.from_user.id
    core.broadcast_wait.discard(uid)
    core.admin_add_wait.discard(uid)
    core.operator_add_wait.discard(uid)
    core.broadcast_msg.pop(uid, None)
    await message.reply_text("Operazione annullata.")
