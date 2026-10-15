"""Lato utente: /start, pulsante "chiedi aiuto" e inoltro dei messaggi.

Ogni ticket è un topic nella supergruppo operatori (vedi plugins/operators.py).
"""

from __future__ import annotations

import logging

from pyrogram import Client, filters
from pyrogram.errors import MessageNotModified, RPCError
from pyrogram.types import CallbackQuery, LinkPreviewOptions, Message

import core
import db
from . import structures

log = logging.getLogger(__name__)


@Client.on_message(filters.command("start") & filters.private)
async def start(client: Client, message: Message):
    db.upsert_user(message.from_user.id, message.from_user.username)
    await message.reply_text(
        structures.START_TEXT,
        reply_markup=structures.start_keyboard(),
        link_preview_options=LinkPreviewOptions(is_disabled=True),
    )


@Client.on_message(filters.command("help") & filters.private)
async def help_command(client: Client, message: Message):
    is_admin = message.from_user.id in core.admin_ids
    if not is_admin:
        await message.reply_text(
            structures.help_text(is_admin), reply_markup=structures.start_keyboard()
        )
    else:
        await message.reply_text(structures.help_text(is_admin))


@Client.on_callback_query(filters.regex(r"^helpme$"))
async def helpme(client: Client, cq: CallbackQuery):
    if db.is_banned(cq.from_user.id):
        await cq.answer()
        try:
            await cq.edit_message_text(structures.BANNED_USER_TEXT)
        except MessageNotModified:
            pass
        return

    # Prima di qualunque await: il messaggio successivo dell'utente deve trovarlo già impostato.
    core.pending_first.add(cq.from_user.id)
    await cq.answer()
    try:
        await cq.edit_message_text(structures.PROMPT_TEXT)
    except MessageNotModified:
        pass


@Client.on_message(
    filters.private
    & filters.incoming
    & ~filters.service
    & ~filters.regex(r"^/")
    & ~core.pending_input_filter
)
async def relay_to_operators(client: Client, message: Message):
    uid = message.from_user.id

    # Gli input in attesa sono gestiti da plugins/admin.py: il filtro qui sopra
    # li esclude, quindi non serve un controllo dentro l'handler.
    db.upsert_user(uid, message.from_user.username)

    if db.is_banned(uid):
        await message.reply_text(structures.BANNED_USER_TEXT)
        return

    ops_chat = core.ops_chat_id()

    async with core.lock_for(uid):
        topic_id = db.get_open_topic(uid)

        if topic_id is None:
            if uid not in core.pending_first:
                await message.reply_text(
                    structures.NO_TICKET_TEXT, reply_markup=structures.start_keyboard()
                )
                return

            core.pending_first.discard(uid)
            try:
                topic = await core.call_with_flood(
                    client.create_forum_topic,
                    ops_chat,
                    structures.topic_title(message.from_user),
                )
            except RPCError as e:
                # Senza topic non c'è dove inoltrare: avvisa lo studente e
                # rimetti l'attesa, così il prossimo messaggio riprova.
                log.warning(
                    "Creazione del topic non riuscita (gruppo %s, utente %s): %s",
                    ops_chat,
                    uid,
                    e,
                )
                core.pending_first.add(uid)
                await message.reply_text(structures.OPEN_FAILED_TEXT)
                return

            db.create_ticket(uid, topic.id)
            try:
                await core.call_with_flood(
                    client.send_message,
                    ops_chat,
                    structures.topic_intro(message.from_user),
                    message_thread_id=topic.id,
                )
            except RPCError as e:
                # Il ticket è valido lo stesso: si perde solo il messaggio di apertura.
                log.warning("Intro del topic %s non inviata: %s", topic.id, e)
            topic_id = topic.id
        else:
            # Ticket già aperto: il primo messaggio è arrivato, l'attesa non serve più.
            core.pending_first.discard(uid)

        try:
            delivered = await core.try_copy(
                message, ops_chat, message_thread_id=topic_id
            )
        except RPCError:
            db.close_ticket(uid)
            await message.reply_text(
                structures.TICKET_LOST_TEXT, reply_markup=structures.start_keyboard()
            )
            return

        if not delivered:
            # Tipo non inoltrabile: la conversazione resta aperta.
            await message.reply_text(structures.USER_UNSUPPORTED_TEXT)


@Client.on_message(filters.command("close") & filters.private)
async def close(client: Client, message: Message):
    uid = message.from_user.id

    async with core.lock_for(uid):
        topic_id = db.get_open_topic(uid)
        if topic_id is None:
            await message.reply_text(
                structures.NO_TICKET_TEXT, reply_markup=structures.start_keyboard()
            )
            return

        ops_chat = core.ops_chat_id()
        db.close_ticket(uid)
        try:
            await core.call_with_flood(
                client.send_message,
                ops_chat,
                "ℹ️ L'utente ha chiuso la conversazione.",
                message_thread_id=topic_id,
            )
        except RPCError:
            pass
        await core.send_ban_notice(client, ops_chat, topic_id, uid)
        try:
            await core.call_with_flood(
                client.close_forum_topic, ops_chat, topic_id
            )
        except RPCError:
            pass

    await message.reply_text(
        structures.TICKET_CLOSED_USER_TEXT, reply_markup=structures.start_keyboard()
    )
