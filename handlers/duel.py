"""
PvP Duel handler — TZ section 8.1.
Turn-based combat with inline keyboard, 45-second timeout.
"""
import asyncio
import logging
import random
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ContextTypes, CommandHandler, CallbackQueryHandler, MessageHandler, filters,
)
from database import (
    get_user, user_exists, get_user_spells, get_daily_limit, increment_daily,
    add_xp, add_gold, get_conn, execute, fetchrow, fetchall,
)
from utils.i18n import t
from utils.helpers import house_emoji
from game.battle_engine import (
    fresh_status, tick_status, resolve_turn, determine_turn_order,
    format_battle_status,
)
from game.spells import get_spell, spell_display_name, SPELLS
from config import DAILY_LIMITS, DUEL_TIMEOUT_SECONDS, DUEL_INVITE_TIMEOUT, MAX_LEVEL_DIFF_PVP

logger = logging.getLogger(__name__)

# In-memory duel state: duel_id → state dict
_active_duels: dict[int, dict] = {}
# pending invites: challenger_id → {opponent_id, duel_id, task}
_pending_invites: dict[int, dict] = {}


def _get_next_duel_id() -> int:
    return max(_active_duels.keys(), default=0) + 1


def _spells_keyboard(spell_ids: list[str], duel_id: int, actor: str, lang: str) -> InlineKeyboardMarkup:
    buttons = []
    for sid in spell_ids[:8]:  # show up to 8 spells
        spell = SPELLS.get(sid)
        if not spell:
            continue
        name = spell_display_name(sid, lang)
        mana = spell.get("mana", 0)
        dmg  = spell.get("damage", 0)
        heal = spell.get("heal", 0)
        label = f"{name} | 💧{mana}"
        if dmg:   label += f" ⚔️{dmg}"
        if heal:  label += f" 💚{heal}"
        buttons.append([InlineKeyboardButton(label, callback_data=f"duel_cast:{duel_id}:{actor}:{sid}")])
    return InlineKeyboardMarkup(buttons)


def _format_battle_text(state: dict) -> str:
    p = state["player"]
    o = state["opponent"]
    ps = format_battle_status(state["player_status"])
    os = format_battle_status(state["opponent_status"])
    log_tail = "\n".join(state["log"][-5:])

    return (
        f"⚔️ *Дуэль!*\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🧙 {p['wizard_name']} {house_emoji(p['house'])} {ps}\n"
        f"❤️ {state['player_hp']}/{p['max_hp']} | 💧{state['player_mana']}/{p['max_mana']}\n\n"
        f"🧙 {o['wizard_name']} {house_emoji(o['house'])} {os}\n"
        f"❤️ {state['opponent_hp']}/{o['max_hp']} | 💧{state['opponent_mana']}/{o['max_mana']}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"{log_tail}"
    )


async def _end_duel(duel_id: int, winner_id: int | None, ctx: ContextTypes.DEFAULT_TYPE):
    state = _active_duels.pop(duel_id, None)
    if not state:
        return

    player   = state["player"]
    opponent = state["opponent"]

    if state.get("timeout_task"):
        state["timeout_task"].cancel()

    # determine loser
    loser_id = None
    if winner_id == player["user_id"]:
        loser_id = opponent["user_id"]
    elif winner_id == opponent["user_id"]:
        loser_id = player["user_id"]

    # rewards per TZ 8.1
    if winner_id:
        xp_win   = random.randint(50, 150)
        gold_win = random.randint(20, 80)
        xp_lose  = 10
        add_xp(winner_id, xp_win)
        add_gold(winner_id, gold_win)
        if loser_id:
            add_xp(loser_id, xp_lose)

        # house points
        with get_conn() as conn:
            execute(conn, "UPDATE house_points SET points = points + 10 WHERE house = (SELECT house FROM users WHERE user_id = %s)", winner_id)
            if loser_id:
                execute(conn, "UPDATE house_points SET points = points + 5 WHERE house = (SELECT house FROM users WHERE user_id = %s)", loser_id)

        # update stats
        with get_conn() as conn:
            execute(conn, "UPDATE user_stats SET pvp_wins = pvp_wins + 1, pvp_total = pvp_total + 1 WHERE user_id = %s", winner_id)
            if loser_id:
                execute(conn, "UPDATE user_stats SET pvp_losses = pvp_losses + 1, pvp_total = pvp_total + 1 WHERE user_id = %s", loser_id)

        # Save duel result
        with get_conn() as conn:
            execute(conn, "UPDATE duels SET winner_id = %s, status = 'finished', ended_at = NOW() WHERE id = %s", winner_id, duel_id)

        winner = player if winner_id == player["user_id"] else opponent
        summary = (
            f"🏆 *{winner['wizard_name']} победил!*\n"
            f"+{xp_win} XP  +{gold_win} 💰"
        )
    else:
        summary = "🤝 Ничья!"

    # Send result to both players
    for uid in [player["user_id"], opponent["user_id"]]:
        try:
            await ctx.bot.send_message(uid, summary, parse_mode="Markdown")
        except Exception:
            pass


async def _turn_timeout(duel_id: int, actor_id: int, ctx: ContextTypes.DEFAULT_TYPE):
    await asyncio.sleep(DUEL_TIMEOUT_SECONDS)
    state = _active_duels.get(duel_id)
    if not state:
        return
    # Timeout = actor loses their turn, flip turn
    state["log"].append(f"⏰ {t(actor_id, 'duel_timeout')}")
    _flip_turn(state)
    await _send_turn(duel_id, ctx)


def _flip_turn(state: dict):
    if state["current_turn"] == "player":
        state["current_turn"] = "opponent"
    else:
        state["current_turn"] = "player"


async def _send_turn(duel_id: int, ctx: ContextTypes.DEFAULT_TYPE):
    state = _active_duels.get(duel_id)
    if not state:
        return

    # Tick DoT status effects
    if state["current_turn"] == "player":
        new_status, dot = tick_status(state["player_status"])
        state["player_status"] = new_status
        state["player_hp"]     = max(0, state["player_hp"] - dot)
        if dot:
            state["log"].append(f"🔥 {state['player']['wizard_name']}: -{dot} ХП (эффект)")
        actor    = state["player"]
        actor_id = actor["user_id"]
    else:
        new_status, dot = tick_status(state["opponent_status"])
        state["opponent_status"] = new_status
        state["opponent_hp"]     = max(0, state["opponent_hp"] - dot)
        if dot:
            state["log"].append(f"🔥 {state['opponent']['wizard_name']}: -{dot} ХП (эффект)")
        actor    = state["opponent"]
        actor_id = actor["user_id"]

    # Check death from DoT
    if state["player_hp"] <= 0:
        await _end_duel(duel_id, state["opponent"]["user_id"], ctx)
        return
    if state["opponent_hp"] <= 0:
        await _end_duel(duel_id, state["player"]["user_id"], ctx)
        return

    text   = _format_battle_text(state)
    spells = [row["spell_id"] for row in get_user_spells(actor_id)]
    lang   = actor.get("lang", "ru")
    markup = _spells_keyboard(spells, duel_id, state["current_turn"], lang)

    try:
        msg = await ctx.bot.send_message(actor_id, text, parse_mode="Markdown", reply_markup=markup)
        state["last_msg_id"] = msg.message_id
    except Exception as e:
        logger.error(f"send_turn error: {e}")

    # Notify other player to wait
    other_id = state["opponent"]["user_id"] if state["current_turn"] == "player" else state["player"]["user_id"]
    try:
        await ctx.bot.send_message(other_id, _format_battle_text(state), parse_mode="Markdown")
    except Exception:
        pass

    # Schedule timeout
    if state.get("timeout_task"):
        state["timeout_task"].cancel()
    task = asyncio.get_event_loop().create_task(_turn_timeout(duel_id, actor_id, ctx))
    state["timeout_task"] = task


async def cmd_duel(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not user_exists(user_id):
        await update.message.reply_text(t(user_id, "not_registered"))
        return

    # Daily limit check
    used = get_daily_limit(user_id, "pvp_duels")
    if used >= DAILY_LIMITS["pvp_duels"]:
        await update.message.reply_text(t(user_id, "daily_limit_reached"))
        return

    if ctx.args:
        target_name = " ".join(ctx.args)
        with get_conn() as conn:
            target = fetchrow(conn, "SELECT * FROM users WHERE LOWER(wizard_name) = LOWER(%s)", target_name)
        if not target:
            await update.message.reply_text(t(user_id, "duel_player_not_found"))
            return
        target_id = target["user_id"]
    else:
        # Random opponent
        user = get_user(user_id)
        with get_conn() as conn:
            candidates = fetchall(conn, """
                SELECT * FROM users
                WHERE user_id != %s
                  AND ABS(level - %s) <= %s
                ORDER BY RANDOM() LIMIT 1
            """, user_id, user["level"], MAX_LEVEL_DIFF_PVP)
        if not candidates:
            await update.message.reply_text(t(user_id, "duel_no_opponents"))
            return
        target = candidates[0]
        target_id = target["user_id"]

    if target_id == user_id:
        await update.message.reply_text(t(user_id, "duel_self"))
        return

    player = get_user(user_id)
    opp    = get_user(target_id)

    if abs(player["level"] - opp["level"]) > MAX_LEVEL_DIFF_PVP:
        await update.message.reply_text(t(user_id, "duel_level_diff"))
        return

    # Send invite
    markup = InlineKeyboardMarkup([[
        InlineKeyboardButton(t(target_id, "btn_duel_accept"), callback_data=f"duel_accept:{user_id}"),
        InlineKeyboardButton(t(target_id, "btn_duel_decline"), callback_data=f"duel_decline:{user_id}"),
    ]])
    try:
        await ctx.bot.send_message(
            target_id,
            t(target_id, "duel_invite", challenger=player["wizard_name"]),
            parse_mode="Markdown",
            reply_markup=markup,
        )
    except Exception:
        await update.message.reply_text(t(user_id, "duel_cant_reach"))
        return

    await update.message.reply_text(t(user_id, "duel_invite_sent", opponent=opp["wizard_name"]))

    # Auto-expire invite
    async def _expire():
        await asyncio.sleep(DUEL_INVITE_TIMEOUT)
        _pending_invites.pop(user_id, None)
    task = asyncio.get_event_loop().create_task(_expire())
    _pending_invites[user_id] = {"opponent_id": target_id, "task": task}


async def cb_duel_accept(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query     = update.callback_query
    await query.answer()
    opponent_id   = query.from_user.id
    challenger_id = int(query.data.split(":")[1])

    invite = _pending_invites.pop(challenger_id, None)
    if not invite:
        await query.edit_message_text(t(opponent_id, "duel_expired"))
        return

    invite["task"].cancel()
    player = get_user(challenger_id)
    opp    = get_user(opponent_id)

    # Create DB record
    with get_conn() as conn:
        execute(conn, """
            INSERT INTO duels (challenger_id, opponent_id, status)
            VALUES (%s, %s, 'active')
        """, challenger_id, opponent_id)
        row = fetchrow(conn, "SELECT id FROM duels WHERE challenger_id=%s AND opponent_id=%s ORDER BY id DESC LIMIT 1", challenger_id, opponent_id)
    duel_id = row["id"]

    # Increment daily counters
    increment_daily(challenger_id, "pvp_duels")
    increment_daily(opponent_id,   "pvp_duels")

    first = determine_turn_order(player["speed"], opp["speed"])
    state = {
        "duel_id":         duel_id,
        "player":          dict(player),
        "opponent":        dict(opp),
        "player_hp":       player["hp"],
        "opponent_hp":     opp["hp"],
        "player_mana":     player["mana"],
        "opponent_mana":   opp["mana"],
        "player_status":   fresh_status(),
        "opponent_status": fresh_status(),
        "current_turn":    first,
        "turn_number":     1,
        "log":             ["⚔️ Дуэль начинается!"],
        "timeout_task":    None,
    }
    _active_duels[duel_id] = state

    await query.edit_message_text(t(opponent_id, "duel_accepted", challenger=player["wizard_name"]))
    await ctx.bot.send_message(challenger_id, t(challenger_id, "duel_accepted_notify", opponent=opp["wizard_name"]))
    await _send_turn(duel_id, ctx)


async def cb_duel_decline(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query         = update.callback_query
    await query.answer()
    opponent_id   = query.from_user.id
    challenger_id = int(query.data.split(":")[1])
    _pending_invites.pop(challenger_id, None)
    await query.edit_message_text(t(opponent_id, "duel_declined_by_you"))
    try:
        await ctx.bot.send_message(challenger_id, t(challenger_id, "duel_declined"))
    except Exception:
        pass


async def cb_duel_cast(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query  = update.callback_query
    await query.answer()
    parts  = query.data.split(":")
    duel_id, actor_key, spell_id = int(parts[1]), parts[2], parts[3]
    user_id = query.from_user.id

    state = _active_duels.get(duel_id)
    if not state:
        await query.edit_message_text("❌ Дуэль уже завершена.")
        return

    # Verify it's this player's turn
    if actor_key == "player" and user_id != state["player"]["user_id"]:
        await query.answer("❌ Сейчас не твой ход!", show_alert=True)
        return
    if actor_key == "opponent" and user_id != state["opponent"]["user_id"]:
        await query.answer("❌ Сейчас не твой ход!", show_alert=True)
        return

    if state["timeout_task"]:
        state["timeout_task"].cancel()

    if actor_key == "player":
        attacker = state["player"];   defender = state["opponent"]
        atk_hp   = state["player_hp"];   def_hp = state["opponent_hp"]
        atk_mana = state["player_mana"]
        atk_st   = state["player_status"]; def_st = state["opponent_status"]
    else:
        attacker = state["opponent"]; defender = state["player"]
        atk_hp   = state["opponent_hp"]; def_hp = state["player_hp"]
        atk_mana = state["opponent_mana"]
        atk_st   = state["opponent_status"]; def_st = state["player_status"]

    result = resolve_turn(spell_id, attacker, defender, atk_st, def_st, atk_hp, def_hp, atk_mana)

    # Apply results
    if actor_key == "player":
        state["player_hp"]     = result["attacker_hp"]
        state["opponent_hp"]   = result["defender_hp"]
        state["player_mana"]   = max(0, atk_mana - result["mana_cost"])
    else:
        state["opponent_hp"]   = result["attacker_hp"]
        state["player_hp"]     = result["defender_hp"]
        state["opponent_mana"] = max(0, atk_mana - result["mana_cost"])

    lang = attacker.get("lang", "ru")
    sname = spell_display_name(spell_id, lang)
    state["log"].append(f"{house_emoji(attacker['house'])} {attacker['wizard_name']}: {sname} — {result['log']}")

    # Check end
    if result.get("instant_kill") or state["player_hp"] <= 0 or state["opponent_hp"] <= 0:
        winner_id = state["opponent"]["user_id"] if state["player_hp"] <= 0 else state["player"]["user_id"]
        await query.edit_message_text(_format_battle_text(state), parse_mode="Markdown")
        await _end_duel(duel_id, winner_id, ctx)
        return

    state["turn_number"] += 1
    _flip_turn(state)
    await query.edit_message_text(_format_battle_text(state), parse_mode="Markdown")
    await _send_turn(duel_id, ctx)


async def handle_duel_button(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if update.message.text == t(user_id, "btn_duel"):
        await cmd_duel(update, ctx)


def register_duel_handlers(app):
    app.add_handler(CommandHandler("duel", cmd_duel))
    app.add_handler(CallbackQueryHandler(cb_duel_accept,  pattern=r"^duel_accept:"))
    app.add_handler(CallbackQueryHandler(cb_duel_decline, pattern=r"^duel_decline:"))
    app.add_handler(CallbackQueryHandler(cb_duel_cast,    pattern=r"^duel_cast:"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_duel_button), group=4)
