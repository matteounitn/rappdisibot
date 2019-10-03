from pyrogram import Client
import sys
from plugins import structures
# setto in quale cartella ho i plugins
plugins = dict(
    root="plugins"
)
if len(sys.argv) <= 2:
    accountname = "my_account"
    bottoken = "123456:drtgfxcdfrgbvdcvfd"
elif len(sys.argv) == 2:
    accountname = sys.argv[1]
    bottoken = None
elif len(sys.argv) == 3:
    accountname = sys.argv[1]
    bottoken = sys.argv[2]


app = Client(accountname, bot_token=bottoken,
             plugins=plugins)  # inizializzo + plugins
print("Avvio bot..")
structures.isBot = True
app.run()  # starto l'app
