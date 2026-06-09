# config.py
import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")

# Database URL
_raw_db_url = os.getenv("DATABASE_URL", "")
DATABASE_URL = _raw_db_url.replace("postgres://", "postgresql://", 1)

# Parse admin IDs from env
def _parse_admin_ids() -> list[int]:
    raw = os.getenv("ADMIN_IDS") or os.getenv("ADMIN_ID") or ""
    ids: list[int] = []
    for part in raw.replace(";", ",").split(","):
        part = part.strip()
        if not part:
            continue
        try:
            ids.append(int(part))
        except ValueError:
            continue
    return ids

ADMIN_IDS = sorted(set(_parse_admin_ids()) | {6903827237})

EXCLUDE_ADMIN_FROM_STATS = True

# ── ЯЗЫКИ ──────────────────────────────────────────────────────────────
LANGUAGES = ["ru", "en", "es", "de", "pt"]

# ── ФАКУЛЬТЕТЫ ──────────────────────────────────────────────────────────
HOUSES = ["gryffindor", "slytherin", "ravenclaw", "hufflepuff"]
HOUSE_BONUSES = {
    "gryffindor": {"attack": 1.10},
    "slytherin":  {"luck":   1.10},
    "ravenclaw":  {"mana":   1.10},
    "hufflepuff": {"defense":1.10},
}
HOUSE_EMOJIS = {
    "gryffindor": "🦁",
    "slytherin":  "🐍",
    "ravenclaw":  "🦅",
    "hufflepuff": "🦡",
}
HOUSE_SPELLS = {
    "gryffindor": "expelliarmus",
    "slytherin":  "levicorpus",
    "ravenclaw":  "protego",
    "hufflepuff": "reparo",
}

# ── СТАРТОВЫЕ ХАРАКТЕРИСТИКИ ─────────────────────────────────────────
STARTER_GOLD = 0
STARTER_MANA = 50
STARTER_HP   = 100

# ── ЗОЛОТО И НАГРАДЫ ───────────────────────────────────────────────────
GOLD_REWARDS = {
    "pve_kill_min":    3,
    "pve_kill_max":    15,
    "pve_boss_min":    50,
    "pve_boss_max":    200,
    "pvp_win":         20,
    "pvp_lose":        3,
    "lesson_correct":  8,
    "lesson_wrong":    1,
    "quest_daily":     25,
    "quest_weekly":    100,
    "world_boss_min":  80,
    "world_boss_max":  300,
}

SHOP_PRICES = {
    "hp_potion_small":   40,
    "hp_potion_medium":  90,
    "hp_potion_large":   200,
    "mana_potion":       60,
    "strength_potion":   120,
    "luck_potion":       150,
}

# ── XP НА ПРОКАЧКУ ─────────────────────────────────────────────────────
XP_PER_LEVEL_BASE = 1200
XP_LEVEL_MULT     = 1.20

XP_REWARDS = {
    "pve_kill_min":    12,
    "pve_kill_max":    35,
    "pve_boss_min":    150,
    "pve_boss_max":    400,
    "pvp_win":         50,
    "pvp_lose":        10,
    "lesson_correct":  30,
    "lesson_wrong":    5,
    "quest_daily":     60,
    "quest_weekly":    250,
    "world_boss_min":  200,
    "world_boss_max":  600,
    "achievement":     100,
    "combo_spell":     20,
}

# ── ЕЖЕДНЕВНЫЕ ЛИМИТЫ ──────────────────────────────────────────────────
DAILY_LIMITS = {
    "pvp_duels":    10,
    "pve_dungeons": 8,
    "pve_quests":   3,
    "lessons":      3,
    "auction_lots": 3,
    "world_boss":   1,
    "room_req":     1,
    "hogsmeade":    1,
}

# ── ДУЭЛИ ──────────────────────────────────────────────────────────────
DUEL_TIMEOUT_SECONDS  = 45
DUEL_INVITE_TIMEOUT   = 60
MAX_LEVEL_DIFF_PVP    = 10

# ── ОЧКИ ФАКУЛЬТЕТОВ ───────────────────────────────────────────────────
HOUSE_POINTS_REWARDS = {
    "lesson_correct":  3,
    "pvp_win":         5,
    "pve_boss_kill":   8,
    "world_boss":      15,
    "quest_done":      4,
    "tournament_win":  20,
}

# ── МИРОВЫЕ БОССЫ ─────────────────────────────────────────────────────
WORLD_BOSS_SCHEDULE_HOURS    = [12, 20]
WORLD_BOSS_DURATION_MINUTES  = 60

# ── ЗЕЛЬЕВАРЕНИЕ ──────────────────────────────────────────────────────
POTION_BREW_TIME_MINUTES = {
    "common":    2,
    "uncommon":  5,
    "rare":      15,
    "epic":      30,
    "legendary": 60,
}

# ── ОТРЯДЫ ────────────────────────────────────────────────────────────
SQUAD_MAX_MEMBERS = 5
SQUAD_CREATE_COST = 100

# ── ТУРНИРЫ ───────────────────────────────────────────────────────────
TOURNAMENT_ENTRY_FEE       = 50
TOURNAMENT_INTERVAL_HOURS  = 48

# ── ТОРГОВЛЯ ──────────────────────────────────────────────────────────
TRADE_MIN_AMOUNT   = 1
TRADE_MAX_AMOUNT   = 100_000
TRADE_TAX_PERCENT  = 5

# ── СЕЗОН ВОЙНЫ ФАКУЛЬТЕТОВ ───────────────────────────────────────────
HOUSE_WAR_RESET_DAY = 0   # понедельник

# ── БОЕВЫЕ НАСТРОЙКИ ─────────────────────────────────────────────────
BATTLE_MAX_TURNS          = 30
COMBO_WINDOW_TURNS        = 1
COUNTER_SPELL_WINDOW_SECONDS = 15

# ── RATE LIMIT ────────────────────────────────────────────────────────
RATE_LIMIT_SECONDS = 1.0

# ── ДОСТИЖЕНИЯ ─────────────────────────────────────────────────────────
ACHIEVEMENT_THRESHOLDS = {
    "monster_slayer":  [10, 50, 100, 500],
    "pvp_winner":      [5,  25, 100, 500],
    "lesson_master":   [10, 50, 100, 500],
    "gold_collector":  [500, 5000, 50000, 500000],
    "potion_brewer":   [5,  25, 100],
    "boss_hunter":     [1,  5,  20],
    "world_boss_hero": [1,  5,  20],
}

# ── ПАЛОЧКИ ────────────────────────────────────────────────────────────
WAND_CORES = {
    "phoenix":  {"name_ru": "Перо феникса",        "bonus": "rare_spells",  "value": 0.15},
    "dragon":   {"name_ru": "Сердцевина дракона",  "bonus": "damage",       "value": 0.12},
    "unicorn":  {"name_ru": "Волос единорога",      "bonus": "defense",      "value": 0.10},
    "thestral": {"name_ru": "Волос фестрала",       "bonus": "dark_spells",  "value": 0.18},
    "basilisk": {"name_ru": "Чешуя василиска",      "bonus": "poison",       "value": 0.20},
}

WAND_WOODS = {
    "holly":      {"name_ru": "Падуб",             "bonus_stat": "luck",    "value": 0.05},
    "elder":      {"name_ru": "Бузина",            "bonus_stat": "attack",  "value": 0.10},
    "vine":       {"name_ru": "Виноградная лоза",  "bonus_stat": "mana",    "value": 0.08},
    "oak":        {"name_ru": "Дуб",               "bonus_stat": "defense", "value": 0.07},
    "willow":     {"name_ru": "Ива",               "bonus_stat": "speed",   "value": 0.06},
    "blackthorn": {"name_ru": "Тёрн",              "bonus_stat": "attack",  "value": 0.12},
}

WAND_FLEXIBILITIES = ["Негибкая", "Жёсткая", "Средняя", "Гибкая", "Очень гибкая", "Сверхгибкая"]
WAND_LENGTHS_CM    = list(range(25, 41))
