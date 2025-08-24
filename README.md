🕵️ Spy x Civilians Telegram Bot

A multiplayer social deduction game bot for Telegram, inspired by “Spyfall”.
Players join a group, one (or more) becomes the Spy, and others are Civilians who know a secret location. The Spy must deduce the location while Civilians try to catch them.

Built with Telethon, Flask (for Render keep-alive), and PostgreSQL (for persistent storage).

🚀 Features

🎮 Multiple game modes (Classic, Fake Civilian, Double Spy, Chaos)

🗳️ Discussion, voting, and result phases

📍 Custom locations (per-group, persistent in database)

👥 Player management (/join, /remove, /players)

🛑 Admin controls (/stopgame, /resetlocations)

📢 Owner broadcast command

🗄️ PostgreSQL persistence for users & locations

📦 Requirements

Python 3.9+

PostgreSQL database (for storing users and custom locations)

Python Packages

Listed in requirements.txt (create one if not already):

telethon
flask
psycopg[binary]

⚙️ Configuration

Set the following environment variables (Render, Railway, or .env file):

API_ID=your_telegram_api_id
API_HASH=your_telegram_api_hash
BOT_TOKEN=your_bot_token
OWNER_ID=your_tg_user_id
DATABASE_URL=postgresql://user:password@host:port/dbname


👉 DATABASE_URL must point to your Postgres instance.

▶️ Running Locally

Clone the repo and install dependencies:

pip install -r requirements.txt


Run the bot:

python main.py


Open Telegram and type /start to the bot.

☁️ Deployment

Works on Render, Railway, or any service that supports long-running Python apps.

A small Flask server is included in main.py to keep the service alive on Render.

Just set env vars on the platform, deploy, and it runs 24/7.

🎮 Commands
General

/start – Start private chat with the bot

/startgame – Start a new game in a group

/join – Join a running game

/players – Show current players

/begin – Assign roles & begin game

/status – Show game status

/extend – Extend discussion by 1 min

/guess <location> – Spy guesses the location

Admin

/stopgame – Stop current game

/remove <user> – Remove a player

/addlocation <name> – Add custom location

/removelocation <name> – Remove custom location

/listlocations – Show all available locations

/resetlocations – Reset custom locations for the group

Owner Only

/broadcast <message> – Send a message to all registered users

🗄️ Database

Tables created:

CREATE TABLE IF NOT EXISTS users (
    user_id BIGINT PRIMARY KEY
);

CREATE TABLE IF NOT EXISTS locations (
    chat_id BIGINT NOT NULL,
    location TEXT NOT NULL,
    PRIMARY KEY (chat_id, location)
);


users → tracks all players who started the bot

locations → tracks custom per-group locations

✅ Both tables are persistent across restarts/redeploys.

📜 License

MIT – free to use and modify.