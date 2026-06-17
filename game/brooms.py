"""
Мётлы — кастомизация с характеристиками + рывок в дуэли.

8 мётел разной редкости. Дают бонусы к статам (как плащи)
+ рывок в бою: улететь на любое число клеток (2 раза за бой).
Чем лучше метла — тем больше дальность рывка и бонусы.

Получение: покупка за золото + выпадение за победы.
"""

# rarity: common / rare / epic / legendary
# bonuses: atk, def, hp, mana, luck — добавляются к статам
# dash: дальность рывка в дуэли (клеток), dashes: сколько раз за бой
BROOMS = {
    "training": {
        "name": "Учебная метла", "emoji": "🧹", "color": "#9aa0b5", "rarity": "common",
        "price": 0, "atk": 0, "def": 0, "hp": 0, "luck": 0,
        "dash": 3, "dashes": 2,
        "desc": "Простая метла. Рывок на 3 клетки, 2 раза за бой.",
    },
    "cleansweep": {
        "name": "Чистомёт", "emoji": "🪶", "color": "#a0855c", "rarity": "common",
        "price": 600, "atk": 3, "def": 0, "hp": 0, "luck": 0,
        "dash": 4, "dashes": 2,
        "desc": "+3 атаки. Рывок на 4 клетки.",
    },
    "comet": {
        "name": "Комета", "emoji": "☄️", "color": "#e0833c", "rarity": "rare",
        "price": 1400, "atk": 5, "def": 0, "hp": 0, "luck": 3,
        "dash": 4, "dashes": 3,
        "desc": "+5 атаки, +3 удачи. Рывок на 4 клетки, 3 раза.",
    },
    "nimbus": {
        "name": "Нимбус 2000", "emoji": "🌟", "color": "#5c9dff", "rarity": "rare",
        "price": 1400, "atk": 4, "def": 4, "hp": 20, "luck": 0,
        "dash": 5, "dashes": 3,
        "desc": "+4 атк, +4 защ, +20 HP. Рывок на 5 клеток, 3 раза.",
    },
    "firebolt": {
        "name": "Молния", "emoji": "⚡", "color": "#ffd86b", "rarity": "epic",
        "price": 3000, "atk": 8, "def": 4, "hp": 0, "luck": 5,
        "dash": 6, "dashes": 3,
        "desc": "+8 атк, +5 удачи. Рывок на 6 клеток, 3 раза!",
    },
    "thunder": {
        "name": "Громовержец", "emoji": "🌩️", "color": "#a05ce0", "rarity": "epic",
        "price": 3000, "atk": 6, "def": 8, "hp": 30, "luck": 0,
        "dash": 6, "dashes": 4,
        "desc": "+6 атк, +8 защ, +30 HP. Рывок на 6, 4 раза за бой!",
    },
    "shadow": {
        "name": "Теневой вихрь", "emoji": "🌑", "color": "#5a4a7a", "rarity": "legendary",
        "price": 6500, "atk": 10, "def": 6, "hp": 0, "luck": 8,
        "dash": 99, "dashes": 4,
        "desc": "+10 атк, +8 удачи. Рывок на ЛЮБОЕ число клеток, 4 раза.",
    },
    "phoenix": {
        "name": "Феникс", "emoji": "🔥", "color": "#ff6b3c", "rarity": "legendary",
        "price": 9000, "atk": 12, "def": 10, "hp": 40, "luck": 10,
        "dash": 99, "dashes": 5,
        "desc": "Лучшая метла: +всё. Рывок на ЛЮБОЕ число клеток, 5 раз!",
    },
}

ALL_BROOM_IDS = list(BROOMS.keys())
STARTER_BROOM = "training"

# Мётлы за победы (id: побед нужно)
BROOM_WIN_DROPS = [
    ("cleansweep", 3), ("comet", 6), ("nimbus", 9),
    ("firebolt", 14), ("thunder", 19), ("shadow", 26), ("phoenix", 35),
]


def ensure_broom_tables():
    from database import get_conn, execute
    with get_conn() as conn:
        execute(conn, """
            CREATE TABLE IF NOT EXISTS player_brooms (
                user_id BIGINT NOT NULL,
                broom_id TEXT NOT NULL,
                UNIQUE(user_id, broom_id)
            )
        """)
        execute(conn, """
            CREATE TABLE IF NOT EXISTS player_broom_active (
                user_id BIGINT PRIMARY KEY,
                broom_id TEXT DEFAULT 'training'
            )
        """)


def grant_starter_broom(user_id: int):
    ensure_broom_tables()
    from database import get_conn, execute
    with get_conn() as conn:
        execute(conn, "INSERT INTO player_brooms (user_id, broom_id) VALUES (%s,%s) ON CONFLICT DO NOTHING", user_id, STARTER_BROOM)
        execute(conn, "INSERT INTO player_broom_active (user_id, broom_id) VALUES (%s,%s) ON CONFLICT DO NOTHING", user_id, STARTER_BROOM)


def get_owned_brooms(user_id: int) -> list:
    ensure_broom_tables()
    from database import get_conn, fetchall
    with get_conn() as conn:
        rows = fetchall(conn, "SELECT broom_id FROM player_brooms WHERE user_id=%s", user_id)
    owned = [r["broom_id"] for r in rows]
    if STARTER_BROOM not in owned:
        grant_starter_broom(user_id)
        owned.append(STARTER_BROOM)
    return owned


def get_active_broom(user_id: int) -> str:
    ensure_broom_tables()
    from database import get_conn, fetchrow
    with get_conn() as conn:
        row = fetchrow(conn, "SELECT broom_id FROM player_broom_active WHERE user_id=%s", user_id)
    if not row:
        grant_starter_broom(user_id)
        return STARTER_BROOM
    return row["broom_id"]


def set_active_broom(user_id: int, broom_id: str) -> bool:
    if broom_id not in BROOMS:
        return False
    if broom_id not in get_owned_brooms(user_id):
        return False
    from database import get_conn, execute
    with get_conn() as conn:
        execute(conn, """INSERT INTO player_broom_active (user_id, broom_id) VALUES (%s,%s)
                         ON CONFLICT (user_id) DO UPDATE SET broom_id=%s""", user_id, broom_id, broom_id)
    return True


def give_broom(user_id: int, broom_id: str) -> bool:
    if broom_id not in BROOMS:
        return False
    ensure_broom_tables()
    from database import get_conn, execute
    with get_conn() as conn:
        execute(conn, "INSERT INTO player_brooms (user_id, broom_id) VALUES (%s,%s) ON CONFLICT DO NOTHING", user_id, broom_id)
    return True


def get_broom_bonuses(user_id: int) -> dict:
    bid = get_active_broom(user_id)
    b = BROOMS.get(bid, BROOMS[STARTER_BROOM])
    return {"atk": b.get("atk", 0), "def": b.get("def", 0),
            "hp": b.get("hp", 0), "luck": b.get("luck", 0),
            "dash": b.get("dash", 2), "dashes": b.get("dashes", 2)}
