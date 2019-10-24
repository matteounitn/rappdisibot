from pyrogram import Client
import argparse
from plugins import structures
# setto in quale cartella ho i plugins
plugins = dict(
    root="plugins"
)

plugins = dict(
    root="plugins"
)
parser = argparse.ArgumentParser()
parser.add_argument('-a', '--account', action='store', type=str,
                    help="set which session are you using")
parser.add_argument('-t', '--token', action='store', type=str,
                    help="Token to use")

args = parser.parse_args()
if not args.account:
    accountname = "my_account"
else:
    accountname = args.account

if not args.token:
    print("[ERROR] You have to set a token!")
    exit(1)


app = Client(accountname, bot_token=args.token,
             plugins=plugins)  # inizializzo + plugins
print("Avvio bot..")
structures.isBot = True
app.run()  # starto l'app
