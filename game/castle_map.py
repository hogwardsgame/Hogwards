"""
Карта-замок: исследование лабиринта с видом сверху.

Игрок ходит стрелочками по сетке. Стены, тупики, ловушки,
скрытые комнаты с лутом (золото, ингредиенты, сердцевины палочек).

Карта генерируется случайно при входе. За проход — награды.
В будущем: ивент-поиск конкретного предмета (админ запускает).
"""
import random
import json
import time

SIZE = 9  # размер лабиринта

# Типы клеток
EMPTY = 0
WALL = 1
LOOT = 2      # сундук с предметом
TRAP = 3      # ловушка
EXIT = 4      # выход (бонус за прохождение)
START = 5

# Лут, который можно найти (id, шанс-вес)
LOOT_TABLE = [
    ("gold_small",   {"type": "gold", "amount": 50, "name": "50 золота", "emoji": "💰"}, 30),
    ("gold_medium",  {"type": "gold", "amount": 120, "name": "120 золота", "emoji": "💰"}, 18),
    ("gold_large",   {"type": "gold", "amount": 250, "name": "250 золота", "emoji": "💰"}, 8),
    ("hp_potion_small",  {"type": "item", "item": "hp_potion_small", "name": "Малое зелье HP", "emoji": "🧪"}, 15),
    ("hp_potion_medium", {"type": "item", "item": "hp_potion_medium", "name": "Среднее зелье HP", "emoji": "🧪"}, 8),
    ("phoenix_feather",  {"type": "item", "item": "phoenix_feather", "name": "Перо феникса (сердцевина)", "emoji": "🪶"}, 5),
    ("dragon_heartstring", {"type": "item", "item": "dragon_heartstring", "name": "Струна дракона (сердцевина)", "emoji": "🐉"}, 4),
    ("unicorn_hair",     {"type": "item", "item": "unicorn_hair", "name": "Волос единорога (сердцевина)", "emoji": "🦄"}, 4),
]


def _gen_maze(size, n_loot=5, n_trap=4):
    """Генерирует лабиринт: стены по краям + случайные внутри, лут и ловушки."""
    grid = [[EMPTY for _ in range(size)] for _ in range(size)]
    # рамка-стены
    for i in range(size):
        grid[0][i] = WALL; grid[size-1][i] = WALL
        grid[i][0] = WALL; grid[i][size-1] = WALL
    # случайные внутренние стены (~22%)
    for r in range(2, size-1):
        for c in range(1, size-1):
            if random.random() < 0.22:
                grid[r][c] = WALL
    # старт — низ-центр (всегда свободен)
    sr, sc = size-2, size//2
    grid[sr][sc] = START
    # гарантируем проходы вокруг старта
    grid[sr-1][sc] = EMPTY if grid[sr-1][sc] == WALL else grid[sr-1][sc]
    # выход — верх-центр
    grid[1][size//2] = EXIT
    grid[1][size//2-1] = EMPTY
    # размещаем лут на свободных клетках
    free = [(r,c) for r in range(1,size-1) for c in range(1,size-1)
            if grid[r][c] == EMPTY and not (r==sr and c==sc)]
    random.shuffle(free)
    loot_cells = {}
    idx = 0
    for _ in range(min(n_loot, len(free))):
        r, c = free[idx]; idx += 1
        grid[r][c] = LOOT
        loot_cells[f"{r},{c}"] = _roll_loot()
    for _ in range(min(n_trap, len(free) - idx)):
        if idx >= len(free): break
        r, c = free[idx]; idx += 1
        grid[r][c] = TRAP
    return grid, sr, sc, loot_cells


def _roll_loot():
    total = sum(w for _,_,w in LOOT_TABLE)
    roll = random.uniform(0, total)
    acc = 0
    for lid, data, w in LOOT_TABLE:
        acc += w
        if roll <= acc:
            return data
    return LOOT_TABLE[0][1]


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


def new_run(user_id: int):
    """Начать новое исследование замка."""
    ensure_castle_table()
    from database import get_conn, execute
    grid, sr, sc, loot_cells = _gen_maze(SIZE)
    # если активен ивент — прячем особый приз на случайной свободной клетке
    event_cell = None
    try:
        from game.castle_event import is_event_active
        if is_event_active():
            free = [(r,c) for r in range(1,SIZE-1) for c in range(1,SIZE-1)
                    if grid[r][c] == EMPTY and not (r==sr and c==sc)]
            if free:
                er, ec = random.choice(free)
                grid[er][ec] = 6  # 6 = EVENT_PRIZE
                event_cell = f"{er},{ec}"
    except Exception:
        pass
    state = {
        "grid": grid, "pr": sr, "pc": sc, "size": SIZE,
        "loot": loot_cells, "collected": [], "trapsSprung": [],
        "hp": 100, "gold_found": 0, "items_found": [],
        "revealed": _around(sr, sc, SIZE), "done": False, "moves": 0,
        "eventCell": event_cell,
    }
    with get_conn() as conn:
        execute(conn, """INSERT INTO castle_runs (user_id, state, started_at) VALUES (%s,%s,%s)
                         ON CONFLICT (user_id) DO UPDATE SET state=%s, started_at=%s""",
                user_id, json.dumps(state), time.time(), json.dumps(state), time.time())
    return _client_state(state)


def _around(r, c, size):
    """Видимые клетки вокруг позиции (туман войны)."""
    cells = []
    for dr in range(-1, 2):
        for dc in range(-1, 2):
            nr, nc = r+dr, c+dc
            if 0 <= nr < size and 0 <= nc < size:
                cells.append(f"{nr},{nc}")
    return cells


def _client_state(state):
    """Состояние для клиента (с туманом войны — только раскрытые клетки)."""
    size = state["size"]
    revealed = set(state["revealed"])
    vis = []
    for r in range(size):
        row = []
        for c in range(size):
            key = f"{r},{c}"
            if key in revealed:
                cell = state["grid"][r][c]
                # собранный лут показываем как пустой
                if key in state["collected"]:
                    cell = EMPTY
                row.append(cell)
            else:
                row.append(-1)  # туман
        vis.append(row)
    return {
        "grid": vis, "pr": state["pr"], "pc": state["pc"], "size": size,
        "hp": state["hp"], "goldFound": state["gold_found"],
        "itemsFound": state["items_found"], "done": state["done"], "moves": state["moves"],
    }


def move(user_id: int, direction: str):
    """Шаг игрока. Возвращает обновлённое состояние + событие."""
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
        # границы и стены
        if not (0 <= nr < size and 0 <= nc < size) or state["grid"][nr][nc] == WALL:
            return {"event": "wall", **_client_state(state)}
        # двигаемся
        state["pr"], state["pc"] = nr, nc
        state["moves"] += 1
        # раскрываем вокруг
        for k in _around(nr, nc, size):
            if k not in state["revealed"]:
                state["revealed"].append(k)
        event = {"event": "move"}
        cell = state["grid"][nr][nc]
        key = f"{nr},{nc}"
        # лут
        if cell == LOOT and key not in state["collected"]:
            state["collected"].append(key)
            loot = state["loot"].get(key)
            if loot:
                if loot["type"] == "gold":
                    state["gold_found"] += loot["amount"]
                    _give_gold(user_id, loot["amount"])
                    event = {"event": "loot", "loot": loot}
                else:
                    _give_item(user_id, loot["item"], 1)
                    state["items_found"].append({"name": loot["name"], "emoji": loot["emoji"]})
                    event = {"event": "loot", "loot": loot}
        # ловушка
        elif cell == TRAP and key not in state["trapsSprung"]:
            state["trapsSprung"].append(key)
            dmg = random.randint(10, 25)
            state["hp"] = max(0, state["hp"] - dmg)
            event = {"event": "trap", "damage": dmg}
            if state["hp"] <= 0:
                state["done"] = True
                event = {"event": "dead", "damage": dmg}
        # выход
        elif cell == EXIT:
            state["done"] = True
            bonus = 100 + state["moves"]
            _give_gold(user_id, bonus)
            state["gold_found"] += bonus
            event = {"event": "exit", "bonus": bonus}
        # ивент-приз (6)
        elif cell == 6 and key == state.get("eventCell"):
            try:
                from game.castle_event import claim_prize
                from database import fetchrow as _fr
                from database import get_conn as _gc
                with _gc() as c2:
                    urow = _fr(c2, "SELECT wizard_name FROM users WHERE user_id=%s", user_id)
                uname = (urow["wizard_name"] if urow else None) or "Игрок"
                res = claim_prize(user_id, uname)
                if res.get("won"):
                    state["grid"][nr][nc] = EMPTY
                    state["collected"].append(key)
                    event = {"event": "eventWin", "prize": {"name": res["prizeName"], "emoji": res["prizeEmoji"], "qty": res["prizeQty"]}}
                else:
                    state["grid"][nr][nc] = EMPTY
                    event = {"event": "eventTaken"}
            except Exception:
                event = {"event": "move"}
        execute(conn, "UPDATE castle_runs SET state=%s WHERE user_id=%s", json.dumps(state), user_id)
    out = _client_state(state)
    out.update(event)
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
