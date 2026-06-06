import asyncpg
import os
from config import DATABASE_URL


_pool: asyncpg.Pool | None = None


async def get_pool() -> asyncpg.Pool:
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(DATABASE_URL, min_size=2, max_size=10)
    return _pool


async def close_pool():
    global _pool
    if _pool:
        await _pool.close()
        _pool = None


# ─── Schema ───────────────────────────────────────────────────────────────────

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
    gold          INT  DEFAULT 100,
    lang          TEXT DEFAULT 'ru',
    created_at    TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS user_stats (
    user_id       BIGINT PRIMARY KEY REFERENCES users(user_id),
    pvp_wins      INT DEFAULT 0,
    pvp_losses    INT DEFAULT 0,
    pvp_total     INT DEFAULT 0,
    pve_kills     INT DEFAULT 0,
    quests_done   INT DEFAULT 0,
    lessons_done  INT DEFAULT 0
);

CREATE TABLE IF NOT EXISTS user_spells (
    id        SERIAL PRIMARY KEY,
    user_id   BIGINT REFERENCES users(user_id),
    spell_id  TEXT NOT NULL,
    learned_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(user_id, spell_id)
);

CREATE TABLE IF NOT EXISTS inventory (
    id         SERIAL PRIMARY KEY,
    user_id    BIGINT REFERENCES users(user_id),
    item_id    TEXT NOT NULL,
    quantity   INT DEFAULT 1,
    acquired_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS equipped_items (
    user_id   BIGINT REFERENCES users(user_id),
    slot      TEXT NOT NULL,
    item_id   TEXT NOT NULL,
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
    id       SERIAL PRIMARY KEY,
    duel_id  INT REFERENCES duels(id),
    turn     INT,
    actor_id BIGINT,
    action   TEXT,
    details  JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS pve_sessions (
    id         SERIAL PRIMARY KEY,
    user_id    BIGINT REFERENCES users(user_id),
    zone       TEXT,
    monster    TEXT,
    result     TEXT,
    xp_gained  INT DEFAULT 0,
    gold_gained INT DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS lessons (
    id          SERIAL PRIMARY KEY,
    subject     TEXT NOT NULL,
    teacher     TEXT NOT NULL,
    starts_at   TIMESTAMPTZ NOT NULL,
    ends_at     TIMESTAMPTZ NOT NULL,
    is_active   BOOLEAN DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS lesson_attendance (
    id        SERIAL PRIMARY KEY,
    lesson_id INT REFERENCES lessons(id),
    user_id   BIGINT REFERENCES users(user_id),
    rewarded  BOOLEAN DEFAULT FALSE,
    joined_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS quests (
    id          SERIAL PRIMARY KEY,
    quest_id    TEXT UNIQUE NOT NULL,
    type        TEXT NOT NULL,
    title_key   TEXT,
    description_key TEXT,
    is_active   BOOLEAN DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS user_quests (
    id        SERIAL PRIMARY KEY,
    user_id   BIGINT REFERENCES users(user_id),
    quest_id  TEXT,
    step      INT DEFAULT 0,
    status    TEXT DEFAULT 'active',
    started_at TIMESTAMPTZ DEFAULT NOW(),
    completed_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS house_points (
    house     TEXT PRIMARY KEY,
    points    INT DEFAULT 0,
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS shop_items (
    id          SERIAL PRIMARY KEY,
    item_id     TEXT NOT NULL,
    price_gold  INT NOT NULL,
    stock       INT DEFAULT -1,
    available_until TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS auction_lots (
    id           SERIAL PRIMARY KEY,
    seller_id    BIGINT REFERENCES users(user_id),
    item_id      TEXT NOT NULL,
    start_price  INT NOT NULL,
    current_price INT NOT NULL,
    buyer_id     BIGINT,
    status       TEXT DEFAULT 'active',
    ends_at      TIMESTAMPTZ NOT NULL,
    created_at   TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS auction_bids (
    id       SERIAL PRIMARY KEY,
    lot_id   INT REFERENCES auction_lots(id),
    bidder_id BIGINT REFERENCES users(user_id),
    amount   INT NOT NULL,
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
    user_id        BIGINT REFERENCES users(user_id),
    date           DATE DEFAULT CURRENT_DATE,
    pvp_duels      INT DEFAULT 0,
    pve_dungeons   INT DEFAULT 0,
    pve_quests     INT DEFAULT 0,
    lessons        INT DEFAULT 0,
    auction_lots   INT DEFAULT 0,
    PRIMARY KEY (user_id, date)
);

CREATE TABLE IF NOT EXISTS admin_log (
    id         SERIAL PRIMARY KEY,
    admin_id   BIGINT,
    action     TEXT,
    target_id  BIGINT,
    details    TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

INSERT INTO house_points (house, points)
VALUES ('gryffindor', 0), ('slytherin', 0), ('ravenclaw', 0), ('hufflepuff', 0)
ON CONFLICT DO NOTHING;
"""


async def init_db():
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(CREATE_TABLES_SQL)


# ─── User helpers ─────────────────────────────────────────────────────────────

async def get_user(user_id: int):
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await conn.fetchrow("SELECT * FROM users WHERE user_id = $1", user_id)


async def user_exists(user_id: int) -> bool:
    return await get_user(user_id) is not None


async def wizard_name_taken(name: str) -> bool:
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT 1 FROM users WHERE LOWER(wizard_name) = LOWER($1)", name)
        return row is not None


async def create_user(user_id: int, username: str, wizard_name: str, house: str, lang: str, starter_spell: str):
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            await conn.execute("""
                INSERT INTO users (user_id, username, wizard_name, house, lang, gold, hp, max_hp, mana, max_mana)
                VALUES ($1, $2, $3, $4, $5, 100, 100, 100, 50, 50)
            """, user_id, username, wizard_name, house, lang)

            await conn.execute("""
                INSERT INTO user_stats (user_id) VALUES ($1)
            """, user_id)

            await conn.execute("""
                INSERT INTO user_spells (user_id, spell_id) VALUES ($1, $2)
            """, user_id, starter_spell)


async def set_user_lang(user_id: int, lang: str):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("UPDATE users SET lang = $1 WHERE user_id = $2", lang, user_id)


async def get_user_spells(user_id: int):
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await conn.fetch("SELECT spell_id FROM user_spells WHERE user_id = $1", user_id)


async def get_house_counts() -> dict:
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT house, COUNT(*) as cnt FROM users GROUP BY house")
        return {r["house"]: r["cnt"] for r in rows}


async def get_house_points():
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await conn.fetch("SELECT house, points FROM house_points ORDER BY points DESC")


async def add_xp(user_id: int, xp: int):
    """Add XP and handle level ups. Returns (new_level, leveled_up)."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        user = await conn.fetchrow("SELECT level, xp FROM users WHERE user_id = $1", user_id)
        new_xp = user["xp"] + xp
        level = user["level"]

        leveled_up = False
        while True:
            needed = int(500 * level * (1.15 ** (level - 1)))
            if new_xp >= needed:
                new_xp -= needed
                level += 1
                leveled_up = True
            else:
                break

        if leveled_up:
            await conn.execute("""
                UPDATE users SET xp = $1, level = $2,
                    max_hp = max_hp + 5, hp = LEAST(hp + 5, max_hp + 5),
                    max_mana = max_mana + 3, mana = LEAST(mana + 3, max_mana + 3),
                    attack = attack + 1, defense = defense + 1
                WHERE user_id = $3
            """, new_xp, level, user_id)
        else:
            await conn.execute("UPDATE users SET xp = $1 WHERE user_id = $2", new_xp, user_id)

        return level, leveled_up


async def add_gold(user_id: int, amount: int):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("UPDATE users SET gold = gold + $1 WHERE user_id = $2", amount, user_id)


async def get_daily_limit(user_id: int, activity: str) -> int:
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            f"SELECT {activity} FROM daily_limits WHERE user_id = $1 AND date = CURRENT_DATE",
            user_id
        )
        return row[activity] if row else 0


async def increment_daily(user_id: int, activity: str):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(f"""
            INSERT INTO daily_limits (user_id, date, {activity})
            VALUES ($1, CURRENT_DATE, 1)
            ON CONFLICT (user_id, date)
            DO UPDATE SET {activity} = daily_limits.{activity} + 1
        """, user_id)


async def get_leaderboard(limit: int = 10):
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await conn.fetch(
            "SELECT wizard_name, house, level, xp FROM users ORDER BY level DESC, xp DESC LIMIT $1",
            limit
        )
