# 🕵️ Spy x Civilians Telegram Bot

A fun multiplayer group game bot for Telegram where players try to identify the spy among them! The bot features multiple game modes, custom locations, and persistent data storage.

## 🎮 Game Overview

**Spy x Civilians** is a social deduction game where:
- One or more players are assigned as **Spies** 🕵️
- The remaining players are **Civilians** 👥 who know a secret location
- **Spies** must blend in and guess the location to win
- **Civilians** must identify and vote out the spy to win

## ✨ Features

### 🎯 Game Modes
- **Classic Mode**: One spy vs civilians
- **Fake Civilian Mode**: One spy + one civilian gets wrong location
- **Double Spy Mode**: Two spies working together
- **Chaos Mode**: Random combination of spy and fake civilian

### 🏢 Location System
- 50+ default locations (Hospital, Airport, Cinema, etc.)
- Custom location support per group
- Persistent location storage in database

### 🔧 Admin Features
- Game management (start, stop, remove players)
- Custom location management
- Broadcast messages to all users
- Anti-spam protection with cooldowns

### 💾 Database Integration
- PostgreSQL database for persistent storage
- User tracking and custom locations per group
- Automatic database initialization

## 🚀 Deployment

This bot is designed to be deployed on **Render.com** with 24/7 uptime using UptimeRobot.

### Prerequisites
- Python 3.8+
- PostgreSQL database
- Telegram Bot Token
- Render.com account
- UptimeRobot account (for keeping bot alive)

### Environment Variables

Create a `.env` file or set these environment variables:

```bash
API_ID=your_telegram_api_id
API_HASH=your_telegram_api_hash
BOT_TOKEN=your_bot_token_from_botfather
OWNER_ID=your_telegram_user_id
DATABASE_URL=your_postgresql_connection_string
```

### 📋 Installation Steps

1. **Clone the repository**
   ```bash
   git clone https://github.com/yourusername/spy-civilians-bot.git
   cd spy-civilians-bot
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Set up environment variables**
   - Get API_ID and API_HASH from [my.telegram.org](https://my.telegram.org)
   - Create bot with [@BotFather](https://t.me/botfather) for BOT_TOKEN
   - Get your OWNER_ID from [@userinfobot](https://t.me/userinfobot)
   - Set up PostgreSQL database (Render provides free PostgreSQL)

4. **Deploy to Render**
   - Connect your GitHub repository to Render
   - Choose "Web Service" deployment
   - Set environment variables in Render dashboard
   - Deploy!

### 🔄 24/7 Uptime Setup

To keep your bot running 24/7 on Render's free plan:

1. **Get your Render app URL** (e.g., `https://your-app.onrender.com`)

2. **Set up UptimeRobot monitoring**:
   - Create account at [UptimeRobot](https://uptimerobot.com)
   - Add new monitor with your Render URL
   - Set interval to 5 minutes
   - This prevents Render from sleeping due to inactivity

## 🎮 How to Use

### Basic Commands

| Command | Description |
|---------|-------------|
| `/start` | Welcome message and bot introduction |
| `/help` | Show all available commands |
| `/rules` | Display game rules |

### Game Commands

| Command | Description |
|---------|-------------|
| `/startgame` | Start a new game (anyone) |
| `/join` | Join the current game |
| `/begin` | Begin the game after setup |
| `/players` | Show list of joined players |
| `/status` | Show current game status |
| `/extend` | Extend discussion by 1 minute |
| `/guess <location>` | Spy guesses the location |
| `/stopgame` | Force end game (admins/host only) |
| `/remove @user` | Remove player (admins/host only) |

### Location Management (Admins Only)

| Command | Description |
|---------|-------------|
| `/addlocation <name>` | Add custom location to group |
| `/removelocation <name>` | Remove custom location |
| `/listlocations` | Show all available locations |
| `/resetlocations` | Clear all custom locations |

### Owner Commands

| Command | Description |
|---------|-------------|
| `/broadcast <message>` | Send message to all bot users |

## 🎯 Game Flow

1. **Setup Phase**:
   - Host runs `/startgame`
   - Sets discussion time (1-30 minutes)
   - Chooses game mode
   - Players join with `/join`

2. **Role Assignment**:
   - Host runs `/begin`
   - Bot privately messages each player their role
   - Game starts with discussion phase

3. **Discussion Phase**:
   - Players discuss and ask questions
   - Spy tries to blend in and deduce location
   - Timer counts down
   - Spy can `/guess` location anytime

4. **Voting Phase**:
   - Players vote to eliminate suspected spy
   - Results are revealed
   - Winners are announced

## 📁 Project Structure

```
spy-civilians-bot/
├── main.py              # Main bot logic and handlers
├── db.py               # Database operations
├── requirements.txt    # Python dependencies
├── README.md          # This file
└── .gitignore         # Git ignore file
```

## 🛠️ Technical Details

### Dependencies
- **telethon**: Telegram client library
- **psycopg**: PostgreSQL adapter
- **flask**: Web framework for health check endpoint
- **asyncio**: Asynchronous programming support

### Database Schema
```sql
-- Users table for broadcast functionality
CREATE TABLE users (
    user_id BIGINT PRIMARY KEY
);

-- Custom locations per group
CREATE TABLE locations (
    chat_id BIGINT NOT NULL,
    location TEXT NOT NULL,
    PRIMARY KEY (chat_id, location)
);
```

### Anti-Spam Features
- Command cooldown: 1.5 seconds between commands
- Button cooldown: 0.75 seconds between inline button presses
- Per-user throttling to prevent spam

## 🔒 Security Features

- Admin-only commands for sensitive operations
- Input validation and sanitization
- Database connection with SSL requirements
- Error handling for failed private message delivery

## 🐛 Troubleshooting

### Common Issues

1. **Bot not responding**:
   - Check if bot is running on Render
   - Verify environment variables are set
   - Check UptimeRobot is pinging correctly

2. **Role messages not delivered**:
   - Players must `/start` the bot in private chat first
   - Bot will notify if players need to start it

3. **Database connection issues**:
   - Verify DATABASE_URL is correct
   - Ensure SSL mode is enabled
   - Check PostgreSQL service status

## 📝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- Thanks to the Telegram Bot API team
- Inspired by classic social deduction games
- Built with love for the gaming community

## 📞 Support

If you encounter any issues or have questions:
- Open an issue on GitHub
- Contact the bot owner via Telegram

---

**Happy Gaming! 🎮**