"""
Башня испытаний: этажи с растущей сложностью.

Игрок поднимается по этажам, на каждом — бой с врагом.
Чем выше этаж, тем сильнее враг и больше награда.
Каждый 5-й этаж — мини-босс. Сохраняется рекорд высоты.
HP не восстанавливается между этажами (ресурс-менеджмент).
"""

# Враги башни по типам (ротация)
TOWER_ENEMIES = [
    {"name": "Тёмный маг", "emoji": "🧙‍♂️"},
    {"name": "Страж", "emoji": "💂"},
    {"name": "Призрак", "emoji": "👻"},
    {"name": "Голем", "emoji": "🗿"},
    {"name": "Вампир", "emoji": "🧛"},
    {"name": "Оборотень", "emoji": "🐺"},
]
BOSS_FLOORS_EMOJI = {"name": "Хранитель этажа", "emoji": "👹"}


def ensure_tower_table():
    from database import get_conn, execute
    with get_conn() as conn:
        execute(conn, """
            CREATE TABLE IF NOT EXISTS tower_progress (
                user_id BIGINT PRIMARY KEY,
                best_floor INT DEFAULT 0,
                current_floor INT DEFAULT 1,
                current_hp INT DEFAULT 0,
                run_active BOOLEAN DEFAULT FALSE
            )
        """)


def get_tower_state(user_id, player_level, player_hp):
    """Текущее состояние башни игрока."""
    ensure_tower_table()
    from database import get_conn, fetchrow, execute
    with get_conn() as conn:
        row = fetchrow(conn, "SELECT * FROM tower_progress WHERE user_id=%s", user_id)
        if not row:
            execute(conn, "INSERT INTO tower_progress (user_id) VALUES (%s) ON CONFLICT DO NOTHING", user_id)
            row = {"best_floor": 0, "current_floor": 1, "current_hp": 0, "run_active": False}
    return {
        "bestFloor": row["best_floor"], "currentFloor": row["current_floor"],
        "currentHp": row["current_hp"], "runActive": row["run_active"],
    }


def get_floor_enemy(floor, player_level, player_hp):
    """Враг для этажа, отмасштабированный."""
    is_boss = (floor % 5 == 0)
    base = max(100, player_hp)
    # сложность растёт с этажом
    hp_mult = 1.0 + floor * 0.12
    dmg_base = 12 + floor * 1.5
    if is_boss:
        hp_mult *= 1.5
        dmg_base *= 1.3
        enemy = BOSS_FLOORS_EMOJI
        grid = 6 if floor >= 10 else 5
    else:
        enemy = TOWER_ENEMIES[(floor - 1) % len(TOWER_ENEMIES)]
        grid = 5
    lvl_factor = 1.0 + (player_level - 1) * 0.02
    hp = int(base * hp_mult * lvl_factor)
    dmg = int(dmg_base * lvl_factor)
    # награда за этаж
    gold = 30 + floor * 15 + (100 if is_boss else 0)
    xp = 15 + floor * 8 + (50 if is_boss else 0)
    return {
        "floor": floor, "name": enemy["name"], "emoji": enemy["emoji"],
        "isBoss": is_boss, "hp": hp, "maxHp": hp, "dmg": dmg, "grid": grid,
        "gold": gold, "xp": xp,
    }


def start_run(user_id, player_hp):
    """Начать новый подъём с 1 этажа."""
    ensure_tower_table()
    from database import get_conn, execute
    with get_conn() as conn:
        execute(conn, """INSERT INTO tower_progress (user_id, current_floor, current_hp, run_active)
                         VALUES (%s, 1, %s, TRUE)
                         ON CONFLICT (user_id) DO UPDATE SET current_floor=1, current_hp=%s, run_active=TRUE""",
                user_id, player_hp, player_hp)
    return {"ok": True}


def floor_won(user_id, remaining_hp):
    """Этаж пройден — поднимаемся выше, сохраняем HP и рекорд."""
    ensure_tower_table()
    from database import get_conn, fetchrow, execute, add_gold
    with get_conn() as conn:
        row = fetchrow(conn, "SELECT * FROM tower_progress WHERE user_id=%s", user_id)
        if not row or not row["run_active"]:
            return {"ok": False}
        cleared = row["current_floor"]
        new_floor = cleared + 1
        best = max(row["best_floor"], cleared)
        execute(conn, "UPDATE tower_progress SET current_floor=%s, current_hp=%s, best_floor=%s WHERE user_id=%s",
                new_floor, remaining_hp, best, user_id)
    # выдаём награду за этаж
    enemy = get_floor_enemy(cleared, 1, 100)
    add_gold(user_id, enemy["gold"])
    try:
        from database import add_xp
        add_xp(user_id, enemy["xp"])
    except Exception:
        pass
    try:
        from game.battle_pass import add_points
        add_points(user_id, "tower_floor")
    except Exception:
        pass
    return {"ok": True, "cleared": cleared, "nextFloor": new_floor,
            "gold": enemy["gold"], "xp": enemy["xp"], "best": best}


def run_failed(user_id):
    """Поражение — подъём окончен."""
    ensure_tower_table()
    from database import get_conn, fetchrow, execute
    with get_conn() as conn:
        row = fetchrow(conn, "SELECT * FROM tower_progress WHERE user_id=%s", user_id)
        reached = row["current_floor"] if row else 1
        best = max(row["best_floor"] if row else 0, reached - 1)
        execute(conn, "UPDATE tower_progress SET run_active=FALSE, best_floor=%s WHERE user_id=%s", best, user_id)
    return {"ok": True, "reached": reached, "best": best}


def get_leaderboard(limit=20):
    """Топ по высоте башни."""
    ensure_tower_table()
    from database import get_conn, fetchall
    try:
        from config import ADMIN_IDS
    except Exception:
        ADMIN_IDS = []
    with get_conn() as conn:
        rows = fetchall(conn, """
            SELECT t.user_id, t.best_floor, u.wizard_name, u.house
            FROM tower_progress t JOIN users u ON u.user_id = t.user_id
            WHERE t.best_floor > 0
            ORDER BY t.best_floor DESC LIMIT %s
        """, limit + len(ADMIN_IDS))
    out = []
    house_emoji = {"gryffindor":"🦁","slytherin":"🐍","ravenclaw":"🦅","hufflepuff":"🦡"}
    for r in rows:
        if r["user_id"] in ADMIN_IDS:
            continue
        out.append({"name": r["wizard_name"] or "Игрок", "floor": r["best_floor"],
                    "houseEmoji": house_emoji.get(r["house"], "")})
        if len(out) >= limit:
            break
    return out
