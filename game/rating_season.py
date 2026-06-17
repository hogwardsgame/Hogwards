"""
Сезоны рейтинга: ежемесячный сброс + награды топам.

В конце сезона (месяц) рейтинг частично сбрасывается (×0.5, soft reset),
топ-игроки получают награды и сезонный значок.
Новый сезон — новая гонка за топ.
"""
import datetime

# Награды за топ места в сезоне
SEASON_REWARDS = {
    1: {"gold": 3000, "badge": "champion", "title": "👑 Чемпион сезона", "name": "1 место"},
    2: {"gold": 2000, "badge": "vip", "title": "🥈 Призёр сезона", "name": "2 место"},
    3: {"gold": 1500, "badge": "vip", "title": "🥉 Призёр сезона", "name": "3 место"},
}
# Топ 4-10 — утешительная награда
TOP10_GOLD = 500

SOFT_RESET_FACTOR = 0.5  # рейтинг ×0.5 в новом сезоне


def _current_season():
    now = datetime.date.today()
    return f"{now.year}-{now.month:02d}"


def ensure_season_table():
    from database import get_conn, execute
    with get_conn() as conn:
        execute(conn, """
            CREATE TABLE IF NOT EXISTS rating_season (
                id INT PRIMARY KEY DEFAULT 1,
                current_season TEXT
            )
        """)
        execute(conn, """
            CREATE TABLE IF NOT EXISTS season_rewards_claimed (
                user_id BIGINT NOT NULL,
                season TEXT NOT NULL,
                place INT,
                UNIQUE(user_id, season)
            )
        """)


def get_season_info():
    """Текущий сезон + дней до конца."""
    season = _current_season()
    now = datetime.date.today()
    # последний день месяца
    if now.month == 12:
        next_month = datetime.date(now.year + 1, 1, 1)
    else:
        next_month = datetime.date(now.year, now.month + 1, 1)
    days_left = (next_month - now).days
    return {"season": season, "daysLeft": days_left}


def check_and_rollover():
    """Проверяет смену сезона. Если месяц сменился — soft reset рейтинга + награды."""
    ensure_season_table()
    from database import get_conn, fetchrow, execute
    season = _current_season()
    with get_conn() as conn:
        row = fetchrow(conn, "SELECT current_season FROM rating_season WHERE id=1")
        if not row:
            execute(conn, "INSERT INTO rating_season (id, current_season) VALUES (1, %s) ON CONFLICT DO NOTHING", season)
            return False
        stored = row["current_season"]
    if stored == season:
        return False  # тот же сезон
    # СМЕНА СЕЗОНА — награждаем топ прошлого сезона и делаем soft reset
    _award_top_and_reset(stored, season)
    return True


def _award_top_and_reset(old_season, new_season):
    from database import get_conn, fetchall, execute, add_gold
    try:
        from config import ADMIN_IDS
    except Exception:
        ADMIN_IDS = []
    # топ игроков прошлого сезона
    with get_conn() as conn:
        rows = fetchall(conn, "SELECT user_id, rating FROM duel_rating WHERE rating > 0 ORDER BY rating DESC LIMIT 30")
    place = 0
    for r in rows:
        if r["user_id"] in ADMIN_IDS:
            continue
        place += 1
        uid = r["user_id"]
        # награда
        if place in SEASON_REWARDS:
            rew = SEASON_REWARDS[place]
            add_gold(uid, rew["gold"])
            try:
                from game.world_chat import give_badge
                give_badge(uid, rew["badge"])
            except Exception:
                pass
        elif place <= 10:
            add_gold(uid, TOP10_GOLD)
        # помечаем для уведомления
        try:
            with get_conn() as conn:
                execute(conn, """INSERT INTO season_rewards_claimed (user_id, season, place) VALUES (%s,%s,%s)
                                 ON CONFLICT DO NOTHING""", uid, old_season, place)
        except Exception:
            pass
        if place >= 10:
            break
    # soft reset: рейтинг ×0.5, обнуляем стрики
    with get_conn() as conn:
        execute(conn, "UPDATE duel_rating SET rating = FLOOR(rating * %s), streak = 0", SOFT_RESET_FACTOR)
        execute(conn, "UPDATE rating_season SET current_season=%s WHERE id=1", new_season)
    # анонс в чат
    try:
        from game.world_chat import system_message
        system_message(f"📅 Новый сезон рейтинга {new_season}! Рейтинги пересчитаны. Топы прошлого сезона награждены. Гонка началась заново!")
    except Exception:
        pass


def get_pending_reward(user_id):
    """Награда сезона, которую игрок ещё не видел (для показа)."""
    ensure_season_table()
    from database import get_conn, fetchrow
    with get_conn() as conn:
        row = fetchrow(conn, """SELECT season, place FROM season_rewards_claimed
                                WHERE user_id=%s ORDER BY season DESC LIMIT 1""", user_id)
    if not row:
        return None
    place = row["place"]
    info = {"season": row["season"], "place": place}
    if place in SEASON_REWARDS:
        info["reward"] = SEASON_REWARDS[place]["name"]
        info["gold"] = SEASON_REWARDS[place]["gold"]
    elif place <= 10:
        info["reward"] = f"Топ-10 ({place} место)"
        info["gold"] = TOP10_GOLD
    return info
