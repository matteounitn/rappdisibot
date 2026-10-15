"""Lato operatori: inoltro delle risposte dal topic al diretto dell'utente."""

from __future__ import annotations

import logging

from pyrogram import Client, filters
from pyrogram.errors import MessageNotModified, RPCError
from pyrogram.types import CallbackQuery, Message

import core
import db
from . import structures

log = logging.getLogger(__name__)


@Client.on_message(
    core.ops_chat_filter
    & core.operator_filter
    & filters.incoming
    & ~filters.service
    & ~filters.regex(r"^/")
)
async def relay_to_user(client: Client, message: Message):
    uid = db.get_user_by_topic(message.message_thread_id)
    if uid is None:
        # Topic "General", topic sconosciuto o ticket già chiuso.
        return

    try:
        delivered = await core.try_copy(message, uid)
    except RPCError:
        await core.call_with_flood(
            client.send_message,
            message.chat.id,
            structures.USER_BLOCKED_TEXT,
            message_thread_id=message.message_thread_id,
        )
        return

    if not delivered:
        await core.call_with_flood(
            client.send_message,
            message.chat.id,
            structures.OPERATOR_UNSUPPORTED_TEXT,
            message_thread_id=message.message_thread_id,
        )


@Client.on_message(
    filters.command("close") & core.ops_chat_filter & core.operator_filter
)
async def close(client: Client, message: Message):
    tid = message.message_thread_id
    if tid is None:
        await message.reply_text("Usa /close dentro il topic del ticket.")
        return

    uid = db.get_user_by_topic(tid)
    if uid is None:
        await message.reply_text("Nessun ticket aperto associato a questo topic.")
        return

    async with core.lock_for(uid):
        db.close_ticket(uid)
        try:
            await core.call_with_flood(
                client.send_message,
                uid,
                structures.TICKET_CLOSED_USER_TEXT,
                reply_markup=structures.start_keyboard(),
            )
        except RPCError:
            pass
        await core.send_ban_notice(client, message.chat.id, tid, uid)
        try:
            await core.call_with_flood(client.close_forum_topic, message.chat.id, tid)
        except RPCError:
            pass

    # Il topic è appena stato chiuso: la conferma è cosmetica e non deve far
    # fallire l'handler (postare in un topic chiuso può essere rifiutato).
    try:
        await message.reply_text("✅ Ticket chiuso.")
    except RPCError:
        pass

@Client.on_message(
    filters.command("allontana") & core.ops_chat_filter & core.operator_filter
)
async def allontana_command(client: Client, message: Message):
    if len(message.command) == 1:
        if message.message_thread_id is None:
            await message.reply_text(structures.ALLONTANA_USAGE_TEXT)
            return
        uid = db.get_user_by_topic_any(message.message_thread_id)
        if uid is None:
            await message.reply_text(structures.NO_TICKET_IN_TOPIC_TEXT)
            return
        if db.is_banned(uid):
            await message.reply_text(structures.ALREADY_BANNED_TEXT)
            return
        await message.reply_text(
            structures.ban_confirm_text(uid),
            reply_markup=structures.ban_confirm_keyboard(uid),
        )
        return

    uid = core.resolve_target(message.command[1])
    if uid is None:
        await message.reply_text(structures.TARGET_NOT_FOUND_TEXT)
        return
    if db.is_banned(uid):
        await message.reply_text(structures.ALREADY_BANNED_TEXT)
        return
    await message.reply_text(
        structures.ban_confirm_text(uid),
        reply_markup=structures.ban_confirm_keyboard(uid),
    )


@Client.on_message(
    filters.command("riammetti") & core.ops_chat_filter & core.operator_filter
)
async def unban_command(client: Client, message: Message):
    if len(message.command) < 2:
        await message.reply_text(structures.UNBAN_USAGE_TEXT)
        return
    uid = core.resolve_target(message.command[1])
    if uid is None:
        await message.reply_text(structures.TARGET_NOT_FOUND_TEXT)
        return
    if not db.is_banned(uid):
        await message.reply_text(structures.NOT_BANNED_TEXT)
        return
    db.set_banned(uid, False)
    await message.reply_text(structures.UNBANNED_TEXT)


async def _answer_cq(cq: CallbackQuery, text: str | None = None) -> None:
    try:
        if text:
            await cq.answer(text)
        else:
            await cq.answer()
    except RPCError:
        pass


async def _edit_cq(cq: CallbackQuery, text: str, reply_markup=None) -> None:
    try:
        await core.call_with_flood(
            cq.edit_message_text,
            text,
            reply_markup=reply_markup,
        )
    except MessageNotModified:
        pass
    except RPCError as e:
        log.warning("Aggiornamento del messaggio non riuscito: %s", e)


@Client.on_callback_query(
    filters.regex(r"^ban:ask:(\d+)$") & core.ops_chat_filter & core.operator_filter
)
async def ban_ask_callback(client: Client, cq: CallbackQuery):
    uid = int(cq.matches[0].group(1))
    await _answer_cq(cq)
    await _edit_cq(
        cq,
        structures.ban_confirm_text(uid),
        reply_markup=structures.ban_confirm_keyboard(uid),
    )


@Client.on_callback_query(
    filters.regex(r"^ban:yes:(\d+)$") & core.ops_chat_filter & core.operator_filter
)
async def ban_yes_callback(client: Client, cq: CallbackQuery):
    uid = int(cq.matches[0].group(1))
    db.set_banned(uid, True)
    await _answer_cq(cq, "🚫 Utente allontanato")
    username = db.get_username(uid)
    target = f"@{username}" if username else str(uid)
    await _edit_cq(
        cq,
        structures.banned_notice_text(uid, target),
        reply_markup=structures.unban_keyboard(uid),
    )


@Client.on_callback_query(
    filters.regex(r"^ban:no:(\d+)$") & core.ops_chat_filter & core.operator_filter
)
async def ban_no_callback(client: Client, cq: CallbackQuery):
    await _answer_cq(cq, "Annullato")
    await _edit_cq(
        cq,
        structures.BAN_CANCELLED_TEXT,
        reply_markup=None,
    )


@Client.on_callback_query(
    filters.regex(r"^unban:(\d+)$") & core.ops_chat_filter & core.operator_filter
)
async def unban_callback(client: Client, cq: CallbackQuery):
    uid = int(cq.matches[0].group(1))
    db.set_banned(uid, False)
    await _answer_cq(cq, "✅ Blocco rimosso")
    await _edit_cq(
        cq,
        structures.CLOSE_NOTICE_TEXT,
        reply_markup=structures.close_notice_keyboard(uid),
    )
@Client.on_message(
    filters.command("help") & core.ops_chat_filter & core.operator_filter
)
async def help_command(client: Client, message: Message):
    await message.reply_text(structures.OPERATOR_HELP_TEXT)
