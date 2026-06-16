"""
Мировой чат с командами админа, цветными никами, значками и званиями.

Сообщения хранятся в БД. Клиенты опрашивают ленту.
Админ может выдавать золото/предметы прямо из чата командами.
"""
import time
import json

MAX_MSG_LEN = 200
FEED_LIMIT = 50
ANTIFLOOD_SEC = 2  # минимум секунд между сообщениями

# Звания по уровню (level -> название, цвет)
RANKS = [
    (1,  "Первокурсник", "#9aa0b5"),
    (5,  "Студент",      "#7dd3fc"),
    (10, "Староста",     "#86efac"),
    (20, "Отличник",     "#c4b5fd"),
    (35, "Маг",          "#fbbf24"),
    (50, "Архимаг",      "#fb923c"),
    (75, "Легенда",      "#f472b6"),
]

# Значки (badge) — присваиваются за достижения/админом
BADGES = {
    "admin":    {"emoji": "⚜️", "name": "Администратор", "color": "#ffd700"},
    "vip":      {"emoji": "💎", "name": "VIP", "color": "#a78bfa"},
    "champion": {"emoji": "🏆", "name": "Чемпион", "color": "#fbbf24"},
    "veteran":  {"emoji": "🎖️", "name": "Ветеран", "color": "#fb923c"},
    "winner":   {"emoji": "👑", "name": "Победитель ивента", "color": "#34d399"},
}

# Цвета факультетов для ников
HOUSE_COLOR = {
    "gryffindor": "#ff6b5c", "slytherin": "#4ade80",
    "ravenclaw": "#60a5fa", "hufflepuff": "#fbbf24",
}
HOUSE_EMOJI = {"gryffindor": "🦁", "slytherin": "🐍", "ravenclaw": "🦅", "hufflepuff": "🦡"}


def ensure_chat_tables():
    from database import get_conn, execute
    with get_conn() as conn:
        execute(conn, """
            CREATE TABLE IF NOT EXISTS world_chat (
                id BIGSERIAL PRIMARY KEY,
                user_id BIGINT,
                name TEXT,
                house TEXT,
                level INT DEFAULT 1,
                badges TEXT DEFAULT '',
                text TEXT,
                is_system BOOLEAN DEFAULT FALSE,
                created_at DOUBLE PRECISION
            )
        """)
        execute(conn, """
            CREATE TABLE IF NOT EXISTS chat_badges (
                user_id BIGINT NOT NULL,
                badge TEXT NOT NULL,
                UNIQUE(user_id, badge)
            )
        """)
        execute(conn, """
            CREATE TABLE IF NOT EXISTS chat_lastmsg (
                user_id BIGINT PRIMARY KEY,
                last_at DOUBLE PRECISION
            )
        """)


def get_rank(level):
    name, color = RANKS[0][1], RANKS[0][2]
    for lvl, nm, col in RANKS:
        if level >= lvl:
            name, color = nm, col
    return {"name": name, "color": color}


def get_user_badges(user_id):
    ensure_chat_tables()
    from database import get_conn, fetchall
    from config import ADMIN_IDS
    with get_conn() as conn:
        rows = fetchall(conn, "SELECT badge FROM chat_badges WHERE user_id=%s", user_id)
    badges = [r["badge"] for r in rows]
    if user_id in ADMIN_IDS and "admin" not in badges:
        badges.insert(0, "admin")
    return badges


def give_badge(user_id, badge):
    if badge not in BADGES:
        return False
    ensure_chat_tables()
    from database import get_conn, execute
    with get_conn() as conn:
        execute(conn, "INSERT INTO chat_badges (user_id, badge) VALUES (%s,%s) ON CONFLICT DO NOTHING", user_id, badge)
    return True


def post_message(user_id, name, house, level, text, is_system=False):
    """Отправить сообщение. Возвращает {ok, msg} или {error}."""
    ensure_chat_tables()
    from database import get_conn, execute, fetchrow
    text = (text or "").strip()[:MAX_MSG_LEN]
    if not text and not is_system:
        return {"error": "empty"}
    now = time.time()
    if not is_system:
        # антифлуд
        with get_conn() as conn:
            last = fetchrow(conn, "SELECT last_at FROM chat_lastmsg WHERE user_id=%s", user_id)
            if last and (now - last["last_at"]) < ANTIFLOOD_SEC:
                return {"error": "flood", "msg": "Не так быстро!"}
    badges = ",".join(get_user_badges(user_id)) if not is_system else ""
    with get_conn() as conn:
        execute(conn, """INSERT INTO world_chat (user_id, name, house, level, badges, text, is_system, created_at)
                         VALUES (%s,%s,%s,%s,%s,%s,%s,%s)""",
                user_id, name, house, level, badges, text, is_system, now)
        if not is_system:
            execute(conn, """INSERT INTO chat_lastmsg (user_id, last_at) VALUES (%s,%s)
                             ON CONFLICT (user_id) DO UPDATE SET last_at=%s""", user_id, now, now)
        # чистим старые сообщения (оставляем последние 200)
        execute(conn, """DELETE FROM world_chat WHERE id NOT IN
                         (SELECT id FROM world_chat ORDER BY id DESC LIMIT 200)""")
    return {"ok": True}


def system_message(text):
    """Системное сообщение (анонсы ивентов и т.п.)."""
    return post_message(0, "Система", "", 0, text, is_system=True)


def get_feed(after_id=0):
    """Лента сообщений (новее after_id)."""
    ensure_chat_tables()
    from database import get_conn, fetchall
    with get_conn() as conn:
        rows = fetchall(conn, """SELECT * FROM world_chat WHERE id > %s
                                 ORDER BY id DESC LIMIT %s""", after_id, FEED_LIMIT)
    out = []
    for r in reversed(rows):
        badge_list = [b for b in (r["badges"] or "").split(",") if b]
        badge_icons = [BADGES[b]["emoji"] for b in badge_list if b in BADGES]
        rank = get_rank(r["level"] or 1)
        is_admin = "admin" in badge_list
        name_color = "#ffd700" if is_admin else HOUSE_COLOR.get(r["house"], rank["color"])
        out.append({
            "id": r["id"], "userId": r["user_id"], "name": r["name"],
            "house": r["house"], "houseEmoji": HOUSE_EMOJI.get(r["house"], ""),
            "level": r["level"], "rank": rank["name"], "nameColor": name_color,
            "badges": badge_icons, "text": r["text"], "isSystem": r["is_system"],
            "isAdmin": is_admin, "ts": r["created_at"],
        })
    return out


# ─── Команды админа (вызываются из чата) ───
def handle_admin_command(admin_id, text):
    """
    Обрабатывает команды админа из чата.
    Команды:
      /gold <id> <кол-во>     — выдать золото
      /item <id> <item_id>    — выдать предмет
      /badge <id> <badge>     — выдать значок
      /say <текст>            — системное сообщение
      /clear                  — очистить чат
    Возвращает {ok, msg} или None если не команда.
    """
    from config import ADMIN_IDS
    if admin_id not in ADMIN_IDS:
        return None
    if not text.startswith("/"):
        return None
    parts = text.strip().split()
    cmd = parts[0].lower()
    try:
        if cmd == "/gold" and len(parts) >= 3:
            target = int(parts[1]); amount = int(parts[2])
            from database import add_gold
            add_gold(target, amount)
            return {"ok": True, "msg": f"✅ Выдано {amount}💰 игроку {target}"}
        elif cmd == "/item" and len(parts) >= 3:
            target = int(parts[1]); item_id = parts[2]
            qty = int(parts[3]) if len(parts) >= 4 else 1
            from database import add_item_to_inventory
            add_item_to_inventory(target, item_id, qty)
            return {"ok": True, "msg": f"✅ Выдан предмет {item_id} x{qty} игроку {target}"}
        elif cmd == "/badge" and len(parts) >= 3:
            target = int(parts[1]); badge = parts[2]
            if give_badge(target, badge):
                return {"ok": True, "msg": f"✅ Значок {badge} выдан игроку {target}"}
            return {"ok": False, "msg": "Неизвестный значок"}
        elif cmd == "/say" and len(parts) >= 2:
            msg = text[len("/say"):].strip()
            system_message("📢 " + msg)
            return {"ok": True, "msg": "Объявление отправлено", "silent": True}
        elif cmd == "/event" and len(parts) >= 2:
            # /event <item_id> [кол-во] — спрятать приз в замке и запустить ивент
            item_id = parts[1]
            qty = int(parts[2]) if len(parts) >= 3 else 1
            try:
                from game.items import ITEMS
                item = ITEMS.get(item_id)
                if item:
                    nm = item.get("name", {})
                    pname = nm.get("ru", item_id) if isinstance(nm, dict) else str(nm or item_id)
                    pemoji = item.get("emoji", "🎁")
                else:
                    pname = item_id; pemoji = "🎁"
            except Exception:
                pname = item_id; pemoji = "🎁"
            from game.castle_event import start_event
            start_event(item_id, qty, pname, pemoji)
            return {"ok": True, "msg": f"🎪 Ивент запущен! Приз: {pemoji} {pname} x{qty}", "silent": True}
        elif cmd == "/clear":
            from database import get_conn, execute
            with get_conn() as conn:
                execute(conn, "DELETE FROM world_chat")
            return {"ok": True, "msg": "Чат очищен", "silent": True}
        else:
            return {"ok": False, "msg": "Команды: /gold /item /badge /say /clear"}
    except Exception as e:
        return {"ok": False, "msg": f"Ошибка: {e}"}
