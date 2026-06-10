"""
Events handler — TZ section 12.
Weekly boss event (Fri-Sun), monthly tournament, House Cup reset.
"""
import logging
import random
from datetime import datetime, timezone
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler, MessageHandler, filters
from database import (
    get_user, user_exists, get_conn, execute, fetchrow, fetchall,
    add_xp, add_gold,
)
from utils.i18n import t
from utils.helpers import house_emoji
from game.monsters import MONSTERS
from game.drop_system import monster_drop, roll_item_drop
from game.battle_engine import fresh_status, tick_status, resolve_turn, format_battle_status
from game.spells import spell_display_name, SPELLS
from game.items import item_display_name, ITEMS

logger = logging.getLogger(__name__)

# In-memory event boss sessions: user_id → session
_event_sessions: dict[int, dict] = {}

WEEKLY_BOSS_ID = "aragog"   # rotated by scheduler
EVENT_BOSS_HP_MULTIPLIER = 3.0


def _get_active_event() -> dict | None:
    with get_conn() as conn:
        return fetchrow(conn,
            "SELECT * FROM events WHERE is_active=TRUE AND ends_at > NOW() ORDER BY id DESC LIMIT 1")


def _get_event_leaderboard(event_id: int, limit: int = 10) -> list:
    """Top players by damage dealt to event boss."""
    with get_conn() as conn:
        return fetchall(conn, """
            SELECT u.wizard_name, u.house,
                   SUM((dl.details::jsonb->>'damage')::int) as total_dmg
            FROM duel_log dl
            JOIN users u ON u.user_id = dl.actor_id
            WHERE dl.details::jsonb->>'event_id' = %s
            GROUP BY u.wizard_name, u.house
            ORDER BY total_dmg DESC
            LIMIT %s
        """, str(event_id), limit)


async def cmd_events(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not user_exists(user_id):
        await update.message.reply_text(t(user_id, "not_registered"))
        return

    event = _get_active_event()
    if not event:
        await update.message.reply_text(t(user_id, "event_none_active"))
        return

    ends_at = event["ends_at"]
    ends_str = ends_at.strftime("%d.%m %H:%M UTC") if hasattr(ends_at, "strftime") else str(ends_at)
    data = event.get("data") or {}

    boss_id  = data.get("boss", WEEKLY_BOSS_ID)
    boss     = MONSTERS.get(boss_id, MONSTERS[WEEKLY_BOSS_ID])
    boss_hp  = data.get("boss_hp", int(boss["hp"] * EVENT_BOSS_HP_MULTIPLIER))
    boss_cur = data.get("boss_current_hp", boss_hp)

    hp_bar_len = 20
    filled = int(hp_bar_len * boss_cur / boss_hp)
    hp_bar = "█" * filled + "░" * (hp_bar_len - filled)

    bname = boss["name"].get("ru", boss["id"])
    text = (
        f"🎉 *Событие: {event.get('title_key', 'Ивент')}*\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"{boss.get('emoji','🐉')} *{bname}*\n"
        f"❤️ `[{hp_bar}]` {boss_cur}/{boss_hp}\n"
        f"⏰ До окончания: {ends_str}\n\n"
        f"Топ-3 нанесут наибольший урон — получат эпический предмет!"
    )
    buttons = [[InlineKeyboardButton("⚔️ Атаковать босса!", callback_data=f"event_fight:{event['id']}")]]
    await update.message.reply_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(buttons))


async def cb_event_fight(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query    = update.callback_query
    user_id  = query.from_user.id
    event_id = int(query.data.split(":")[1])

    if user_id in _event_sessions:
        await query.answer("⚔️ Бой уже идёт!", show_alert=True)
        return

    event = _get_active_event()
    if not event or event["id"] != event_id:
        await query.edit_message_text("❌ Событие завершено.")
        return

    user = get_user(user_id)
    data = event.get("data") or {}
    boss_id  = data.get("boss", WEEKLY_BOSS_ID)
    boss     = dict(MONSTERS.get(boss_id, MONSTERS[WEEKLY_BOSS_ID]))
    boss_hp  = data.get("boss_current_hp", int(boss["hp"] * EVENT_BOSS_HP_MULTIPLIER))

    session = {
        "event_id":       event_id,
        "user":           dict(user),
        "boss":           boss,
        "player_hp":      user["hp"],
        "player_mana":    user["mana"],
        "boss_hp":        boss_hp,
        "boss_max_hp":    boss_hp,
        "player_status":  fresh_status(),
        "boss_status":    fresh_status(),
        "damage_dealt":   0,
        "turn":           1,
        "log":            [f"⚔️ Сражение с {boss['name'].get('ru', boss['id'])}!"],
    }
    _event_sessions[user_id] = session

    spells = [row["spell_id"] for row in __import__("database").get_user_spells(user_id)]
    lang   = user.get("lang", "ru")
    markup = _event_spells_keyboard(spells, lang)
    await query.edit_message_text(_format_event_battle(session), parse_mode="Markdown", reply_markup=markup)


def _event_spells_keyboard(spell_ids: list[str], lang: str) -> InlineKeyboardMarkup:
    buttons = []
    for sid in spell_ids[:6]:
        spell = SPELLS.get(sid)
        if not spell:
            continue
        name  = spell_display_name(sid, lang)
        mana  = spell.get("mana", 0)
        dmg   = spell.get("damage", 0)
        buttons.append([InlineKeyboardButton(
            f"{name} | 💧{mana} ⚔️{dmg}",
            callback_data=f"event_cast:{sid}"
        )])
    buttons.append([InlineKeyboardButton("🏃 Отступить", callback_data="event_flee")])
    return InlineKeyboardMarkup(buttons)


def _format_event_battle(session: dict) -> str:
    boss = session["boss"]
    user = session["user"]
    ps   = format_battle_status(session["player_status"])
    bs   = format_battle_status(session["boss_status"])
    log_tail = "\n".join(session["log"][-4:])
    bname = boss["name"].get("ru", boss["id"])
    return (
        f"{boss.get('emoji','🐉')} *{bname}* {bs}\n"
        f"❤️ {session['boss_hp']}/{session['boss_max_hp']}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🧙 {user['wizard_name']} {ps}\n"
        f"❤️ {session['player_hp']}/{user['max_hp']} | 💧{session['player_mana']}/{user['max_mana']}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"{log_tail}"
    )


async def cb_event_cast(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query    = update.callback_query
    await query.answer()
    user_id  = query.from_user.id
    spell_id = query.data.split(":")[1]

    session = _event_sessions.get(user_id)
    if not session:
        await query.edit_message_text("❌ Бой завершён.")
        return

    user = session["user"]
    boss = session["boss"]
    lang = user.get("lang", "ru")

    result = resolve_turn(
        spell_id, user, boss,
        session["player_status"], session["boss_status"],
        session["player_hp"], session["boss_hp"], session["player_mana"],
    )

    dmg_dealt = result["damage"]
    session["player_hp"]     = result["attacker_hp"]
    session["boss_hp"]       = max(0, result["defender_hp"])
    session["player_mana"]   = max(0, session["player_mana"] - result["mana_cost"])
    session["damage_dealt"] += dmg_dealt

    sname = spell_display_name(spell_id, lang)
    session["log"].append(f"🧙 {sname}: {result['log']}")

    if result.get("instant_kill") or session["boss_hp"] <= 0:
        await _event_boss_phase_done(query, user_id, session)
        return

    # Boss counter-attack
    from game.monsters import monster_ai_action, MONSTER_SPELLS
    m_action = monster_ai_action(boss, session["boss_hp"], session["player_hp"], session["turn"])
    if m_action["action"] == "defend":
        session["boss_status"]["block"] = True
        session["log"].append(f"{boss.get('emoji','🐉')} Защищается!")
    else:
        m_spell = m_action["spell"] or {}
        m_dmg   = int(m_spell.get("damage", boss["attack"]) * (boss["attack"] / 50))
        defense   = user.get("defense", 5)
        reduction = defense / (defense + 30)
        m_dmg     = max(int(m_dmg * (1 - reduction)), 1)
        session["player_hp"] = max(0, session["player_hp"] - m_dmg)
        session["log"].append(f"{boss.get('emoji','🐉')} Атакует: -{m_dmg} ХП")

    ps, dot_p = tick_status(session["player_status"])
    bs, dot_b = tick_status(session["boss_status"])
    session["player_status"] = ps
    session["boss_status"]   = bs
    session["player_hp"]  = max(0, session["player_hp"] - dot_p)
    session["boss_hp"]    = max(0, session["boss_hp"]   - dot_b)
    session["turn"] += 1

    if session["player_hp"] <= 0:
        _event_sessions.pop(user_id, None)
        add_xp(user_id, 20)
        await query.edit_message_text(
            f"💀 Ты пал в бою!\nНанесено урона: {session['damage_dealt']}\n+20 XP за участие",
            parse_mode="Markdown"
        )
        return

    spells = [row["spell_id"] for row in __import__("database").get_user_spells(user_id)]
    markup = _event_spells_keyboard(spells, lang)
    await query.edit_message_text(_format_event_battle(session), parse_mode="Markdown", reply_markup=markup)


async def _event_boss_phase_done(query, user_id: int, session: dict):
    """Boss HP phase depleted — deal damage to global boss pool, give rewards."""
    _event_sessions.pop(user_id, None)
    event_id   = session["event_id"]
    dmg_dealt  = session["damage_dealt"]

    # Update global boss HP in event data
    with get_conn() as conn:
        event = fetchrow(conn, "SELECT * FROM events WHERE id=%s", event_id)
        if event:
            import json
            data = event.get("data") or {}
            if isinstance(data, str):
                data = json.loads(data)
            cur_hp = data.get("boss_current_hp", session["boss_max_hp"])
            new_hp = max(0, cur_hp - dmg_dealt)
            data["boss_current_hp"] = new_hp
            execute(conn, "UPDATE events SET data=%s WHERE id=%s", json.dumps(data), event_id)

    # Log damage for leaderboard
    with get_conn() as conn:
        execute(conn, """
            INSERT INTO duel_log (duel_id, turn, actor_id, action, details)
            VALUES (NULL, %s, %s, 'event_attack', %s::jsonb)
        """, session["turn"], user_id,
            f'{{"damage":{dmg_dealt},"event_id":"{event_id}"}}')

    xp_gain   = min(dmg_dealt * 2, 500)
    gold_gain = min(dmg_dealt, 200)
    add_xp(user_id, xp_gain)
    add_gold(user_id, gold_gain)

    await query.edit_message_text(
        f"💥 *Фаза завершена!*\n"
        f"Нанесено урона боссу: {dmg_dealt}\n"
        f"+{xp_gain} XP  +{gold_gain} 💰\n\n"
        f"Продолжай атаковать, чтобы попасть в топ-3!",
        parse_mode="Markdown"
    )


async def cb_event_flee(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query   = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    session = _event_sessions.pop(user_id, None)
    dmg = session["damage_dealt"] if session else 0
    await query.edit_message_text(f"🏃 Отступил. Нанесено урона: {dmg}")


async def start_weekly_event(bot, boss_id: str = WEEKLY_BOSS_ID):
    """Called by APScheduler every Friday."""
    from datetime import timedelta
    boss  = MONSTERS.get(boss_id, MONSTERS[WEEKLY_BOSS_ID])
    boss_hp = int(boss["hp"] * EVENT_BOSS_HP_MULTIPLIER)
    ends_at = datetime.now(timezone.utc) + timedelta(days=3)
    import json

    with get_conn() as conn:
        execute(conn, "UPDATE events SET is_active=FALSE WHERE is_active=TRUE")
        execute(conn, """
            INSERT INTO events (event_type, title_key, starts_at, ends_at, is_active, data)
            VALUES ('weekly_boss', 'Еженедельный босс', NOW(), %s, TRUE, %s::jsonb)
        """, ends_at, json.dumps({"boss": boss_id, "boss_hp": boss_hp, "boss_current_hp": boss_hp}))

    with get_conn() as conn:
        users = fetchall(conn, "SELECT user_id FROM users")
    bname = boss["name"].get("ru", boss["id"])
    for row in users:
        try:
            await bot.send_message(
                row["user_id"],
                f"🎉 *Еженедельный ивент начался!*\n"
                f"Особый босс: {boss.get('emoji','🐉')} *{bname}*\n"
                f"Атакуй его в меню ивентов! Топ-3 по урону получат эпический предмет!\n"
                f"⏰ До воскресенья.",
                parse_mode="Markdown"
            )
        except Exception:
            pass


async def end_weekly_event(bot):
    """Called by APScheduler every Monday — rewards top-3."""
    with get_conn() as conn:
        event = fetchrow(conn, "SELECT * FROM events WHERE is_active=TRUE AND event_type='weekly_boss' LIMIT 1")
    if not event:
        return

    with get_conn() as conn:
        top3 = fetchall(conn, """
            SELECT actor_id, SUM((details::jsonb->>'damage')::int) as total_dmg
            FROM duel_log
            WHERE details::jsonb->>'event_id' = %s
            GROUP BY actor_id ORDER BY total_dmg DESC LIMIT 3
        """, str(event["id"]))
        execute(conn, "UPDATE events SET is_active=FALSE WHERE id=%s", event["id"])

    rarity_by_rank = ["epic", "epic", "very_rare"]
    for i, row in enumerate(top3):
        uid  = row["actor_id"]
        item = roll_item_drop(min_rarity=rarity_by_rank[i], guaranteed=True)
        if item:
            with get_conn() as conn:
                execute(conn, "INSERT INTO inventory (user_id, item_id) VALUES (%s,%s)", uid, item["id"])
        try:
            rank_label = ["🥇 1-е", "🥈 2-е", "🥉 3-е"][i]
            await bot.send_message(uid,
                f"🏆 *Ивент завершён!* {rank_label} место!\n"
                f"Урона нанесено: {row['total_dmg']}\n"
                f"Награда: {item_display_name(item,'ru') if item else 'предмет'} добавлен в инвентарь!",
                parse_mode="Markdown"
            )
        except Exception as e:
            logger.error(f"event reward notify: {e}")



def register_events_handlers(app):
    app.add_handler(CommandHandler("events", cmd_events))
    app.add_handler(CallbackQueryHandler(cb_event_fight, pattern=r"^event_fight:"))
    app.add_handler(CallbackQueryHandler(cb_event_cast,  pattern=r"^event_cast:"))
    app.add_handler(CallbackQueryHandler(cb_event_flee,  pattern=r"^event_flee"))
    