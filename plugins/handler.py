import time

from pyrogram import Client, Filters, InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.errors import FloodWait, BadRequest

from plugins.structures import assistant_icon
from . import structures

once = False
msgs = {}


@Client.on_message(Filters.command(["start", "help"]))
def start(client, message):
    if structures.isHelper(message.from_user.id):
        message.reply(
            "Benvenuto 👋\nAttraverso questo bot potrai fornire assistenza agli studenti.\n\nIl primo rappresentante che accetta la richiesta, apre una chat con lo studente.\n\nStato attuale:\n**Rappresentante** ✅")
    elif not structures.isBanned(message.from_user.id):
        if structures.antiflood(message.from_user.id, 'start', sec=5):
            message.reply(
                "Benvenuto 👋\n**Scrivi la tua richiesta** e mi occuperò di inoltrarla ai rappresentanti.\n\nTi darò la possibilità di rimanere anonimo (🕵️‍♂️).")
    elif structures.antiflood(message.from_user.id, 'start', sec=10):
        message.reply(f"{assistant_icon}: Sei stato bloccato per l'uso improprio del bot.")


def notifyOthers(text, iduser, callback_query, show_keyboard=True):
    hasMedia = structures.get(iduser, 'media')
    keyboard = None
    if hasMedia is not False and show_keyboard:
        keyboard = [[
            InlineKeyboardButton(
                "🖼 Vedi Media",
                callback_data=f"media_{iduser}"
            )
        ]]
    if iduser in msgs:
        for msg in msgs[iduser]:
            if msg.chat.id != callback_query.message.chat.id:
                try:
                    if hasMedia is not False and show_keyboard:
                        msg.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
                    else:
                        msg.edit_text(text)
                except FloodWait as f:
                    print(f)
                    time.sleep(f.x)
                    if hasMedia is not False and show_keyboard:
                        msg.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
                    else:
                        msg.edit_text(text)
                except Exception as e:
                    print(e)
        msgs[iduser].clear()
        return True
    else:
        callback_query.message.delete()
        return False


@Client.on_callback_query()
def callbackAnswer(client, callback_query):
    try:
        if callback_query.data == "userNormal":
            client.edit_message_text(callback_query.message.chat.id, callback_query.message.message_id,
                                     f"{assistant_icon}: Abbiamo ricevuto la tua richiesta.")
            structures.set(callback_query.message.chat.id, 'anonymous', False)
            askForHelp(client, callback_query.from_user.first_name, callback_query.from_user.id,
                       structures.get(callback_query.message.chat.id, 'message'))

        elif callback_query.data == "userAnonymous":
            client.edit_message_text(callback_query.message.chat.id, callback_query.message.message_id,
                                     f"{assistant_icon}: Abbiamo ricevuto la tua richiesta.")
            structures.set(callback_query.message.chat.id, 'anonymous', True)
            askForHelp(client, callback_query.from_user.first_name, callback_query.from_user.id,
                       structures.get(callback_query.message.chat.id, 'message'), True)
        elif "helperAnonymous" in callback_query.data:
            if structures.getHelper(callback_query.message.chat.id, 'connectedWith') is False:
                iduser = callback_query.data.split("_")[1]
                if not notifyOthers(
                        f"{assistant_icon}: La richiesta è stata presa in carico.\n\nIl messaggio dell'utente è:\n\n__{structures.get(iduser, 'message')}__",
                        iduser, callback_query):
                    return
                hasMedia = structures.get(iduser, 'media')
                if hasMedia is not False:
                    keyboard = [[
                        InlineKeyboardButton(
                            "🖼 Vedi Media",
                            callback_data=f"media_{iduser}"
                        )
                    ]]
                    client.edit_message_text(callback_query.message.chat.id, callback_query.message.message_id,
                                             f"{assistant_icon}: Fatto! Da adesso in poi risponderai all'utente.\nFai /end per concludere la chat.\n\n__Il messaggio era: {structures.get(iduser, 'message')}__",
                                             reply_markup=InlineKeyboardMarkup(keyboard))
                else:
                    client.edit_message_text(callback_query.message.chat.id, callback_query.message.message_id,
                                             f"{assistant_icon}: Fatto! Da adesso in poi risponderai all'utente.\nFai /end per concludere la chat.\n\n__Il messaggio era: {structures.get(iduser, 'message')}__")
                time.sleep(0.5)
                try:
                    client.send_message(iduser,
                                        f"{assistant_icon}: La tua richiesta è stata processata.\n\n__(la chat inizia ora, concludila con__ /end __quando hai finito)__.")
                except Exception as e:
                    print(e)
                    check = str(e).split(":")[0]
                    if check == "[400 USER_IS_BLOCKED]":
                        client.send_message(callback_query.message.chat.id,
                                            f"{assistant_icon}: L'utente ha bloccato il bot! Annullo.")
                    return

                structures.setHelper(callback_query.message.chat.id, 'anonymous', True)
                structures.antiflood(str(callback_query.message.chat.id), 'afkcheck', sec=0)
                structures.setHelper(callback_query.message.chat.id, 'connectedWith', iduser)
                structures.set(iduser, 'connectedWith', callback_query.message.chat.id)
                structures.set(iduser, 'status', True)
            else:
                client.send_message(callback_query.message.chat.id,
                                    f"{assistant_icon}: Sei già in chat con un utente!\nFai /end se vuoi rispondere ad un altro utente.")
        elif "helperNormal" in callback_query.data:
            if structures.getHelper(callback_query.message.chat.id, 'connectedWith') is False:
                iduser = callback_query.data.split("_")[1]
                if not notifyOthers(
                        f"{assistant_icon}: La richiesta è stata presa in carico da [{callback_query.from_user.first_name}](tg://user?id={callback_query.message.chat.id})\n\nIl messaggio dell'utente è:\n\n__{structures.get(iduser, 'message')}__",
                        iduser, callback_query):
                    return
                hasMedia = structures.get(iduser, 'media')
                if hasMedia is not False:
                    keyboard = [[
                        InlineKeyboardButton(
                            "🖼 Vedi Media",
                            callback_data=f"media_{iduser}"
                        )
                    ]]
                    client.edit_message_text(callback_query.message.chat.id, callback_query.message.message_id,
                                             f"{assistant_icon}: Fatto! Da adesso in poi risponderai all'utente.\nFai /end per concludere la chat.\n\n__Il messaggio era: {structures.get(iduser, 'message')}__",
                                             reply_markup=InlineKeyboardMarkup(keyboard))
                else:
                    client.edit_message_text(callback_query.message.chat.id, callback_query.message.message_id,
                                             f"{assistant_icon}: Fatto! Da adesso in poi risponderai all'utente.\nFai /end per concludere la chat.\n\n__Il messaggio era: {structures.get(iduser, 'message')}__")
                time.sleep(0.5)
                try:
                    client.send_message(iduser,
                                        f"{assistant_icon}: La tua richiesta è stata processata da [{callback_query.from_user.first_name}](tg://user?id={callback_query.message.chat.id}).\nLa chat inizia ora, concludila con /end quando hai finito.")
                except Exception as e:
                    print(e)
                    check = str(e).split(":")[0]
                    if check == "[400 USER_IS_BLOCKED]":
                        client.send_message(callback_query.message.chat.id,
                                            f"{assistant_icon}: L'utente ha bloccato il bot! Annullo.")
                    return
                structures.setHelper(callback_query.message.chat.id, 'anonymous', False)
                structures.antiflood(str(callback_query.message.chat.id), 'afkcheck', sec=0)
                structures.setHelper(callback_query.message.chat.id, 'connectedWith', iduser)
                structures.set(iduser, 'connectedWith', callback_query.message.chat.id)
                structures.set(iduser, 'status', True)
            else:
                client.send_message(callback_query.message.chat.id,
                                    f"{assistant_icon}: Sei già in chat con un utente!\nFai /end se vuoi rispondere ad un altro utente.")
        elif "blockUser" in callback_query.data:
            iduser = callback_query.data.split("_")[1]
            if not notifyOthers(
                    f"{assistant_icon}: L'utente è stato bloccato da [{callback_query.from_user.first_name}](tg://user?id={callback_query.message.chat.id})\nIl messaggio dell'utente è:\n\n__{structures.get(iduser, 'message')}__",
                    iduser, callback_query):
                return
            if structures.get(iduser, 'rejected') is not False:
                structures.set(iduser, 'rejected', structures.get(iduser, 'rejected') + 1)
            else:
                structures.set(iduser, 'rejected', 1)
            if structures.toggleBan(iduser):
                client.edit_message_text(callback_query.message.chat.id, callback_query.message.message_id,
                                         f"{assistant_icon}: Ho sbannato l'utente dal bot.",
                                         reply_markup=InlineKeyboardMarkup(
                                             [[InlineKeyboardButton("🚫 Blocca utente ",
                                                                    callback_data=f"blockUser_{iduser}")]]))
                structures.redisWR(structures.userAF, str(iduser), 'handler', 0)
            else:
                client.edit_message_text(callback_query.message.chat.id, callback_query.message.message_id,
                                         f"{assistant_icon}: Ho bannato l'utente dal bot.",
                                         reply_markup=InlineKeyboardMarkup(
                                             [[InlineKeyboardButton("✅ Sblocca utente ",
                                                                    callback_data=f"blockUser_{iduser}")]]))
        elif callback_query.data == "cancelCurrentOperation":
            client.edit_message_text(callback_query.message.chat.id, callback_query.message.message_id,
                                     f"{assistant_icon}: Ho annullato l'operazione.")
            structures.redisWR(structures.userAF, str(callback_query.message.chat.id), 'handler', 0)
        elif callback_query.data == "aBroadcastConfirm":
            client.edit_message_text(callback_query.message.chat.id, callback_query.message.message_id,
                                     f"{assistant_icon}: Procedo all'invio!",
                                     reply_markup=InlineKeyboardMarkup(structures.BackKeyboard))
            sendBroadcast(client)
        elif callback_query.data == "close":
            callback_query.message.delete()
        elif "delRequest" in callback_query.data:
            iduser = callback_query.data.split("_")[1]
            if not notifyOthers(
                    f"{assistant_icon}: La richiesta è stata scartata da [{callback_query.from_user.first_name}](tg://user?id={callback_query.message.chat.id}).",
                    iduser, callback_query, show_keyboard=False):
                return
            client.edit_message_text(callback_query.message.chat.id, callback_query.message.message_id,
                                     f"{assistant_icon}: Ho scartato la richiesta.\n\nIl messaggio dell'utente:\n\n__{structures.get(iduser, 'message')}__")
            structures.redisWR(structures.userAF, str(iduser), 'handler', 0)
            client.send_message(iduser,
                                f"{assistant_icon}: I rappresentanti hanno scartato la tua richiesta.")
            if structures.get(iduser, 'rejected') is not False:
                structures.set(iduser, 'rejected', structures.get(iduser, 'rejected') + 1)
            else:
                structures.set(iduser, 'rejected', 1)
        elif "media" in callback_query.data:
            iduser = callback_query.data.split("_")[1]
            hasMedia = structures.get(iduser, 'media')
            if hasMedia is not False:
                client.send_cached_media(callback_query.message.chat.id, hasMedia)
    except BadRequest as e:
        print(e)
        client.send_message("@matteounitn", f"Errore handler:\n{e}")
        callback_query.answer()

    except FloodWait as f:
        print("FLOODWAIT for " + str(f.x) + " seconds.")
        callback_query.answer()
        time.sleep(f.x)


@Client.on_message(Filters.command("end"))
def end(client, message):
    if structures.isHelper(message.from_user.id) and structures.isInSession(message.from_user.id, type='helper'):
        try:
            client.send_message(structures.getHelper(message.from_user.id, 'connectedWith'),
                                f"{assistant_icon}: Il rappresentante ha concluso la chat.")
        except:
            pass
        structures.redisWR(structures.userAF, str(structures.getHelper(message.from_user.id, 'connectedWith')),
                           'handler', 0)
        structures.set(structures.getHelper(message.from_user.id, 'connectedWith'), 'status', False)
        structures.setHelper(message.from_user.id, 'connectedWith', False)

        try:
            message.reply(
                f"{assistant_icon}: Hai concluso la chat.")

        except:
            pass
    elif structures.isInSession(message.from_user.id) and not structures.isBanned(message.from_user.id):
        structures.set(message.from_user.id, 'status', False)
        try:
            client.send_message(structures.get(message.from_user.id, 'connectedWith'),
                                f"{assistant_icon}: L'utente ha concluso la chat.")
        except:
            pass
        structures.setHelper(structures.get(message.from_user.id, 'connectedWith'), 'connectedWith', False)
        structures.redisWR(structures.userAF, str(message.from_user.id), 'handler', 0)
        try:
            message.reply(
                f"{assistant_icon}: Hai concluso la chat.")

        except:
            pass


def forward(client, message, anon):
    try:
        client.forward_messages(structures.get(message.from_user.id, 'connectedWith'), message.chat.id,
                                message.message_id,
                                as_copy=anon)
        structures.redisWR(structures.userAF, str(structures.get(message.from_user.id, 'connectedWith')), 'afkcheck',
                           int(time.time()))
    except FloodWait as e:
        print(e)
        time.sleep(e.x)
        forward(client, message, anon)
    except Exception as e:
        print(e)
        check = str(e).split(":")[0]
        if check == "[400 USER_IS_BLOCKED]":
            message.reply(f"{assistant_icon}: Per motivi organizzativi, la chat è stata annullata. Rifai la richiesta.")
            structures.set(message.from_user.id, 'status', False)
            structures.setHelper(structures.get(message.from_user.id, 'connectedWith'), 'connectedWith', False)
            structures.redisWR(structures.userAF, str(message.from_user.id), 'handler', 0)
        else:
            client.send_message("@matteounitn",
                                f"Errore \n{e}\n\n [{message.from_user.first_name}](tg://user?id={message.from_user.id})")
            message.reply(
                f"{assistant_icon}: Qualcosa è andato storto!\nGli amministratori sono già stati avvisati del problema.")


def answerHelper(client, message, anon):
    try:
        client.forward_messages(structures.getHelper(message.from_user.id, 'connectedWith'), message.chat.id,
                                message.message_id,
                                as_copy=anon)
        structures.redisWR(structures.userAF, str(message.from_user.id), 'afkcheck', int(time.time()))
    except FloodWait as e:
        print(e)
        time.sleep(e.x)
        answerHelper(client, message, anon)
    except Exception as e:
        print(e)
        check = str(e).split(":")[0]
        if check == "[400 USER_IS_BLOCKED]":
            message.reply(f"{assistant_icon}: L'utente ha fermato il bot! Annullo la chat.")
            structures.redisWR(structures.userAF, str(structures.getHelper(message.from_user.id, 'connectedWith')),
                               'handler', 0)
            structures.set(structures.getHelper(message.from_user.id, 'connectedWith'), 'status', False)
            structures.setHelper(message.from_user.id, 'connectedWith', False)
        else:
            client.send_message("@matteounitn",
                                f"Errore \n{e}\n\n [{message.from_user.first_name}](tg://user?id={message.from_user.id})")
            message.reply(
                f"{assistant_icon}: Qualcosa è andato storto!\nGli amministratori sono già stati avvisati del problema.")


def askForHelp(client, first_name, userid, text, anon=False):
    if not anon:
        nome = first_name
        link = f"tg://user?id={userid}"
    else:
        nome = "Anonymous"
        link = None
    if str(userid) not in msgs:
        msgs[str(userid)] = []
    else:
        msgs[str(userid)].clear()
    helperKeyboard = [[  # First row
        InlineKeyboardButton(  # Generates a callback query when pressed
            "🕵️‍♂️ Anonimo",
            callback_data=f"helperAnonymous_{userid}"
        ),
        InlineKeyboardButton(  # Generates a callback query when pressed
            "💬 Normale",
            callback_data=f"helperNormal_{userid}"
        ),
    ],
        [
            InlineKeyboardButton(
                "❌ Scarta Richiesta",
                callback_data=f"delRequest_{userid}"
            )
        ],  # secondrow
        [
            InlineKeyboardButton(
                "🚫 Blocca utente",
                callback_data=f"blockUser_{userid}"
            )
        ]  # thirdrow
    ]
    hasMedia = structures.get(userid, 'media')
    if hasMedia is not False:
        helperKeyboard.append([
            InlineKeyboardButton(
                "🖼 Vedi Media",
                callback_data=f"media_{userid}"
            )
        ])
    rejected = ""
    percentage = ""
    if structures.get(userid, 'total') is not False:
        structures.set(userid, 'total', structures.get(userid, 'total') + 1)
        total = f"su {int(structures.get(userid, 'total')) - 1} effettuate."
    else:
        structures.set(userid, 'total', 1)
        total = f"su 1 effettuate"
    if structures.get(userid, 'rejected') is not False:
        percentage = f" (**{round(float(structures.get(userid, 'rejected')) / (float(structures.get(userid, 'total') - 1)), 1) * 100}%** di rifiuti)."
        rejected = f"\n\n__Richieste scartate:\n{structures.get(userid, 'rejected')} {total}__"
    if len(text) > 3296:
        client.send_message(userid,
                            f"{assistant_icon}: La richiesta è troppo lunga!\nRiassumi e rifai la richiesta, i dettagli possono essere spiegati nella **live chat**.")
        structures.redisWR(structures.userAF, str(userid), 'handler', 0)
        return
    for key, value in structures.helper.items():
        if 'connectedWith' not in value or not value['connectedWith']:
            try:
                msg = client.send_message(key,
                                          f"{assistant_icon}: Richiesta di assistenza da parte di [{nome}]({link})\nCon testo:\n\n__{text}__\n\nPremi su uno dei pulsanti per rispondere.{rejected}{percentage}",
                                          reply_markup=InlineKeyboardMarkup(helperKeyboard))
                msgs[str(userid)].append(msg)
            except Exception as e:
                print(e)
    if len(msgs[str(userid)]) == 0:
        client.send_message(userid,
                            f"{assistant_icon}: Mi dispiace, nessun rappresentante è disponibile in questo momento 😔\n__Riprova più tardi con una nuova richiesta!__")
        structures.redisWR(structures.userAF, str(userid), 'handler', 0)


@Client.on_message(Filters.command(["helper"]))
def addHelper(client, message):
    if structures.isAdmin(message.from_user.id):
        toget = message.text.split()
        if len(toget) == 2:
            try:
                usr = client.get_chat(toget[1])
            except Exception as e:
                message.reply(f"{assistant_icon}: Non ho trovato l'utente. Riprova")
                return
        else:
            return
        if usr is not None:
            if str(usr.id) not in structures.helper:
                if usr.last_name is not None:
                    name = f"{usr.first_name} {usr.last_name}"
                else:
                    name = f"{usr.first_name}"
                structures.helper[(str(usr.id))] = {}
                message.reply(f"Ho iscritto [{name}](tg://user?id={usr.id}) alla lista.")
            else:
                del structures.helper[str(usr.id)]
                message.reply(f"Ho disiscritto [{usr.first_name}](tg://user?id={usr.id}) alla lista.")


@Client.on_message(Filters.command(["toggle"]))
def unBan(client, message):
    if structures.isAdmin(message.from_user.id):
        toget = message.text.split()
        if len(toget) == 2:
            try:
                usr = client.get_chat(toget[1])
            except Exception as e:
                message.reply(f"{assistant_icon}: Non ho trovato l'utente. Riprova")
                return
        else:
            return
        if usr is not None:
            if usr.last_name is not None:
                name = f"{usr.first_name} {usr.last_name}"
            else:
                name = f"{usr.first_name}"
            if structures.toggleBan(usr.id):
                message.reply(f"{assistant_icon}: Ho sbannato [{name}](tg://user?id={usr.id}) dal bot.")
                structures.redisWR(structures.userAF, str(usr.id), 'handler', 0)
            else:
                message.reply(f"{assistant_icon}: Ho bannato [{name}](tg://user?id={usr.id}) dal bot.")


def getFileID(message):
    fileId = None
    if message.photo is not None:
        fileId = message.photo.file_id
    elif message.video is not None:
        fileId = message.video.file_id
    elif message.audio is not None:
        fileId = message.audio.file_id
    elif message.document is not None:
        fileId = message.document.file_id
    elif message.sticker is not None:
        fileId = message.sticker.file_id
    elif message.animation is not None:
        fileId = message.animation.file_id
    elif message.voice is not None:
        fileId = message.voice.file_id
    return fileId


@Client.on_message()
def handler(client, message):
    if not structures.isHelper(message.from_user.id):
        if not structures.isBanned(message.from_user.id):
            if not structures.get(message.from_user.id, 'status'):  # he is not in a chat with an connectedWith
                if structures.antiflood(message.from_user.id, 'handler', sec=3600):
                    # askForHelp(client, message)
                    message.reply(f"{assistant_icon}: Come vuoi inviare la richiesta?",
                                  reply_markup=InlineKeyboardMarkup(structures.userKeyboard))

                    if message.media is None:
                        structures.set(message.from_user.id, 'message', message.text)
                        structures.set(message.from_user.id, 'media', False)
                    else:  # ha un media
                        if message.caption is not None:
                            caption = message.caption
                        else:
                            caption = ""
                        structures.set(message.from_user.id, 'media', getFileID(message))
                        structures.set(message.from_user.id, 'message',
                                       f"{caption}\n\n👩🏻‍💼: __L'utente ha allegato un media.__")

                elif structures.antiflood(message.from_user.id, 'handlerAnswer', sec=5):
                    message.reply(
                        f"{assistant_icon}: Puoi fare una richiesta di aiuto ogni ora!\nNon preoccuparti,\n__i rappresentanti hanno preso in considerazione la tua richiesta.__\n\n**Risponderemo il prima possibile.**")
            else:
                anon = structures.get(message.from_user.id, 'anonymous')
                forward(client, message, anon)
    else:
        if structures.getHelper(message.from_user.id, 'connectedWith') is not False:
            answerHelper(client, message, structures.getHelper(message.from_user.id, 'anonymous'))
        else:
            message.reply(f"{assistant_icon}: Non sei in contatto con nessun utente!")


def sendBroadcast(client):
    for user in structures.users.keys():
        try:
            client.send_message(user, structures.brdcst)
        except FloodWait as f:
            print(f)
            time.sleep(f.x)
            client.send_message(user, f"**Broadcast**:\n{structures.brdcst}")
        except BadRequest as e:  # se l'utente ha bloccato, mangia l'evento
            print("[" + str(user) + "] is giving an error: " + str(e))
    structures.brdcst = ""


@Client.on_message(Filters.command(["count"]), group=-1)
def count(client, message):
    if structures.isHelper(message.from_user.id):
        message.reply(f"Il numero di utenti nel database sono {len(structures.users.keys())}")
    message.stop_propagation()


@Client.on_message(Filters.command(["broadcast"]), group=-1)
def broadcast(client, message):
    if structures.isAdmin(message.from_user.id):
        structures.brdcst = message.text.replace("/broadcast ", "")

        message.reply(f"Il messaggio che vuoi inviare è il seguente:\n\n{structures.brdcst}\n\n**Confermi l'invio?**",
                      reply_markup=InlineKeyboardMarkup(structures.BroadcastKeyboard))
        message.stop_propagation()


@Client.on_message(group=500)
def execOnce(client, message):
    global once
    if not once:
        once = True
        print("OK!")
        structures.scheduler.add_job(structures.killStartedConversations, 'interval', minutes=10, args=[client])
