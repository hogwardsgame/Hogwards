"""
PvP Duel handler.
Переработан полностью:
  - Вызов ТОЛЬКО по ID (ники убраны в целях безопасности)
  - Показ своего ID в меню дуэлей
  - Комбо-заклинания и контрзаклинания в PvP
  - Красивые панели боя с шкалами HP/маны
  - Журнал боя с эффектами и флейвором
  - Тик DoT-эффектов каждый ход
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
    add_xp, add_gold, add_house_points, get_conn, execute, fetchrow, fetchall,
)
from utils.i18n import t
from utils.helpers import house_emoji
from game.battle_engine import (
    fresh_status, tick_status, resolve_turn, determine_turn_order,
    format_pvp_panel, format_battle_status, can_cast_any, MANA_REGEN_PER_TURN,
    COMBO_SPELLS, HOUSE_EMOJI,
)
from game.spells import get_spell, spell_display_name, SPELLS, RARITY_EMOJI
from config import DAILY_LIMITS, DUEL_TIMEOUT_SECONDS, DUEL_INVITE_TIMEOUT, MAX_LEVEL_DIFF_PVP, XP_REWARDS, GOLD_REWARDS, HOUSE_POINTS_REWARDS

logger = logging.getLogger(__name__)

_active_duels:   dict[int, dict] = {}
_pending_invites: dict[int, dict] = {}


def _get_next_duel_id() -> int:
    return max(_active_duels.keys(), default=0) + 1


def _spells_keyboard(spell_ids: list[str], duel_id: int, actor: str, lang: str,
                     current_mana: int = 9999, prev_spell: str = None) -> InlineKeyboardMarkup:
    """Клавиатура заклинаний с подсветкой комбо."""
    buttons = []
    for sid in spell_ids[:8]:
        spell = SPELLS.get(sid)
        if not spell:
            continue
        name = spell_display_name(sid, lang)
        mana = spell.get("mana", 0)
        dmg  = spell.get("damage", 0)
        heal = spell.get("heal", 0)
        rarity_e = RARITY_EMOJI.get(spell.get("rarity", "common"), "⚪")

        is_combo = prev_spell and (
            (prev_spell, sid) in COMBO_SPELLS or (sid, prev_spell) in COMBO_SPELLS
        )
        combo_mark = "✨" if is_combo else ""

        if mana > current_mana:
            label = f"🚫 {rarity_e}{name} 💧{mana}"
        else:
            label = f"{combo_mark}{rarity_e}{name} 💧{mana}"
            if dmg:  label += f" ⚔️{dmg}"
            if heal: label += f" 💚{heal}"
        buttons.append([InlineKeyboardButton(label, callback_data=f"duel_cast:{duel_id}:{actor}:{sid}")])
    return InlineKeyboardMarkup(buttons)


async def _end_duel(duel_id: int, winner_id: int | None, ctx: ContextTypes.DEFAULT_TYPE):
    state = _active_duels.pop(duel_id, None)
    if not state:
        return

    player   = state["player"]
    opponent = state["opponent"]

    if state.get("timeout_task"):
        state["timeout_task"].cancel()

    loser_id = None
    if winner_id == player["user_id"]:
        loser_id = opponent["user_id"]
    elif winner_id == opponent["user_id"]:
        loser_id = player["user_id"]

    if winner_id:
        xp_win   = XP_REWARDS["pvp_win"]
        gold_win = GOLD_REWARDS["pvp_win"]
        xp_lose  = XP_REWARDS["pvp_lose"]
        gold_lose = GOLD_REWARDS["pvp_lose"]

        add_xp(winner_id, xp_win)
        add_gold(winner_id, gold_win)
        if loser_id:
            add_xp(loser_id, xp_lose)
            add_gold(loser_id, gold_lose)

        # Очки факультета
        winner_user = get_user(winner_id)
        add_house_points(winner_id, winner_user["house"], HOUSE_POINTS_REWARDS["pvp_win"], "pvp_win")

        # Статистика
        with get_conn() as conn:
            execute(conn, "UPDATE user_stats SET pvp_wins = pvp_wins + 1, pvp_total = pvp_total + 1 WHERE user_id = %s", winner_id)
            if loser_id:
                execute(conn, "UPDATE user_stats SET pvp_losses = pvp_losses + 1, pvp_total = pvp_total + 1 WHERE user_id = %s", loser_id)

        with get_conn() as conn:
            execute(conn, """
                UPDATE duels SET winner_id = %s, status = 'finished', ended_at = NOW()
                WHERE id = %s
            """, winner_id, duel_id)

        winner_name = player["wizard_name"] if winner_id == player["user_id"] else opponent["wizard_name"]
        loser_name  = opponent["wizard_name"] if winner_id == player["user_id"] else player["wizard_name"]

        result_text = (
            f"🏆 *{winner_name} победил!*\n"
            f"❌ {loser_name} проиграл\n\n"
            f"Победитель: +{xp_win} XP | +{gold_win} 💰\n"
            f"Проигравший: +{xp_lose} XP | +{gold_lose} 💰"
        )
        try:
            await ctx.bot.send_message(player["user_id"], result_text, parse_mode="Markdown")
        except Exception:
            pass
        if player["user_id"] != opponent["user_id"]:
            try:
                await ctx.bot.send_message(opponent["user_id"], result_text, parse_mode="Markdown")
            except Exception:
                pass
    else:
        with get_conn() as conn:
            execute(conn, "UPDATE duels SET status = 'draw', ended_at = NOW() WHERE id = %s", duel_id)
        draw_text = "🤝 *Ничья!* Оба волшебника исчерпали силы."
        for uid in (player["user_id"], opponent["user_id"]):
            try:
                await ctx.bot.send_message(uid, draw_text, parse_mode="Markdown")
            except Exception:
                pass


def _flip_turn(state: dict):
    state["current_turn"] = "opponent" if state["current_turn"] == "player" else "player"


async def _send_turn(duel_id: int, ctx: ContextTypes.DEFAULT_TYPE):
    state = _active_duels.get(duel_id)
    if not state:
        return

    # Тик DoT-эффектов
    ps, dot_p = tick_status(state["player_status"])
    ms, dot_m = tick_status(state["opponent_status"])
    state["player_status"]   = ps
    state["opponent_status"] = ms
    if dot_p > 0:
        state["player_hp"] = max(0, state["player_hp"] - dot_p)
        state["log"].append(f"🔥 {state['player']['wizard_name']} получает {dot_p} урона от эффекта")
    if dot_m > 0:
        state["opponent_hp"] = max(0, state["opponent_hp"] - dot_m)
        state["log"].append(f"🔥 {state['opponent']['wizard_name']} получает {dot_m} урона от эффекта")

    # Ограничение лога
    state["log"] = state["log"][-5:]

    # После DoT кто-то может умереть
    if state["player_hp"] <= 0:
        await _end_duel(duel_id, state["opponent"]["user_id"], ctx)
        return
    if state["opponent_hp"] <= 0:
        await _end_duel(duel_id, state["player"]["user_id"], ctx)
        return

    # Ход: кто сейчас ходит
    if state["current_turn"] == "player":
        actor     = state["player"]
        actor_key = "player"
        cur_mana  = state["player_mana"]
        prev_s    = state.get("player_prev_spell")
    else:
        actor     = state["opponent"]
        actor_key = "opponent"
        cur_mana  = state["opponent_mana"]
        prev_s    = state.get("opponent_prev_spell")

    actor_spells = [row["spell_id"] for row in get_user_spells(actor["user_id"])]

    # Если нет маны — регенерация
    if not can_cast_any(actor_spells, cur_mana):
        new_mana = min(actor.get("max_mana", 50), cur_mana + MANA_REGEN_PER_TURN)
        if actor_key == "player":
            state["player_mana"] = new_mana
        else:
            state["opponent_mana"] = new_mana
        state["log"].append(f"✨ {actor['wizard_name']} восстанавливает ману +{MANA_REGEN_PER_TURN} 💧")
        cur_mana = new_mana

    lang   = actor.get("lang", "ru")
    markup = _spells_keyboard(actor_spells, duel_id, actor_key, lang, cur_mana, prev_s)

    panel = format_pvp_panel(state)
    try:
        await ctx.bot.send_message(
            actor["user_id"],
            panel,
            parse_mode="Markdown",
            reply_markup=markup,
        )
    except Exception as e:
        logger.error(f"Ошибка отправки хода: {e}")

    # Таймаут хода
    async def _timeout():
        await asyncio.sleep(DUEL_TIMEOUT_SECONDS)
        st = _active_duels.get(duel_id)
        if st and st["current_turn"] == actor_key:
            st["log"].append(f"⏰ {actor['wizard_name']} не успел — ход пропущен!")
            _flip_turn(st)
            st["turn_number"] += 1
            await _send_turn(duel_id, ctx)

    if state.get("timeout_task"):
        state["timeout_task"].cancel()
    state["timeout_task"] = asyncio.get_event_loop().create_task(_timeout())


async def cmd_duel(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """/duel — меню дуэлей. Вызов только по ID."""
    user_id = update.effective_user.id
    if not user_exists(user_id):
        await update.message.reply_text(t(user_id, "not_registered"))
        return

    used = get_daily_limit(user_id, "pvp_duels")
    if used >= DAILY_LIMITS["pvp_duels"]:
        await update.message.reply_text(t(user_id, "daily_limit_reached"))
        return

    # Прямой вызов по ID: /duel 123456789
    if ctx.args and ctx.args[0].isdigit():
        target_id = int(ctx.args[0])
        with get_conn() as conn:
            target = fetchrow(conn, "SELECT * FROM users WHERE user_id = %s", target_id)
        if not target:
            await update.message.reply_text(
                "❌ Игрок с таким ID не найден.\n\n"
                "💡 Попроси противника написать /profile — там есть его ID."
            )
            return
        await _send_duel_invite(update, ctx, user_id, target)
        return

    player = get_user(user_id)
    markup = InlineKeyboardMarkup([
        [InlineKeyboardButton("🎲 Случайный противник", callback_data="duel_menu:random")],
        [InlineKeyboardButton("🔢 Вызвать по ID",       callback_data="duel_menu:by_id")],
    ])
    await update.message.reply_text(
        f"⚔️ *Дуэль*\n\n"
        f"Твой ID: `{user_id}`\n"
        f"Уровень: {player['level']} | Лимит разницы: ±{MAX_LEVEL_DIFF_PVP}\n"
        f"Дуэлей сегодня: {used}/{DAILY_LIMITS['pvp_duels']}\n\n"
        f"💡 Поделись своим ID с другом, чтобы он мог вызвать тебя командой:\n"
        f"`/duel {user_id}`",
        parse_mode="Markdown",
        reply_markup=markup,
    )


async def cb_duel_menu(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query   = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    action  = query.data.split(":")[1]

    if action == "random":
        user = get_user(user_id)
        if not user:
            await query.edit_message_text("❌ Сначала зарегистрируйся через /start.")
            return

        with get_conn() as conn:
            candidates = fetchall(conn, """
                SELECT user_id, wizard_name, house, level
                FROM users
                WHERE user_id != %s
                  AND ABS(level - %s) <= %s
                  AND COALESCE(is_banned, FALSE) = FALSE
                ORDER BY RANDOM()
                LIMIT 5
            """, user_id, user["level"], MAX_LEVEL_DIFF_PVP)

        if not candidates:
            await query.edit_message_text(
                "😔 Сейчас нет доступных противников.\n\n"
                "Причины обычно такие: нет других игроков, большая разница уровней или игроки забанены."
            )
            return

        buttons = []
        for c in candidates:
            h = HOUSE_EMOJI.get(c["house"], "🏠")
            buttons.append([InlineKeyboardButton(
                f"{h} {c['wizard_name']} (ур.{c['level']})",
                callback_data=f"duel_challenge:{c['user_id']}"
            )])
        buttons.append([InlineKeyboardButton("🔀 Другие", callback_data="duel_menu:random")])
        await query.edit_message_text("⚔️ Выбери противника:", reply_markup=InlineKeyboardMarkup(buttons))

    elif action == "by_id":
        ctx.user_data["awaiting_duel_id"] = True
        await query.edit_message_text(
            "🔢 Введи *Telegram ID* противника:\n\n"
            "Пример: `123456789`\n\n"
            "💡 ID можно узнать из /profile противника или из меню /duel.",
            parse_mode="Markdown"
        )


async def cb_duel_challenge(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query     = update.callback_query
    await query.answer()
    user_id   = query.from_user.id
    target_id = int(query.data.split(":")[1])

    with get_conn() as conn:
        target = fetchrow(conn, "SELECT * FROM users WHERE user_id = %s", target_id)
    if not target:
        await query.edit_message_text("❌ Игрок не найден.")
        return
    await _send_duel_invite_from_query(query, ctx, user_id, target)


async def handle_duel_text_input(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Ловит ввод ID после нажатия 'Вызвать по ID'."""
    user_id = update.effective_user.id
    if not ctx.user_data.get("awaiting_duel_id"):
        return
    ctx.user_data.pop("awaiting_duel_id", None)

    arg = update.message.text.strip()
    if not arg.isdigit():
        await update.message.reply_text(
            "❌ ID должен быть числом. Попробуй ещё раз через /duel."
        )
        return

    target_id = int(arg)
    with get_conn() as conn:
        target = fetchrow(conn, "SELECT * FROM users WHERE user_id = %s", target_id)

    if not target:
        await update.message.reply_text("❌ Игрок с таким ID не найден.")
        return
    await _send_duel_invite(update, ctx, user_id, target)


async def _send_duel_invite(update, ctx, user_id: int, target: dict):
    target_id = target["user_id"]
    if target_id == user_id:
        await update.message.reply_text("❌ Нельзя вызвать самого себя.")
        return

    player = get_user(user_id)
    if abs(player["level"] - target["level"]) > MAX_LEVEL_DIFF_PVP:
        await update.message.reply_text(
            f"❌ Разница в уровнях слишком велика (максимум ±{MAX_LEVEL_DIFF_PVP})."
        )
        return

    markup = InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ Принять", callback_data=f"duel_accept:{user_id}"),
        InlineKeyboardButton("❌ Отклонить", callback_data=f"duel_decline:{user_id}"),
    ]])
    try:
        await ctx.bot.send_message(
            target_id,
            f"⚔️ *Вызов на дуэль!*\n\n"
            f"Волшебник *{player['wizard_name']}* "
            f"({HOUSE_EMOJI.get(player['house'], '🏠')}, ур.{player['level']}) "
            f"вызывает тебя на дуэль!\n\n"
            f"У тебя {DUEL_INVITE_TIMEOUT} секунд на ответ.",
            parse_mode="Markdown",
            reply_markup=markup,
        )
    except Exception:
        await update.message.reply_text("❌ Не удалось отправить вызов — игрок недоступен.")
        return

    await update.message.reply_text(
        f"📨 Вызов отправлен игроку *{target['wizard_name']}*!\n"
        f"Ждём ответа {DUEL_INVITE_TIMEOUT} секунд...",
        parse_mode="Markdown"
    )

    async def _expire():
        await asyncio.sleep(DUEL_INVITE_TIMEOUT)
        _pending_invites.pop(user_id, None)
    task = asyncio.get_event_loop().create_task(_expire())
    _pending_invites[user_id] = {"opponent_id": target_id, "task": task}


async def _send_duel_invite_from_query(query, ctx, user_id: int, target: dict):
    target_id = target["user_id"]
    if target_id == user_id:
        await query.edit_message_text("❌ Нельзя вызвать самого себя.")
        return

    player = get_user(user_id)
    if abs(player["level"] - target["level"]) > MAX_LEVEL_DIFF_PVP:
        await query.edit_message_text(f"❌ Разница в уровнях слишком велика (максимум ±{MAX_LEVEL_DIFF_PVP}).")
        return

    markup = InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ Принять", callback_data=f"duel_accept:{user_id}"),
        InlineKeyboardButton("❌ Отклонить", callback_data=f"duel_decline:{user_id}"),
    ]])
    try:
        await ctx.bot.send_message(
            target_id,
            f"⚔️ *Вызов на дуэль!*\n\n"
            f"Волшебник *{player['wizard_name']}* "
            f"({HOUSE_EMOJI.get(player['house'], '🏠')}, ур.{player['level']}) "
            f"вызывает тебя!\n\nЕсть {DUEL_INVITE_TIMEOUT} секунд.",
            parse_mode="Markdown",
            reply_markup=markup,
        )
    except Exception:
        await query.edit_message_text("❌ Не удалось отправить вызов.")
        return

    await query.edit_message_text(
        f"📨 Вызов отправлен *{target['wizard_name']}*!",
        parse_mode="Markdown"
    )

    async def _expire():
        await asyncio.sleep(DUEL_INVITE_TIMEOUT)
        _pending_invites.pop(user_id, None)
    task = asyncio.get_event_loop().create_task(_expire())
    _pending_invites[user_id] = {"opponent_id": target_id, "task": task}


async def cb_duel_accept(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query         = update.callback_query
    await query.answer()
    opponent_id   = query.from_user.id
    challenger_id = int(query.data.split(":")[1])

    invite = _pending_invites.pop(challenger_id, None)
    if not invite:
        await query.edit_message_text("❌ Вызов истёк или отозван.")
        return

    invite["task"].cancel()
    player = get_user(challenger_id)
    opp    = get_user(opponent_id)

    with get_conn() as conn:
        execute(conn, """
            INSERT INTO duels (challenger_id, opponent_id, status)
            VALUES (%s, %s, 'active')
        """, challenger_id, opponent_id)
        row = fetchrow(conn,
            "SELECT id FROM duels WHERE challenger_id=%s AND opponent_id=%s ORDER BY id DESC LIMIT 1",
            challenger_id, opponent_id)
    duel_id = row["id"]

    increment_daily(challenger_id, "pvp_duels")
    increment_daily(opponent_id,   "pvp_duels")

    first = determine_turn_order(player["speed"], opp["speed"])
    state = {
        "duel_id":             duel_id,
        "player":              dict(player),
        "opponent":            dict(opp),
        "player_hp":           player["hp"],
        "opponent_hp":         opp["hp"],
        "player_mana":         player["mana"],
        "opponent_mana":       opp["mana"],
        "player_status":       fresh_status(),
        "opponent_status":     fresh_status(),
        "current_turn":        first,
        "turn_number":         1,
        "log":                 ["⚔️ Дуэль начинается!"],
        "timeout_task":        None,
        "player_prev_spell":   None,
        "opponent_prev_spell": None,
    }
    _active_duels[duel_id] = state

    first_name = player["wizard_name"] if first == "player" else opp["wizard_name"]
    await query.edit_message_text(
        f"✅ Дуэль принята!\n\nПервым ходит: *{first_name}*",
        parse_mode="Markdown"
    )
    try:
        await ctx.bot.send_message(
            challenger_id,
            f"✅ *{opp['wizard_name']}* принял вызов!\n\nПервым ходит: *{first_name}*",
            parse_mode="Markdown"
        )
    except Exception:
        pass
    await _send_turn(duel_id, ctx)


async def cb_duel_decline(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query         = update.callback_query
    await query.answer()
    opponent_id   = query.from_user.id
    challenger_id = int(query.data.split(":")[1])
    _pending_invites.pop(challenger_id, None)
    opp = get_user(opponent_id)
    await query.edit_message_text("❌ Ты отклонил вызов.")
    try:
        await ctx.bot.send_message(
            challenger_id,
            f"❌ *{opp['wizard_name']}* отклонил твой вызов.",
            parse_mode="Markdown"
        )
    except Exception:
        pass


async def cb_duel_cast(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query   = update.callback_query
    await query.answer()
    parts   = query.data.split(":")
    duel_id, actor_key, spell_id = int(parts[1]), parts[2], parts[3]
    user_id = query.from_user.id

    state = _active_duels.get(duel_id)
    if not state:
        await query.edit_message_text("❌ Дуэль уже завершена.")
        return

    # Проверка хода
    if actor_key == "player" and user_id != state["player"]["user_id"]:
        await query.answer("❌ Сейчас не твой ход!", show_alert=True)
        return
    if actor_key == "opponent" and user_id != state["opponent"]["user_id"]:
        await query.answer("❌ Сейчас не твой ход!", show_alert=True)
        return

    if state.get("timeout_task"):
        state["timeout_task"].cancel()

    if actor_key == "player":
        attacker = state["player"];   defender = state["opponent"]
        atk_hp   = state["player_hp"];  def_hp  = state["opponent_hp"]
        atk_mana = state["player_mana"]
        atk_st   = state["player_status"]; def_st = state["opponent_status"]
        prev_sp  = state.get("player_prev_spell")
        def_spells = [r["spell_id"] for r in get_user_spells(defender["user_id"])]
    else:
        attacker = state["opponent"]; defender = state["player"]
        atk_hp   = state["opponent_hp"]; def_hp = state["player_hp"]
        atk_mana = state["opponent_mana"]
        atk_st   = state["opponent_status"]; def_st = state["player_status"]
        prev_sp  = state.get("opponent_prev_spell")
        def_spells = [r["spell_id"] for r in get_user_spells(defender["user_id"])]

    result = resolve_turn(
        spell_id, attacker, defender, atk_st, def_st,
        atk_hp, def_hp, atk_mana,
        prev_spell_id=prev_sp,
        defender_spell_ids=def_spells,
    )

    # Применяем результаты
    if actor_key == "player":
        state["player_hp"]       = result["attacker_hp"]
        state["opponent_hp"]     = result["defender_hp"]
        state["player_mana"]     = max(0, atk_mana - result["mana_cost"])
        state["player_status"]   = result["new_atk_status"]
        state["opponent_status"] = result["new_def_status"]
        state["player_prev_spell"] = spell_id
    else:
        state["opponent_hp"]     = result["attacker_hp"]
        state["player_hp"]       = result["defender_hp"]
        state["opponent_mana"]   = max(0, atk_mana - result["mana_cost"])
        state["opponent_status"] = result["new_atk_status"]
        state["player_status"]   = result["new_def_status"]
        state["opponent_prev_spell"] = spell_id

    lang  = attacker.get("lang", "ru")
    sname = spell_display_name(spell_id, lang)
    h     = HOUSE_EMOJI.get(attacker.get("house", ""), "🏠")

    log_entry = f"{h} {attacker['wizard_name']}: {sname} — {result['log']}"
    if result.get("combo"):
        log_entry = f"✨ КОМБО «{result['combo']['name']}»!\n" + log_entry
    if result.get("counter"):
        log_entry += f"\n🛡️ Контр: {result['counter']['desc']}"
    if result.get("flavour"):
        log_entry += f"\n_{result['flavour']}_"
    state["log"].append(log_entry)
    state["log"] = state["log"][-5:]

    # Обновляем панель для обоих
    panel = format_pvp_panel(state)
    await query.edit_message_text(panel, parse_mode="Markdown")

    # Конец дуэли
    if result.get("instant_kill") or state["player_hp"] <= 0 or state["opponent_hp"] <= 0:
        if state["player_hp"] <= 0 and state["opponent_hp"] <= 0:
            winner_id = None
        elif state["player_hp"] <= 0:
            winner_id = state["opponent"]["user_id"]
        else:
            winner_id = state["player"]["user_id"]
        await _end_duel(duel_id, winner_id, ctx)
        return

    state["turn_number"] += 1
    _flip_turn(state)
    await _send_turn(duel_id, ctx)


async def handle_duel_button(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if update.message.text == t(user_id, "btn_duel"):
        await cmd_duel(update, ctx)
        return
    await handle_duel_text_input(update, ctx)


def register_duel_handlers(app):
    app.add_handler(CommandHandler("duel", cmd_duel))
    app.add_handler(CallbackQueryHandler(cb_duel_accept,    pattern=r"^duel_accept:"))
    app.add_handler(CallbackQueryHandler(cb_duel_decline,   pattern=r"^duel_decline:"))
    app.add_handler(CallbackQueryHandler(cb_duel_cast,      pattern=r"^duel_cast:"))
    app.add_handler(CallbackQueryHandler(cb_duel_menu,      pattern=r"^duel_menu:"))
    app.add_handler(CallbackQueryHandler(cb_duel_challenge, pattern=r"^duel_challenge:"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_duel_button), group=4)
