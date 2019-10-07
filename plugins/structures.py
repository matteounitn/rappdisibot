from pottery import RedisDict
from pyrogram import InlineKeyboardButton
from redis import Redis
import time
from apscheduler.schedulers.background import BackgroundScheduler

scheduler = BackgroundScheduler()
redis = Redis.from_url('redis://localhost:6379/10')
scheduler.start()
isBot = False
brdcst = ""
admin = ["387885123"]
userAF = RedisDict(redis=redis, key='usersAF')  # for antiflood
helper = RedisDict(redis=redis, key='helpers')
users = RedisDict(redis=redis, key='users')
assistant_icon = "👩🏻‍💼"
userKeyboard = [[  # First row
    InlineKeyboardButton(  # Generates a callback query when pressed
        "🕵️‍♂️ Anonimo",
        callback_data="userAnonymous"
    ),
    InlineKeyboardButton(  # Generates a callback query when pressed
        "💬 Normale",
        callback_data="userNormal"
    ),
], [InlineKeyboardButton(  # Generates a callback query when pressed
    "🔙 Annulla",
    callback_data="cancelCurrentOperation"
),
]

]

BroadcastKeyboard = [
    [InlineKeyboardButton(  #
        "📣 Conferma!",
        callback_data="aBroadcastConfirm"
    )],  # firstrow
    [InlineKeyboardButton("❌ Chiudi", callback_data="close")]  # secondrow
]
BackKeyboard = [
    [InlineKeyboardButton("❌ Chiudi", callback_data="close")]  # secondrow
]


def current_time(): return int(round(time.time()))


def killStartedConversations(client):
    for key, value in helper.items():
        if 'connectedWith' in value and value['connectedWith'] is not False and antiflood(key, 'afkcheck', sec=3600):
            set(value['connectedWith'], 'status', False)
            client.send_message(value['connectedWith'], f"{assistant_icon}: La chat è stata chiusa per inattività.")
            redisWR(userAF, str(value['connectedWith']), 'handler', 0)
            client.send_message(key, f"{assistant_icon}: La chat è stata chiusa per inattività.")
            setHelper(key, 'connectedWith', False)


def get(chatid, variable):
    if str(chatid) in users:
        if str(variable) in users[str(chatid)]:
            return users[str(chatid)][str(variable)]
    return False


def getHelper(chatid, variable):
    if str(chatid) in helper:
        if str(variable) in helper[str(chatid)]:
            return helper[str(chatid)][str(variable)]
    return False


def set(chatid, variable, value):
    if str(chatid) not in users:
        users[str(chatid)] = {}
    redisWR(users, str(chatid), str(variable), value)


def setHelper(chatid, variable, value):
    if str(chatid) not in helper:
        helper[str(chatid)] = {}
    redisWR(helper, str(chatid), str(variable), value)


def isHelper(id): return str(id) in helper or str(id) in admin


def isAdmin(id): return str(id) in admin


def isBanned(id):
    id = str(id)
    if id not in users:
        users[id] = {}
    if 'banned' not in users[id]:
        redisWR(users, id, 'banned', False)
    return users[id]['banned']


def toggleBan(id):
    id = str(id)
    if id not in users:
        users[id] = {}
    if 'banned' not in users[id]:
        redisWR(users, id, 'banned', False)
    elif users[id]['banned']:
        redisWR(users, id, 'banned', False)
    else:
        redisWR(users, id, 'banned', True)
    if not users[id]['banned']:
        set(id, 'rejected', False)
        set(id, 'total', False)
    return not users[id]['banned']


def redisWR(maindict, keychild, key, value=None, delete=False):
    if not delete:
        tmpdic = maindict[keychild]
        tmpdic[key] = value
        maindict[keychild] = tmpdic
    else:
        tmpdic = maindict[keychild]
        del tmpdic[key]
        maindict[keychild] = tmpdic


def antiflood(id, command, sec=30):
    now = current_time()
    strid = str(id)
    if strid in userAF:
        if command in userAF[strid]:
            if now - userAF[strid][command] >= sec:
                redisWR(userAF, strid, command, now)
                # user[strid][command] = now
                return True
            else:
                return False
        else:
            redisWR(userAF, strid, command, now)
            # user[strid][command] = now
            return True
    else:
        userAF[strid] = {}
        redisWR(userAF, strid, command, now)
        # user[strid][command] = now
        return True


def isInSession(id, type='user'):
    if type == 'user':
        return get(id, 'status')
    else:
        return getHelper(id, 'connectedWith') is not False