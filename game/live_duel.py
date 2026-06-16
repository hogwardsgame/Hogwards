"""
Живой PvP для магических дуэлей.

Два игрока ходят втайне одновременно, сервер сводит ходы и разыгрывает.
Матчмейкинг через очередь + приглашение по ID.

Состояние боя хранится в БД (таблица live_duels) как JSON.
Клиенты опрашивают сервер для синхронизации.
"""
import json
import time
import random

GRID = 5
TURN_TIMEOUT = 30  # секунд на ход — потом автопоражение

# Заклинания (синхронизировано с фронтом)
DUEL_SPELLS = {
    "fireball":   {"dmg": 24, "burn": 3},
    "lightning":  {"dmg": 18},
    "ice_chains": {"dmg": 20, "freeze": 2},
    "sun_ray":    {"dmg": 30},
    "dark_magic": {"dmg": 22, "burn": 2},
    "wind_blade": {"dmg": 20, "bigsplash": True},
}


def ensure_tables():
    from database import get_conn, execute
    with get_conn() as conn:
        execute(conn, """
            CREATE TABLE IF NOT EXISTS duel_queue (
                user_id BIGINT PRIMARY KEY,
                wizard_name TEXT,
                emoji TEXT DEFAULT '🧙',
                queued_at DOUBLE PRECISION,
                match_id TEXT
            )
        """)
        execute(conn, "ALTER TABLE duel_queue ADD COLUMN IF NOT EXISTS emoji TEXT DEFAULT '🧙'")
        execute(conn, """
            CREATE TABLE IF NOT EXISTS live_duels (
                match_id TEXT PRIMARY KEY,
                p1_id BIGINT, p2_id BIGINT,
                p1_name TEXT, p2_name TEXT,
                state TEXT,
                created_at DOUBLE PRECISION,
                updated_at DOUBLE PRECISION
            )
        """)


def _new_state(p1_id, p2_id, p1_name, p2_name, p1_emoji="🧙", p2_emoji="🧙‍♂️"):
    return {
        "p1": {"id": p1_id, "name": p1_name, "emoji": p1_emoji, "hp": 130, "maxHp": 130, "r": 4, "c": 2, "burn": 0, "frozen": 0, "move": None, "spell": None, "aim": None, "ready": False},
        "p2": {"id": p2_id, "name": p2_name, "emoji": p2_emoji, "hp": 130, "maxHp": 130, "r": 0, "c": 2, "burn": 0, "frozen": 0, "move": None, "spell": None, "aim": None, "ready": False},
        "turn": 1, "over": False, "winner": None, "log": "Бой начался!",
        "lastResolve": None, "turnStarted": time.time(),
    }


def _save(match_id, state):
    from database import get_conn, execute
    with get_conn() as conn:
        execute(conn, "UPDATE live_duels SET state=%s, updated_at=%s WHERE match_id=%s",
                json.dumps(state), time.time(), match_id)


def _load(match_id):
    from database import get_conn, fetchrow
    with get_conn() as conn:
        row = fetchrow(conn, "SELECT * FROM live_duels WHERE match_id=%s", match_id)
    if not row:
        return None
    return row


def find_or_queue(user_id, wizard_name, emoji="🧙"):
    """Поиск соперника. Возвращает {status: matched|waiting, matchId, side}."""
    ensure_tables()
    from database import get_conn, execute, fetchrow, fetchall
    now = time.time()
    with get_conn() as conn:
        # уже в матче?
        mine = fetchrow(conn, "SELECT match_id FROM duel_queue WHERE user_id=%s", user_id)
        if mine and mine["match_id"]:
            mid = mine["match_id"]
            duel = fetchrow(conn, "SELECT p1_id FROM live_duels WHERE match_id=%s", mid)
            if duel:
                execute(conn, "DELETE FROM duel_queue WHERE user_id=%s", user_id)
                side = "p1" if duel["p1_id"] == user_id else "p2"
                return {"status": "matched", "matchId": mid, "side": side}
        # чистим старые записи очереди (>60 сек)
        execute(conn, "DELETE FROM duel_queue WHERE queued_at < %s AND match_id IS NULL", now - 60)
        # ищем соперника в очереди (не себя, без матча)
        opp = fetchrow(conn, """SELECT user_id, wizard_name, emoji FROM duel_queue
                                WHERE user_id != %s AND match_id IS NULL
                                ORDER BY queued_at ASC LIMIT 1""", user_id)
        if opp:
            # создаём матч
            match_id = f"d{int(now)}_{random.randint(1000,9999)}"
            opp_id = opp["user_id"]
            opp_emoji = opp.get("emoji") or "🧙"
            state = _new_state(opp_id, user_id, opp["wizard_name"] or "Соперник", wizard_name or "Игрок", opp_emoji, emoji)
            execute(conn, """INSERT INTO live_duels (match_id, p1_id, p2_id, p1_name, p2_name, state, created_at, updated_at)
                             VALUES (%s,%s,%s,%s,%s,%s,%s,%s)""",
                    match_id, opp_id, user_id, opp["wizard_name"] or "Соперник", wizard_name or "Игрок",
                    json.dumps(state), now, now)
            # помечаем обоих
            execute(conn, "UPDATE duel_queue SET match_id=%s WHERE user_id=%s", match_id, opp_id)
            execute(conn, "DELETE FROM duel_queue WHERE user_id=%s", user_id)
            return {"status": "matched", "matchId": match_id, "side": "p2"}
        else:
            # встаём в очередь
            execute(conn, """INSERT INTO duel_queue (user_id, wizard_name, emoji, queued_at, match_id)
                             VALUES (%s,%s,%s,%s,NULL)
                             ON CONFLICT (user_id) DO UPDATE SET queued_at=%s, match_id=NULL, emoji=%s""",
                    user_id, wizard_name, emoji, now, now, emoji)
            return {"status": "waiting"}


def cancel_queue(user_id):
    ensure_tables()
    from database import get_conn, execute
    with get_conn() as conn:
        execute(conn, "DELETE FROM duel_queue WHERE user_id=%s AND match_id IS NULL", user_id)
    return {"ok": True}


def create_invite(user_id, wizard_name, emoji="🧙"):
    """Создать бой по приглашению. Возвращает matchId (код), которым делятся."""
    ensure_tables()
    from database import get_conn, execute
    now = time.time()
    match_id = f"inv{user_id % 100000}"  # код на основе ID, предсказуемый для друга
    state = _new_state(user_id, 0, wizard_name or "Хозяин", "Ожидание...", emoji, "🧙")
    with get_conn() as conn:
        execute(conn, "DELETE FROM live_duels WHERE match_id=%s", match_id)
        execute(conn, """INSERT INTO live_duels (match_id, p1_id, p2_id, p1_name, p2_name, state, created_at, updated_at)
                         VALUES (%s,%s,0,%s,%s,%s,%s,%s)""",
                match_id, user_id, wizard_name or "Хозяин", "Ожидание...", json.dumps(state), now, now)
    return {"matchId": match_id, "side": "p1"}


def join_invite(user_id, wizard_name, host_id, emoji="🧙"):
    """Присоединиться к бою друга по его ID."""
    ensure_tables()
    from database import get_conn, execute, fetchrow
    match_id = f"inv{int(host_id) % 100000}"
    with get_conn() as conn:
        duel = fetchrow(conn, "SELECT * FROM live_duels WHERE match_id=%s", match_id)
        if not duel:
            return {"status": "notfound"}
        state = json.loads(duel["state"])
        if state["p2"]["id"] and state["p2"]["id"] != 0 and state["p2"]["id"] != user_id:
            return {"status": "full"}
        state["p2"]["id"] = user_id
        state["p2"]["name"] = wizard_name or "Игрок"
        state["p2"]["emoji"] = emoji
        execute(conn, "UPDATE live_duels SET p2_id=%s, p2_name=%s, state=%s WHERE match_id=%s",
                user_id, wizard_name or "Игрок", json.dumps(state), match_id)
    return {"status": "matched", "matchId": match_id, "side": "p2"}


def submit_move(match_id, user_id, move, spell, aim):
    """Принять ход игрока. Если оба готовы — разыграть."""
    from database import get_conn, execute, fetchrow
    with get_conn() as conn:
        duel = fetchrow(conn, "SELECT * FROM live_duels WHERE match_id=%s", match_id)
        if not duel:
            return {"error": "notfound"}
        state = json.loads(duel["state"])
        if state["over"]:
            return {"ok": True, "state": state}
        side = "p1" if duel["p1_id"] == user_id else "p2"
        state[side]["move"] = move
        state[side]["spell"] = spell
        state[side]["aim"] = aim
        state[side]["ready"] = True
        # оба готовы?
        if state["p1"]["ready"] and state["p2"]["ready"]:
            state = _resolve_turn(state)
        execute(conn, "UPDATE live_duels SET state=%s, updated_at=%s WHERE match_id=%s",
                json.dumps(state), time.time(), match_id)
    return {"ok": True, "state": state}


def _moved(pos, move, steps=1):
    r, c = pos["r"], pos["c"]
    if move == "up": r -= steps
    elif move == "down": r += steps
    elif move == "left": c -= steps
    elif move == "right": c += steps
    r = max(0, min(GRID-1, r)); c = max(0, min(GRID-1, c))
    return r, c


def _splash(aim, big=False):
    out = []
    if big:
        for dr in (-1,0,1):
            for dc in (-1,0,1):
                if dr==0 and dc==0: continue
                out.append((aim["r"]+dr, aim["c"]+dc))
    else:
        out = [(aim["r"]-1,aim["c"]),(aim["r"]+1,aim["c"]),(aim["r"],aim["c"]-1),(aim["r"],aim["c"]+1)]
    return [(r,c) for r,c in out if 0<=r<GRID and 0<=c<GRID]


def _resolve_turn(state):
    p1, p2 = state["p1"], state["p2"]
    # движение (заморозка блокирует)
    if p1["frozen"] <= 0 and p1["move"]:
        p1["r"], p1["c"] = _moved(p1, p1["move"])
    if p2["frozen"] <= 0 and p2["move"]:
        p2["r"], p2["c"] = _moved(p2, p2["move"])
    # атаки одновременно
    logs = []
    for atk, dfn, label in [(p1, p2, p1["name"]), (p2, p1, p2["name"])]:
        if not atk["spell"] or not atk["aim"]:
            continue
        sp = DUEL_SPELLS.get(atk["spell"], {})
        aim = atk["aim"]
        dmg = 0; crit = False
        if aim["r"] == dfn["r"] and aim["c"] == dfn["c"]:
            dmg = int(sp.get("dmg", 0) * 1.5); crit = True
        else:
            if (dfn["r"], dfn["c"]) in _splash(aim, sp.get("bigsplash")):
                dmg = int(sp.get("dmg", 0) * 0.5)
        if dmg > 0:
            dfn["hp"] = max(0, dfn["hp"] - dmg)
            if sp.get("burn"): dfn["burn"] = max(dfn["burn"], sp["burn"])
            if sp.get("freeze"): dfn["frozen"] = max(dfn["frozen"], sp["freeze"])
            logs.append(f"{label}: {'КРИТ ' if crit else ''}-{dmg}")
        else:
            logs.append(f"{label}: мимо")
    # тик эффектов
    for f in (p1, p2):
        if f["burn"] > 0:
            f["hp"] = max(0, f["hp"] - 6); f["burn"] -= 1
        if f["frozen"] > 0:
            f["frozen"] -= 1
    # сброс готовности
    for f in (p1, p2):
        f["ready"] = False; f["move"] = None; f["spell"] = None; f["aim"] = None
    state["turn"] += 1
    state["turnStarted"] = time.time()
    state["log"] = " • ".join(logs) if logs else "Ходы разыграны"
    state["lastResolve"] = time.time()
    # проверка победы
    if p1["hp"] <= 0 or p2["hp"] <= 0:
        state["over"] = True
        if p1["hp"] <= 0 and p2["hp"] <= 0:
            state["winner"] = 0  # ничья
        elif p2["hp"] <= 0:
            state["winner"] = p1["id"]
        else:
            state["winner"] = p2["id"]
    return state


def get_match_state(match_id, user_id):
    """Получить текущее состояние боя для игрока."""
    from database import get_conn, fetchrow, execute
    with get_conn() as conn:
        duel = fetchrow(conn, "SELECT * FROM live_duels WHERE match_id=%s", match_id)
        if not duel:
            return {"error": "notfound"}
        state = json.loads(duel["state"])
        # авто-поражение: если игрок не сходил за TURN_TIMEOUT — ему засчитывается поражение
        if not state["over"] and state["p2"]["id"] and (time.time() - state.get("turnStarted", 0)) > TURN_TIMEOUT:
            p1_ready = state["p1"]["ready"]
            p2_ready = state["p2"]["ready"]
            # тот, кто НЕ готов — проигрывает (если оба не готовы — ничья)
            if not p1_ready and not p2_ready:
                state["over"] = True
                state["winner"] = 0
                state["log"] = "Оба игрока неактивны — ничья"
            elif not p1_ready:
                state["over"] = True
                state["winner"] = state["p2"]["id"]
                state["log"] = "Соперник неактивен — победа!"
            elif not p2_ready:
                state["over"] = True
                state["winner"] = state["p1"]["id"]
                state["log"] = "Соперник неактивен — победа!"
            execute(conn, "UPDATE live_duels SET state=%s WHERE match_id=%s", json.dumps(state), match_id)
    side = "p1" if duel["p1_id"] == user_id else "p2"
    return {"ok": True, "state": state, "side": side,
            "bothJoined": bool(state["p2"]["id"] and state["p2"]["id"] != 0)}
