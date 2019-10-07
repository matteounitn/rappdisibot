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
- Insert your bot token in `bot.py`. More precisely:
`app = Client("HERE",plugins=plugins)`
(If you don't know how to get bot API KEY just google "How to create bot with botfather telegram")
### Step 4
- Start your bot with `python3 bot.py`.
### Step 5
- Edit `plugins/structures.py` and set your id. This let you use `/helper @username` command.
