"""
Турнир на выбывание (сольный бэкэнд).

Игрок проходит сетку из 8 участников: четвертьфинал → полуфинал → финал.
3 победы подряд = чемпион. Соперники — ИИ-волшебники, усиливающиеся с раундом.
Раз в день. Большой приз + значок чемпиона за победу в турнире.
HP не лечится между боями (как в реальном турнире).
"""
import datetime
import random

ROUNDS = 3  # четвертьфинал, полуфинал, финал

# Имена соперников-волшебников (флавор)
OPPONENT_NAMES = [
    ("Малфой", "🐍"), ("Забини", "🐍"), ("Крам", "🦅"), ("Диггори", "🦡"),
    ("Делакур", "🦅"), ("Уизли", "🦁"), ("Лонгботтом", "🦁"), ("Чанг", "🦅"),
    ("Нотт", "🐍"), ("Финч", "🦡"), ("Белби", "🦅"), ("Корнер", "🦅"),
]

ROUND_NAMES = {1: "Четвертьфинал", 2: "Полуфинал", 3: "🏆 ФИНАЛ"}


def _today():
    return datetime.date.today().isoformat()


def ensure_tournament_table():
    from database import get_conn, execute
    with get_conn() as conn:
        execute(conn, """
            CREATE TABLE IF NOT EXISTS tournament_runs (
                user_id BIGINT PRIMARY KEY,
                last_win_date TEXT,
                current_round INT DEFAULT 0,
                current_hp INT DEFAULT 0,
                run_date TEXT,
                run_active BOOLEAN DEFAULT FALSE,
                wins_total INT DEFAULT 0
            )
        """)


def get_status(user_id):
    ensure_tournament_table()
    from database import get_conn, fetchrow, execute
    with get_conn() as conn:
        row = fetchrow(conn, "SELECT * FROM tournament_runs WHERE user_id=%s", user_id)
        if not row:
            execute(conn, "INSERT INTO tournament_runs (user_id) VALUES (%s) ON CONFLICT DO NOTHING", user_id)
            row = {"last_win_date": None, "current_round": 0, "current_hp": 0, "run_date": None, "run_active": False, "wins_total": 0}
    today = _today()
    won_today = (row["last_win_date"] == today)
    run_active = row["run_active"] and (row["run_date"] == today)
    return {
        "wonToday": won_today, "runActive": run_active,
        "currentRound": row["current_round"], "rounds": ROUNDS,
        "winsTotal": row["wins_total"] or 0,
    }


def get_round_opponent(rnd, player_level, player_hp):
    """Соперник для раунда."""
    name, emoji = random.choice(OPPONENT_NAMES)
    is_final = (rnd == ROUNDS)
    base = max(100, player_hp)
    # соперники сильнее с каждым раундом
    hp_mult = 1.2 + rnd * 0.3
    dmg_base = 16 + rnd * 4
    if is_final:
        hp_mult += 0.3
    lvl_factor = 1.0 + (player_level - 1) * 0.02
    hp = int(base * hp_mult * lvl_factor)
    dmg = int(dmg_base * lvl_factor)
    # ИИ умнее в поздних раундах
    ai_skill = 0.6 + rnd * 0.1
    return {
        "round": rnd, "roundName": ROUND_NAMES.get(rnd, f"Раунд {rnd}"),
        "name": name, "emoji": emoji, "isFinal": is_final,
        "hp": hp, "maxHp": hp, "dmg": dmg, "grid": 6 if is_final else 5,
        "aiSkill": ai_skill, "totalRounds": ROUNDS,
    }


def start_run(user_id, player_hp):
    ensure_tournament_table()
    from database import get_conn, fetchrow, execute
    today = _today()
    with get_conn() as conn:
        row = fetchrow(conn, "SELECT last_win_date FROM tournament_runs WHERE user_id=%s", user_id)
        if row and row["last_win_date"] == today:
            return {"ok": False, "msg": "Ты уже побеждал в турнире сегодня. Возвращайся завтра!"}
        execute(conn, """INSERT INTO tournament_runs (user_id, current_round, current_hp, run_date, run_active)
                         VALUES (%s, 1, %s, %s, TRUE)
                         ON CONFLICT (user_id) DO UPDATE SET current_round=1, current_hp=%s, run_date=%s, run_active=TRUE""",
                user_id, player_hp, today, player_hp, today)
    return {"ok": True}


def round_won(user_id, remaining_hp):
    """Раунд выигран. Если финал — чемпион!"""
    ensure_tournament_table()
    from database import get_conn, fetchrow, execute, add_gold
    today = _today()
    with get_conn() as conn:
        row = fetchrow(conn, "SELECT * FROM tournament_runs WHERE user_id=%s", user_id)
        if not row or not row["run_active"]:
            return {"ok": False}
        rnd = row["current_round"]
        if rnd >= ROUNDS:
            # ЧЕМПИОН!
            execute(conn, """UPDATE tournament_runs SET run_active=FALSE, last_win_date=%s,
                             wins_total=wins_total+1 WHERE user_id=%s""", today, user_id)
            champion = True
        else:
            execute(conn, "UPDATE tournament_runs SET current_round=%s, current_hp=%s WHERE user_id=%s",
                    rnd + 1, remaining_hp, user_id)
            champion = False
    if champion:
        gold = 1000
        add_gold(user_id, gold)
        try:
            from database import add_xp
            add_xp(user_id, 500)
        except Exception:
            pass
        # значок чемпиона
        try:
            from game.world_chat import give_badge, system_message
            give_badge(user_id, "champion")
        except Exception:
            pass
        # анонс в чат
        try:
            from database import get_user
            from game.world_chat import system_message
            u = get_user(user_id)
            nm = (u.get("wizard_name") if u else None) or "Игрок"
            system_message(f"🏆 {nm} побеждает в Турнире на выбывание и становится Чемпионом! 👑")
        except Exception:
            pass
        return {"ok": True, "champion": True, "gold": gold, "xp": 500}
    return {"ok": True, "champion": False, "nextRound": rnd + 1}


def run_failed(user_id):
    ensure_tournament_table()
    from database import get_conn, fetchrow, execute
    with get_conn() as conn:
        row = fetchrow(conn, "SELECT current_round FROM tournament_runs WHERE user_id=%s", user_id)
        reached = row["current_round"] if row else 1
        execute(conn, "UPDATE tournament_runs SET run_active=FALSE WHERE user_id=%s", user_id)
    return {"ok": True, "reached": reached}


def get_champions(limit=20):
    """Топ по числу побед в турнирах."""
    ensure_tournament_table()
    from database import get_conn, fetchall
    try:
        from config import ADMIN_IDS
    except Exception:
        ADMIN_IDS = []
    with get_conn() as conn:
        rows = fetchall(conn, """
            SELECT t.user_id, t.wins_total, u.wizard_name, u.house
            FROM tournament_runs t JOIN users u ON u.user_id = t.user_id
            WHERE t.wins_total > 0
            ORDER BY t.wins_total DESC LIMIT %s
        """, limit + len(ADMIN_IDS))
    out = []
    house_emoji = {"gryffindor":"🦁","slytherin":"🐍","ravenclaw":"🦅","hufflepuff":"🦡"}
    for r in rows:
        if r["user_id"] in ADMIN_IDS:
            continue
        out.append({"name": r["wizard_name"] or "Игрок", "wins": r["wins_total"],
                    "houseEmoji": house_emoji.get(r["house"], "")})
        if len(out) >= limit:
            break
    return out
