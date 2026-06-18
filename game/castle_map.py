"""
Замок — рогалик-данж в стиле Shattered Pixel Dungeon.

Многоэтажное подземелье: спускаешься по лестнице всё глубже.
На карте монстры (бой прямо на месте), сундуки, ловушки.
Чем глубже этаж — тем сильнее монстры и лучше лут.
HP переносится между этажами. Цель — спуститься как можно глубже.
"""
import random
import json
import time

SIZE = 13

EMPTY = 0
WALL = 1
LOOT = 2
TRAP = 3
STAIRS = 4
START = 5
EVENT_PRIZE = 6
GRASS = 7
DOOR = 8

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

# Боссы для каждого 10-го этажа (по глубине)
BOSSES = [
    {"name": "Тёмный рыцарь", "emoji": "🛡️", "hp": 200, "dmg": 25},
    {"name": "Король скелетов", "emoji": "👑", "hp": 280, "dmg": 30},
    {"name": "Древний дракон", "emoji": "🐉", "hp": 380, "dmg": 36},
    {"name": "Повелитель тьмы", "emoji": "💀", "hp": 500, "dmg": 42},
    {"name": "Владыка бездны", "emoji": "👁️", "hp": 650, "dmg": 50},
]

LOOT_TABLE = [
    ("gold_small",   {"type": "gold", "amount": 40, "name": "40 золота", "emoji": "💰"}, 28),
    ("gold_medium",  {"type": "gold", "amount": 100, "name": "100 золота", "emoji": "💰"}, 16),
    ("gold_large",   {"type": "gold", "amount": 220, "name": "220 золота", "emoji": "💰"}, 7),
    ("hp_potion_small",  {"type": "item", "item": "hp_potion_small", "name": "Малое зелье HP", "emoji": "🧪"}, 14),
    ("hp_potion_medium", {"type": "item", "item": "hp_potion_medium", "name": "Среднее зелье HP", "emoji": "🧪"}, 9),
    ("hp_heal", {"type": "heal", "amount": 30, "name": "Лечебное зелье (+30 HP)", "emoji": "❤️"}, 12),
    ("phoenix_feather",  {"type": "item", "item": "phoenix_feather", "name": "Перо феникса", "emoji": "🪶"}, 4),
    ("dragon_heartstring", {"type": "item", "item": "dragon_heartstring", "name": "Струна дракона", "emoji": "🐉"}, 3),
    ("unicorn_hair",     {"type": "item", "item": "unicorn_hair", "name": "Волос единорога", "emoji": "🦄"}, 3),
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
    size = SIZE
    grid = [[WALL for _ in range(size)] for _ in range(size)]
    sr, sc = size - 2, size // 2
    visited = set()
    stack = [(sr, sc)]
    grid[sr][sc] = EMPTY
    visited.add((sr, sc))
    while stack:
        r, c = stack[-1]
        neighbors = []
        for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
            nr, nc = r + dr, c + dc
            if 1 <= nr < size - 1 and 1 <= nc < size - 1 and (nr, nc) not in visited:
                neighbors.append((nr, nc))
        if neighbors:
            nr, nc = random.choice(neighbors)
            grid[nr][nc] = EMPTY
            visited.add((nr, nc))
            stack.append((nr, nc))
        else:
            stack.pop()
    for r in range(1, size - 1):
        for c in range(1, size - 1):
            if grid[r][c] == WALL and random.random() < 0.10:
                grid[r][c] = EMPTY
    # вырезаем несколько открытых комнат (как в рогалике)
    n_rooms = random.randint(2, 4)
    for _ in range(n_rooms):
        rh = random.randint(2, 3); rw = random.randint(2, 3)
        rr = random.randint(1, size - rh - 1); rc = random.randint(1, size - rw - 1)
        for r in range(rr, rr + rh):
            for c in range(rc, rc + rw):
                grid[r][c] = EMPTY
                visited.add((r, c))
    grid[sr][sc] = START
    free = [(r, c) for (r, c) in visited if grid[r][c] in (EMPTY, GRASS) and (r, c) != (sr, sc)]
    free.sort(key=lambda p: -((p[0] - sr) ** 2 + (p[1] - sc) ** 2))
    stairs = free[0]
    grid[stairs[0]][stairs[1]] = STAIRS
    free = free[1:]
    random.shuffle(free)
    idx = 0
    is_boss_floor = (depth % 10 == 0)
    monsters = {}
    if is_boss_floor:
        # один мощный босс на этаже
        bidx = min(len(BOSSES) - 1, depth // 10 - 1)
        b = BOSSES[bidx]
        hp = int(b["hp"] * (1 + (depth // 10 - 1) * 0.3))
        dmg = int(b["dmg"] * (1 + (depth // 10 - 1) * 0.2))
        if free:
            r, c = free[idx]; idx += 1
            monsters[f"{r},{c}"] = {"name": b["name"], "emoji": b["emoji"], "hp": hp, "maxHp": hp, "dmg": dmg, "isBoss": True}
    else:
        # формула: 1-4 этаж = 2-3 монстра, с 5-го +1, дальше каждые 4 этажа +1
        base = 2 + random.randint(0, 1)            # 2-3 на старте
        bonus = 0
        if depth >= 5:
            bonus = 1 + max(0, (depth - 5) // 4)   # +1 с 5-го, далее каждые 4 этажа +1
        n_monsters = min(len(free), base + bonus)
        for _ in range(n_monsters):
            if idx >= len(free):
                break
            r, c = free[idx]; idx += 1
            mtype = MONSTERS[min(len(MONSTERS) - 1, (depth - 1) // 2 + random.randint(0, 2))]
            hp = int(mtype["hp"] * (1 + depth * 0.15))
            dmg = int(mtype["dmg"] * (1 + depth * 0.1))
            monsters[f"{r},{c}"] = {"name": mtype["name"], "emoji": mtype["emoji"], "hp": hp, "maxHp": hp, "dmg": dmg}
    loot_cells = {}
    n_loot = min(max(0, len(free) - idx), 3 + depth // 3 + random.randint(0, 2))
    for _ in range(n_loot):
        if idx >= len(free):
            break
        r, c = free[idx]; idx += 1
        grid[r][c] = LOOT
        loot_cells[f"{r},{c}"] = _roll_loot()
    n_trap = min(max(0, len(free) - idx), 2 + depth // 4)
    for _ in range(n_trap):
        if idx >= len(free):
            break
        r, c = free[idx]; idx += 1
        grid[r][c] = TRAP
    return grid, sr, sc, loot_cells, monsters, stairs


def ensure_castle_table():
    from database import get_conn, execute
    with get_conn() as conn:
        execute(conn, """
            CREATE TABLE IF NOT EXISTS castle_runs (
                user_id BIGINT PRIMARY KEY,
                state TEXT,
                started_at DOUBLE PRECISION
            )
        """)


def _build_state(depth, hp, max_hp, gold_found=0, items_found=None, atk=12):
    grid, sr, sc, loot_cells, monsters, stairs = _gen_floor(depth)
    event_cell = None
    try:
        from game.castle_event import get_active_event
        ev = get_active_event()
        if ev and ev.get("prizeFloor", 1) == depth:
            free = [(r, c) for r in range(1, SIZE - 1) for c in range(1, SIZE - 1)
                    if grid[r][c] in (EMPTY, GRASS) and not (r == sr and c == sc)]
            if free:
                er, ec = random.choice(free)
                grid[er][ec] = EVENT_PRIZE
                event_cell = f"{er},{ec}"
    except Exception:
        pass
    return {
        "grid": grid, "pr": sr, "pc": sc, "size": SIZE, "depth": depth,
        "loot": loot_cells, "monsters": monsters, "collected": [], "trapsSprung": [],
        "hp": hp, "maxHp": max_hp, "atk": atk,
        "gold_found": gold_found, "items_found": items_found or [],
        "done": False, "moves": 0, "eventCell": event_cell,
    }


def new_run(user_id: int):
    ensure_castle_table()
    from database import get_conn, execute, get_user
    user = get_user(user_id)
    max_hp = 100
    atk = 12
    try:
        if user:
            atk = 8 + int((user.get("attack", 10) or 10) * 0.4)
            mh = user.get("max_hp", 100) or 100
            max_hp = 100 + int(max(0, mh - 100) * 0.3)
    except Exception:
        pass
    state = _build_state(1, max_hp, max_hp, atk=atk)
    with get_conn() as conn:
        execute(conn, """INSERT INTO castle_runs (user_id, state, started_at) VALUES (%s,%s,%s)
                         ON CONFLICT (user_id) DO UPDATE SET state=%s, started_at=%s""",
                user_id, json.dumps(state), time.time(), json.dumps(state), time.time())
    return _client_state(state)


def _client_state(state):
    size = state["size"]
    vis = []
    for r in range(size):
        row = []
        for c in range(size):
            key = f"{r},{c}"
            cell = state["grid"][r][c]
            if key in state["collected"] and cell == LOOT:
                cell = EMPTY
            row.append(cell)
        vis.append(row)
    mons = []
    for key, m in state.get("monsters", {}).items():
        rr, cc = key.split(",")
        mons.append({"r": int(rr), "c": int(cc), "emoji": m["emoji"],
                     "name": m["name"], "hp": m["hp"], "maxHp": m["maxHp"]})
    return {
        "grid": vis, "pr": state["pr"], "pc": state["pc"], "size": size,
        "hp": state["hp"], "maxHp": state["maxHp"], "depth": state["depth"],
        "goldFound": state["gold_found"], "monsters": mons,
        "itemsFound": state["items_found"], "done": state["done"], "moves": state["moves"],
    }


def move(user_id: int, direction: str):
    ensure_castle_table()
    from database import get_conn, fetchrow, execute
    with get_conn() as conn:
        row = fetchrow(conn, "SELECT state FROM castle_runs WHERE user_id=%s", user_id)
        if not row:
            return {"error": "norun"}
        state = json.loads(row["state"])
        if state.get("done"):
            return {"event": "done", **_client_state(state)}
        size = state["size"]
        r, c = state["pr"], state["pc"]
        nr, nc = r, c
        if direction == "up": nr -= 1
        elif direction == "down": nr += 1
        elif direction == "left": nc -= 1
        elif direction == "right": nc += 1
        if not (0 <= nr < size and 0 <= nc < size) or state["grid"][nr][nc] == WALL:
            return {"event": "wall", **_client_state(state)}

        event = {"event": "move"}
        key = f"{nr},{nc}"
        monsters = state.get("monsters", {})
        if key in monsters:
            # встреча с монстром → магдуэль (бой в отдельном оверлее)
            m = monsters[key]
            out = _client_state(state)
            out["event"] = "encounter"
            out["monster"] = {
                "key": key, "name": m["name"], "emoji": m["emoji"],
                "hp": m["maxHp"], "dmg": m.get("dmg", 12),
                "isBoss": m.get("isBoss", False), "depth": state["depth"],
            }
            return out

        state["pr"], state["pc"] = nr, nc
        state["moves"] += 1
        cell = state["grid"][nr][nc]

        if cell == LOOT and key not in state["collected"]:
            state["collected"].append(key)
            loot = state["loot"].get(key)
            if loot:
                if loot["type"] == "gold":
                    state["gold_found"] += loot["amount"]
                    _give_gold(user_id, loot["amount"])
                    event = {"event": "loot", "loot": loot}
                elif loot["type"] == "heal":
                    state["hp"] = min(state["maxHp"], state["hp"] + loot["amount"])
                    event = {"event": "loot", "loot": loot}
                else:
                    _give_item(user_id, loot["item"], 1)
                    state["items_found"].append({"name": loot["name"], "emoji": loot["emoji"]})
                    event = {"event": "loot", "loot": loot}
        elif cell == TRAP and key not in state["trapsSprung"]:
            state["trapsSprung"].append(key)
            dmg = random.randint(8, 16) + state["depth"] * 2
            state["hp"] = max(0, state["hp"] - dmg)
            event = {"event": "trap", "damage": dmg}
            if state["hp"] <= 0:
                state["done"] = True
                event = {"event": "dead", "damage": dmg}
        elif cell == STAIRS:
            # нельзя спуститься, пока на этаже есть монстры
            if state.get("monsters"):
                state["pr"], state["pc"] = nr, nc
                execute(conn, "UPDATE castle_runs SET state=%s WHERE user_id=%s", json.dumps(state), user_id)
                out = _client_state(state)
                out["event"] = "stairsBlocked"
                out["monstersLeft"] = len(state["monsters"])
                return out
            depth = state["depth"] + 1
            bonus = 50 + depth * 20
            _give_gold(user_id, bonus)
            new_state = _build_state(depth, state["hp"], state["maxHp"],
                                     gold_found=state["gold_found"] + bonus,
                                     items_found=state["items_found"], atk=state.get("atk", 12))
            execute(conn, "UPDATE castle_runs SET state=%s WHERE user_id=%s", json.dumps(new_state), user_id)
            out = _client_state(new_state)
            out["event"] = "descend"
            out["depth"] = depth
            out["bonus"] = bonus
            return out
        elif cell == EVENT_PRIZE and key == state.get("eventCell"):
            try:
                from game.castle_event import claim_prize
                urow = fetchrow(conn, "SELECT wizard_name FROM users WHERE user_id=%s", user_id)
                uname = (urow["wizard_name"] if urow else None) or "Игрок"
                res = claim_prize(user_id, uname)
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


def win_fight(user_id: int, key: str):
    """Победа в дуэли над монстром: убираем его, игрок занимает клетку."""
    ensure_castle_table()
    from database import get_conn, fetchrow, execute
    with get_conn() as conn:
        row = fetchrow(conn, "SELECT state FROM castle_runs WHERE user_id=%s", user_id)
        if not row:
            return {"error": "norun"}
        state = json.loads(row["state"])
        monsters = state.get("monsters", {})
        was_boss = False
        if key in monsters:
            was_boss = monsters[key].get("isBoss", False)
            try:
                rr, cc = key.split(",")
                state["pr"], state["pc"] = int(rr), int(cc)
            except Exception:
                pass
            del monsters[key]
            state["monsters"] = monsters
            state["moves"] += 1
        # награда за убийство (золото)
        reward = 20 + state["depth"] * 8
        if was_boss:
            reward = 200 + state["depth"] * 25
        _give_gold(user_id, reward)
        state["gold_found"] += reward
        execute(conn, "UPDATE castle_runs SET state=%s WHERE user_id=%s", json.dumps(state), user_id)
    out = _client_state(state)
    out["event"] = "kill"
    out["reward"] = reward
    out["wasBoss"] = was_boss
    return out


def lose_fight(user_id: int):
    """Поражение в дуэли — конец забега."""
    ensure_castle_table()
    from database import get_conn, fetchrow, execute
    with get_conn() as conn:
        row = fetchrow(conn, "SELECT state FROM castle_runs WHERE user_id=%s", user_id)
        if not row:
            return {"error": "norun"}
        state = json.loads(row["state"])
        state["done"] = True
        execute(conn, "UPDATE castle_runs SET state=%s WHERE user_id=%s", json.dumps(state), user_id)
    out = _client_state(state)
    out["event"] = "dead"
    return out


def get_run(user_id: int):
    ensure_castle_table()
    from database import get_conn, fetchrow
    with get_conn() as conn:
        row = fetchrow(conn, "SELECT state FROM castle_runs WHERE user_id=%s", user_id)
    if not row:
        return None
    return _client_state(json.loads(row["state"]))


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
