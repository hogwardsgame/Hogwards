"""
Плащи — кастомизация персонажа с характеристиками.

8 плащей разных редкостей. Дают бонусы к общим статам (везде)
+ спецэффекты в магической дуэли (скорость, усиление стихий).

Получение: покупка за золото + выпадение за победы в дуэли.
"""

# rarity: common / rare / epic / legendary
# bonuses: atk, def, hp, mana — добавляются к общим статам
# duel: спецэффект в дуэли (move_bonus, burn_bonus, freeze_bonus, shield_bonus, ...)
CLOAKS = {
    "novice": {
        "name": "Плащ ученика", "emoji": "🧥", "color": "#9aa0b5", "rarity": "common",
        "price": 0, "atk": 0, "def": 0, "hp": 0, "mana": 0, "duel": {},
        "desc": "Простой плащ первокурсника. Базовый вид.",
    },
    "warrior": {
        "name": "Боевой плащ", "emoji": "🟥", "color": "#e0533c", "rarity": "common",
        "price": 500, "atk": 8, "def": 2, "hp": 0, "mana": 0, "duel": {"dmg_bonus": 0.1},
        "desc": "+8 атаки. В дуэли: +10% урона заклинаний.",
    },
    "guardian": {
        "name": "Плащ защитника", "emoji": "🟦", "color": "#3c7de0", "rarity": "common",
        "price": 500, "atk": 0, "def": 8, "hp": 20, "mana": 0, "duel": {"shield_bonus": 5},
        "desc": "+8 защиты, +20 HP. В дуэли: щит крепче.",
    },
    "healer": {
        "name": "Плащ целителя", "emoji": "🟩", "color": "#3ce07d", "rarity": "rare",
        "price": 1200, "atk": 0, "def": 4, "hp": 30, "mana": 30, "duel": {"heal_bonus": 0.2},
        "desc": "+30 HP, +30 маны. В дуэли: лечение сильнее на 20%.",
    },
    "swift": {
        "name": "Плащ скорости", "emoji": "🟪", "color": "#a05ce0", "rarity": "rare",
        "price": 1200, "atk": 4, "def": 0, "hp": 0, "mana": 20, "duel": {"move_bonus": 1},
        "desc": "+4 атаки. В дуэли: можно шагать на 2 клетки!",
    },
    "dark": {
        "name": "Плащ тьмы", "emoji": "⬛", "color": "#5a4a7a", "rarity": "epic",
        "price": 2500, "atk": 12, "def": 4, "hp": 0, "mana": 0, "duel": {"burn_bonus": 3, "freeze_bonus": 1},
        "desc": "+12 атаки. В дуэли: поджог и заморозка длятся дольше.",
    },
    "frost": {
        "name": "Морозный плащ", "emoji": "🟦", "color": "#5cd8ff", "rarity": "epic",
        "price": 2500, "atk": 6, "def": 10, "hp": 20, "mana": 20, "duel": {"freeze_bonus": 2},
        "desc": "+6 атаки, +10 защиты. В дуэли: заморозка на 2 хода дольше.",
    },
    "legend": {
        "name": "Плащ легенды", "emoji": "🟨", "color": "#ffd86b", "rarity": "legendary",
        "price": 6000, "atk": 15, "def": 12, "hp": 40, "mana": 40, "duel": {"dmg_bonus": 0.15, "shield_bonus": 5, "move_bonus": 1},
        "desc": "Лучший плащ: +всё. В дуэли: урон, щит и дальний шаг.",
    },
}

ALL_CLOAK_IDS = list(CLOAKS.keys())
STARTER_CLOAK = "novice"

# Плащи, что выпадают за победы (id: побед нужно)
CLOAK_WIN_DROPS = [
    ("warrior", 2), ("guardian", 4), ("healer", 7),
    ("swift", 10), ("frost", 14), ("dark", 18), ("legend", 25),
]


def ensure_cloak_tables():
    from database import get_conn, execute
    with get_conn() as conn:
        execute(conn, """
            CREATE TABLE IF NOT EXISTS player_cloaks (
                user_id BIGINT NOT NULL,
                cloak_id TEXT NOT NULL,
                UNIQUE(user_id, cloak_id)
            )
        """)
        execute(conn, """
            CREATE TABLE IF NOT EXISTS player_cloak_active (
                user_id BIGINT PRIMARY KEY,
                cloak_id TEXT DEFAULT 'novice'
            )
        """)


def grant_starter_cloak(user_id: int):
    ensure_cloak_tables()
    from database import get_conn, execute
    with get_conn() as conn:
        execute(conn, "INSERT INTO player_cloaks (user_id, cloak_id) VALUES (%s, %s) ON CONFLICT DO NOTHING",
                user_id, STARTER_CLOAK)
        execute(conn, "INSERT INTO player_cloak_active (user_id, cloak_id) VALUES (%s, %s) ON CONFLICT DO NOTHING",
                user_id, STARTER_CLOAK)


def get_owned_cloaks(user_id: int) -> list:
    ensure_cloak_tables()
    from database import get_conn, fetchall
    with get_conn() as conn:
        rows = fetchall(conn, "SELECT cloak_id FROM player_cloaks WHERE user_id=%s", user_id)
    owned = [r["cloak_id"] for r in rows]
    if STARTER_CLOAK not in owned:
        grant_starter_cloak(user_id)
        owned.append(STARTER_CLOAK)
    return owned


def get_active_cloak(user_id: int) -> str:
    ensure_cloak_tables()
    from database import get_conn, fetchrow
    with get_conn() as conn:
        row = fetchrow(conn, "SELECT cloak_id FROM player_cloak_active WHERE user_id=%s", user_id)
    if not row:
        grant_starter_cloak(user_id)
        return STARTER_CLOAK
    return row["cloak_id"]


def set_active_cloak(user_id: int, cloak_id: str) -> bool:
    if cloak_id not in CLOAKS:
        return False
    owned = get_owned_cloaks(user_id)
    if cloak_id not in owned:
        return False
    from database import get_conn, execute
    with get_conn() as conn:
        execute(conn, """INSERT INTO player_cloak_active (user_id, cloak_id) VALUES (%s,%s)
                         ON CONFLICT (user_id) DO UPDATE SET cloak_id=%s""",
                user_id, cloak_id, cloak_id)
    return True


def give_cloak(user_id: int, cloak_id: str) -> bool:
    if cloak_id not in CLOAKS:
        return False
    ensure_cloak_tables()
    from database import get_conn, execute
    with get_conn() as conn:
        execute(conn, "INSERT INTO player_cloaks (user_id, cloak_id) VALUES (%s,%s) ON CONFLICT DO NOTHING",
                user_id, cloak_id)
    return True


def get_cloak_bonuses(user_id: int) -> dict:
    """Бонусы активного плаща к статам: {atk, def, hp, mana}."""
    cid = get_active_cloak(user_id)
    c = CLOAKS.get(cid, CLOAKS[STARTER_CLOAK])
    return {"atk": c.get("atk", 0), "def": c.get("def", 0),
            "hp": c.get("hp", 0), "mana": c.get("mana", 0)}
