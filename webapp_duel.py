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
    """Принять или отклонить приглашение."""
    inv = _invites.get(invite_id)
    if not inv or inv["to_id"] != user_id:
        return {"ok": False, "msg": "Приглашение не найдено или истекло"}
    if accept:
        inv["status"] = "accepted"
        # На следующем шаге здесь будет создание боевой комнаты
        return {"ok": True, "accepted": True, "msg": "Вызов принят! (бой — на следующем шаге)",
                "opponentId": inv["from_id"]}
    else:
        inv["status"] = "declined"
        return {"ok": True, "accepted": False, "msg": "Вызов отклонён"}


def check_invite_status(user_id: int, invite_id: str) -> dict:
    """Вызывающий опрашивает: принял ли соперник."""
    inv = _invites.get(invite_id)
    if not inv:
        return {"status": "expired"}
    return {"status": inv["status"], "opponentId": inv["to_id"]}
