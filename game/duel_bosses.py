"""
Боссы для магической дуэли (на сетке).

10 боссов с разными механиками. Характеристики масштабируются под уровень игрока.
Чем сложнее босс — тем больше поле и награда.
С боссов падают ингредиенты для зелий.
"""

# Боссы по возрастанию сложности.
# grid — размер поля (сложные боссы = больше клеток)
# hp_mult/dmg_mult — множители к базовым (база зависит от уровня игрока)
# mechanic — особая механика боя
# ingredient — что падает (для зелий)
BOSSES = {
    "troll": {
        "name": "Горный тролль", "emoji": "🧌", "order": 1, "grid": 5,
        "hp_mult": 1.0, "dmg": 14, "mechanic": "none",
        "mech_desc": "Простой, но крепкий. Хорош для разминки.",
        "gold": 80, "xp": 40, "ingredient": "troll_hair", "ingredient_chance": 0.5,
    },
    "acromantula": {
        "name": "Акромантул", "emoji": "🕷️", "order": 2, "grid": 5,
        "hp_mult": 1.15, "dmg": 16, "mechanic": "web",
        "mech_desc": "Паутина: иногда замораживает тебя на 1 ход.",
        "gold": 120, "xp": 60, "ingredient": "spider_venom", "ingredient_chance": 0.45,
    },
    "basilisk": {
        "name": "Василиск", "emoji": "🐍", "order": 3, "grid": 5,
        "hp_mult": 1.3, "dmg": 18, "mechanic": "poison",
        "mech_desc": "Яд: при попадании по тебе отравляет (−урон каждый ход).",
        "gold": 160, "xp": 80, "ingredient": "basilisk_scale", "ingredient_chance": 0.4,
    },
    "dementor": {
        "name": "Дементор", "emoji": "👻", "order": 4, "grid": 6,
        "hp_mult": 1.4, "dmg": 20, "mechanic": "drain",
        "mech_desc": "Высасывает: лечится за счёт нанесённого тебе урона.",
        "gold": 220, "xp": 110, "ingredient": "dementor_essence", "ingredient_chance": 0.35,
    },
    "werewolf": {
        "name": "Оборотень", "emoji": "🐺", "order": 5, "grid": 6,
        "hp_mult": 1.5, "dmg": 22, "mechanic": "rage",
        "mech_desc": "Ярость: чем меньше у него HP, тем сильнее бьёт.",
        "gold": 280, "xp": 140, "ingredient": "werewolf_fang", "ingredient_chance": 0.3,
    },
    "phoenix_dark": {
        "name": "Тёмный феникс", "emoji": "🔥", "order": 6, "grid": 6,
        "hp_mult": 1.6, "dmg": 24, "mechanic": "revive",
        "mech_desc": "Возрождение: один раз воскресает с 30% HP.",
        "gold": 350, "xp": 180, "ingredient": "phoenix_ash", "ingredient_chance": 0.28,
    },
    "giant": {
        "name": "Великан", "emoji": "🗿", "order": 7, "grid": 6,
        "hp_mult": 1.9, "dmg": 26, "mechanic": "smash",
        "mech_desc": "Удар по площади: бьёт сразу по большой зоне.",
        "gold": 450, "xp": 230, "ingredient": "giant_bone", "ingredient_chance": 0.25,
    },
    "hydra": {
        "name": "Гидра", "emoji": "🐉", "order": 8, "grid": 7,
        "hp_mult": 2.1, "dmg": 28, "mechanic": "multi",
        "mech_desc": "Многоголовая: атакует дважды за ход.",
        "gold": 600, "xp": 300, "ingredient": "hydra_blood", "ingredient_chance": 0.22,
    },
    "lord": {
        "name": "Тёмный Лорд", "emoji": "💀", "order": 9, "grid": 7,
        "hp_mult": 2.4, "dmg": 30, "mechanic": "curse",
        "mech_desc": "Проклятие: блокирует одно твоё заклинание на ход.",
        "gold": 800, "xp": 400, "ingredient": "dark_crystal", "ingredient_chance": 0.2,
    },
    "death": {
        "name": "Сама Смерть", "emoji": "☠️", "order": 10, "grid": 7,
        "hp_mult": 3.0, "dmg": 35, "mechanic": "all",
        "mech_desc": "Использует все механики сразу. Финальный вызов.",
        "gold": 1200, "xp": 600, "ingredient": "death_shard", "ingredient_chance": 0.15,
    },
}

# Ингредиенты (для зелий) — описание
INGREDIENTS = {
    "troll_hair":       {"name": "Волос тролля", "emoji": "🧶"},
    "spider_venom":     {"name": "Яд паука", "emoji": "🕸️"},
    "basilisk_scale":   {"name": "Чешуя василиска", "emoji": "🟢"},
    "dementor_essence": {"name": "Эссенция дементора", "emoji": "💨"},
    "werewolf_fang":    {"name": "Клык оборотня", "emoji": "🦷"},
    "phoenix_ash":      {"name": "Пепел феникса", "emoji": "🔥"},
    "giant_bone":       {"name": "Кость великана", "emoji": "🦴"},
    "hydra_blood":      {"name": "Кровь гидры", "emoji": "🩸"},
    "dark_crystal":     {"name": "Тёмный кристалл", "emoji": "🔮"},
    "death_shard":      {"name": "Осколок смерти", "emoji": "💎"},
}


def get_boss_for_player(boss_id: str, player_level: int, player_hp: int):
    """Возвращает характеристики босса, отмасштабированные под игрока."""
    b = BOSSES.get(boss_id)
    if not b:
        return None
    # база HP босса = HP игрока (нормализованное), умноженное на множитель
    # игрок в дуэли имеет ~100-200 HP; босс масштабируется от этого + уровня
    base = max(120, player_hp)
    lvl_factor = 1.0 + (player_level - 1) * 0.03  # +3% за уровень (несильно)
    boss_hp = int(base * b["hp_mult"] * lvl_factor)
    boss_dmg = int(b["dmg"] * lvl_factor)
    return {
        "id": boss_id, "name": b["name"], "emoji": b["emoji"],
        "grid": b["grid"], "hp": boss_hp, "maxHp": boss_hp, "dmg": boss_dmg,
        "mechanic": b["mechanic"], "mechDesc": b["mech_desc"],
        "gold": b["gold"], "xp": b["xp"], "order": b["order"],
        "ingredient": b["ingredient"], "ingredientChance": b["ingredient_chance"],
    }


def ensure_boss_tables():
    from database import get_conn, execute
    with get_conn() as conn:
        execute(conn, """
            CREATE TABLE IF NOT EXISTS boss_progress (
                user_id BIGINT NOT NULL,
                boss_id TEXT NOT NULL,
                defeated BOOLEAN DEFAULT FALSE,
                UNIQUE(user_id, boss_id)
            )
        """)
        execute(conn, """
            CREATE TABLE IF NOT EXISTS player_ingredients (
                user_id BIGINT NOT NULL,
                ingredient_id TEXT NOT NULL,
                quantity INT DEFAULT 0,
                UNIQUE(user_id, ingredient_id)
            )
        """)


def get_boss_progress(user_id: int) -> dict:
    """Какие боссы побеждены."""
    ensure_boss_tables()
    from database import get_conn, fetchall
    with get_conn() as conn:
        rows = fetchall(conn, "SELECT boss_id, defeated FROM boss_progress WHERE user_id=%s", user_id)
    return {r["boss_id"]: r["defeated"] for r in rows}


def mark_boss_defeated(user_id: int, boss_id: str):
    ensure_boss_tables()
    from database import get_conn, execute
    with get_conn() as conn:
        execute(conn, """INSERT INTO boss_progress (user_id, boss_id, defeated) VALUES (%s,%s,TRUE)
                         ON CONFLICT (user_id, boss_id) DO UPDATE SET defeated=TRUE""", user_id, boss_id)


def give_ingredient(user_id: int, ingredient_id: str, qty: int = 1):
    ensure_boss_tables()
    from database import get_conn, execute
    with get_conn() as conn:
        execute(conn, """INSERT INTO player_ingredients (user_id, ingredient_id, quantity) VALUES (%s,%s,%s)
                         ON CONFLICT (user_id, ingredient_id) DO UPDATE SET quantity = player_ingredients.quantity + %s""",
                user_id, ingredient_id, qty, qty)


def get_ingredients(user_id: int) -> dict:
    ensure_boss_tables()
    from database import get_conn, fetchall
    with get_conn() as conn:
        rows = fetchall(conn, "SELECT ingredient_id, quantity FROM player_ingredients WHERE user_id=%s", user_id)
    return {r["ingredient_id"]: r["quantity"] for r in rows if r["quantity"] > 0}
