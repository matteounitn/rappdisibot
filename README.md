# RappDisiBot

## Setup
### Step 0
- `git clone https://github.com/matteotn/rappdisibot.git`
### Step 1
- Go to https://my.telegram.org/auth?to=apps;
- Create an app(doesn't matter how do you call it);
- Get API ID and API KEYS;
- Replace them in `config.ini.example` and save it as `config.ini`
### Step 2
- Edit `plugins/structures.py` and set your id in the `admin=["ID"]`. This let you use `/helper @username` command.
### Step 3
- Get your api KEY with `botfather` (telegram side)
(If you don't know how to get bot API KEY just google "How to create bot with botfather telegram")

## How to install without Docker
### Step 0 Dependencies
- Install Redis `sudo apt install redis-server`
- Start Redis server with `redis-server`
- execute `pip3 install -U -r requirements.txt`
### Step 1
- Start your bot with `python3 bot.py -t TOKEN`.
(TOKEN is the one you got using botfather)

#### Example
Assuming your token is `123456:drtgfxcdfrgbvdcvfd`

`python3 bot.py -t 123456:drtgfxcdfrgbvdcvfd`

##### Using screen (background running)
`screen -dmS mybot python3 bot.py -t 123456:drtgfxcdfrgbvdcvfd`

and close the instance with

`screen -X -S mybot quit`

## How to install with docker

This is easier, but the DB is **internal to the container.**

If you remove or update the container **without backupping the db**, it will be lost.

### Step 0
- `docker build -t rappdisibot . `
### Step 1
- `docker run -d --name mybot -e token=YOURTOKENHERE rappdisibot` where YOURTOKENHERE is the token obtained in **Set Up - Step 3** from _@botFather_
- Check logs with `docker logs mybot`
- If you want, you can **access the bot files**: `docker run -d --name mybot -e token=YOURTOKENHERE -v /path/to/desidered/folder:/bot rappdisibot`

**File binding is recommended because you can backup your files. (you can also backup db)**

#### Example

Assuming your token is `123456:drtgfxcdfrgbvdcvfd`

- `docker run -d --name mybot -e token=123456:drtgfxcdfrgbvdcvfd rappdisibot` without file binding.

Assuming you want files in `/home/myuser/mybot`

- `docker run -d --name mybot -e token=123456:drtgfxcdfrgbvdcvfd -v /home/myuser/mybot:/bot rappdisibot` with file binding


### Backup your redis DB in docker
Assuming your token is `123456:drtgfxcdfrgbvdcvfd`

Assuming you had files in `/home/myuser/mybot`, by running the container with this command:

`docker run -d --name mybot -e token=123456:drtgfxcdfrgbvdcvfd -v /home/myuser/mybot:/bot rappdisibot` 

you can easily backup your redis instance by doing:

- `docker exec -it mybot bash`
- make sure you are in /bot using `pwd`
- `redis-cli`
- `select 10`
- `BGSAVE`
- if you didn't change redis backup location, you should have your backup file `dump.rdb` inside `/bot` folder.
- `quit`
- `exit`

Now you should have your `dump.rdb` in `/home/myuser/mybot` (or whatever bind you used before).

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
