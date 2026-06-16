"""
Система рейтинга и лиг для магических дуэлей.

Очки рейтинга (RP) за победы/поражения. Лиги от Бронзы до Легенды.
Сложность боя влияет на очки.
"""

# Лиги: (название, эмодзи, минимальный рейтинг)
LEAGUES = [
    ("Бронза",   "🥉", 0),
    ("Серебро",  "🥈", 300),
    ("Золото",   "🥇", 700),
    ("Платина",  "💎", 1200),
    ("Алмаз",    "💠", 1800),
    ("Мастер",   "👑", 2500),
    ("Легенда",  "🏆", 3500),
]

# Очки за бой по сложности
RP_WIN = {"easy": 12, "normal": 22, "hard": 35}
RP_LOSS = {"easy": -6, "normal": -10, "hard": -14}


def get_league(rating: int):
    """Вернуть (название, эмодзи, прогресс_до_следующей, очки_до_следующей)."""
    rating = max(0, rating)
    current = LEAGUES[0]
    nxt = None
    for i, lg in enumerate(LEAGUES):
        if rating >= lg[2]:
            current = lg
            nxt = LEAGUES[i+1] if i+1 < len(LEAGUES) else None
        else:
            break
    if nxt:
        span = nxt[2] - current[2]
        done = rating - current[2]
        progress = int(done / span * 100) if span > 0 else 100
        to_next = nxt[2] - rating
    else:
        progress = 100
        to_next = 0
    return {
        "name": current[0], "emoji": current[1], "minRating": current[2],
        "nextName": nxt[0] if nxt else None, "nextEmoji": nxt[1] if nxt else None,
        "progress": progress, "toNext": to_next,
    }


def ensure_duel_rating_table():
    from database import get_conn, execute
    with get_conn() as conn:
        execute(conn, """
            CREATE TABLE IF NOT EXISTS duel_rating (
                user_id BIGINT PRIMARY KEY,
                rating INT DEFAULT 0,
                wins INT DEFAULT 0,
                losses INT DEFAULT 0,
                streak INT DEFAULT 0,
                best_streak INT DEFAULT 0
            )
        """)


def get_duel_rating(user_id: int) -> dict:
    ensure_duel_rating_table()
    from database import get_conn, fetchrow, execute
    with get_conn() as conn:
        row = fetchrow(conn, "SELECT * FROM duel_rating WHERE user_id=%s", user_id)
        if not row:
            execute(conn, "INSERT INTO duel_rating (user_id) VALUES (%s) ON CONFLICT DO NOTHING", user_id)
            return {"rating": 0, "wins": 0, "losses": 0, "streak": 0, "best_streak": 0}
    return {"rating": row["rating"], "wins": row["wins"], "losses": row["losses"],
            "streak": row["streak"], "best_streak": row["best_streak"]}


def update_duel_rating(user_id: int, won: bool, difficulty: str) -> dict:
    """Начислить очки за бой. Возвращает {rating, delta, league, leveledUp, streak}."""
    ensure_duel_rating_table()
    from database import get_conn, fetchrow, execute
    with get_conn() as conn:
        row = fetchrow(conn, "SELECT * FROM duel_rating WHERE user_id=%s", user_id)
        if not row:
            execute(conn, "INSERT INTO duel_rating (user_id) VALUES (%s)", user_id)
            rating, wins, losses, streak, best = 0, 0, 0, 0, 0
        else:
            rating, wins, losses = row["rating"], row["wins"], row["losses"]
            streak, best = row["streak"], row["best_streak"]

        old_league = get_league(rating)["name"]
        if won:
            delta = RP_WIN.get(difficulty, 22)
            streak += 1
            # бонус за серию побед
            if streak >= 3:
                delta += min(15, streak * 2)
            best = max(best, streak)
            wins += 1
        else:
            delta = RP_LOSS.get(difficulty, -10)
            streak = 0
            losses += 1
        rating = max(0, rating + delta)
        new_league = get_league(rating)["name"]
        execute(conn, """UPDATE duel_rating SET rating=%s, wins=%s, losses=%s, streak=%s, best_streak=%s
                         WHERE user_id=%s""", rating, wins, losses, streak, best, user_id)

    lg = get_league(rating)
    return {"rating": rating, "delta": delta, "league": lg,
            "leveledUp": (new_league != old_league and won),
            "streak": streak, "wins": wins, "losses": losses}


def get_duel_leaderboard(limit: int = 20, exclude_ids=None):
    """Топ игроков по рейтингу дуэлей."""
    ensure_duel_rating_table()
    from database import get_conn, fetchall
    exclude_ids = exclude_ids or [0]
    with get_conn() as conn:
        rows = fetchall(conn, """
            SELECT dr.user_id, dr.rating, dr.wins, dr.losses, u.wizard_name, u.house
            FROM duel_rating dr
            JOIN users u ON u.user_id = dr.user_id
            WHERE dr.user_id != ALL(%s) AND dr.rating > 0
            ORDER BY dr.rating DESC
            LIMIT %s
        """, exclude_ids, limit)
    out = []
    for r in rows:
        lg = get_league(r["rating"])
        out.append({
            "userId": r["user_id"], "name": r["wizard_name"], "house": r["house"],
            "rating": r["rating"], "wins": r["wins"], "losses": r["losses"],
            "league": lg["name"], "leagueEmoji": lg["emoji"],
        })
    return out
