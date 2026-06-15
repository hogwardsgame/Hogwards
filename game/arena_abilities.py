"""
Боевые умения для Арены (2D-бой с ИИ).

10 умений с типами, маной и кулдауном. Прокачиваются через XP
(зелье улучшения даёт XP, накопил — поднялся уровень умения).

Рост на уровень слабый (~4% за уровень), чтобы скилл решал больше прокачки.
"""

# Типы умений (для тактики и иконок)
# damage  — прямой урон
# shield  — щит (блок следующей атаки)
# heal    — лечение
# control — урон + замедление/оглушение (враг слабее/пропускает)
# poison  — урон + яд (тикает несколько ходов)

ARENA_ABILITIES = {
    "fireball": {
        "name": "Огненный шар", "emoji": "🔥", "type": "damage",
        "mana": 30, "cooldown": 0,
        "base_damage": 28, "element": "fire",
        "desc": "Мощный сгусток пламени. Надёжный основной урон.",
    },
    "ice_chains": {
        "name": "Ледяные оковы", "emoji": "❄️", "type": "control",
        "mana": 35, "cooldown": 2,
        "base_damage": 18, "slow": 1, "element": "ice",
        "desc": "Урон + замедление: следующий ход врага слабее.",
    },
    "lightning": {
        "name": "Молния", "emoji": "⚡", "type": "damage",
        "mana": 18, "cooldown": 0,
        "base_damage": 16, "element": "lightning",
        "desc": "Быстрый дешёвый разряд. Можно спамить.",
    },
    "shield": {
        "name": "Щит", "emoji": "🛡️", "type": "shield",
        "mana": 25, "cooldown": 2,
        "base_shield": 30, "element": "arcane",
        "desc": "Поглощает урон следующей атаки врага.",
    },
    "heal": {
        "name": "Лечение", "emoji": "💚", "type": "heal",
        "mana": 35, "cooldown": 3,
        "base_heal": 32, "element": "nature",
        "desc": "Восстанавливает здоровье.",
    },
    "dark_magic": {
        "name": "Тёмная магия", "emoji": "☠️", "type": "poison",
        "mana": 30, "cooldown": 1,
        "base_damage": 14, "poison": 8, "poison_turns": 3, "element": "dark",
        "desc": "Урон + яд: жжёт врага несколько ходов.",
    },
    "stone_skin": {
        "name": "Каменная кожа", "emoji": "🪨", "type": "shield",
        "mana": 28, "cooldown": 3,
        "base_shield": 22, "heal_bonus": 8, "element": "earth",
        "desc": "Щит + немного восстановления здоровья.",
    },
    "wind_blade": {
        "name": "Ветряной клинок", "emoji": "🌀", "type": "damage",
        "mana": 22, "cooldown": 1,
        "base_damage": 20, "crit_bonus": 0.15, "element": "air",
        "desc": "Режущий вихрь с повышенным шансом крита.",
    },
    "sun_ray": {
        "name": "Солнечный луч", "emoji": "☀️", "type": "damage",
        "mana": 40, "cooldown": 2,
        "base_damage": 34, "element": "light",
        "desc": "Слепящий луч. Большой урон, дорогой по мане.",
    },
    "poison_cloud": {
        "name": "Ядовитое облако", "emoji": "🟢", "type": "poison",
        "mana": 32, "cooldown": 2,
        "base_damage": 10, "poison": 12, "poison_turns": 4, "element": "toxic",
        "desc": "Слабый удар, но сильный длительный яд.",
    },
}

ALL_ABILITY_IDS = list(ARENA_ABILITIES.keys())

# Сколько XP нужно для каждого уровня умения (уровень -> XP для следующего)
# Уровни 1..10. Рост плавный.
def xp_for_level(level: int) -> int:
    """XP, нужное чтобы перейти с этого уровня на следующий."""
    if level >= 10:
        return 0  # макс
    return 50 + (level - 1) * 30   # ур1->2: 50, 2->3: 80, ... 9->10: 290

MAX_ABILITY_LEVEL = 10

# Сколько XP даёт одно зелье улучшения
UPGRADE_POTION_XP = 25

# ── Формулы силы умения с учётом уровня ──
# Рост ~4% за уровень от базы. 1 vs 3 уровень ≈ 8% разницы.
def level_multiplier(level: int) -> float:
    return 1.0 + (level - 1) * 0.04

def ability_damage(ability_id: str, level: int) -> int:
    ab = ARENA_ABILITIES.get(ability_id, {})
    base = ab.get("base_damage", 0)
    return round(base * level_multiplier(level))

def ability_heal(ability_id: str, level: int) -> int:
    ab = ARENA_ABILITIES.get(ability_id, {})
    base = ab.get("base_heal", 0) or ab.get("heal_bonus", 0)
    return round(base * level_multiplier(level))

def ability_shield(ability_id: str, level: int) -> int:
    ab = ARENA_ABILITIES.get(ability_id, {})
    base = ab.get("base_shield", 0)
    return round(base * level_multiplier(level))

def ability_poison(ability_id: str, level: int) -> int:
    ab = ARENA_ABILITIES.get(ability_id, {})
    base = ab.get("poison", 0)
    return round(base * level_multiplier(level))


# ── Таблица прокачки умений игрока в БД ──
def ensure_ability_table():
    from database import get_conn, execute
    with get_conn() as conn:
        execute(conn, """
            CREATE TABLE IF NOT EXISTS arena_abilities (
                user_id  BIGINT NOT NULL,
                ability_id TEXT NOT NULL,
                level    INT DEFAULT 1,
                xp       INT DEFAULT 0,
                UNIQUE(user_id, ability_id)
            )
        """)


def grant_starter_abilities(user_id: int):
    """Выдать новичку все 10 умений на 1 уровне."""
    ensure_ability_table()
    from database import get_conn, execute
    with get_conn() as conn:
        for aid in ALL_ABILITY_IDS:
            execute(conn, """
                INSERT INTO arena_abilities (user_id, ability_id, level, xp)
                VALUES (%s, %s, 1, 0)
                ON CONFLICT (user_id, ability_id) DO NOTHING
            """, user_id, aid)


def get_player_abilities(user_id: int) -> dict:
    """Вернуть {ability_id: {level, xp}} игрока. Если пусто — выдать стартовые."""
    ensure_ability_table()
    from database import get_conn, fetchall
    with get_conn() as conn:
        rows = fetchall(conn, "SELECT ability_id, level, xp FROM arena_abilities WHERE user_id=%s", user_id)
    if not rows:
        grant_starter_abilities(user_id)
        with get_conn() as conn:
            rows = fetchall(conn, "SELECT ability_id, level, xp FROM arena_abilities WHERE user_id=%s", user_id)
    out = {}
    for r in rows:
        out[r["ability_id"]] = {"level": r["level"], "xp": r["xp"]}
    return out


def add_ability_xp(user_id: int, ability_id: str, xp_amount: int) -> dict:
    """Влить XP в умение. Возвращает {leveledUp, newLevel, xp, needed}."""
    ensure_ability_table()
    if ability_id not in ARENA_ABILITIES:
        return {"error": "Умение не найдено"}
    from database import get_conn, fetchrow, execute
    with get_conn() as conn:
        row = fetchrow(conn, "SELECT level, xp FROM arena_abilities WHERE user_id=%s AND ability_id=%s",
                       user_id, ability_id)
        if not row:
            execute(conn, "INSERT INTO arena_abilities (user_id, ability_id, level, xp) VALUES (%s,%s,1,0)",
                    user_id, ability_id)
            level, xp = 1, 0
        else:
            level, xp = row["level"], row["xp"]
        if level >= MAX_ABILITY_LEVEL:
            return {"leveledUp": False, "newLevel": level, "xp": 0, "needed": 0, "maxed": True}
        xp += xp_amount
        leveled = False
        # может подняться на несколько уровней
        while level < MAX_ABILITY_LEVEL:
            need = xp_for_level(level)
            if xp >= need:
                xp -= need
                level += 1
                leveled = True
            else:
                break
        if level >= MAX_ABILITY_LEVEL:
            xp = 0
        execute(conn, "UPDATE arena_abilities SET level=%s, xp=%s WHERE user_id=%s AND ability_id=%s",
                level, xp, user_id, ability_id)
    needed = xp_for_level(level) if level < MAX_ABILITY_LEVEL else 0
    return {"leveledUp": leveled, "newLevel": level, "xp": xp, "needed": needed,
            "maxed": level >= MAX_ABILITY_LEVEL}
