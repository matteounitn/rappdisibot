# RappDisiBot
## How to install
### Step 0
- Install Redis `sudo apt install redis-server`
- Eventually start Redis server with `redis-server`
### Step 1
- Go to https://my.telegram.org/auth?to=apps;
- Create an app(doesn't matter how do you call it);
- Get API ID and API KEYS;
- Replace them in `config.ini.example` and save it as `config.ini`
### Step 2 Dependencies
- execute `pip3 install -U -r requirements.txt`
- Done.
### Step 3
- Get your api KEY with `botfather` (telegram side)
(If you don't know how to get bot API KEY just google "How to create bot with botfather telegram")
### Step 4
- Edit `plugins/structures.py` and set your id in the `admin=["ID"]`. This let you use `/helper @username` command.
### Step 5
- Start your bot with `python3 bot.py -t TOKEN`.
(TOKEN is the token you got using botfather)

#### Example
Assuming your token is `123456:drtgfxcdfrgbvdcvfd`

`python3 bot.py -t 123456:drtgfxcdfrgbvdcvfd`

##### Using screen (background running)
`screen -dmS mybot python3 bot.py -t 123456:drtgfxcdfrgbvdcvfd`

and close the instance with
`screen -X -S mybot quit`
## Commands
### Admin commands

- `/helper @username` or `/helper id`. Set an user as a helper (Rappresentante)
- `/broadcast message`. Send a message to all the users.
- and Helper commands.

__An admin can't be an user.__

### Helper commands
- `/count`. How many users started the bot.

## To do
* [Multi language using this method or something equivalent](https://phrase.com/blog/posts/translate-python-gnu-gettext/)
