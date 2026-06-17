"""
Ежедневный данж: раз в день забег из волн врагов.

3 волны врагов подряд (HP не лечится между волнами), в конце — награда.
Можно пройти раз в сутки. Гарантированная награда + шанс на ингредиент.
Причина заходить каждый день.
"""
import datetime
import random

WAVES = 3  # волн в данже

# Враги данжа (тематический сет, меняется по дню недели)
DUNGEON_SETS = [
    {"theme": "Подземелья Слизерина", "emoji": "🐍", "enemies": [
        {"name": "Змей", "emoji": "🐍"}, {"name": "Тёмный страж", "emoji": "🦎"}, {"name": "Василиск", "emoji": "🐲"}]},
    {"theme": "Запретный лес", "emoji": "🌲", "enemies": [
        {"name": "Акромантул", "emoji": "🕷️"}, {"name": "Кентавр", "emoji": "🏹"}, {"name": "Оборотень", "emoji": "🐺"}]},
    {"theme": "Подземелье душ", "emoji": "👻", "enemies": [
        {"name": "Призрак", "emoji": "👻"}, {"name": "Полтергейст", "emoji": "💀"}, {"name": "Дементор", "emoji": "🌫️"}]},
    {"theme": "Логово дракона", "emoji": "🐉", "enemies": [
        {"name": "Дракончик", "emoji": "🦎"}, {"name": "Виверна", "emoji": "🐉"}, {"name": "Древний дракон", "emoji": "🔥"}]},
    {"theme": "Чертоги Азкабана", "emoji": "⛓️", "enemies": [
        {"name": "Узник", "emoji": "🧟"}, {"name": "Страж", "emoji": "💂"}, {"name": "Тёмный лорд", "emoji": "💀"}]},
    {"theme": "Тайная комната", "emoji": "🚪", "enemies": [
        {"name": "Тень", "emoji": "👤"}, {"name": "Горгулья", "emoji": "🗿"}, {"name": "Босс комнаты", "emoji": "👹"}]},
    {"theme": "Башня астрономии", "emoji": "🔭", "enemies": [
        {"name": "Звёздный дух", "emoji": "✨"}, {"name": "Лунный волк", "emoji": "🌙"}, {"name": "Космический ужас", "emoji": "🌌"}]},
]


def _today():
    return datetime.date.today().isoformat()


def ensure_dungeon_table():
    from database import get_conn, execute
    with get_conn() as conn:
        execute(conn, """
            CREATE TABLE IF NOT EXISTS daily_dungeon (
                user_id BIGINT PRIMARY KEY,
                last_clear_date TEXT,
                current_wave INT DEFAULT 0,
                current_hp INT DEFAULT 0,
                run_date TEXT,
                run_active BOOLEAN DEFAULT FALSE
            )
        """)


def get_today_set():
    """Сет данжа на сегодня (по дню)."""
    idx = datetime.date.today().toordinal() % len(DUNGEON_SETS)
    return DUNGEON_SETS[idx]


def get_status(user_id):
    """Статус данжа: пройден ли сегодня, активен ли забег."""
    ensure_dungeon_table()
    from database import get_conn, fetchrow, execute
    with get_conn() as conn:
        row = fetchrow(conn, "SELECT * FROM daily_dungeon WHERE user_id=%s", user_id)
        if not row:
            execute(conn, "INSERT INTO daily_dungeon (user_id) VALUES (%s) ON CONFLICT DO NOTHING", user_id)
            row = {"last_clear_date": None, "current_wave": 0, "current_hp": 0, "run_date": None, "run_active": False}
    today = _today()
    cleared_today = (row["last_clear_date"] == today)
    run_active = row["run_active"] and (row["run_date"] == today)
    dset = get_today_set()
    return {
        "clearedToday": cleared_today, "runActive": run_active,
        "currentWave": row["current_wave"], "theme": dset["theme"], "themeEmoji": dset["emoji"],
        "waves": WAVES,
    }


def get_wave_enemy(wave, player_level, player_hp):
    """Враг для волны."""
    dset = get_today_set()
    enemies = dset["enemies"]
    enemy = enemies[min(wave - 1, len(enemies) - 1)]
    is_last = (wave == WAVES)
    base = max(100, player_hp)
    hp_mult = 1.1 + wave * 0.25
    if is_last:
        hp_mult *= 1.3
    dmg_base = 14 + wave * 3
    lvl_factor = 1.0 + (player_level - 1) * 0.02
    hp = int(base * hp_mult * lvl_factor)
    dmg = int(dmg_base * lvl_factor)
    return {
        "wave": wave, "name": enemy["name"], "emoji": enemy["emoji"],
        "isLast": is_last, "hp": hp, "maxHp": hp, "dmg": dmg,
        "grid": 6 if is_last else 5, "totalWaves": WAVES,
    }


def start_run(user_id, player_hp):
    ensure_dungeon_table()
    from database import get_conn, fetchrow, execute
    today = _today()
    with get_conn() as conn:
        row = fetchrow(conn, "SELECT last_clear_date FROM daily_dungeon WHERE user_id=%s", user_id)
        if row and row["last_clear_date"] == today:
            return {"ok": False, "msg": "Данж уже пройден сегодня. Возвращайся завтра!"}
        execute(conn, """INSERT INTO daily_dungeon (user_id, current_wave, current_hp, run_date, run_active)
                         VALUES (%s, 1, %s, %s, TRUE)
                         ON CONFLICT (user_id) DO UPDATE SET current_wave=1, current_hp=%s, run_date=%s, run_active=TRUE""",
                user_id, player_hp, today, player_hp, today)
    return {"ok": True}


def wave_won(user_id, remaining_hp):
    """Волна пройдена. Если последняя — выдаём награду."""
    ensure_dungeon_table()
    from database import get_conn, fetchrow, execute, add_gold
    today = _today()
    with get_conn() as conn:
        row = fetchrow(conn, "SELECT * FROM daily_dungeon WHERE user_id=%s", user_id)
        if not row or not row["run_active"]:
            return {"ok": False}
        wave = row["current_wave"]
        if wave >= WAVES:
            # данж пройден!
            execute(conn, "UPDATE daily_dungeon SET run_active=FALSE, last_clear_date=%s WHERE user_id=%s", today, user_id)
            done = True
            next_wave = wave
        else:
            next_wave = wave + 1
            execute(conn, "UPDATE daily_dungeon SET current_wave=%s, current_hp=%s WHERE user_id=%s",
                    next_wave, remaining_hp, user_id)
            done = False
    if done:
        # награда за прохождение
        gold = 300
        add_gold(user_id, gold)
        try:
            from database import add_xp
            add_xp(user_id, 150)
        except Exception:
            pass
        # шанс на ингредиент для зелий
        drop = None
        try:
            from game.duel_bosses import INGREDIENTS, give_ingredient
            if random.random() < 0.6:
                ing_id = random.choice(list(INGREDIENTS.keys()))
                give_ingredient(user_id, ing_id, 1)
                info = INGREDIENTS.get(ing_id, {})
                drop = {"name": info.get("name", ""), "emoji": info.get("emoji", "🧪")}
        except Exception:
            pass
        return {"ok": True, "done": True, "gold": gold, "xp": 150, "drop": drop}
    return {"ok": True, "done": False, "nextWave": next_wave}


def run_failed(user_id):
    ensure_dungeon_table()
    from database import get_conn, execute
    with get_conn() as conn:
        # поражение — забег окончен, но НЕ засчитываем как пройденный (можно попробовать снова сегодня)
        execute(conn, "UPDATE daily_dungeon SET run_active=FALSE WHERE user_id=%s", user_id)
    return {"ok": True}
