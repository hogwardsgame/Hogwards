"""
Замок — рогалик-данж. Чистая версия.
Карта 11x11, вся на экране. Туман войны. Бой через магдуэль.
"""
import random
import json
import time

SIZE = 11
EMPTY = 0
WALL = 1
LOOT = 2
TRAP = 3
STAIRS = 4
START = 5
EVENT_PRIZE = 6

MONSTERS = [
    {"name": "Крыса", "emoji": "🐀", "hp": 20, "dmg": 5},
    {"name": "Гоблин", "emoji": "👺", "hp": 30, "dmg": 8},
    {"name": "Скелет", "emoji": "💀", "hp": 40, "dmg": 11},
    {"name": "Слизень", "emoji": "🟢", "hp": 50, "dmg": 9},
    {"name": "Летучая мышь", "emoji": "🦇", "hp": 35, "dmg": 13},
    {"name": "Паук", "emoji": "🕷️", "hp": 45, "dmg": 12},
    {"name": "Призрак", "emoji": "👻", "hp": 55, "dmg": 15},
    {"name": "Орк", "emoji": "👹", "hp": 70, "dmg": 18},
    {"name": "Голем", "emoji": "🗿", "hp": 100, "dmg": 16},
    {"name": "Демон", "emoji": "😈", "hp": 90, "dmg": 22},
]
BOSSES = [
    {"name": "Тёмный рыцарь", "emoji": "🛡️", "hp": 200, "dmg": 25},
    {"name": "Король скелетов", "emoji": "👑", "hp": 280, "dmg": 30},
    {"name": "Древний дракон", "emoji": "🐉", "hp": 380, "dmg": 36},
    {"name": "Повелитель тьмы", "emoji": "💀", "hp": 500, "dmg": 42},
    {"name": "Владыка бездны", "emoji": "👁️", "hp": 650, "dmg": 50},
]

LOOT_TABLE = [
    ("g1", {"type": "gold", "amount": 40, "name": "40 золота", "emoji": "💰"}, 28),
    ("g2", {"type": "gold", "amount": 100, "name": "100 золота", "emoji": "💰"}, 16),
    ("g3", {"type": "gold", "amount": 220, "name": "220 золота", "emoji": "💰"}, 7),
    ("p1", {"type": "item", "item": "hp_potion_small", "name": "Малое зелье HP", "emoji": "🧪"}, 14),
    ("p2", {"type": "item", "item": "hp_potion_medium", "name": "Среднее зелье HP", "emoji": "🧪"}, 9),
    ("h1", {"type": "heal", "amount": 30, "name": "Лечебное зелье", "emoji": "❤️"}, 12),
    ("c1", {"type": "item", "item": "phoenix_feather", "name": "Перо феникса", "emoji": "🪶"}, 4),
    ("c2", {"type": "item", "item": "dragon_heartstring", "name": "Струна дракона", "emoji": "🐉"}, 3),
    ("c3", {"type": "item", "item": "unicorn_hair", "name": "Волос единорога", "emoji": "🦄"}, 3),
]


def _roll_loot():
    total = sum(w for _, _, w in LOOT_TABLE)
    roll = random.uniform(0, total)
    acc = 0
    for lid, data, w in LOOT_TABLE:
        acc += w
        if roll <= acc:
            return dict(data)
    return dict(LOOT_TABLE[0][1])


def _gen_floor(depth):
    """Лабиринт на толстых стенах (recursive backtracker, шаг 2)."""
    size = SIZE
    grid = [[WALL] * size for _ in range(size)]
    # стартовая ячейка (нечётная)
    sr, sc = size - 2, size // 2
    if sr % 2 == 0: sr -= 1
    if sc % 2 == 0: sc -= 1
    visited = set()
    stack = [(sr, sc)]
    grid[sr][sc] = EMPTY
    visited.add((sr, sc))
    while stack:
        r, c = stack[-1]
        nb = []
        for dr, dc in [(-2, 0), (2, 0), (0, -2), (0, 2)]:
            nr, nc = r + dr, c + dc
            if 1 <= nr < size - 1 and 1 <= nc < size - 1 and (nr, nc) not in visited:
                nb.append((nr, nc, dr, dc))
        if nb:
            nr, nc, dr, dc = random.choice(nb)
            grid[r + dr // 2][c + dc // 2] = EMPTY
            grid[nr][nc] = EMPTY
            visited.add((nr, nc))
            stack.append((nr, nc))
        else:
            stack.pop()
    # немного петель
    for r in range(1, size - 1):
        for c in range(1, size - 1):
            if grid[r][c] == WALL and random.random() < 0.10:
                if (grid[r-1][c] == EMPTY and grid[r+1][c] == EMPTY) or (grid[r][c-1] == EMPTY and grid[r][c+1] == EMPTY):
                    grid[r][c] = EMPTY
                    visited.add((r, c))
    grid[sr][sc] = START
    free = [(r, c) for (r, c) in visited if grid[r][c] == EMPTY and (r, c) != (sr, sc)]
    free.sort(key=lambda p: -((p[0] - sr) ** 2 + (p[1] - sc) ** 2))
    stairs = free[0] if free else (1, 1)
    grid[stairs[0]][stairs[1]] = STAIRS
    free = free[1:]
    random.shuffle(free)
    idx = 0
    monsters = {}
    is_boss = (depth % 10 == 0)
    if is_boss:
        b = BOSSES[min(len(BOSSES) - 1, depth // 10 - 1)]
        hp = int(b["hp"] * (1 + (depth // 10 - 1) * 0.3))
        dmg = int(b["dmg"] * (1 + (depth // 10 - 1) * 0.2))
        if idx < len(free):
            r, c = free[idx]; idx += 1
            monsters[f"{r},{c}"] = {"name": b["name"], "emoji": b["emoji"], "hp": hp, "maxHp": hp, "dmg": dmg, "isBoss": True}
    else:
        n = 2 + random.randint(0, 1)
        if depth >= 5:
            n += 1 + max(0, (depth - 5) // 4)
        for _ in range(min(n, len(free))):
            if idx >= len(free): break
            r, c = free[idx]; idx += 1
            mt = MONSTERS[min(len(MONSTERS) - 1, (depth - 1) // 2 + random.randint(0, 2))]
            hp = int(mt["hp"] * (1 + depth * 0.15))
            dmg = int(mt["dmg"] * (1 + depth * 0.1))
            monsters[f"{r},{c}"] = {"name": mt["name"], "emoji": mt["emoji"], "hp": hp, "maxHp": hp, "dmg": dmg}
    loot = {}
    nl = min(max(0, len(free) - idx), 3 + depth // 3 + random.randint(0, 2))
    for _ in range(nl):
        if idx >= len(free): break
        r, c = free[idx]; idx += 1
        grid[r][c] = LOOT
        loot[f"{r},{c}"] = _roll_loot()
    nt = min(max(0, len(free) - idx), 2 + depth // 4)
    for _ in range(nt):
        if idx >= len(free): break
        r, c = free[idx]; idx += 1
        grid[r][c] = TRAP
    return grid, sr, sc, loot, monsters


def ensure_castle_table():
    from database import get_conn, execute
    with get_conn() as conn:
        execute(conn, """CREATE TABLE IF NOT EXISTS castle_runs (
            user_id BIGINT PRIMARY KEY, state TEXT, started_at DOUBLE PRECISION)""")


def _reveal(state, r, c, radius=3):
    explored = set(state.get("explored", []))
    size = state["size"]
    for dr in range(-radius, radius + 1):
        for dc in range(-radius, radius + 1):
            if abs(dr) + abs(dc) <= radius + 1:
                rr, cc = r + dr, c + dc
                if 0 <= rr < size and 0 <= cc < size:
                    explored.add(f"{rr},{cc}")
    state["explored"] = list(explored)


def _build_state(depth, max_hp, gold_found=0, items_found=None, atk=12):
    grid, sr, sc, loot, monsters = _gen_floor(depth)
    event_cell = None
    try:
        from game.castle_event import get_active_event
        ev = get_active_event()
        if ev and ev.get("prizeFloor", 1) == depth:
            cands = [(r, c) for r in range(1, SIZE-1) for c in range(1, SIZE-1)
                     if grid[r][c] == EMPTY and not (r == sr and c == sc)]
            if cands:
                er, ec = random.choice(cands)
                grid[er][ec] = EVENT_PRIZE
                event_cell = f"{er},{ec}"
    except Exception:
        pass
    state = {
        "grid": grid, "pr": sr, "pc": sc, "size": SIZE, "depth": depth,
        "loot": loot, "monsters": monsters, "collected": [], "trapsSprung": [],
        "maxHp": max_hp, "atk": atk, "gold_found": gold_found,
        "items_found": items_found or [], "done": False, "eventCell": event_cell,
        "explored": [],
    }
    _reveal(state, sr, sc)
    return state


def new_run(user_id):
    ensure_castle_table()
    from database import get_conn, execute, get_user
    user = get_user(user_id)
    max_hp = 100
    try:
        if user:
            mh = user.get("max_hp", 100) or 100
            max_hp = 100 + int(max(0, mh - 100) * 0.3)
    except Exception:
        pass
    state = _build_state(1, max_hp)
    with get_conn() as conn:
        execute(conn, """INSERT INTO castle_runs (user_id, state, started_at) VALUES (%s,%s,%s)
                 ON CONFLICT (user_id) DO UPDATE SET state=%s, started_at=%s""",
                user_id, json.dumps(state), time.time(), json.dumps(state), time.time())
    return _client_state(state)


def _client_state(state):
    size = state["size"]
    explored = set(state.get("explored", []))
    vis = []
    for r in range(size):
        rowv = []
        for c in range(size):
            key = f"{r},{c}"
            if explored and key not in explored:
                rowv.append(-1)
                continue
            cell = state["grid"][r][c]
            if key in state["collected"] and cell == LOOT:
                cell = EMPTY
            rowv.append(cell)
        vis.append(rowv)
    mons = []
    for key, m in state.get("monsters", {}).items():
        if explored and key not in explored:
            continue
        rr, cc = key.split(",")
        mons.append({"r": int(rr), "c": int(cc), "emoji": m["emoji"], "name": m["name"]})
    return {
        "grid": vis, "pr": state["pr"], "pc": state["pc"], "size": size,
        "depth": state["depth"], "goldFound": state["gold_found"],
        "monsters": mons, "monstersTotal": len(state.get("monsters", {})),
        "itemsFound": state["items_found"], "done": state["done"],
    }


def move(user_id, direction):
    ensure_castle_table()
    from database import get_conn, fetchrow, execute
    with get_conn() as conn:
        row = fetchrow(conn, "SELECT state FROM castle_runs WHERE user_id=%s", user_id)
        if not row:
            return {"error": "norun"}
        state = json.loads(row["state"])
        # совместимость: старый забег другого размера → новый
        if state.get("size") != SIZE:
            state = _build_state(1, state.get("maxHp", 100))
            execute(conn, "UPDATE castle_runs SET state=%s WHERE user_id=%s", json.dumps(state), user_id)
            out = _client_state(state)
            out["event"] = "move"
            return out
        if state.get("done"):
            out = _client_state(state); out["event"] = "done"; return out
        size = state["size"]
        r, c = state["pr"], state["pc"]
        nr, nc = r, c
        if direction == "up": nr -= 1
        elif direction == "down": nr += 1
        elif direction == "left": nc -= 1
        elif direction == "right": nc += 1
        # граница или стена
        if not (0 <= nr < size and 0 <= nc < size) or state["grid"][nr][nc] == WALL:
            out = _client_state(state); out["event"] = "wall"; return out
        key = f"{nr},{nc}"
        # монстр → дуэль
        monsters = state.get("monsters", {})
        if key in monsters:
            m = monsters[key]
            out = _client_state(state)
            out["event"] = "encounter"
            out["monster"] = {"key": key, "name": m["name"], "emoji": m["emoji"],
                              "hp": m["maxHp"], "dmg": m.get("dmg", 12),
                              "isBoss": m.get("isBoss", False), "depth": state["depth"]}
            return out
        # двигаемся
        state["pr"], state["pc"] = nr, nc
        _reveal(state, nr, nc)
        cell = state["grid"][nr][nc]
        event = {"event": "move"}
        if cell == LOOT and key not in state["collected"]:
            state["collected"].append(key)
            lt = state["loot"].get(key)
            if lt:
                if lt["type"] == "gold":
                    state["gold_found"] += lt["amount"]; _give_gold(user_id, lt["amount"])
                elif lt["type"] == "heal":
                    pass
                else:
                    _give_item(user_id, lt["item"], 1)
                    state["items_found"].append({"name": lt["name"], "emoji": lt["emoji"]})
                event = {"event": "loot", "loot": lt}
        elif cell == TRAP and key not in state["trapsSprung"]:
            state["trapsSprung"].append(key)
            event = {"event": "trap", "damage": 0}
        elif cell == STAIRS:
            if state.get("monsters"):
                execute(conn, "UPDATE castle_runs SET state=%s WHERE user_id=%s", json.dumps(state), user_id)
                out = _client_state(state); out["event"] = "stairsBlocked"
                out["monstersLeft"] = len(state["monsters"]); return out
            depth = state["depth"] + 1
            bonus = 50 + depth * 20
            _give_gold(user_id, bonus)
            ns = _build_state(depth, state["maxHp"], state["gold_found"] + bonus, state["items_found"], state.get("atk", 12))
            execute(conn, "UPDATE castle_runs SET state=%s WHERE user_id=%s", json.dumps(ns), user_id)
            out = _client_state(ns); out["event"] = "descend"; out["depth"] = depth; out["bonus"] = bonus
            return out
        elif cell == EVENT_PRIZE and key == state.get("eventCell"):
            try:
                from game.castle_event import claim_prize
                ur = fetchrow(conn, "SELECT wizard_name FROM users WHERE user_id=%s", user_id)
                un = (ur["wizard_name"] if ur else None) or "Игрок"
                res = claim_prize(user_id, un)
                state["grid"][nr][nc] = EMPTY
                if res.get("won"):
                    event = {"event": "eventWin", "prize": {"name": res["prizeName"], "emoji": res["prizeEmoji"], "qty": res["prizeQty"]}}
                else:
                    event = {"event": "eventTaken"}
            except Exception:
                event = {"event": "move"}
        execute(conn, "UPDATE castle_runs SET state=%s WHERE user_id=%s", json.dumps(state), user_id)
    out = _client_state(state)
    out.update(event)
    return out


def win_fight(user_id, key):
    ensure_castle_table()
    from database import get_conn, fetchrow, execute
    with get_conn() as conn:
        row = fetchrow(conn, "SELECT state FROM castle_runs WHERE user_id=%s", user_id)
        if not row: return {"error": "norun"}
        state = json.loads(row["state"])
        monsters = state.get("monsters", {})
        was_boss = False
        if key in monsters:
            was_boss = monsters[key].get("isBoss", False)
            rr, cc = key.split(",")
            state["pr"], state["pc"] = int(rr), int(cc)
            _reveal(state, int(rr), int(cc))
            del monsters[key]
            state["monsters"] = monsters
        reward = (200 + state["depth"] * 25) if was_boss else (20 + state["depth"] * 8)
        _give_gold(user_id, reward)
        state["gold_found"] += reward
        execute(conn, "UPDATE castle_runs SET state=%s WHERE user_id=%s", json.dumps(state), user_id)
    out = _client_state(state)
    out["event"] = "kill"; out["reward"] = reward; out["wasBoss"] = was_boss
    return out


def lose_fight(user_id):
    ensure_castle_table()
    from database import get_conn, fetchrow, execute
    with get_conn() as conn:
        row = fetchrow(conn, "SELECT state FROM castle_runs WHERE user_id=%s", user_id)
        if not row: return {"error": "norun"}
        state = json.loads(row["state"])
        state["done"] = True
        execute(conn, "UPDATE castle_runs SET state=%s WHERE user_id=%s", json.dumps(state), user_id)
    out = _client_state(state); out["event"] = "dead"
    return out


def get_run(user_id):
    ensure_castle_table()
    from database import get_conn, fetchrow
    with get_conn() as conn:
        row = fetchrow(conn, "SELECT state FROM castle_runs WHERE user_id=%s", user_id)
    if not row: return None
    st = json.loads(row["state"])
    if st.get("size") != SIZE:
        return None
    return _client_state(st)


def _give_gold(user_id, amount):
    try:
        from database import add_gold
        add_gold(user_id, amount)
    except Exception:
        pass


def _give_item(user_id, item_id, qty):
    try:
        from database import add_item_to_inventory
        add_item_to_inventory(user_id, item_id, qty)
    except Exception:
        pass
