"""
Живой PvP — Шаг 1: приглашения и матчинг.

Возможности:
- Вызов конкретного игрока по ID
- Случайный соперник в пределах ±4 уровней
- Уведомление сопернику в Telegram (через Bot HTTP API)
- Переключатель блокировки случайных приглашений (анти-спам)

Приглашения и комнаты живут в памяти сервера (бой короткий).
Само состояние боя и обмен ходами — следующие шаги.
"""
import logging
import os
import time
import random
import json
import urllib.request

logger = logging.getLogger(__name__)

BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
MINIAPP_URL = "https://hogwardsgame.github.io/hogwarts-app/"

# Ожидающие приглашения: invite_id -> {from_id, to_id, from_name, ts, status}
_invites: dict[str, dict] = {}
_INVITE_TTL = 120  # приглашение живёт 2 минуты
LEVEL_RANGE = 4


def _cleanup():
    now = time.time()
    dead = [iid for iid, inv in _invites.items() if now - inv.get("ts", now) > _INVITE_TTL]
    for iid in dead:
        _invites.pop(iid, None)


def _send_telegram(chat_id: int, text: str, reply_markup=None):
    """Отправить сообщение через Bot HTTP API (не зависим от объекта бота)."""
    if not BOT_TOKEN:
        return False
    try:
        payload = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
        if reply_markup:
            payload["reply_markup"] = json.dumps(reply_markup)
        data = json.dumps(payload).encode()
        req = urllib.request.Request(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
            data=data, headers={"Content-Type": "application/json"},
        )
        urllib.request.urlopen(req, timeout=5)
        return True
    except Exception as e:
        logger.warning("pvp notify: %s", e)
        return False


# ── Настройка блокировки случайных приглашений ──────────────────────────────
def get_block_status(user_id: int) -> bool:
    """True = случайные приглашения заблокированы."""
    from database import get_setting
    val = get_setting(f"pvp_block:{user_id}", "0")
    return val == "1"


def set_block_status(user_id: int, blocked: bool) -> bool:
    from database import set_setting
    set_setting(f"pvp_block:{user_id}", "1" if blocked else "0")
    return blocked


def toggle_block(user_id: int) -> dict:
    new_state = not get_block_status(user_id)
    set_block_status(user_id, new_state)
    return {"blocked": new_state}


# ── Создание приглашений ────────────────────────────────────────────────────
def _make_invite(from_id: int, from_name: str, to_id: int) -> str:
    invite_id = f"{from_id}_{to_id}_{int(time.time())}"
    _invites[invite_id] = {
        "from_id": from_id, "to_id": to_id, "from_name": from_name,
        "ts": time.time(), "status": "pending",
    }
    return invite_id


def challenge_by_id(user_id: int, target_id: int) -> dict:
    """Вызвать конкретного игрока по ID."""
    _cleanup()
    from database import get_user
    if target_id == user_id:
        return {"ok": False, "msg": "Нельзя вызвать самого себя"}
    me = get_user(user_id)
    target = get_user(target_id)
    if not target:
        return {"ok": False, "msg": "Игрок с таким ID не найден"}
    # Прямой вызов по ID работает даже при блокировке случайных — это адресный вызов
    invite_id = _make_invite(user_id, me["wizard_name"], target_id)
    _notify_target(target_id, me, invite_id)
    return {"ok": True, "msg": f"⚔️ Вызов отправлен игроку {target['wizard_name']}!", "inviteId": invite_id}


def challenge_random(user_id: int) -> dict:
    """Найти случайного соперника в пределах ±4 уровней."""
    _cleanup()
    from database import get_user, get_conn, fetchall
    me = get_user(user_id)
    if not me:
        return {"ok": False, "msg": "Профиль не найден"}
    lvl = me.get("level", 1)
    try:
        with get_conn() as conn:
            rows = fetchall(conn, """
                SELECT user_id, wizard_name, level FROM users
                WHERE user_id != %s
                  AND level BETWEEN %s AND %s
                  AND COALESCE(is_banned, FALSE) = FALSE
                ORDER BY RANDOM() LIMIT 20
            """, user_id, lvl - LEVEL_RANGE, lvl + LEVEL_RANGE)
    except Exception as e:
        logger.warning("pvp random: %s", e)
        rows = []
    # Отфильтровываем тех, кто заблокировал случайные приглашения
    candidates = [r for r in rows if not get_block_status(r["user_id"])]
    if not candidates:
        return {"ok": False, "msg": "Подходящих соперников сейчас нет. Попробуй позже или вызови по ID."}
    target = random.choice(candidates)
    invite_id = _make_invite(user_id, me["wizard_name"], target["user_id"])
    _notify_target(target["user_id"], me, invite_id)
    return {"ok": True, "msg": f"⚔️ Соперник найден: {target['wizard_name']}! Ждём ответа...", "inviteId": invite_id}


def _notify_target(target_id: int, challenger: dict, invite_id: str):
    """Отправить сопернику уведомление о вызове в Telegram."""
    name = challenger.get("wizard_name", "Соперник")
    lvl = challenger.get("level", 1)
    text = (f"⚔️ <b>Вызов на дуэль!</b>\n\n"
            f"Волшебник <b>{name}</b> (уровень {lvl}) вызывает тебя на дуэль в Mini App!\n\n"
            f"Открой приложение, чтобы принять вызов. ⚡")
    kb = {"inline_keyboard": [[{"text": "⚔️ Открыть дуэль", "web_app": {"url": MINIAPP_URL}}]]}
    _send_telegram(target_id, text, kb)


# ── Проверка входящих приглашений (опрос) ───────────────────────────────────
def get_incoming(user_id: int) -> dict:
    """Входящие приглашения для игрока (Mini App опрашивает)."""
    _cleanup()
    incoming = []
    for iid, inv in _invites.items():
        if inv["to_id"] == user_id and inv["status"] == "pending":
            incoming.append({
                "inviteId": iid,
                "fromId": inv["from_id"],
                "fromName": inv["from_name"],
            })
    return {"incoming": incoming, "blocked": get_block_status(user_id)}


def respond_invite(user_id: int, invite_id: str, accept: bool) -> dict:
    """Принять или отклонить приглашение. При принятии создаётся боевая комната."""
    inv = _invites.get(invite_id)
    if not inv or inv["to_id"] != user_id:
        return {"ok": False, "msg": "Приглашение не найдено или истекло"}
    if accept:
        inv["status"] = "accepted"
        room_id = _create_room(inv["from_id"], inv["to_id"])
        inv["room_id"] = room_id
        return {"ok": True, "accepted": True, "msg": "Вызов принят! Бой начинается...",
                "opponentId": inv["from_id"], "roomId": room_id}
    else:
        inv["status"] = "declined"
        return {"ok": True, "accepted": False, "msg": "Вызов отклонён"}


def check_invite_status(user_id: int, invite_id: str) -> dict:
    """Вызывающий опрашивает: принял ли соперник."""
    inv = _invites.get(invite_id)
    if not inv:
        return {"status": "expired"}
    return {"status": inv["status"], "opponentId": inv["to_id"], "roomId": inv.get("room_id")}


# ── Боевые комнаты (Шаг 2-3): состояние боя + ходы ──────────────────────────
_rooms: dict[str, dict] = {}
_ROOM_TTL = 600       # комната живёт 10 минут
_TURN_TIME = 40       # секунд на ход


def _cleanup_rooms():
    now = time.time()
    dead = [rid for rid, r in _rooms.items() if now - r.get("ts", now) > _ROOM_TTL]
    for rid in dead:
        _rooms.pop(rid, None)


def _combat(user: dict) -> dict:
    return {
        "user_id": user["user_id"], "wizard_name": user["wizard_name"],
        "house": user.get("house", ""), "max_hp": user["max_hp"], "max_mana": user["max_mana"],
        "attack": user["attack"], "defense": user["defense"],
        "speed": user["speed"], "luck": user.get("luck", 5), "level": user.get("level", 1),
    }


def _create_room(p1_id: int, p2_id: int) -> str:
    """Создать боевую комнату для двух игроков."""
    _cleanup_rooms()
    from database import get_user, get_user_spells
    from game.battle_engine import fresh_status
    u1, u2 = get_user(p1_id), get_user(p2_id)
    if not u1 or not u2:
        return ""
    room_id = f"room_{p1_id}_{p2_id}_{int(time.time())}"
    s1 = [r["spell_id"] for r in (get_user_spells(p1_id) or [])] or ["expelliarmus"]
    s2 = [r["spell_id"] for r in (get_user_spells(p2_id) or [])] or ["expelliarmus"]
    c1, c2 = _combat(u1), _combat(u2)
    first = p1_id if c1["speed"] >= c2["speed"] else p2_id
    _rooms[room_id] = {
        "p1": c1, "p2": c2,
        "spells": {p1_id: s1, p2_id: s2},
        "hp": {p1_id: c1["max_hp"], p2_id: c2["max_hp"]},
        "mana": {p1_id: c1["max_mana"], p2_id: c2["max_mana"]},
        "status": {p1_id: fresh_status(), p2_id: fresh_status()},
        "prev_spell": {p1_id: None, p2_id: None},
        "turn": first,
        "turn_deadline": time.time() + _TURN_TIME,
        "log": ["⚔️ Дуэль началась!"],
        "over": False, "winner": None,
        "last_turn": None,
        "ts": time.time(),
    }
    return room_id


def _spell_brief_pvp(spell_id: str):
    from game.spells import SPELLS, spell_display_name
    from game.battle_engine import element_badge
    s = SPELLS.get(spell_id, {})
    return {"id": spell_id, "name": spell_display_name(spell_id, "ru"),
            "emoji": s.get("emoji", "✨"), "mana": s.get("mana", 0),
            "damage": s.get("damage", 0), "heal": s.get("heal", 0),
            "element": element_badge(s)}


def get_battle_state(user_id: int, room_id: str) -> dict:
    """Состояние боя глазами конкретного игрока."""
    r = _rooms.get(room_id)
    if not r:
        return {"active": False, "error": "no_room"}
    # Определяем «я» и «соперник»
    if user_id == r["p1"]["user_id"]:
        me, foe = r["p1"], r["p2"]
    elif user_id == r["p2"]["user_id"]:
        me, foe = r["p2"], r["p1"]
    else:
        return {"active": False, "error": "not_in_room"}
    my_id, foe_id = me["user_id"], foe["user_id"]

    # Авто-пропуск хода при таймауте (анти-зависание)
    if not r["over"] and time.time() > r["turn_deadline"]:
        idle = r["turn"]
        other = r["p2"]["user_id"] if idle == r["p1"]["user_id"] else r["p1"]["user_id"]
        idle_max_mana = r["p1"]["max_mana"] if idle == r["p1"]["user_id"] else r["p2"]["max_mana"]
        r["mana"][idle] = min(idle_max_mana, r["mana"][idle] + 10)
        r["turn"] = other
        r["turn_deadline"] = time.time() + _TURN_TIME
        r["log"].append("⏱ Ход пропущен (таймаут)")

    return {
        "active": True,
        "roomId": room_id,
        "me": {"name": me["wizard_name"], "house": me["house"],
               "hp": r["hp"][my_id], "maxHp": me["max_hp"],
               "mana": r["mana"][my_id], "maxMana": me["max_mana"]},
        "foe": {"name": foe["wizard_name"], "house": foe["house"],
                "hp": r["hp"][foe_id], "maxHp": foe["max_hp"],
                "mana": r["mana"][foe_id], "maxMana": foe["max_mana"]},
        "yourTurn": (r["turn"] == my_id) and not r["over"],
        "spells": [_spell_brief_pvp(s) for s in r["spells"][my_id]],
        "log": r["log"][-5:],
        "over": r["over"],
        "youWon": (r["winner"] == my_id) if r["over"] else None,
        "timeLeft": max(0, int(r["turn_deadline"] - time.time())) if not r["over"] else 0,
        "lastTurn": r.get("last_turn"),
    }


def battle_cast(user_id: int, room_id: str, spell_id: str) -> dict:
    """Игрок применяет заклинание (только в свой ход)."""
    from game.battle_engine import resolve_turn
    from game.spells import SPELLS, spell_display_name
    r = _rooms.get(room_id)
    if not r or r["over"]:
        return get_battle_state(user_id, room_id)
    if r["turn"] != user_id:
        return get_battle_state(user_id, room_id)
    if spell_id not in r["spells"].get(user_id, []):
        return get_battle_state(user_id, room_id)

    # Кто атакующий, кто защищающийся
    if user_id == r["p1"]["user_id"]:
        atk, dfn = r["p1"], r["p2"]
    else:
        atk, dfn = r["p2"], r["p1"]
    atk_id, dfn_id = atk["user_id"], dfn["user_id"]

    spell = SPELLS.get(spell_id, {})
    if r["mana"][atk_id] < spell.get("mana", 0):
        r["log"].append("💧 Недостаточно маны!")
        return get_battle_state(user_id, room_id)

    res = resolve_turn(spell_id, atk, dfn, r["status"][atk_id], r["status"][dfn_id],
                       r["hp"][atk_id], r["hp"][dfn_id], r["mana"][atk_id],
                       prev_spell_id=r["prev_spell"][atk_id])
    dmg = max(0, r["hp"][dfn_id] - res["defender_hp"])
    r["hp"][atk_id] = res["attacker_hp"]
    r["hp"][dfn_id] = res["defender_hp"]
    r["mana"][atk_id] = max(0, r["mana"][atk_id] - res["mana_cost"])
    r["status"][atk_id] = res["new_atk_status"]
    r["status"][dfn_id] = res["new_def_status"]
    r["prev_spell"][atk_id] = spell_id

    from game.battle_engine import element_badge
    sname = spell_display_name(spell_id, "ru")
    line = f"{atk['wizard_name']}: {sname}"
    if res.get("crit"): line = "💥 " + line + " (КРИТ!)"
    r["log"].append(line)
    r["last_turn"] = {
        "by": atk_id, "dmg": dmg, "heal": res.get("heal", 0) or 0,
        "crit": bool(res.get("crit")), "element": element_badge(spell),
    }

    # Проверка победы
    if r["hp"][dfn_id] <= 0:
        r["over"] = True
        r["winner"] = atk_id
        r["log"].append(f"🏆 {atk['wizard_name']} побеждает!")
        _finish_battle(r, atk_id, dfn_id)
        return get_battle_state(user_id, room_id)

    # Передаём ход, реген маны защищающемуся к его ходу
    r["mana"][dfn_id] = min(dfn["max_mana"], r["mana"][dfn_id] + 10)
    r["turn"] = dfn_id
    r["turn_deadline"] = time.time() + _TURN_TIME
    return get_battle_state(user_id, room_id)


def battle_flee(user_id: int, room_id: str) -> dict:
    """Сдаться/выйти — соперник побеждает."""
    r = _rooms.get(room_id)
    if not r or r["over"]:
        return {"active": False}
    foe_id = r["p2"]["user_id"] if user_id == r["p1"]["user_id"] else r["p1"]["user_id"]
    r["over"] = True
    r["winner"] = foe_id
    r["log"].append("🏳️ Соперник сдался!")
    _finish_battle(r, foe_id, user_id)
    return get_battle_state(user_id, room_id)


def _finish_battle(r: dict, winner_id: int, loser_id: int):
    """Начислить статистику, ELO и награды."""
    try:
        from database import get_conn, execute, add_gold, add_xp
        with get_conn() as conn:
            execute(conn, "INSERT INTO user_stats (user_id) VALUES (%s) ON CONFLICT DO NOTHING", winner_id)
            execute(conn, "INSERT INTO user_stats (user_id) VALUES (%s) ON CONFLICT DO NOTHING", loser_id)
            execute(conn, "UPDATE user_stats SET pvp_wins=pvp_wins+1, pvp_total=pvp_total+1 WHERE user_id=%s", winner_id)
            execute(conn, "UPDATE user_stats SET pvp_losses=pvp_losses+1, pvp_total=pvp_total+1 WHERE user_id=%s", loser_id)
        try:
            from handlers.duel_league import update_elo
            update_elo(winner_id, loser_id)
        except Exception:
            pass
        add_gold(winner_id, 60)
        add_xp(winner_id, 90)
    except Exception as e:
        logger.warning("live finish: %s", e)
