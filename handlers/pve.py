"""
PvE Dungeons handler — TZ section 8.2.
Player fights monsters zone by zone; every 5 kills = mini-boss.
"""
import logging
import random
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler, MessageHandler, filters
from database import (
    get_user, user_exists, get_user_spells, get_daily_limit, increment_daily,
    add_xp, add_gold, get_conn, execute, fetchval,
)
from utils.i18n import t
from utils.helpers import house_emoji
from game.battle_engine import fresh_status, tick_status, resolve_turn, format_battle_status
from game.spells import spell_display_name, SPELLS
from game.monsters import ZONES, get_zone, available_zones, pick_monster, monster_ai_action
from game.drop_system import monster_drop, apply_antifarm_xp
from config import DAILY_LIMITS

logger = logging.getLogger(__name__)

# In-memory PvE sessions: user_id → session
_pve_sessions: dict[int, dict] = {}


def _zones_keyboard(player_level: int, user_id: int) -> InlineKeyboardMarkup:
    zones = available_zones(player_level)
    buttons = []
    for z in zones:
        name = z["name"].get(t(user_id, "_lang_code") or "ru", z["name"]["en"])
        buttons.append([InlineKeyboardButton(
            f"{z['emoji']} {name}",
            callback_data=f"pve_enter:{z['id']}"
        )])
    return InlineKeyboardMarkup(buttons)


def _spells_keyboard(spell_ids: list[str], lang: str) -> InlineKeyboardMarkup:
    buttons = []
    for sid in spell_ids[:8]:
        spell = SPELLS.get(sid)
        if not spell:
            continue
        name  = spell_display_name(sid, lang)
        mana  = spell.get("mana", 0)
        dmg   = spell.get("damage", 0)
        heal  = spell.get("heal", 0)
        label = f"{name} | 💧{mana}"
        if dmg:  label += f" ⚔️{dmg}"
        if heal: label += f" 💚{heal}"
        buttons.append([InlineKeyboardButton(label, callback_data=f"pve_cast:{sid}")])
    buttons.append([InlineKeyboardButton("🏃 Сбежать", callback_data="pve_flee")])
    return InlineKeyboardMarkup(buttons)


def _format_pve_text(session: dict) -> str:
    monster = session["monster"]
    user    = session["user"]
    ps = format_battle_status(session["player_status"])
    ms = format_battle_status(session["monster_status"])
    log_tail = "\n".join(session["log"][-4:])
    mname = monster["name"].get("ru", monster["id"])
    return (
        f"{monster.get('emoji','🐉')} *{mname}*\n"
        f"❤️ {session['monster_hp']}/{monster['hp']} {ms}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🧙 {user['wizard_name']} {house_emoji(user['house'])} {ps}\n"
        f"❤️ {session['player_hp']}/{user['max_hp']} | 💧{session['player_mana']}/{user['max_mana']}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"{log_tail}"
    )


async def cmd_dungeon(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not user_exists(user_id):
        await update.message.reply_text(t(user_id, "not_registered"))
        return

    used = get_daily_limit(user_id, "pve_dungeons")
    if used >= DAILY_LIMITS["pve_dungeons"]:
        await update.message.reply_text(t(user_id, "daily_limit_reached"))
        return

    user = get_user(user_id)
    zones = available_zones(user["level"])
    if not zones:
        await update.message.reply_text(t(user_id, "pve_no_zones"))
        return

    # ИСПРАВЛЕНИЕ 1: сбрасываем зависшую сессию при входе в меню зон
    _pve_sessions.pop(user_id, None)

    buttons = []
    for z in zones:
        name = z["name"].get("ru", z["name"]["en"])
        buttons.append([InlineKeyboardButton(
            f"{z['emoji']} {name} (мин. {z['min_level']} ур.)",
            callback_data=f"pve_enter:{z['id']}"
        )])
    markup = InlineKeyboardMarkup(buttons)
    await update.message.reply_text(t(user_id, "pve_choose_zone"), reply_markup=markup)


async def cb_pve_enter(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query   = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    zone_id = query.data.split(":")[1]

    # ИСПРАВЛЕНИЕ 1: если сессия зависла — тихо сбрасываем вместо блокировки
    if user_id in _pve_sessions:
        _pve_sessions.pop(user_id, None)

    user  = get_user(user_id)
    zone  = get_zone(zone_id)
    if not zone:
        await query.edit_message_text("❌ Зона не найдена.")
        return

    # ИСПРАВЛЕНИЕ 2: правильное обращение к БД через контекстный менеджер
    with get_conn() as conn:
        kills_in_zone = fetchval(
            conn,
            "SELECT COUNT(*) FROM pve_sessions WHERE user_id=%s AND zone=%s AND result='win'",
            user_id, zone_id
        ) or 0
    is_boss = (kills_in_zone > 0) and (kills_in_zone % zone["boss_every"] == 0)

    monster = pick_monster(zone_id, is_boss=is_boss)
    if not monster:
        await query.edit_message_text("❌ Монстр не найден.")
        return

    session = {
        "zone_id":        zone_id,
        "user":           dict(user),
        "monster":        dict(monster),
        "player_hp":      user["hp"],
        "player_mana":    user["mana"],
        "monster_hp":     monster["hp"],
        "player_status":  fresh_status(),
        "monster_status": fresh_status(),
        "turn":           1,
        "log":            [f"🏴 Ты встретил {monster['name'].get('ru','?')}!"],
    }
    _pve_sessions[user_id] = session

    spells = [row["spell_id"] for row in get_user_spells(user_id)]
    lang   = user.get("lang", "ru")
    markup = _spells_keyboard(spells, lang)
    await query.edit_message_text(_format_pve_text(session), parse_mode="Markdown", reply_markup=markup)


async def cb_pve_cast(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query    = update.callback_query
    await query.answer()
    user_id  = query.from_user.id
    spell_id = query.data.split(":")[1]

    session = _pve_sessions.get(user_id)
    if not session:
        await query.edit_message_text("❌ Бой завершён.")
        return

    user    = session["user"]
    monster = session["monster"]
    lang    = user.get("lang", "ru")

    # ── Player turn ──────────────────────────────────────────────────────────
    result = resolve_turn(
        spell_id, user, monster,
        session["player_status"], session["monster_status"],
        session["player_hp"], session["monster_hp"], session["player_mana"],
    )
    session["player_hp"]     = result["attacker_hp"]
    session["monster_hp"]    = result["defender_hp"]
    session["player_mana"]   = max(0, session["player_mana"] - result["mana_cost"])
    session["player_status"] = result.get("new_atk_status", session["player_status"])
    session["monster_status"]= result.get("new_def_status", session["monster_status"])

    sname = spell_display_name(spell_id, lang)
    session["log"].append(f"🧙 {sname}: {result['log']}")

    # Check monster death
    if result.get("instant_kill") or session["monster_hp"] <= 0:
        await _pve_win(query, user_id, session, ctx)
        return

    # ── Monster turn ─────────────────────────────────────────────────────────
    m_action = monster_ai_action(monster, session["monster_hp"], session["player_hp"], session["turn"])

    if m_action["action"] == "defend":
        session["monster_status"]["block"] = True
        session["log"].append(f"{monster.get('emoji','🐉')} Защищается!")
    else:
        m_spell = m_action["spell"] or {}
        m_dmg   = int(m_spell.get("damage", monster["attack"]) * (monster["attack"] / 30))
        defense   = user.get("defense", 5)
        reduction = defense / (defense + 30)
        m_dmg     = int(m_dmg * (1 - reduction))
        if session["player_status"].get("block"):
            m_dmg = int(m_dmg * 0.6)
        m_dmg = max(m_dmg, 1)
        session["player_hp"] = max(0, session["player_hp"] - m_dmg)
        effect = m_spell.get("effect")
        eff_tag = f" ({effect})" if effect else ""
        session["log"].append(f"{monster.get('emoji','🐉')} {m_action['spell_id']}: -{m_dmg} ХП{eff_tag}")

    # Tick statuses
    ps, dot_p = tick_status(session["player_status"])
    ms, dot_m = tick_status(session["monster_status"])
    session["player_status"]  = ps
    session["monster_status"] = ms
    session["player_hp"]  = max(0, session["player_hp"] - dot_p)
    session["monster_hp"] = max(0, session["monster_hp"] - dot_m)
    session["turn"] += 1

    if session["player_hp"] <= 0:
        await _pve_lose(query, user_id, session)
        return
    if session["monster_hp"] <= 0:
        await _pve_win(query, user_id, session, ctx)
        return

    # Continue
    spells = [row["spell_id"] for row in get_user_spells(user_id)]
    markup = _spells_keyboard(spells, lang)
    await query.edit_message_text(_format_pve_text(session), parse_mode="Markdown", reply_markup=markup)


async def _pve_win(query, user_id: int, session: dict, ctx: ContextTypes.DEFAULT_TYPE):
    _pve_sessions.pop(user_id, None)
    user    = session["user"]
    monster = session["monster"]

    luck_mod = 1.0 + (user.get("luck", 5) - 5) * 0.01
    drop     = monster_drop(monster, luck_modifier=luck_mod)

    # Anti-farm XP
    with get_conn() as conn:
        repeat_count = fetchval(
            conn,
            "SELECT COUNT(*) FROM pve_sessions WHERE user_id=%s AND monster=%s AND created_at::date=CURRENT_DATE",
            user_id, monster["id"]
        ) or 0
    xp_actual = apply_antifarm_xp(drop["xp"], repeat_count, 0, user["level"], 0)

    new_level, leveled_up = add_xp(user_id, xp_actual)
    add_gold(user_id, drop["gold"])
    increment_daily(user_id, "pve_dungeons")

    with get_conn() as conn:
        execute(conn, """
            INSERT INTO pve_sessions (user_id, zone, monster, result, xp_gained, gold_gained)
            VALUES (%s, %s, %s, 'win', %s, %s)
        """, user_id, session["zone_id"], monster["id"], xp_actual, drop["gold"])

    with get_conn() as conn:
        execute(conn,
            "UPDATE house_points SET points = points + 5 WHERE house = (SELECT house FROM users WHERE user_id=%s)",
            user_id)

    mname = monster["name"].get("ru", monster["id"])
    text = (
        f"🏆 *{mname} повержен!*\n"
        f"+{xp_actual} XP | +{drop['gold']} 💰\n"
    )
    if drop["spell"]:
        text += f"✨ Получено заклинание: `{drop['spell']}`!\n"
    if drop["item"]:
        text += f"🎁 Получен предмет: `{drop['item']['id']}`!\n"
    if leveled_up:
        text += f"\n🎉 Уровень повышен до {new_level}!"

    await query.edit_message_text(text, parse_mode="Markdown")


async def _pve_lose(query, user_id: int, session: dict):
    _pve_sessions.pop(user_id, None)
    mname = session["monster"]["name"].get("ru", session["monster"]["id"])
    xp_consolation = 10
    add_xp(user_id, xp_consolation)
    with get_conn() as conn:
        execute(conn, """
            INSERT INTO pve_sessions (user_id, zone, monster, result, xp_gained, gold_gained)
            VALUES (%s, %s, %s, 'loss', %s, 0)
        """, user_id, session["zone_id"], session["monster"]["id"], xp_consolation)
    await query.edit_message_text(
        f"💀 *{mname} победил тебя!*\n+{xp_consolation} XP за участие.",
        parse_mode="Markdown"
    )


async def cb_pve_flee(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query   = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    _pve_sessions.pop(user_id, None)
    await query.edit_message_text(t(user_id, "pve_fled"))


async def handle_dungeon_button(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if update.message.text == t(user_id, "btn_dungeon"):
        await cmd_dungeon(update, ctx)


def register_pve_handlers(app):
    app.add_handler(CommandHandler("dungeon", cmd_dungeon))
    app.add_handler(CallbackQueryHandler(cb_pve_enter, pattern=r"^pve_enter:"))
    app.add_handler(CallbackQueryHandler(cb_pve_cast,  pattern=r"^pve_cast:"))
    app.add_handler(CallbackQueryHandler(cb_pve_flee,  pattern=r"^pve_flee"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_dungeon_button), group=5)
