import psycopg2
import psycopg2.extras
from psycopg2.pool import ThreadedConnectionPool
from contextlib import contextmanager
from config import DATABASE_URL
import logging

logger = logging.getLogger(__name__)

_pool: ThreadedConnectionPool | None = None


def get_pool() -> ThreadedConnectionPool:
    global _pool
    if _pool is None:
        if not DATABASE_URL:
            raise RuntimeError("DATABASE_URL is not set!")
        _pool = ThreadedConnectionPool(2, 10, DATABASE_URL)
    return _pool


@contextmanager
def get_conn():
    pool = get_pool()
    conn = pool.getconn()
    conn.autocommit = False
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        pool.putconn(conn)


def fetchrow(conn, sql, *args):
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(sql, args)
        return cur.fetchone()


def fetchall(conn, sql, *args):
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(sql, args)
        return cur.fetchall()


def fetchval(conn, sql, *args):
    with conn.cursor() as cur:
        cur.execute(sql, args)
        row = cur.fetchone()
        return row[0] if row else None


def execute(conn, sql, *args):
    with conn.cursor() as cur:
        cur.execute(sql, args)


# ─── Schema ────────────────────────────────────────────────────────────────────

CREATE_TABLES_SQL = """
CREATE TABLE IF NOT EXISTS users (
    user_id       BIGINT PRIMARY KEY,
    username      TEXT,
    wizard_name   TEXT UNIQUE NOT NULL,
    house         TEXT NOT NULL,
    level         INT  DEFAULT 1,
    xp            INT  DEFAULT 0,
    hp            INT  DEFAULT 100,
    max_hp        INT  DEFAULT 100,
    mana          INT  DEFAULT 50,
    max_mana      INT  DEFAULT 50,
    attack        INT  DEFAULT 10,
    defense       INT  DEFAULT 5,
    speed         INT  DEFAULT 10,
    luck          INT  DEFAULT 5,
    gold          INT  DEFAULT 0,
    lang          TEXT DEFAULT 'ru',
    is_banned     BOOLEAN DEFAULT FALSE,
    tutorial_done BOOLEAN DEFAULT FALSE,
    title         TEXT DEFAULT NULL,
    wand_wood     TEXT DEFAULT NULL,
    wand_core     TEXT DEFAULT NULL,
    wand_length   INT  DEFAULT NULL,
    wand_flex     TEXT DEFAULT NULL,
    squad_id      INT  DEFAULT NULL,
    last_active   TIMESTAMPTZ DEFAULT NOW(),
    created_at    TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS user_stats (
    user_id           BIGINT PRIMARY KEY REFERENCES users(user_id),
    pvp_wins          INT DEFAULT 0,
    pvp_losses        INT DEFAULT 0,
    pvp_total         INT DEFAULT 0,
    pve_kills         INT DEFAULT 0,
    boss_kills        INT DEFAULT 0,
    world_boss_kills  INT DEFAULT 0,
    quests_done       INT DEFAULT 0,
    lessons_done      INT DEFAULT 0,
    potions_brewed    INT DEFAULT 0,
    gold_earned       INT DEFAULT 0,
    combo_used        INT DEFAULT 0
);

CREATE TABLE IF NOT EXISTS user_spells (
    id         SERIAL PRIMARY KEY,
    user_id    BIGINT REFERENCES users(user_id),
    spell_id   TEXT NOT NULL,
    learned_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(user_id, spell_id)
);

CREATE TABLE IF NOT EXISTS inventory (
    id          SERIAL PRIMARY KEY,
    user_id     BIGINT REFERENCES users(user_id),
    item_id     TEXT NOT NULL,
    quantity    INT DEFAULT 1,
    acquired_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(user_id, item_id)
);

CREATE TABLE IF NOT EXISTS equipped_items (
    user_id BIGINT REFERENCES users(user_id),
    slot    TEXT NOT NULL,
    item_id TEXT NOT NULL,
    bonus   INT DEFAULT 0,
    PRIMARY KEY (user_id, slot)
);

CREATE TABLE IF NOT EXISTS duels (
    id            SERIAL PRIMARY KEY,
    challenger_id BIGINT REFERENCES users(user_id),
    opponent_id   BIGINT REFERENCES users(user_id),
    winner_id     BIGINT,
    status        TEXT DEFAULT 'pending',
    started_at    TIMESTAMPTZ DEFAULT NOW(),
    ended_at      TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS duel_log (
    id         SERIAL PRIMARY KEY,
    duel_id    INT REFERENCES duels(id),
    turn       INT,
    actor_id   BIGINT,
    action     TEXT,
    details    JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS pve_sessions (
    id          SERIAL PRIMARY KEY,
    user_id     BIGINT REFERENCES users(user_id),
    zone        TEXT,
    monster     TEXT,
    result      TEXT,
    xp_gained   INT DEFAULT 0,
    gold_gained INT DEFAULT 0,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS lessons (
    id        SERIAL PRIMARY KEY,
    subject   TEXT NOT NULL,
    teacher   TEXT NOT NULL,
    starts_at TIMESTAMPTZ NOT NULL,
    ends_at   TIMESTAMPTZ NOT NULL,
    is_active BOOLEAN DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS lesson_attendance (
    id        SERIAL PRIMARY KEY,
    lesson_id INT REFERENCES lessons(id),
    user_id   BIGINT REFERENCES users(user_id),
    rewarded  BOOLEAN DEFAULT FALSE,
    score     INT DEFAULT 0,
    joined_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(lesson_id, user_id)
);

CREATE TABLE IF NOT EXISTS quests (
    id              SERIAL PRIMARY KEY,
    quest_id        TEXT UNIQUE NOT NULL,
    type            TEXT NOT NULL,
    title_key       TEXT,
    description_key TEXT,
    is_active       BOOLEAN DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS user_quests (
    id           SERIAL PRIMARY KEY,
    user_id      BIGINT REFERENCES users(user_id),
    quest_id     TEXT,
    step         INT DEFAULT 0,
    status       TEXT DEFAULT 'active',
    started_at   TIMESTAMPTZ DEFAULT NOW(),
    completed_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS house_points (
    house      TEXT PRIMARY KEY,
    points     INT DEFAULT 0,
    season     INT DEFAULT 1,
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS house_points_log (
    id         SERIAL PRIMARY KEY,
    user_id    BIGINT REFERENCES users(user_id),
    house      TEXT,
    points     INT,
    reason     TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS shop_items (
    id              SERIAL PRIMARY KEY,
    item_id         TEXT NOT NULL,
    price_gold      INT NOT NULL,
    stock           INT DEFAULT -1,
    available_until TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS auction_lots (
    id            SERIAL PRIMARY KEY,
    seller_id     BIGINT REFERENCES users(user_id),
    item_id       TEXT NOT NULL,
    start_price   INT NOT NULL,
    current_price INT NOT NULL,
    buyer_id      BIGINT,
    status        TEXT DEFAULT 'active',
    ends_at       TIMESTAMPTZ NOT NULL,
    created_at    TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS auction_bids (
    id        SERIAL PRIMARY KEY,
    lot_id    INT REFERENCES auction_lots(id),
    bidder_id BIGINT REFERENCES users(user_id),
    amount    INT NOT NULL,
    placed_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS events (
    id         SERIAL PRIMARY KEY,
    event_type TEXT NOT NULL,
    title_key  TEXT,
    starts_at  TIMESTAMPTZ,
    ends_at    TIMESTAMPTZ,
    is_active  BOOLEAN DEFAULT FALSE,
    data       JSONB
);

CREATE TABLE IF NOT EXISTS daily_limits (
    user_id       BIGINT REFERENCES users(user_id),
    date          DATE DEFAULT CURRENT_DATE,
    pvp_duels     INT DEFAULT 0,
    pve_dungeons  INT DEFAULT 0,
    pve_quests    INT DEFAULT 0,
    lessons       INT DEFAULT 0,
    auction_lots  INT DEFAULT 0,
    world_boss    INT DEFAULT 0,
    room_req      INT DEFAULT 0,
    hogsmeade     INT DEFAULT 0,
    forest        INT DEFAULT 0,
    black_market  INT DEFAULT 0,
    PRIMARY KEY (user_id, date)
);

CREATE TABLE IF NOT EXISTS weekly_stats (
    user_id   BIGINT PRIMARY KEY REFERENCES users(user_id),
    xp_week   INT DEFAULT 0,
    gold_week INT DEFAULT 0,
    kills_week INT DEFAULT 0,
    wins_week  INT DEFAULT 0,
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS active_potions (
    user_id    BIGINT NOT NULL,
    potion_id  TEXT NOT NULL,
    effect     TEXT NOT NULL,
    value      FLOAT NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (user_id, potion_id)
);

CREATE TABLE IF NOT EXISTS gringotts (
    user_id     BIGINT PRIMARY KEY REFERENCES users(user_id),
    balance     INT DEFAULT 0,
    last_interest TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS admin_log (
    id         SERIAL PRIMARY KEY,
    admin_id   BIGINT,
    action     TEXT,
    target_id  BIGINT,
    details    TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS conversation_states (
    user_id    BIGINT PRIMARY KEY,
    state_key  TEXT,
    state_data JSONB,
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- ── ДОСТИЖЕНИЯ ─────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS achievements (
    id          SERIAL PRIMARY KEY,
    user_id     BIGINT REFERENCES users(user_id),
    achievement TEXT NOT NULL,
    tier        INT DEFAULT 1,
    unlocked_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(user_id, achievement)
);

-- ── ТИТУЛЫ ─────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS user_titles (
    id         SERIAL PRIMARY KEY,
    user_id    BIGINT REFERENCES users(user_id),
    title_id   TEXT NOT NULL,
    earned_at  TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(user_id, title_id)
);

-- ── ОТРЯДЫ ─────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS squads (
    id          SERIAL PRIMARY KEY,
    name        TEXT UNIQUE NOT NULL,
    leader_id   BIGINT REFERENCES users(user_id),
    description TEXT DEFAULT '',
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

-- ── ТУРНИРЫ ────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS tournaments (
    id         SERIAL PRIMARY KEY,
    status     TEXT DEFAULT 'pending',
    started_at TIMESTAMPTZ,
    ended_at   TIMESTAMPTZ,
    winner_id  BIGINT,
    data       JSONB
);

CREATE TABLE IF NOT EXISTS tournament_participants (
    id            SERIAL PRIMARY KEY,
    tournament_id INT REFERENCES tournaments(id),
    user_id       BIGINT REFERENCES users(user_id),
    wins          INT DEFAULT 0,
    losses        INT DEFAULT 0,
    eliminated    BOOLEAN DEFAULT FALSE,
    UNIQUE(tournament_id, user_id)
);

-- ── ТОРГОВЛЯ ───────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS trade_log (
    id          SERIAL PRIMARY KEY,
    sender_id   BIGINT REFERENCES users(user_id),
    receiver_id BIGINT REFERENCES users(user_id),
    amount      INT NOT NULL,
    tax         INT DEFAULT 0,
    note        TEXT,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

-- ── ЗЕЛЬЕВАРЕНИЕ ───────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS potion_recipes (
    id         SERIAL PRIMARY KEY,
    recipe_id  TEXT UNIQUE NOT NULL,
    name_ru    TEXT,
    rarity     TEXT DEFAULT 'common',
    ingredients JSONB,
    result_item TEXT,
    is_active   BOOLEAN DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS user_recipes (
    id         SERIAL PRIMARY KEY,
    user_id    BIGINT REFERENCES users(user_id),
    recipe_id  TEXT NOT NULL,
    learned_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(user_id, recipe_id)
);

CREATE TABLE IF NOT EXISTS brewing_queue (
    id          SERIAL PRIMARY KEY,
    user_id     BIGINT REFERENCES users(user_id),
    recipe_id   TEXT NOT NULL,
    started_at  TIMESTAMPTZ DEFAULT NOW(),
    ready_at    TIMESTAMPTZ NOT NULL,
    collected   BOOLEAN DEFAULT FALSE
);

-- ── МИРОВЫЕ БОССЫ ──────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS world_bosses (
    id          SERIAL PRIMARY KEY,
    boss_id     TEXT NOT NULL,
    max_hp      INT NOT NULL,
    current_hp  INT NOT NULL,
    status      TEXT DEFAULT 'active',
    started_at  TIMESTAMPTZ DEFAULT NOW(),
    ended_at    TIMESTAMPTZ,
    season      INT DEFAULT 1
);

CREATE TABLE IF NOT EXISTS world_boss_damage (
    id            SERIAL PRIMARY KEY,
    world_boss_id INT REFERENCES world_bosses(id),
    user_id       BIGINT REFERENCES users(user_id),
    damage        INT DEFAULT 0,
    hits          INT DEFAULT 0,
    UNIQUE(world_boss_id, user_id)
);

-- ── ЛОКАЦИИ (исследование) ─────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS location_progress (
    user_id     BIGINT REFERENCES users(user_id),
    location_id TEXT NOT NULL,
    visits      INT DEFAULT 0,
    last_visit  TIMESTAMPTZ,
    PRIMARY KEY (user_id, location_id)
);

-- ── РЕЙТИНГИ (сезонные снимки) ────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS season_ratings (
    id          SERIAL PRIMARY KEY,
    season      INT NOT NULL,
    user_id     BIGINT REFERENCES users(user_id),
    category    TEXT NOT NULL,
    value       INT DEFAULT 0,
    rank        INT,
    snapshot_at TIMESTAMPTZ DEFAULT NOW()
);

-- ── ХОГСМИД (магазин) ──────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS hogsmeade_stock (
    id              SERIAL PRIMARY KEY,
    item_id         TEXT NOT NULL,
    price           INT NOT NULL,
    quantity        INT DEFAULT 1,
    is_rare         BOOLEAN DEFAULT FALSE,
    refreshed_at    TIMESTAMPTZ DEFAULT NOW(),
    available_until TIMESTAMPTZ
);

-- ── Комната Требований (ежедневные события) ────────────────────────────────
CREATE TABLE IF NOT EXISTS room_of_requirement (
    id           SERIAL PRIMARY KEY,
    event_type   TEXT NOT NULL,
    data         JSONB,
    created_at   TIMESTAMPTZ DEFAULT NOW(),
    date         DATE DEFAULT CURRENT_DATE
);

-- ── Начальные данные ───────────────────────────────────────────────────────
INSERT INTO house_points (house, points, season)
VALUES ('gryffindor', 0, 1), ('slytherin', 0, 1), ('ravenclaw', 0, 1), ('hufflepuff', 0, 1)
ON CONFLICT DO NOTHING;
"""


MIGRATION_SQL = """
-- ── Миграции (добавляем недостающие колонки если таблица уже существует) ───
ALTER TABLE house_points ADD COLUMN IF NOT EXISTS season INT DEFAULT 1;
ALTER TABLE house_points ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT NOW();

-- Для экипировки: handlers/inventory.py сохраняет бонус надетого предмета,
-- чтобы при снятии/замене вычесть ровно тот же бонус.
ALTER TABLE equipped_items ADD COLUMN IF NOT EXISTS bonus INT DEFAULT 0;

-- Новые активности для ежедневных лимитов
ALTER TABLE daily_limits ADD COLUMN IF NOT EXISTS forest       INT DEFAULT 0;
ALTER TABLE daily_limits ADD COLUMN IF NOT EXISTS black_market INT DEFAULT 0;
ALTER TABLE users ADD COLUMN IF NOT EXISTS last_active TIMESTAMPTZ DEFAULT NOW();

-- В старых базах у одного игрока могло быть несколько строк одного предмета.
-- Перед уникальным индексом складываем количество в одну строку.
WITH summed AS (
    SELECT user_id, item_id, MIN(id) AS keep_id, SUM(quantity) AS total_quantity
    FROM inventory
    GROUP BY user_id, item_id
    HAVING COUNT(*) > 1
)
UPDATE inventory i
SET quantity = summed.total_quantity
FROM summed
WHERE i.id = summed.keep_id;

WITH summed AS (
    SELECT user_id, item_id, MIN(id) AS keep_id
    FROM inventory
    GROUP BY user_id, item_id
    HAVING COUNT(*) > 1
)
DELETE FROM inventory i
USING summed
WHERE i.user_id = summed.user_id
  AND i.item_id = summed.item_id
  AND i.id <> summed.keep_id;

CREATE UNIQUE INDEX IF NOT EXISTS inventory_user_item_unique
ON inventory(user_id, item_id);
"""


def init_db():
    with get_conn() as conn:
        with conn.cursor() as cur:
            # Сначала создаём таблицы, потом применяем миграции.
            # Иначе на чистой базе ALTER TABLE падает, потому что таблиц ещё нет.
            cur.execute(CREATE_TABLES_SQL)
            cur.execute(MIGRATION_SQL)
    logger.info("Database initialised.")


# ─── User helpers ──────────────────────────────────────────────────────────────

def get_user(user_id: int):
    with get_conn() as conn:
        return fetchrow(conn, "SELECT * FROM users WHERE user_id = %s", user_id)


def user_exists(user_id: int) -> bool:
    return get_user(user_id) is not None


def wizard_name_taken(name: str) -> bool:
    with get_conn() as conn:
        row = fetchrow(conn, "SELECT 1 FROM users WHERE LOWER(wizard_name) = LOWER(%s)", name)
        return row is not None


def create_user(user_id: int, username: str, wizard_name: str, house: str, lang: str, starter_spell: str):
    with get_conn() as conn:
        execute(conn, """
            INSERT INTO users (user_id, username, wizard_name, house, lang, gold, hp, max_hp, mana, max_mana)
            VALUES (%s, %s, %s, %s, %s, 0, 100, 100, 50, 50)
            ON CONFLICT (user_id) DO NOTHING
        """, user_id, username, wizard_name, house, lang)
        execute(conn, "INSERT INTO user_stats (user_id) VALUES (%s) ON CONFLICT DO NOTHING", user_id)
        execute(conn, """
            INSERT INTO user_spells (user_id, spell_id) VALUES (%s, %s)
            ON CONFLICT DO NOTHING
        """, user_id, starter_spell)


def add_item_to_inventory(user_id: int, item_id: str, quantity: int = 1):
    """Безопасно добавить предмет в инвентарь.
    Если такой предмет уже есть — увеличиваем количество, а не создаём дубль.
    """
    if quantity <= 0:
        return
    with get_conn() as conn:
        execute(conn, """
            INSERT INTO inventory (user_id, item_id, quantity)
            VALUES (%s, %s, %s)
            ON CONFLICT (user_id, item_id)
            DO UPDATE SET quantity = inventory.quantity + EXCLUDED.quantity
        """, user_id, item_id, quantity)



def set_user_lang(user_id: int, lang: str):
    with get_conn() as conn:
        execute(conn, "UPDATE users SET lang = %s WHERE user_id = %s", lang, user_id)


def get_user_spells(user_id: int):
    with get_conn() as conn:
        return fetchall(conn, "SELECT spell_id FROM user_spells WHERE user_id = %s", user_id)


def get_house_counts() -> dict:
    with get_conn() as conn:
        rows = fetchall(conn, "SELECT house, COUNT(*) as cnt FROM users GROUP BY house")
        return {r["house"]: r["cnt"] for r in rows}


def get_house_points():
    with get_conn() as conn:
        return fetchall(conn, "SELECT house, points, season FROM house_points ORDER BY points DESC")


def add_house_points(user_id: int, house: str, points: int, reason: str):
    """Добавить очки факультету и записать в лог."""
    with get_conn() as conn:
        execute(conn, "UPDATE house_points SET points = points + %s WHERE house = %s", points, house)
        execute(conn,
            "INSERT INTO house_points_log (user_id, house, points, reason) VALUES (%s, %s, %s, %s)",
            user_id, house, points, reason)


def get_user_stats(user_id: int):
    with get_conn() as conn:
        return fetchrow(conn, "SELECT * FROM user_stats WHERE user_id = %s", user_id)


def get_spells_count(user_id: int) -> int:
    with get_conn() as conn:
        return fetchval(conn, "SELECT COUNT(*) FROM user_spells WHERE user_id = %s", user_id)


def add_xp(user_id: int, xp: int):
    """Add XP and handle level ups. Returns (new_level, leveled_up)."""
    from config import XP_CURVE_BASE, XP_CURVE_POWER, XP_CURVE_LINEAR, LEVEL_UP_GAINS
    user = get_user(user_id)
    new_xp = user["xp"] + xp
    level = user["level"]
    leveled_up = False
    levels_gained = 0

    while True:
        needed = int(XP_CURVE_BASE * (level ** XP_CURVE_POWER) + XP_CURVE_LINEAR * level)
        if new_xp >= needed:
            new_xp -= needed
            level += 1
            levels_gained += 1
            leveled_up = True
        else:
            break

    with get_conn() as conn:
        if leveled_up:
            g = LEVEL_UP_GAINS
            hp_gain   = g["max_hp"]   * levels_gained
            mana_gain = g["max_mana"] * levels_gained
            atk_gain  = g["attack"]   * levels_gained
            def_gain  = g["defense"]  * levels_gained
            spd_gain  = g.get("speed", 1) * levels_gained
            execute(conn, """
                UPDATE users SET xp = %s, level = %s,
                    max_hp = max_hp + %s, hp = LEAST(hp + %s, max_hp + %s),
                    max_mana = max_mana + %s, mana = LEAST(mana + %s, max_mana + %s),
                    attack = attack + %s, defense = defense + %s, speed = speed + %s
                WHERE user_id = %s
            """, new_xp, level,
                 hp_gain, hp_gain, hp_gain,
                 mana_gain, mana_gain, mana_gain,
                 atk_gain, def_gain, spd_gain, user_id)
        else:
            execute(conn, "UPDATE users SET xp = %s WHERE user_id = %s", new_xp, user_id)

    return level, leveled_up


def add_gold(user_id: int, amount: int):
    with get_conn() as conn:
        execute(conn, "UPDATE users SET gold = GREATEST(0, gold + %s) WHERE user_id = %s", amount, user_id)
    if amount > 0:
        with get_conn() as conn:
            execute(conn,
                "UPDATE user_stats SET gold_earned = gold_earned + %s WHERE user_id = %s",
                amount, user_id)


def get_daily_limit(user_id: int, activity: str) -> int:
    allowed = {"pvp_duels", "pve_dungeons", "pve_quests", "lessons",
               "auction_lots", "world_boss", "room_req", "hogsmeade",
               "forest", "black_market"}
    if activity not in allowed:
        raise ValueError(f"Unknown activity: {activity}")
    with get_conn() as conn:
        row = fetchrow(conn,
            f"SELECT {activity} FROM daily_limits WHERE user_id = %s AND date = CURRENT_DATE",
            user_id)
        return row[activity] if row else 0


def increment_daily(user_id: int, activity: str):
    allowed = {"pvp_duels", "pve_dungeons", "pve_quests", "lessons",
               "auction_lots", "world_boss", "room_req", "hogsmeade",
               "forest", "black_market"}
    if activity not in allowed:
        raise ValueError(f"Unknown activity: {activity}")
    with get_conn() as conn:
        execute(conn, f"""
            INSERT INTO daily_limits (user_id, date, {activity})
            VALUES (%s, CURRENT_DATE, 1)
            ON CONFLICT (user_id, date)
            DO UPDATE SET {activity} = daily_limits.{activity} + 1
        """, user_id)


def get_leaderboard(category: str = "level", limit: int = 10):
    """Многокатегорийный рейтинг. Администраторы исключены из всех топов."""
    from config import ADMIN_IDS
    exclude = list(ADMIN_IDS) if ADMIN_IDS else [0]
    with get_conn() as conn:
        if category == "level":
            return fetchall(conn,
                "SELECT wizard_name, house, level, xp FROM users "
                "WHERE user_id != ALL(%s) AND COALESCE(is_banned, FALSE) = FALSE "
                "ORDER BY level DESC, xp DESC LIMIT %s",
                exclude, limit)
        elif category == "gold":
            return fetchall(conn,
                "SELECT wizard_name, house, gold FROM users "
                "WHERE user_id != ALL(%s) AND COALESCE(is_banned, FALSE) = FALSE "
                "ORDER BY gold DESC LIMIT %s",
                exclude, limit)
        elif category == "pvp":
            return fetchall(conn, """
                SELECT u.wizard_name, u.house, s.pvp_wins
                FROM users u JOIN user_stats s ON u.user_id = s.user_id
                WHERE u.user_id != ALL(%s) AND COALESCE(u.is_banned, FALSE) = FALSE
                ORDER BY s.pvp_wins DESC LIMIT %s
            """, exclude, limit)
        elif category == "pve":
            return fetchall(conn, """
                SELECT u.wizard_name, u.house, s.pve_kills
                FROM users u JOIN user_stats s ON u.user_id = s.user_id
                WHERE u.user_id != ALL(%s) AND COALESCE(u.is_banned, FALSE) = FALSE
                ORDER BY s.pve_kills DESC LIMIT %s
            """, exclude, limit)
        else:
            return []


def reset_house_cup_points():
    with get_conn() as conn:
        execute(conn, "UPDATE house_points SET points = 0, season = season + 1, updated_at = NOW()")


def ban_user(user_id: int):
    with get_conn() as conn:
        execute(conn, "UPDATE users SET is_banned = TRUE WHERE user_id = %s", user_id)


def unban_user(user_id: int):
    with get_conn() as conn:
        execute(conn, "UPDATE users SET is_banned = FALSE WHERE user_id = %s", user_id)


def is_banned(user_id: int) -> bool:
    with get_conn() as conn:
        row = fetchrow(conn, "SELECT is_banned FROM users WHERE user_id = %s", user_id)
        return row["is_banned"] if row else False


def get_all_user_ids() -> list:
    with get_conn() as conn:
        rows = fetchall(conn, "SELECT user_id FROM users WHERE is_banned = FALSE")
        return [r["user_id"] for r in rows]


def log_admin_action(admin_id: int, action: str, target_id: int = None, details: str = None):
    with get_conn() as conn:
        execute(conn,
            "INSERT INTO admin_log (admin_id, action, target_id, details) VALUES (%s, %s, %s, %s)",
            admin_id, action, target_id, details)


# ─── Достижения ────────────────────────────────────────────────────────────────

def get_user_achievements(user_id: int):
    with get_conn() as conn:
        return fetchall(conn, "SELECT achievement, tier FROM achievements WHERE user_id = %s", user_id)


def unlock_achievement(user_id: int, achievement: str, tier: int = 1):
    with get_conn() as conn:
        execute(conn, """
            INSERT INTO achievements (user_id, achievement, tier)
            VALUES (%s, %s, %s)
            ON CONFLICT (user_id, achievement) DO UPDATE SET tier = EXCLUDED.tier
        """, user_id, achievement, tier)


# ─── Отряды ────────────────────────────────────────────────────────────────────

def get_squad(squad_id: int):
    with get_conn() as conn:
        return fetchrow(conn, "SELECT * FROM squads WHERE id = %s", squad_id)


def get_squad_members(squad_id: int):
    with get_conn() as conn:
        return fetchall(conn,
            "SELECT user_id, wizard_name, level FROM users WHERE squad_id = %s",
            squad_id)


def create_squad(name: str, leader_id: int) -> int:
    with get_conn() as conn:
        squad_id = fetchval(conn,
            "INSERT INTO squads (name, leader_id) VALUES (%s, %s) RETURNING id",
            name, leader_id)
        execute(conn, "UPDATE users SET squad_id = %s WHERE user_id = %s", squad_id, leader_id)
        return squad_id


# ─── Мировые боссы ─────────────────────────────────────────────────────────────

def get_active_world_boss():
    with get_conn() as conn:
        return fetchrow(conn,
            "SELECT * FROM world_bosses WHERE status = 'active' ORDER BY started_at DESC LIMIT 1")


def record_world_boss_damage(world_boss_id: int, user_id: int, damage: int):
    with get_conn() as conn:
        execute(conn, """
            INSERT INTO world_boss_damage (world_boss_id, user_id, damage, hits)
            VALUES (%s, %s, %s, 1)
            ON CONFLICT (world_boss_id, user_id)
            DO UPDATE SET damage = world_boss_damage.damage + EXCLUDED.damage,
                          hits   = world_boss_damage.hits + 1
        """, world_boss_id, user_id, damage)
        execute(conn,
            "UPDATE world_bosses SET current_hp = GREATEST(0, current_hp - %s) WHERE id = %s",
            damage, world_boss_id)


def get_world_boss_top(world_boss_id: int, limit: int = 10):
    from config import ADMIN_IDS
    exclude = list(ADMIN_IDS) if ADMIN_IDS else [0]
    with get_conn() as conn:
        return fetchall(conn, """
            SELECT u.wizard_name, u.house, d.damage, d.hits, d.user_id
            FROM world_boss_damage d
            JOIN users u ON d.user_id = u.user_id
            WHERE d.world_boss_id = %s
              AND d.user_id != ALL(%s)
            ORDER BY d.damage DESC LIMIT %s
        """, world_boss_id, exclude, limit)


# ─── Зельеварение ──────────────────────────────────────────────────────────────

def get_user_recipes(user_id: int):
    with get_conn() as conn:
        return fetchall(conn, """
            SELECT r.* FROM potion_recipes r
            JOIN user_recipes ur ON r.recipe_id = ur.recipe_id
            WHERE ur.user_id = %s
        """, user_id)


def get_brewing_queue(user_id: int):
    with get_conn() as conn:
        return fetchall(conn, """
            SELECT * FROM brewing_queue
            WHERE user_id = %s AND collected = FALSE
            ORDER BY ready_at ASC
        """, user_id)


# ─── Торговля ──────────────────────────────────────────────────────────────────

def transfer_gold(sender_id: int, receiver_id: int, amount: int, tax: int, note: str = ""):
    with get_conn() as conn:
        execute(conn, "UPDATE users SET gold = gold - %s WHERE user_id = %s", amount + tax, sender_id)
        execute(conn, "UPDATE users SET gold = gold + %s WHERE user_id = %s", amount, receiver_id)
        execute(conn, """
            INSERT INTO trade_log (sender_id, receiver_id, amount, tax, note)
            VALUES (%s, %s, %s, %s, %s)
        """, sender_id, receiver_id, amount, tax, note)


# ─── ConversationHandler states ────────────────────────────────────────────────

def save_conv_state(user_id: int, state_key: str, state_data: dict):
    import json
    with get_conn() as conn:
        execute(conn, """
            INSERT INTO conversation_states (user_id, state_key, state_data, updated_at)
            VALUES (%s, %s, %s, NOW())
            ON CONFLICT (user_id) DO UPDATE
                SET state_key = EXCLUDED.state_key,
                    state_data = EXCLUDED.state_data,
                    updated_at = NOW()
        """, user_id, state_key, json.dumps(state_data))


def load_conv_state(user_id: int) -> dict | None:
    import json
    with get_conn() as conn:
        row = fetchrow(conn,
            "SELECT state_key, state_data FROM conversation_states WHERE user_id = %s",
            user_id)
        if not row:
            return None
        return {
            "state_key": row["state_key"],
            "state_data": json.loads(row["state_data"]) if row["state_data"] else {}
        }


def clear_conv_state(user_id: int):
    with get_conn() as conn:
        execute(conn, "DELETE FROM conversation_states WHERE user_id = %s", user_id)


def add_weekly_xp(user_id: int, xp: int):
    """Добавить XP в недельную статистику."""
    try:
        with get_conn() as conn:
            execute(conn, """
                INSERT INTO weekly_stats (user_id, xp_week)
                VALUES (%s, %s)
                ON CONFLICT (user_id) DO UPDATE
                SET xp_week = weekly_stats.xp_week + EXCLUDED.xp_week,
                    updated_at = NOW()
            """, user_id, xp)
    except Exception:
        pass


def add_weekly_win(user_id: int):
    try:
        with get_conn() as conn:
            execute(conn, """
                INSERT INTO weekly_stats (user_id, wins_week)
                VALUES (%s, 1)
                ON CONFLICT (user_id) DO UPDATE
                SET wins_week = weekly_stats.wins_week + 1, updated_at = NOW()
            """, user_id)
    except Exception:
        pass


def add_weekly_kill(user_id: int):
    try:
        with get_conn() as conn:
            execute(conn, """
                INSERT INTO weekly_stats (user_id, kills_week)
                VALUES (%s, 1)
                ON CONFLICT (user_id) DO UPDATE
                SET kills_week = weekly_stats.kills_week + 1, updated_at = NOW()
            """, user_id)
    except Exception:
        pass


def get_active_potions(user_id: int) -> list:
    """Получить активные зелья игрока."""
    try:
        with get_conn() as conn:
            return fetchall(conn,
                "SELECT * FROM active_potions WHERE user_id=%s AND expires_at > NOW()",
                user_id)
    except Exception:
        return []


def apply_potion(user_id: int, potion_id: str, effect: str, value: float, duration_minutes: int = 60):
    """Активировать зелье на указанное время."""
    try:
        with get_conn() as conn:
            execute(conn, """
                INSERT INTO active_potions (user_id, potion_id, effect, value, expires_at)
                VALUES (%s, %s, %s, %s, NOW() + INTERVAL '%s minutes')
                ON CONFLICT (user_id, potion_id) DO UPDATE
                SET value=EXCLUDED.value, expires_at=EXCLUDED.expires_at
            """, user_id, potion_id, effect, value, duration_minutes)
    except Exception:
        pass


def get_potion_bonus(user_id: int, effect: str) -> float:
    """Получить суммарный бонус от активных зелий для эффекта."""
    try:
        with get_conn() as conn:
            rows = fetchall(conn,
                "SELECT value FROM active_potions WHERE user_id=%s AND effect=%s AND expires_at>NOW()",
                user_id, effect)
        return sum(r["value"] for r in rows) if rows else 0.0
    except Exception:
        return 0.0


def touch_user_activity(user_id: int):
    """Обновить время последней активности игрока. Вызывать при любом действии."""
    try:
        with get_conn() as conn:
            execute(conn, "UPDATE users SET last_active = NOW() WHERE user_id = %s", user_id)
    except Exception:
        pass


def get_inactive_users(hours: int = 2, limit: int = 500) -> list:
    """Игроки, не активные больше N часов (для случайных атак)."""
    from config import ADMIN_IDS
    exclude = list(ADMIN_IDS) if ADMIN_IDS else [0]
    try:
        with get_conn() as conn:
            return fetchall(conn, """
                SELECT user_id, wizard_name, house, level, lang,
                       attack, defense, max_hp, luck
                FROM users
                WHERE COALESCE(is_banned, FALSE) = FALSE
                  AND user_id != ALL(%s)
                  AND last_active < NOW() - (%s || ' hours')::interval
                ORDER BY last_active ASC
                LIMIT %s
            """, exclude, str(hours), limit)
    except Exception:
        return []
