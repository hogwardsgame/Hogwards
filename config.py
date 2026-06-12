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
STARTER_GOLD = 150   # хватает на первое зелье/предмет, мягкий старт
STARTER_MANA = 50
STARTER_HP   = 100

# ── ЗОЛОТО И НАГРАДЫ ───────────────────────────────────────────────────
GOLD_REWARDS = {
    "pve_kill_min":    5,
    "pve_kill_max":    18,
    "pve_boss_min":    60,
    "pve_boss_max":    220,
    "pvp_win":         25,
    "pvp_lose":        5,
    "lesson_correct":  12,
    "lesson_wrong":    2,
    "quest_daily":     35,
    "quest_weekly":    150,
    "world_boss_min":  100,
    "world_boss_max":  350,
    "forest_min":      20,
    "forest_max":      90,
}

SHOP_PRICES = {
    "hp_potion_small":   50,
    "hp_potion_medium":  120,
    "hp_potion_large":   280,
    "mana_potion":       80,
    "strength_potion":   200,
    "luck_potion":       250,
    "shield_potion":     180,
}

# Базовые цены снаряжения по редкости (используются в shop/forge/black_market)
RARITY_BASE_PRICE = {
    "common":     60,
    "uncommon":   150,
    "rare":       400,
    "very_rare":  900,
    "epic":       2000,
    "legendary":  5000,
    "mythical":   12000,
    "abyssal":    30000,
}

# ── XP НА ПРОКАЧКУ ─────────────────────────────────────────────────────
# Новая сбалансированная кривая: мягкий старт, плавный рост.
# Формула в database.add_xp / helpers.xp_needed_for_level:
#   needed = int(XP_CURVE_BASE * level**XP_CURVE_POWER + XP_CURVE_LINEAR * level)
# ур1→2 ≈ 150 XP, ур10→11 ≈ 3700, ур20→21 ≈ 10000, ур30→31 ≈ 18000
XP_CURVE_BASE   = 100
XP_CURVE_POWER  = 1.5
XP_CURVE_LINEAR = 50

# Прирост характеристик за уровень (применяется в database.add_xp)
LEVEL_UP_GAINS = {
    "max_hp":   12,
    "max_mana": 6,
    "attack":   2,
    "defense":  1,
    "speed":    1,
}

# Оставлено для обратной совместимости (старый код может ссылаться)
XP_PER_LEVEL_BASE = 100
XP_LEVEL_MULT     = 1.15

XP_REWARDS = {
    "pve_kill_min":    15,
    "pve_kill_max":    40,
    "pve_boss_min":    120,
    "pve_boss_max":    350,
    "pvp_win":         60,
    "pvp_lose":        15,
    "lesson_correct":  40,
    "lesson_wrong":    8,
    "quest_daily":     80,
    "quest_weekly":    300,
    "world_boss_min":  200,
    "world_boss_max":  600,
    "achievement":     120,
    "combo_spell":     25,
    "forest_min":      40,
    "forest_max":      120,
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
    "forest":       5,
    "black_market": 3,
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
