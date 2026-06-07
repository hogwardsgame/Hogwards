import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")

# ── ИСПРАВЛЕНИЕ 1: Railway иногда даёт "postgres://" вместо "postgresql://"
# psycopg2 не понимает "postgres://", поэтому заменяем автоматически
_raw_db_url = os.getenv("DATABASE_URL", "")
DATABASE_URL = _raw_db_url.replace("postgres://", "postgresql://", 1)

ADMIN_IDS = [int(x) for x in os.getenv("ADMIN_ID", "0").split(",") if x]

LANGUAGES = ["ru", "en", "es", "de", "pt"]

HOUSES = ["gryffindor", "slytherin", "ravenclaw", "hufflepuff"]

HOUSE_BONUSES = {
    "gryffindor": {"attack": 1.10},
    "slytherin":  {"luck":   1.10},
    "ravenclaw":  {"mana":   1.10},
    "hufflepuff": {"defense":1.10},
}

HOUSE_SPELLS = {
    "gryffindor": "expelliarmus",
    "slytherin":  "levicorpus",
    "ravenclaw":  "protego",
    "hufflepuff": "reparo",
}

STARTER_GOLD = 100
STARTER_MANA = 50
STARTER_HP   = 100

XP_PER_LEVEL_BASE = 500
XP_LEVEL_MULT     = 1.15

DAILY_LIMITS = {
    "pvp_duels":    10,
    "pve_dungeons": 5,
    "pve_quests":   3,
    "lessons":      2,
    "auction_lots": 3,
}

DUEL_TIMEOUT_SECONDS = 45
DUEL_INVITE_TIMEOUT  = 60
MAX_LEVEL_DIFF_PVP   = 5

# ── ИСПРАВЛЕНИЕ 3: лимит запросов — максимум 1 запрос в секунду на пользователя
RATE_LIMIT_SECONDS = 1.0
