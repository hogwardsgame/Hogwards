"""
Батл пасс: сезонный трек наград.

Игрок копит очки (BP) за любые бои/победы/активности.
Каждые N очков — новый уровень пасса с наградой.
Бесплатный трек для всех. Сезон длится ~месяц.
"""
import datetime

POINTS_PER_LEVEL = 100  # очков на уровень
MAX_LEVEL = 30

# Награды по уровням (level -> награда)
# type: gold / item / ingredient / badge / cloak / broom
PASS_REWARDS = {
    1:  {"type": "gold", "amount": 100, "name": "100 золота", "emoji": "💰"},
    2:  {"type": "item", "item": "hp_potion_small", "qty": 2, "name": "2× Малое зелье HP", "emoji": "🧪"},
    3:  {"type": "gold", "amount": 150, "name": "150 золота", "emoji": "💰"},
    4:  {"type": "ingredient", "item": "troll_hair", "qty": 2, "name": "2× Волос тролля", "emoji": "🧶"},
    5:  {"type": "item", "item": "hp_potion_medium", "qty": 2, "name": "2× Среднее зелье HP", "emoji": "🧪"},
    6:  {"type": "gold", "amount": 200, "name": "200 золота", "emoji": "💰"},
    7:  {"type": "ingredient", "item": "spider_venom", "qty": 2, "name": "2× Яд паука", "emoji": "🕸️"},
    8:  {"type": "broom", "item": "cleansweep", "name": "Метла «Чистомёт»", "emoji": "🪶"},
    9:  {"type": "gold", "amount": 250, "name": "250 золота", "emoji": "💰"},
    10: {"type": "badge", "item": "veteran", "name": "Значок «Ветеран»", "emoji": "🎖️"},
    11: {"type": "ingredient", "item": "basilisk_scale", "qty": 2, "name": "2× Чешуя василиска", "emoji": "🟢"},
    12: {"type": "item", "item": "hp_potion_large", "qty": 2, "name": "2× Большое зелье HP", "emoji": "🧪"},
    13: {"type": "gold", "amount": 300, "name": "300 золота", "emoji": "💰"},
    14: {"type": "ingredient", "item": "phoenix_ash", "qty": 1, "name": "Пепел феникса", "emoji": "🔥"},
    15: {"type": "cloak", "item": "warrior", "name": "Плащ воина", "emoji": "🟥"},
    16: {"type": "gold", "amount": 350, "name": "350 золота", "emoji": "💰"},
    17: {"type": "ingredient", "item": "werewolf_fang", "qty": 2, "name": "2× Клык оборотня", "emoji": "🦷"},
    18: {"type": "item", "item": "ability_upgrade_potion", "qty": 1, "name": "Зелье улучшения умений", "emoji": "⭐"},
    19: {"type": "gold", "amount": 400, "name": "400 золота", "emoji": "💰"},
    20: {"type": "broom", "item": "comet", "name": "Метла «Комета»", "emoji": "☄️"},
    21: {"type": "ingredient", "item": "giant_bone", "qty": 2, "name": "2× Кость великана", "emoji": "🦴"},
    22: {"type": "gold", "amount": 500, "name": "500 золота", "emoji": "💰"},
    23: {"type": "ingredient", "item": "hydra_blood", "qty": 2, "name": "2× Кровь гидры", "emoji": "🩸"},
    24: {"type": "item", "item": "ability_upgrade_potion", "qty": 2, "name": "2× Зелье улучшения", "emoji": "⭐"},
    25: {"type": "cloak", "item": "legend", "name": "Плащ легенды", "emoji": "🟨"},
    26: {"type": "gold", "amount": 700, "name": "700 золота", "emoji": "💰"},
    27: {"type": "ingredient", "item": "dark_crystal", "qty": 1, "name": "Тёмный кристалл", "emoji": "🔮"},
    28: {"type": "gold", "amount": 1000, "name": "1000 золота", "emoji": "💰"},
    29: {"type": "ingredient", "item": "death_shard", "qty": 1, "name": "Осколок смерти", "emoji": "💎"},
    30: {"type": "broom", "item": "phoenix", "name": "Метла «Феникс» 🔥", "emoji": "🔥"},
}

# Сколько BP за разные действия
BP_REWARDS = {
    "duel_win": 15, "duel_loss": 5,
    "boss_win": 30, "tower_floor": 12, "dungeon_clear": 40,
}


def _current_season():
    """Идентификатор сезона (год-месяц)."""
    now = datetime.date.today()
    return f"{now.year}-{now.month:02d}"


def ensure_pass_table():
    from database import get_conn, execute
    with get_conn() as conn:
        execute(conn, """
            CREATE TABLE IF NOT EXISTS battle_pass (
                user_id BIGINT NOT NULL,
                season TEXT NOT NULL,
                points INT DEFAULT 0,
                claimed TEXT DEFAULT '',
                UNIQUE(user_id, season)
            )
        """)


def add_points(user_id, action):
    """Начислить BP за действие."""
    pts = BP_REWARDS.get(action, 0)
    if pts <= 0:
        return
    ensure_pass_table()
    from database import get_conn, execute
    season = _current_season()
    with get_conn() as conn:
        execute(conn, """INSERT INTO battle_pass (user_id, season, points) VALUES (%s,%s,%s)
                         ON CONFLICT (user_id, season) DO UPDATE SET points = battle_pass.points + %s""",
                user_id, season, pts, pts)


def get_pass(user_id):
    """Состояние батл-пасса игрока."""
    ensure_pass_table()
    from database import get_conn, fetchrow, execute
    season = _current_season()
    with get_conn() as conn:
        row = fetchrow(conn, "SELECT * FROM battle_pass WHERE user_id=%s AND season=%s", user_id, season)
        if not row:
            execute(conn, "INSERT INTO battle_pass (user_id, season, points) VALUES (%s,%s,0) ON CONFLICT DO NOTHING", user_id, season)
            row = {"points": 0, "claimed": ""}
    points = row["points"]
    level = min(MAX_LEVEL, points // POINTS_PER_LEVEL)
    claimed = set(c for c in (row["claimed"] or "").split(",") if c)
    levels = []
    for lvl in range(1, MAX_LEVEL + 1):
        reward = PASS_REWARDS.get(lvl, {})
        levels.append({
            "level": lvl, "reward": reward,
            "unlocked": level >= lvl,
            "claimed": str(lvl) in claimed,
        })
    return {
        "season": season, "points": points, "level": level, "maxLevel": MAX_LEVEL,
        "pointsPerLevel": POINTS_PER_LEVEL,
        "nextLevelPoints": (level + 1) * POINTS_PER_LEVEL if level < MAX_LEVEL else None,
        "levels": levels,
    }


def claim_reward(user_id, level):
    """Забрать награду уровня."""
    ensure_pass_table()
    from database import get_conn, fetchrow, execute
    season = _current_season()
    with get_conn() as conn:
        row = fetchrow(conn, "SELECT * FROM battle_pass WHERE user_id=%s AND season=%s", user_id, season)
        if not row:
            return {"ok": False, "msg": "Нет данных"}
        points = row["points"]
        cur_level = min(MAX_LEVEL, points // POINTS_PER_LEVEL)
        if cur_level < level:
            return {"ok": False, "msg": "Уровень ещё не открыт"}
        claimed = set(c for c in (row["claimed"] or "").split(",") if c)
        if str(level) in claimed:
            return {"ok": False, "msg": "Уже получено"}
        reward = PASS_REWARDS.get(level)
        if not reward:
            return {"ok": False, "msg": "Нет награды"}
        # выдаём награду
        _grant_reward(user_id, reward)
        claimed.add(str(level))
        execute(conn, "UPDATE battle_pass SET claimed=%s WHERE user_id=%s AND season=%s",
                ",".join(sorted(claimed, key=int)), user_id, season)
    return {"ok": True, "msg": f"✅ Получено: {reward['emoji']} {reward['name']}", "reward": reward}


def _grant_reward(user_id, reward):
    t = reward.get("type")
    try:
        if t == "gold":
            from database import add_gold
            add_gold(user_id, reward["amount"])
        elif t == "item":
            from database import add_item_to_inventory
            add_item_to_inventory(user_id, reward["item"], reward.get("qty", 1))
        elif t == "ingredient":
            from game.duel_bosses import give_ingredient
            give_ingredient(user_id, reward["item"], reward.get("qty", 1))
        elif t == "badge":
            from game.world_chat import give_badge
            give_badge(user_id, reward["item"])
        elif t == "cloak":
            from game.cloaks import give_cloak
            give_cloak(user_id, reward["item"])
        elif t == "broom":
            from game.brooms import give_broom
            give_broom(user_id, reward["item"])
    except Exception:
        pass
