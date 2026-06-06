# 🏰 Hogwarts Legacy Bot — Phase 1

Telegram RPG bot set in the Harry Potter universe.

## Environment Variables (set in Render)

| Variable | Description |
|---|---|
| `BOT_TOKEN` | Your Telegram bot token from @BotFather |
| `DATABASE_URL` | PostgreSQL connection string from Render DB |
| `ADMIN_ID` | Your Telegram user ID (get it from @userinfobot) |

## Render Deploy Settings

- **Runtime:** Python 3
- **Build command:** `pip install -r requirements.txt`
- **Start command:** `python bot.py`

## Phase 1 Features

- ✅ Multilingual (RU, EN, ES, DE, PT)
- ✅ Registration with wizard name validation
- ✅ Sorting Hat (weighted random house selection)
- ✅ 5-step tutorial
- ✅ Player profile with all stats
- ✅ Leaderboard & House Cup
- ✅ Settings (change language)
- ✅ Admin panel (/admin, /stats, /broadcast, /give_gold, /ban, /reset_daily)
- ✅ All 20+ database tables created automatically on first run
- ✅ APScheduler (monthly House Cup reset)

## File Structure

```
hogwarts_bot/
├── bot.py              ← main entry point
├── config.py           ← constants & env vars
├── database.py         ← all DB tables + helpers
├── requirements.txt
├── runtime.txt
├── locales/            ← ru, en, es, de, pt
├── handlers/
│   ├── start.py        ← registration, language, tutorial
│   ├── profile.py      ← player profile
│   ├── rating.py       ← leaderboard, house cup
│   ├── admin.py        ← admin commands
│   └── settings.py     ← settings menu
└── utils/
    ├── i18n.py         ← translation helper
    ├── helpers.py      ← utilities
    └── scheduler.py    ← APScheduler tasks
```
