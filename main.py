from telethon import TelegramClient, events, Button
from telethon.tl.types import ChannelParticipantsAdmins
import random, asyncio, json, os
from dataclasses import dataclass, field
from typing import Optional, Dict
import threading
from flask import Flask
from db import (
    init_db,
    add_user, get_all_users,
    get_custom_locations_db,
    add_custom_location_db, remove_custom_location_db, reset_custom_locations_db
)

# Dummy Flask app for Render
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is running!"

def run_web():
    app.run(host="0.0.0.0", port=10000)

# Start flask server in background thread
threading.Thread(target=run_web).start()

# Initialize database tables
init_db()

# ---------------- CONFIG ----------------
API_ID = int(os.environ.get("API_ID", 0))
API_HASH = os.environ.get("API_HASH", "")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
OWNER_ID = int(os.environ.get("OWNER_ID", 0))

client = TelegramClient('game_bot', API_ID, API_HASH).start(bot_token=BOT_TOKEN)

# ---- Per-Chat Game State ----
@dataclass
class GameState:
    players: list = field(default_factory=list)
    roles: dict = field(default_factory=dict)
    votes: dict = field(default_factory=dict)
    game_started: bool = False
    discussion_time: int = 60
    game_mode: Optional[str] = None
    setup_state: Optional[str] = None
    game_stage: str = "waiting"
    game_starter: Optional[int] = None
    current_location: Optional[str] = None
    discussion_task: Optional[asyncio.Task] = None

# chat_id -> GameState
game_states: Dict[int, GameState] = {}

def get_state(chat_id: int) -> GameState:
    if chat_id not in game_states:
        game_states[chat_id] = GameState()
    return game_states[chat_id]


# ---- Locations (persistent, per-group) ----
DEFAULT_LOCATIONS = [
    "Hospital 🏥", "Airport ✈️", "Cinema 🎬", "Beach 🏖️", "School 🏫",
    "Restaurant 🍽️", "Museum 🖼️", "Train Station 🚉", "Library 📚", "Park 🌳",
    "Hotel 🏨", "Supermarket 🛒", "Bank 🏦", "Bus Station 🚌", "Church ⛪",
    "Police Station 👮", "Fire Station 🚒", "Shopping Mall 🛍️", "Stadium 🏟️",
    "Zoo 🦁", "Amusement Park 🎡", "Aquarium 🐠", "Factory 🏭", "Farm 🚜",
    "Harbor ⚓", "Office 💼", "Post Office 📮", "Gas Station ⛽", "Theater 🎭",
    "Bowling Alley 🎳", "Gym 🏋️", "Cafe ☕", "Casino 🎰", "Prison 🔒",
    "Concert Hall 🎤", "Race Track 🏎️", "Mountain 🏔️", "Forest 🌲",
    "Cave 🕳️", "Desert 🏜️", "Ice Rink ⛸️", "Volcano 🌋", "Bridge 🌉",
    "Space Station 🛰️", "Castle 🏰", "Palace 👑", "Cemetery ⚰️",
    "Underground Bunker 🛡️", "Laboratory 🔬", "Military Base 🎖️",
    "Courtroom ⚖️", "Ship 🚢", "Submarine 🚤", "Jungle 🐒",
    "Market Bazaar 🕌", "Village 🏘️"
]


def build_locations_for_chat(chat_id: int):
    base = DEFAULT_LOCATIONS.copy()
    custom = get_custom_locations_db(chat_id)
    for loc in custom:
        if loc not in base:
            base.append(loc)
    return base



# ---- Anti-Spam / Throttling ----
COMMAND_COOLDOWN = 1.5   # seconds between command presses per user
BUTTON_COOLDOWN  = 0.75  # seconds between inline button taps per user

_user_cooldowns_cmd = {}
_user_cooldowns_cb  = {}

def _now():
    # monotonic clock via event loop
    return asyncio.get_event_loop().time()

async def throttle(event, key: str, cooldown: float = COMMAND_COOLDOWN, reply=True):
    """Return True if user is throttled (and already notified)."""
    uid = event.sender_id
    k = (getattr(event, "chat_id", None), uid, key)
    last = _user_cooldowns_cmd.get(k, 0)
    t = _now()
    if t - last < cooldown:
        if reply:
            try:
                await event.respond("⚠️ Slow down a bit.")
            except:
                pass
        return True
    _user_cooldowns_cmd[k] = t
    return False

async def throttle_cb(event, key: str, cooldown: float = BUTTON_COOLDOWN):
    """Throttle inline button taps."""
    uid = event.sender_id
    k = (getattr(event, "chat_id", None), uid, key)
    last = _user_cooldowns_cb.get(k, 0)
    t = _now()
    if t - last < cooldown:
        try:
            await event.answer("⏳ Easy there…", alert=False)
        except:
            pass
        return True
    _user_cooldowns_cb[k] = t
    return False


def mention_name(user):
    return f"<a href='tg://user?id={user.id}'>{user.first_name}</a>"


# ---------------- HANDLERS ----------------
@client.on(events.NewMessage(pattern='^/start$'))
async def start_cmd(event):
    if await throttle(event, 'start'): return
    text = (
        "👋 Welcome to *Spy x Civilians* Bot!\n\n"
        "🎮 This is a group game where one player is the Spy 🕵️ "
        "and the rest are Civilians 👥.\n\n"
        "👉 To start a new game in a group, use: /startgame\n"
        "👉 To read the rules: /rules\n"
        "👉 For help: /help\n\n"
        "⚠️ Note: The game is played only in groups, but some information "
        "will be sent to you here in private chat."
    )
    await event.respond(text, parse_mode="markdown")

    # Save user id (persistent in Postgres)
    uid = event.sender_id
    await asyncio.to_thread(add_user, uid)



@client.on(events.NewMessage(pattern='/startgame'))
async def start_game(event):
    if await throttle(event, 'startgame'): return
    s = get_state(event.chat_id)
    if s.game_started:
        await event.respond("⚠️ Game already running!")
        return

    s.players.clear()
    s.roles.clear()
    s.votes.clear()
    s.game_started = True
    s.game_mode = None
    s.setup_state = "waiting_time"
    s.game_starter = event.sender_id
    s.game_stage = "joining"
    s.current_location = None
    s.discussion_time = 60
    if s.discussion_task:
        try: s.discussion_task.cancel()
        except: pass
        s.discussion_task = None

    await event.respond(
        "🎮 New Spy x Civilian Game Started!\n\n"
        "Players can join using /join\n\n"
        "👉 First, tell me discussion time in minutes (e.g. type `5` for 5 minutes)."
    )


@client.on(events.NewMessage(pattern='/help'))
async def help_cmd(event):
    if await throttle(event, 'help'): return
    text = (
        "📖 *Spy x Civilians - Help*\n\n"
        "/startgame - Start a new game\n"
        "/join - Join the current game\n"
        "/begin - Begin the game (assign roles)\n"
        "/players - Show list of joined players\n"
        "/status - Show current game stage & info\n"
        "/extend - Extend discussion by 1 min (discussion only)\n"
        "/guess <location> - Spy guesses location (discussion only)\n"
        "/remove @username - Remove a player (admins/host only)\n"
        "/stopgame - Force end the game (admins/host only)\n"
        "/rules - Show game rules\n"
        "\n"
        "🧭 *Custom Locations* (per group):\n"
        "/addlocation <name> - Add a custom location (admins only)\n"
        "/removelocation <name> - Remove a custom location (admins only)\n"
        "/listlocations - Show all locations (default + custom)\n"
        "/resetlocations - Clear all custom locations (admins only)\n"
    )
    await event.respond(text, parse_mode="markdown")


@client.on(events.NewMessage(pattern='/rules'))
async def rules_cmd(event):
    if await throttle(event, 'rules'): return
    rules = (
        "📜 *Spy x Civilians Rules*\n\n"
        "- One or more players are Spies 🕵️.\n"
        "- Civilians 👥 know a secret location.\n"
        "- Spies don't know the location and must deduce it.\n"
        "- Players discuss to identify the Spy.\n"
        "- After discussion, players vote.\n"
        "- Civilians win if they catch the Spy.\n"
        "- Spy wins if not caught, or if they correctly guess the location during discussion."
    )
    await event.respond(rules, parse_mode="markdown")


@client.on(events.NewMessage(pattern='/addlocation'))
async def addlocation_cmd(event):
    # Anti-spam
    if await throttle(event, 'addlocation'): return

    # Group + admin only
    if not (await is_admin(event, event.sender_id)):
        await event.respond("❌ Only group admins can add locations.")
        return

    args = event.raw_text.split(" ", 1)
    if len(args) < 2 or not args[1].strip():
        await event.respond("⚠️ Usage: /addlocation <name>")
        return

    ok, err = add_custom_location_db(event.chat_id, args[1].strip())
    if ok:
        await event.respond(f"✅ Added location: *{args[1].strip()}*", parse_mode="markdown")
    else:
        await event.respond(f"⚠️ {err}")

@client.on(events.NewMessage(pattern='/removelocation'))
async def removelocation_cmd(event):
    if await throttle(event, 'removelocation'): return

    if not (await is_admin(event, event.sender_id)):
        await event.respond("❌ Only group admins can remove custom locations.")
        return

    args = event.raw_text.split(" ", 1)
    if len(args) < 2 or not args[1].strip():
        await event.respond("⚠️ Usage: /removelocation <name>")
        return

    ok, err = remove_custom_location_db(event.chat_id, args[1].strip())
    if ok:
        await event.respond(f"✅ Removed location: *{args[1].strip()}*", parse_mode="markdown")
    else:
        await event.respond(f"⚠️ {err}")

@client.on(events.NewMessage(pattern='/listlocations'))
async def listlocations_cmd(event):
    if await throttle(event, 'listlocations'): return

    pool = build_locations_for_chat(event.chat_id)
    if not pool:
        await event.respond("ℹ️ No locations available.")
        return

    out = "🧭 *Locations for this chat:*\n" + "\n".join(f"• {x}" for x in pool)
    await event.respond(out, parse_mode="markdown")

@client.on(events.NewMessage(pattern='/resetlocations'))
async def resetlocations_cmd(event):
    if await throttle(event, 'resetlocations'): return

    if not (await is_admin(event, event.sender_id)):
        await event.respond("❌ Only group admins can reset custom locations.")
        return

    reset_custom_locations_db(event.chat_id)
    await event.respond("♻️ Custom locations cleared for this chat. Using defaults now.")


# Catch minutes when setup_state == waiting_time
@client.on(events.NewMessage)
async def catch_minutes(event):
    s = get_state(event.chat_id)
    if s.setup_state == "waiting_time":
        try:
            minutes = int(event.raw_text.strip())

            # safety limit (you added earlier)
            if minutes < 1 or minutes > 30:
                await event.respond("⚠️ Please choose between 1 and 30 minutes.")
                return

            s.discussion_time = minutes * 60
            s.setup_state = "waiting_mode"
            await event.respond(
                f"✅ Discussion time set to {minutes} minutes!\n\nNow choose Game Mode:",
                buttons=[
                    [Button.inline("🎯 Classic Mode", b"mode:classic")],
                    [Button.inline("🤔 Fake Civilian Mode", b"mode:fake_civilian")],
                    [Button.inline("🕵️ Double Spy Mode", b"mode:double_spy")],
                    [Button.inline("🎲 Chaos Mode", b"mode:chaos")]
                ]
            )
        except:
            pass


@client.on(events.CallbackQuery)
async def callback_handler(event):
    if await throttle_cb(event, 'cb'): return
    s = get_state(event.chat_id)
    data = event.data.decode()

    # ---------- MODE SELECTION ----------
    if data.startswith("mode:"):
        if s.setup_state != "waiting_mode":
            await event.answer("⚠️ Not in mode selection phase!", alert=True)
            return

        choice = data.split(":", 1)[1]
        if choice == "classic":
            s.game_mode = "Classic"
        elif choice == "fake_civilian":
            s.game_mode = "Fake Civilian"
        elif choice == "double_spy":
            s.game_mode = "Double Spy"
        elif choice == "chaos":
            s.game_mode = "Chaos"

        s.setup_state = None
        await event.edit(f"🎮 Game Mode selected: {s.game_mode}\n\n"
                         "Players can now join using /join.\n"
                         "When ready, use /begin to start.")

    # ---------- VOTING ----------
    elif data.startswith("vote:"):
        voter = event.sender_id
        vote_for = int(data.split(":", 1)[1])

        if voter in s.votes:
            await event.answer("⚠️ You already voted!", alert=True)
            return

        s.votes[voter] = vote_for
        await event.answer("✅ Vote registered!")

        # If all voted
        if len(s.votes) == len(s.players):
            await finish_voting(event)


@client.on(events.NewMessage(pattern='/join'))
async def join_game(event):
    if await throttle(event, 'join'): return
    s = get_state(event.chat_id)
    if not s.game_started:
        await event.respond("❌ No active game! Start with /startgame")
        return
    if event.sender_id in s.players:
        await event.respond("⚠️ You already joined!")
    else:
        s.players.append(event.sender_id)
        await event.respond(
            f"✅ {mention_name(await client.get_entity(event.sender_id))} joined the game!",
            parse_mode="html"
        )


@client.on(events.NewMessage(pattern='/players'))
async def players_cmd(event):
    if await throttle(event, 'players'): return
    s = get_state(event.chat_id)
    if not s.players:
        await event.respond("⚠️ No players have joined yet.")
    else:
        entities = [await client.get_entity(p) for p in s.players]
        names = [f"- {mention_name(e)}" for e in entities]
        await event.respond("👥 Current Players:\n" + "\n".join(names), parse_mode="html")


@client.on(events.NewMessage(pattern='/begin'))
async def begin_game(event):
    if await throttle(event, 'begin'): return
    s = get_state(event.chat_id)

    if not s.game_started or not s.game_mode:
        await event.respond("⚠️ Game has not been set up yet!")
        return
    if len(s.players) < 3:
        await event.respond("⚠️ Need at least 3 players to start!")
        return

    loc_pool = build_locations_for_chat(event.chat_id)
    location = random.choice(loc_pool)
    spy_list = []
    fake_civilian = None
    s.game_stage = "discussion"
    s.current_location = location

    # Assign roles by mode
    if s.game_mode == "Classic":
        spy_list = [random.choice(s.players)]
    elif s.game_mode == "Fake Civilian":
        spy_list = [random.choice(s.players)]
        fake_civilian = random.choice([p for p in s.players if p not in spy_list])
    elif s.game_mode == "Double Spy":
        spy_list = random.sample(s.players, 2)
    elif s.game_mode == "Chaos":
        spy_list = [random.choice(s.players)]
        if random.choice([True, False]):
            fake_civilian = random.choice([p for p in s.players if p not in spy_list])

    # Step 1: test-send role messages (without committing)
    failed = []
    temp_roles = {}
    for p in s.players:
        try:
            if p in spy_list:
                msg = (
                    "🕵️‍♂️ *Secret Role Assigned!*\n\n"
                    "You are the *SPY* 😈\n"
                    "❓ Your mission: Blend in, ask smart questions, and try to *guess the location*.\n\n"
                    "🗣️ Be careful… if they find you, civilians win!"
                )
                await client.send_message(p, msg, parse_mode="markdown")
                temp_roles[p] = "Spy"

            elif fake_civilian == p:
                wrong_location = random.choice([loc for loc in loc_pool if loc != location])
                msg = (
                    "👥 *Secret Role Assigned!*\n\n"
                    "You are a *Civilian* 🙌\n"
                    f"📍 The secret location is: *{wrong_location}*\n\n"
                    "🎯 Your mission: Spot the Spy by asking tricky questions and defending yourself."
                )
                await client.send_message(p, msg, parse_mode="markdown")
                temp_roles[p] = "Fake Civilian"

            else:
                msg = (
                    "👥 *Secret Role Assigned!*\n\n"
                    "You are a *Civilian* 🙌\n"
                    f"📍 The secret location is: *{location}*\n\n"
                    "🎯 Your mission: Spot the Spy by asking tricky questions and defending yourself."
                )
                await client.send_message(p, msg, parse_mode="markdown")
                temp_roles[p] = "Civilian"

        except Exception:
            failed.append(p)

    # Step 2: if failed → abort and reset only this chat
    if failed:
        names = []
        for pid in failed:
            try:
                ent = await client.get_entity(pid)
                names.append(f"- {mention_name(ent)}")
            except:
                names.append(f"- <a href='tg://user?id={pid}'>Unknown</a>")

        await event.respond(
            "⚠️ The following players must /start the bot in PM before the game can begin:\n" +
            "\n".join(names),
            parse_mode="html"
        )

        # important: don't block the lobby
        await reset_game(event.chat_id)
        return

    # Step 3: commit roles
    s.roles = temp_roles

    await event.respond(
        "🎉 *All roles have been secretly assigned!*\n\n"
        f"🗣️ Discussion Phase has started.\n"
        f"⏳ Time: *{s.discussion_time//60}:{s.discussion_time%60:02d} minutes*\n\n"
        "👉 Ask smart questions, confuse the Spy, and defend yourself!",
        parse_mode="markdown"
    )

    # Start per-chat discussion timer
    async def discussion_timer():
        while s.discussion_time > 0 and s.game_stage == "discussion":
            await asyncio.sleep(1)
            s.discussion_time -= 1
            if s.discussion_time % 60 == 0 and s.discussion_time > 0:
                await event.respond(f"⏳ {s.discussion_time // 60} minutes left for discussion!")

        if s.game_stage == "discussion":  # time up -> voting
            buttons = [
                [Button.inline(f"Vote {(await client.get_entity(p)).first_name}", data=f"vote:{p}".encode())]
                for p in s.players
            ]
            await event.respond("🗳️ Discussion ended! Voting starts now (2 minutes):", buttons=buttons)
            s.game_stage = "voting"
            await asyncio.sleep(120)
            await finish_voting(event)

    # cancel old task if any, then create
    if s.discussion_task:
        try: s.discussion_task.cancel()
        except: pass
    s.discussion_task = asyncio.create_task(discussion_timer())


@client.on(events.NewMessage(pattern='/status'))
async def status_cmd(event):
    if await throttle(event, 'status'): return
    s = get_state(event.chat_id)
    if not s.game_started:
        await event.respond("⚠️ No active game.")
        return

    entities = [await client.get_entity(p) for p in s.players]
    names = [mention_name(e) for e in entities]
    await event.respond(
        f"📊 Game Status:\n"
        f"Mode: {s.game_mode}\n"
        f"Stage: {s.game_stage}\n"
        f"Players Joined: {len(s.players)}\n"
        f"👥 " + ", ".join(names),
        parse_mode="html"
    )


@client.on(events.NewMessage(pattern='/extend'))
async def extend_cmd(event):
    if await throttle(event, 'extend'): return
    s = get_state(event.chat_id)
    if s.game_stage != "discussion":
        await event.respond("❌ You can only extend time during discussion phase.")
        return
    s.discussion_time += 60
    await event.respond(f"⏳ Discussion extended by 1 minute! (Now {s.discussion_time//60}:{s.discussion_time%60:02d} remaining)")


@client.on(events.NewMessage(pattern='/guess'))
async def guess_cmd(event):
    if await throttle(event, 'guess'): return
    s = get_state(event.chat_id)
    if s.game_stage != "discussion":
        await event.respond("❌ You can only guess during discussion.")
        return

    user_id = event.sender_id
    if s.roles.get(user_id) != "Spy":
        await event.respond("❌ Only Spy can guess!")
        return

    args = event.raw_text.split(" ", 1)
    if len(args) < 2:
        await event.respond("⚠️ Usage: /guess <location>")
        return

    guess = args[1].strip().lower()
    correct_location = (s.current_location or "").lower()

    if guess == correct_location:
        await event.respond(f"🎉 Spy guessed the location correctly ({s.current_location})!\nSpy wins! 🕵️")
        await reset_game(event.chat_id)
    else:
        await event.respond("❌ Wrong guess! Game continues...")


async def finish_voting(event):
    s = get_state(event.chat_id)
    if s.game_stage == "finished":
        return
    s.game_stage = "finished"

    if not s.votes:
        await event.respond("⚠️ No votes were cast. Spy wins by default 😈")
        await reset_game(event.chat_id)
        return

    # Count votes
    counts = {}
    for v in s.votes.values():
        counts[v] = counts.get(v, 0) + 1
    accused = max(counts, key=counts.get)

    accused_ent = await client.get_entity(accused)
    accused_name = mention_name(accused_ent)

    player_entities = {p: await client.get_entity(p) for p in s.players}
    civilians = [mention_name(ent) for pid, ent in player_entities.items() if s.roles.get(pid) == "Civilian"]
    spies = [mention_name(ent) for pid, ent in player_entities.items() if s.roles.get(pid) == "Spy"]
    fake_civilians = [mention_name(ent) for pid, ent in player_entities.items() if s.roles.get(pid) == "Fake Civilian"]

    breakdown = []
    for voter, target in s.votes.items():
        voter_name = mention_name(player_entities[voter])
        target_name = mention_name(player_entities[target])
        breakdown.append(f"{voter_name} ➝ {target_name}")

    if s.roles.get(accused) == "Spy":
        result = (
            f"🎉 Civilians win!\n"
            f"🕵️ Spy was {mention_name(player_entities[accused])}\n\n"
            f"👥 Civilians: {', '.join(civilians)}"
        )
    else:
        result = (
            f"😈 Spy wins!\n"
            f"❌ {accused_name} was wrongly accused.\n\n"
            f"🕵️ Spies: {', '.join(spies)}"
        )
        if fake_civilians:
            result += f"\n🎭 Fake Civilians: {', '.join(fake_civilians)}"
        if civilians:
            result += f"\n👥 Civilians: {', '.join(civilians)}"

    if breakdown:
        result += "\n\n🗳️ *Voting Breakdown:*\n" + "\n".join(breakdown)

    await event.respond(result, parse_mode="html")
    await reset_game(event.chat_id)


async def is_admin(event, user_id):
    participants = await event.client.get_participants(
        event.chat_id,
        filter=ChannelParticipantsAdmins
    )
    admin_ids = [p.id for p in participants]

    chat = await event.get_chat()
    # check if user is in admins or is group creator
    return user_id in admin_ids or getattr(chat, "creator", False)


@client.on(events.NewMessage(pattern='/stopgame'))
async def stop_game(event):
    if await throttle(event, 'stopgame'): return
    s = get_state(event.chat_id)
    if not s.game_started:
        await event.respond("⚠️ No game is running!")
        return

    if await is_admin(event, event.sender_id) or event.sender_id == s.game_starter:
        await reset_game(event.chat_id)
        await event.respond("🛑 Game has been stopped by admin/host.")
    else:
        await event.respond("❌ Only group admins or game starter can stop the game.")


@client.on(events.NewMessage(pattern='^/remove($| )'))
async def remove_cmd(event):
    if await throttle(event, 'remove'): return
    s = get_state(event.chat_id)
    args = event.raw_text.split(" ", 1)
    if len(args) < 2:
        await event.respond("⚠️ Usage: /remove @username or /remove Name")
        return

    target = args[1].strip()
    if not (await is_admin(event, event.sender_id) or event.sender_id == s.game_starter):
        await event.respond("❌ Only admins or game starter can remove players.")
        return

    try:
        entity = await client.get_entity(target)
        if entity.id in s.players:
            s.players.remove(entity.id)
            await event.respond(f"🚫 {mention_name(entity)} has been removed from the game.", parse_mode="html")
        else:
            await event.respond("⚠️ That user is not in the game.")
    except Exception:
        await event.respond("❌ Could not find that user.")


@client.on(events.NewMessage(pattern='/broadcast'))
async def broadcast_cmd(event):
    if await throttle(event, 'broadcast'): return

    # Only allow you (owner) in PM
    if event.sender_id != OWNER_ID:
        await event.respond("❌ Only the bot owner can use this command.")
        return

    args = event.raw_text.split(" ", 1)
    if len(args) < 2 or not args[1].strip():
        await event.respond("⚠️ Usage: /broadcast <message>")
        return

    msg = args[1].strip()
    sent = 0
    failed = 0

    user_ids = await asyncio.to_thread(get_all_users)
    for uid in user_ids:
        try:
            await client.send_message(uid, msg)
            sent += 1
            await asyncio.sleep(0.1)  # small delay, avoid flood
        except:
            failed += 1

    await event.respond(f"✅ Broadcast complete!\n📨 Sent: {sent}\n❌ Failed: {failed}")


async def reset_game(chat_id: int):
    s = get_state(chat_id)
    if s.discussion_task:
        try:
            s.discussion_task.cancel()
        except:
            pass
        s.discussion_task = None

    # Re-initialize only this chat's state
    game_states[chat_id] = GameState()


print("🤖 Bot is running...")
client.run_until_disconnected()