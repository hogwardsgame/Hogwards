"""
Ивент-лабиринт: админ прячет приз в замке, игроки ищут.

Админ запускает командой /event <предмет> [кол-во].
В чат идёт анонс. Даётся 3 часа. Кто первый найдёт приз в замке — забирает.
Победитель получает приз + значок 👑, ивент закрывается с объявлением.
"""
import time
import json
import random

EVENT_DURATION = 3 * 3600  # 3 часа


def ensure_event_table():
    from database import get_conn, execute
    with get_conn() as conn:
        execute(conn, """
            CREATE TABLE IF NOT EXISTS castle_event (
                id INT PRIMARY KEY DEFAULT 1,
                active BOOLEAN DEFAULT FALSE,
                prize_item TEXT,
                prize_qty INT DEFAULT 1,
                prize_name TEXT,
                prize_emoji TEXT,
                started_at DOUBLE PRECISION,
                ends_at DOUBLE PRECISION,
                winner_id BIGINT,
                winner_name TEXT
            )
        """)


def get_active_event():
    """Возвращает активный ивент или None. Сам закрывает по таймауту."""
    ensure_event_table()
    from database import get_conn, fetchrow, execute
    with get_conn() as conn:
        row = fetchrow(conn, "SELECT * FROM castle_event WHERE id=1")
        if not row or not row["active"]:
            return None
        # проверка таймаута
        if time.time() > row["ends_at"]:
            execute(conn, "UPDATE castle_event SET active=FALSE WHERE id=1")
            # анонс об окончании без победителя
            try:
                from game.world_chat import system_message
                system_message(f"⏰ Ивент окончен! Приз {row['prize_emoji']} {row['prize_name']} никто не нашёл.")
            except Exception:
                pass
            return None
    return {
        "active": True, "prizeItem": row["prize_item"], "prizeQty": row["prize_qty"],
        "prizeName": row["prize_name"], "prizeEmoji": row["prize_emoji"],
        "endsAt": row["ends_at"], "timeLeft": int(row["ends_at"] - time.time()),
    }


def start_event(prize_item, prize_qty, prize_name, prize_emoji):
    """Запустить ивент (вызывается админом)."""
    ensure_event_table()
    from database import get_conn, execute
    now = time.time()
    ends = now + EVENT_DURATION
    with get_conn() as conn:
        execute(conn, """INSERT INTO castle_event (id, active, prize_item, prize_qty, prize_name, prize_emoji, started_at, ends_at, winner_id, winner_name)
                         VALUES (1, TRUE, %s, %s, %s, %s, %s, %s, NULL, NULL)
                         ON CONFLICT (id) DO UPDATE SET active=TRUE, prize_item=%s, prize_qty=%s,
                         prize_name=%s, prize_emoji=%s, started_at=%s, ends_at=%s, winner_id=NULL, winner_name=NULL""",
                prize_item, prize_qty, prize_name, prize_emoji, now, ends,
                prize_item, prize_qty, prize_name, prize_emoji, now, ends)
    # анонс в чат
    try:
        from game.world_chat import system_message
        system_message(f"🎪 ИВЕНТ НАЧАЛСЯ! В замке 🏰 спрятан приз: {prize_emoji} {prize_name}! Кто первый найдёт — забирает! У вас 3 часа. (Мир → Замок)")
    except Exception:
        pass
    return {"ok": True}


def claim_prize(user_id, user_name):
    """Игрок нашёл приз в замке. Первый забирает. Возвращает результат."""
    ensure_event_table()
    from database import get_conn, fetchrow, execute
    with get_conn() as conn:
        row = fetchrow(conn, "SELECT * FROM castle_event WHERE id=1")
        if not row or not row["active"]:
            return {"won": False}
        if time.time() > row["ends_at"]:
            execute(conn, "UPDATE castle_event SET active=FALSE WHERE id=1")
            return {"won": False}
        if row["winner_id"]:
            return {"won": False, "alreadyTaken": True}
        # этот игрок — первый!
        execute(conn, "UPDATE castle_event SET active=FALSE, winner_id=%s, winner_name=%s WHERE id=1",
                user_id, user_name)
        prize_item = row["prize_item"]; prize_qty = row["prize_qty"]
        prize_name = row["prize_name"]; prize_emoji = row["prize_emoji"]
    # выдаём приз
    try:
        from database import add_item_to_inventory
        add_item_to_inventory(user_id, prize_item, prize_qty)
    except Exception:
        pass
    # значок победителя
    try:
        from game.world_chat import give_badge
        give_badge(user_id, "winner")
    except Exception:
        pass
    # анонс победителя
    try:
        from game.world_chat import system_message
        system_message(f"👑 {user_name} нашёл приз {prize_emoji} {prize_name} и побеждает в ивенте! Поздравляем!")
    except Exception:
        pass
    return {"won": True, "prizeName": prize_name, "prizeEmoji": prize_emoji, "prizeQty": prize_qty}


def is_event_active():
    ev = get_active_event()
    return ev is not None
