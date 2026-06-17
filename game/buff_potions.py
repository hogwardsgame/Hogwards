"""
Зелья-баффы: временные усиления.

Два типа:
1. БОЕВЫЕ — сильный эффект на несколько ходов в дуэли (зелье = ход, лимит).
2. ДЛИТЕЛЬНЫЕ (редкие) — слабее, но действуют 3 реальных часа везде (PvE+PvP).

Варятся из ингредиентов, что падают с боссов.
"""
import time

# Боевые баффы (эффект в дуэли, на ходы)
BATTLE_BUFFS = {
    "strength_potion": {
        "name": "Зелье силы", "emoji": "💪", "stat": "atk", "mult": 1.3, "turns": 3,
        "desc": "+30% атаки на 3 хода",
        "ingredients": {"troll_hair": 2, "werewolf_fang": 1},
    },
    "stoneskin_potion": {
        "name": "Зелье каменной кожи", "emoji": "🪨", "stat": "def", "mult": 1.5, "turns": 3,
        "desc": "+50% защиты на 3 хода",
        "ingredients": {"giant_bone": 2, "basilisk_scale": 1},
    },
    "luck_potion": {
        "name": "Зелье удачи", "emoji": "🍀", "stat": "luck", "add": 0.25, "turns": 3,
        "desc": "+25% к криту на 3 хода",
        "ingredients": {"phoenix_ash": 1, "hydra_blood": 1},
    },
    "berserk_potion": {
        "name": "Зелье берсерка", "emoji": "😡", "stat": "atk", "mult": 1.6, "def_mult": 0.7, "turns": 3,
        "desc": "+60% атаки, но −30% защиты на 3 хода",
        "ingredients": {"werewolf_fang": 2, "dark_crystal": 1},
    },
    "rage_potion": {
        "name": "Зелье ярости", "emoji": "🔥", "stat": "splash", "turns": 2,
        "desc": "Следующие заклинания бьют по площади (2 хода)",
        "ingredients": {"hydra_blood": 2, "phoenix_ash": 1},
    },
}

# Длительные баффы (3 реальных часа, слабее, везде)
LONG_BUFFS = {
    "elixir_power": {
        "name": "Эликсир мощи", "emoji": "⚜️", "stat": "atk", "mult": 1.15, "hours": 3,
        "desc": "+15% атаки на 3 часа (везде)",
        "ingredients": {"dark_crystal": 2, "death_shard": 1, "werewolf_fang": 3},
    },
    "elixir_guard": {
        "name": "Эликсир стража", "emoji": "🛡️", "stat": "def", "mult": 1.2, "hours": 3,
        "desc": "+20% защиты на 3 часа (везде)",
        "ingredients": {"giant_bone": 3, "basilisk_scale": 2, "dark_crystal": 1},
    },
    "elixir_fortune": {
        "name": "Эликсир фортуны", "emoji": "🌟", "stat": "luck", "add": 0.1, "hours": 3,
        "desc": "+10% к криту на 3 часа (везде)",
        "ingredients": {"phoenix_ash": 3, "death_shard": 1, "hydra_blood": 2},
    },
}


def ensure_buff_tables():
    from database import get_conn, execute
    with get_conn() as conn:
        execute(conn, """
            CREATE TABLE IF NOT EXISTS player_buff_potions (
                user_id BIGINT NOT NULL,
                potion_id TEXT NOT NULL,
                quantity INT DEFAULT 0,
                UNIQUE(user_id, potion_id)
            )
        """)
        execute(conn, """
            CREATE TABLE IF NOT EXISTS player_active_buffs (
                user_id BIGINT NOT NULL,
                buff_id TEXT NOT NULL,
                expires_at DOUBLE PRECISION,
                UNIQUE(user_id, buff_id)
            )
        """)


def can_brew(user_id, potion_id):
    """Проверяет, хватает ли ингредиентов."""
    recipe = BATTLE_BUFFS.get(potion_id) or LONG_BUFFS.get(potion_id)
    if not recipe:
        return False, "Рецепт не найден"
    from game.duel_bosses import get_ingredients
    have = get_ingredients(user_id)
    for ing, qty in recipe["ingredients"].items():
        if have.get(ing, 0) < qty:
            return False, "Не хватает ингредиентов"
    return True, ""


def brew(user_id, potion_id):
    """Сварить зелье — тратит ингредиенты, добавляет зелье."""
    ensure_buff_tables()
    ok, msg = can_brew(user_id, potion_id)
    if not ok:
        return {"ok": False, "msg": msg}
    recipe = BATTLE_BUFFS.get(potion_id) or LONG_BUFFS.get(potion_id)
    from database import get_conn, execute
    with get_conn() as conn:
        # списываем ингредиенты
        for ing, qty in recipe["ingredients"].items():
            execute(conn, "UPDATE player_ingredients SET quantity=quantity-%s WHERE user_id=%s AND ingredient_id=%s",
                    qty, user_id, ing)
        # добавляем зелье
        execute(conn, """INSERT INTO player_buff_potions (user_id, potion_id, quantity) VALUES (%s,%s,1)
                         ON CONFLICT (user_id, potion_id) DO UPDATE SET quantity=player_buff_potions.quantity+1""",
                user_id, potion_id)
    return {"ok": True, "msg": f"✅ Сварено: {recipe['emoji']} {recipe['name']}"}


def get_buff_potions(user_id):
    """Сколько каких зелий у игрока."""
    ensure_buff_tables()
    from database import get_conn, fetchall
    with get_conn() as conn:
        rows = fetchall(conn, "SELECT potion_id, quantity FROM player_buff_potions WHERE user_id=%s AND quantity > 0", user_id)
    return {r["potion_id"]: r["quantity"] for r in rows}


def use_long_buff(user_id, potion_id):
    """Выпить длительный бафф (3 часа)."""
    ensure_buff_tables()
    recipe = LONG_BUFFS.get(potion_id)
    if not recipe:
        return {"ok": False, "msg": "Это не длительное зелье"}
    have = get_buff_potions(user_id)
    if have.get(potion_id, 0) <= 0:
        return {"ok": False, "msg": "Нет такого зелья"}
    from database import get_conn, execute
    expires = time.time() + recipe["hours"] * 3600
    with get_conn() as conn:
        execute(conn, "UPDATE player_buff_potions SET quantity=quantity-1 WHERE user_id=%s AND potion_id=%s", user_id, potion_id)
        execute(conn, """INSERT INTO player_active_buffs (user_id, buff_id, expires_at) VALUES (%s,%s,%s)
                         ON CONFLICT (user_id, buff_id) DO UPDATE SET expires_at=%s""",
                user_id, potion_id, expires, expires)
    return {"ok": True, "msg": f"✅ {recipe['emoji']} {recipe['name']} активно 3 часа!"}


def consume_battle_potion(user_id, potion_id):
    """Списать боевое зелье (используется в дуэли)."""
    ensure_buff_tables()
    if potion_id not in BATTLE_BUFFS:
        return False
    have = get_buff_potions(user_id)
    if have.get(potion_id, 0) <= 0:
        return False
    from database import get_conn, execute
    with get_conn() as conn:
        execute(conn, "UPDATE player_buff_potions SET quantity=quantity-1 WHERE user_id=%s AND potion_id=%s", user_id, potion_id)
    return True


def get_active_long_buffs(user_id):
    """Активные длительные баффы (не истёкшие). Возвращает множители для статов."""
    ensure_buff_tables()
    from database import get_conn, fetchall, execute
    now = time.time()
    with get_conn() as conn:
        # чистим истёкшие
        execute(conn, "DELETE FROM player_active_buffs WHERE expires_at < %s", now)
        rows = fetchall(conn, "SELECT buff_id, expires_at FROM player_active_buffs WHERE user_id=%s", user_id)
    out = []
    mult = {"atk": 1.0, "def": 1.0, "luck_add": 0.0}
    for r in rows:
        recipe = LONG_BUFFS.get(r["buff_id"])
        if not recipe:
            continue
        stat = recipe["stat"]
        if stat == "atk":
            mult["atk"] *= recipe.get("mult", 1.0)
        elif stat == "def":
            mult["def"] *= recipe.get("mult", 1.0)
        elif stat == "luck":
            mult["luck_add"] += recipe.get("add", 0.0)
        out.append({"id": r["buff_id"], "name": recipe["name"], "emoji": recipe["emoji"],
                    "timeLeft": int(r["expires_at"] - now), "desc": recipe["desc"]})
    return out, mult
