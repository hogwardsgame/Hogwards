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
from utils.helpers import md_escape
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
                     current_mana: int = 9999, prev_spell: str = None,
                     ult_charge: int = 0) -> InlineKeyboardMarkup:
    """Клавиатура заклинаний с предпросмотром урона/маны, комбо, защитой и ультимейтом."""
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
            # Предпросмотр: урон/лечение + мана прямо на кнопке
            stats = []
            if dmg:  stats.append(f"⚔️{dmg}")
            if heal: stats.append(f"💚{heal}")
            stats.append(f"💧{mana}")
            label = f"{combo_mark}{rarity_e}{name} ({' '.join(stats)})"
        buttons.append([InlineKeyboardButton(label, callback_data=f"duel_cast:{duel_id}:{actor}:{sid}")])

    # Тактические кнопки: защита + ультимейт
    tactical = [InlineKeyboardButton("🛡️ Защита (+ману, -урон)", callback_data=f"duel_guard:{duel_id}:{actor}")]
    buttons.append(tactical)
    if ult_charge >= 100:
        buttons.append([InlineKeyboardButton("⚡🔥 УЛЬТИМЕЙТ! 🔥⚡", callback_data=f"duel_ult:{duel_id}:{actor}")])
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

        # Обновляем рейтинг ELO дуэльной лиги
        elo_line = ""
        try:
            from handlers.duel_league import update_elo, _get_division
            res = update_elo(winner_id, loser_id) if loser_id else None
            if res:
                w_change, l_change = res
                from handlers.duel_league import _get_rating
                w_elo = _get_rating(winner_id)["elo"]
                elo_line = f"\n📊 ELO: победитель {w_elo} (+{w_change})"
        except Exception:
            pass
        # Питомец победителя получает опыт
        try:
            from handlers.pets import add_pet_xp
            add_pet_xp(winner_id, 15)
        except Exception:
            pass

        result_text = (
            f"🏆 *{winner_name} победил!*\n"
            f"❌ {loser_name} проиграл\n\n"
            f"Победитель: +{xp_win} XP | +{gold_win} 💰\n"
            f"Проигравший: +{xp_lose} XP | +{gold_lose} 💰"
            f"{elo_line}"
        )
        # Кнопка реванша — другой игрок может перевызвать
        p_uid, o_uid = player["user_id"], opponent["user_id"]
        rematch_p = InlineKeyboardMarkup([[
            InlineKeyboardButton("🔄 Реванш!", callback_data=f"duel_rematch:{o_uid}")
        ]])
        rematch_o = InlineKeyboardMarkup([[
            InlineKeyboardButton("🔄 Реванш!", callback_data=f"duel_rematch:{p_uid}")
        ]])
        try:
            await ctx.bot.send_message(p_uid, result_text, parse_mode="Markdown", reply_markup=rematch_p)
        except Exception:
            pass
        if p_uid != o_uid:
            try:
                await ctx.bot.send_message(o_uid, result_text, parse_mode="Markdown", reply_markup=rematch_o)
            except Exception:
                pass

        # Достижения, задания дня, недельная статистика
        try:
            from handlers.achievements import check_achievements
            await check_achievements(winner_id, ctx)
            if loser_id:
                await check_achievements(loser_id, ctx)
        except Exception:
            pass
        try:
            from handlers.daily_bonus import update_task_progress
            update_task_progress(winner_id, "pvp_total", 1)
            update_task_progress(winner_id, "pvp_wins", 1)
            if loser_id:
                update_task_progress(loser_id, "pvp_total", 1)
        except Exception:
            pass
        try:
            from database import add_weekly_xp, add_weekly_win
            add_weekly_xp(winner_id, xp_win)
            add_weekly_win(winner_id)
            if loser_id:
                add_weekly_xp(loser_id, xp_lose)
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


async def _send_turn(duel_id: int, ctx: ContextTypes.DEFAULT_TYPE, flash: str = ""):
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

    state["log"] = state["log"][-5:]

    # После DoT кто-то может умереть
    if state["player_hp"] <= 0:
        await _end_duel(duel_id, state["opponent"]["user_id"], ctx)
        return
    if state["opponent_hp"] <= 0:
        await _end_duel(duel_id, state["player"]["user_id"], ctx)
        return

    # Кто ходит
    if state["current_turn"] == "player":
        actor, actor_key = state["player"], "player"
        cur_mana = state["player_mana"]
        prev_s   = state.get("player_prev_spell")
        ult      = state.get("player_ult", 0)
    else:
        actor, actor_key = state["opponent"], "opponent"
        cur_mana = state["opponent_mana"]
        prev_s   = state.get("opponent_prev_spell")
        ult      = state.get("opponent_ult", 0)

    actor_spells = [row["spell_id"] for row in get_user_spells(actor["user_id"])]

    # Регенерация маны если нечем кастовать
    if not can_cast_any(actor_spells, cur_mana):
        new_mana = min(actor.get("max_mana", 50), cur_mana + MANA_REGEN_PER_TURN)
        if actor_key == "player":
            state["player_mana"] = new_mana
        else:
            state["opponent_mana"] = new_mana
        state["log"].append(f"✨ {actor['wizard_name']} восстанавливает ману +{MANA_REGEN_PER_TURN} 💧")
        cur_mana = new_mana

    lang   = actor.get("lang", "ru")
    panel  = format_pvp_panel(state, flash=flash)

    active_markup = _spells_keyboard(actor_spells, duel_id, actor_key, lang, cur_mana, prev_s, ult)

    # Редактируем сообщения ОБОИХ игроков (вместо новых)
    await _update_duel_messages(duel_id, ctx, panel, active_markup, actor["user_id"])

    # Таймаут хода
    async def _timeout():
        try:
            await asyncio.sleep(DUEL_TIMEOUT_SECONDS)
            st = _active_duels.get(duel_id)
            if not st:
                return
            # Авто-пропуск хода: переход к сопернику
            st["log"].append(f"⏰ {actor['wizard_name']} пропустил ход (время вышло)")
            st["turn_number"] += 1
            _flip_turn(st)
            await _send_turn(duel_id, ctx)
        except asyncio.CancelledError:
            pass
    state["timeout_task"] = asyncio.get_event_loop().create_task(_timeout())


async def _update_duel_messages(duel_id, ctx, panel, active_markup, active_uid):
    """Редактирует/создаёт сообщения обоих игроков. Активный получает кнопки."""
    state = _active_duels.get(duel_id)
    if not state:
        return
    for who, uid_key, mid_key in (("player","user_id","player_msg_id"),
                                   ("opponent","user_id","opponent_msg_id")):
        person = state[who]
        uid    = person["user_id"]
        is_active = (uid == active_uid)
        markup = active_markup if is_active else None
        mid = state.get(mid_key)
        try:
            if mid:
                await ctx.bot.edit_message_text(
                    chat_id=uid, message_id=mid, text=panel,
                    parse_mode="Markdown", reply_markup=markup
                )
            else:
                msg = await ctx.bot.send_message(uid, panel, parse_mode="Markdown", reply_markup=markup)
                state[mid_key] = msg.message_id
        except Exception as e:
            # Если редактирование не удалось (сообщение удалено) — шлём новое
            try:
                msg = await ctx.bot.send_message(uid, panel, parse_mode="Markdown", reply_markup=markup)
                state[mid_key] = msg.message_id
            except Exception:
                logger.warning("duel msg update uid=%s: %s", uid, e)


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
    _duel_text = (
        f"⚔️ *Дуэль*\n\n"
        f"Твой ID: `{user_id}`\n"
        f"Уровень: {player['level']} | Лимит разницы: ±{MAX_LEVEL_DIFF_PVP}\n"
        f"Дуэлей сегодня: {used}/{DAILY_LIMITS['pvp_duels']}\n\n"
        f"💡 Поделись своим ID с другом, чтобы он мог вызвать тебя командой:\n"
        f"`/duel {user_id}`"
    )
    try:
        from handlers.images import send_with_image
        await send_with_image(update.get_bot(), update.effective_chat.id, "duel",
                              _duel_text, reply_markup=markup)
    except Exception:
        await update.message.reply_text(_duel_text, parse_mode="Markdown", reply_markup=markup)


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
            f"Волшебник *{md_escape(player['wizard_name'])}* "
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
        f"📨 Вызов отправлен игроку *{md_escape(target['wizard_name'])}*!\n"
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
        f"📨 Вызов отправлен *{md_escape(target['wizard_name'])}*!",
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
        # Новое: ультимейт-заряд, защитная стойка, id сообщений для редактирования
        "player_ult":          0,
        "opponent_ult":        0,
        "player_guard":        False,
        "opponent_guard":      False,
        "player_msg_id":       None,
        "opponent_msg_id":     None,
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
            f"✅ *{md_escape(opp['wizard_name'])}* принял вызов!\n\nПервым ходит: *{md_escape(first_name)}*",
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
            f"❌ *{md_escape(opp['wizard_name'])}* отклонил твой вызов.",
            parse_mode="Markdown"
        )
    except Exception:
        pass


async def cb_duel_cast(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query   = update.callback_query
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

    # Если защищающийся в стойке — снижаем входящий урон на 40%
    guard_key = "opponent_guard" if actor_key == "player" else "player_guard"
    if state.get(guard_key):
        reduced = int(result["defender_hp"] + (def_hp - result["defender_hp"]) * 0.4)
        # пересчёт: вернуть 40% урона
        dmg_dealt = def_hp - result["defender_hp"]
        result["defender_hp"] = def_hp - int(dmg_dealt * 0.6)
        state[guard_key] = False  # стойка снимается после удара

    # Применяем результаты
    if actor_key == "player":
        state["player_hp"]       = result["attacker_hp"]
        state["opponent_hp"]     = result["defender_hp"]
        state["player_mana"]     = max(0, atk_mana - result["mana_cost"])
        state["player_status"]   = result["new_atk_status"]
        state["opponent_status"] = result["new_def_status"]
        state["player_prev_spell"] = spell_id
        # Заряд ультимейта: +20 за ход, +15 за крит/комбо
        gain = 20 + (15 if result.get("crit") else 0) + (15 if result.get("combo") else 0)
        state["player_ult"] = min(100, state.get("player_ult", 0) + gain)
    else:
        state["opponent_hp"]     = result["attacker_hp"]
        state["player_hp"]       = result["defender_hp"]
        state["opponent_mana"]   = max(0, atk_mana - result["mana_cost"])
        state["opponent_status"] = result["new_atk_status"]
        state["player_status"]   = result["new_def_status"]
        state["opponent_prev_spell"] = spell_id
        gain = 20 + (15 if result.get("crit") else 0) + (15 if result.get("combo") else 0)
        state["opponent_ult"] = min(100, state.get("opponent_ult", 0) + gain)

    lang  = attacker.get("lang", "ru")
    sname = spell_display_name(spell_id, lang)
    h     = HOUSE_EMOJI.get(attacker.get("house", ""), "🏠")

    log_entry = f"{h} {attacker['wizard_name']}: {sname} — {result['log']}"
    if result.get("combo"):
        log_entry = f"✨🌟 КОМБО «{result['combo']['name']}»! 🌟✨\n" + log_entry
    if result.get("counter"):
        log_entry += f"\n🛡️ Контр: {result['counter']['desc']}"
    if result.get("flavour"):
        log_entry += f"\n_{result['flavour']}_"
    state["log"].append(log_entry)
    state["log"] = state["log"][-5:]

    # Анимация: показываем вспышку каста, затем результат
    flash = ""
    if result.get("crit"):
        flash = "💥💥💥 КРИТИЧЕСКИЙ УДАР! 💥💥💥"
    elif result.get("combo"):
        flash = "✨🌟 КОМБО-ЗАКЛИНАНИЕ! 🌟✨"

    await query.answer()

    # Короткая «анимация» каста на сообщении атакующего
    try:
        cast_msg = f"🪄✨ *{attacker['wizard_name']}* применяет *{sname}*..."
        await query.edit_message_text(cast_msg, parse_mode="Markdown")
        await asyncio.sleep(0.7)
    except Exception:
        pass

    # Конец дуэли?
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
    await _send_turn(duel_id, ctx, flash=flash)


async def cb_duel_guard(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Защитная стойка: восстанавливает ману, снижает следующий входящий урон на 40%."""
    query   = update.callback_query
    parts   = query.data.split(":")
    duel_id, actor_key = int(parts[1]), parts[2]
    user_id = query.from_user.id

    state = _active_duels.get(duel_id)
    if not state:
        await query.answer("Дуэль завершена.", show_alert=True)
        return
    # Проверка хода
    if actor_key == "player" and user_id != state["player"]["user_id"]:
        await query.answer("Сейчас не твой ход!", show_alert=True); return
    if actor_key == "opponent" and user_id != state["opponent"]["user_id"]:
        await query.answer("Сейчас не твой ход!", show_alert=True); return

    if state.get("timeout_task"):
        state["timeout_task"].cancel()
    await query.answer("🛡️ Ты встал в защитную стойку!")

    actor = state["player"] if actor_key == "player" else state["opponent"]
    # Восстановление маны и установка щита
    mana_key = "player_mana" if actor_key == "player" else "opponent_mana"
    guard_key = "player_guard" if actor_key == "player" else "opponent_guard"
    ult_key = "player_ult" if actor_key == "player" else "opponent_ult"
    state[mana_key] = min(actor.get("max_mana", 50), state[mana_key] + 25)
    state[guard_key] = True
    state[ult_key] = min(100, state.get(ult_key, 0) + 10)
    state["log"].append(f"🛡️ {actor['wizard_name']} в защитной стойке (+25💧, -40% урона)")
    state["log"] = state["log"][-5:]

    state["turn_number"] += 1
    _flip_turn(state)
    await _send_turn(duel_id, ctx)


async def cb_duel_ult(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Ультимейт: мощный удар без затрат маны при полной шкале."""
    query   = update.callback_query
    parts   = query.data.split(":")
    duel_id, actor_key = int(parts[1]), parts[2]
    user_id = query.from_user.id

    state = _active_duels.get(duel_id)
    if not state:
        await query.answer("Дуэль завершена.", show_alert=True)
        return
    if actor_key == "player" and user_id != state["player"]["user_id"]:
        await query.answer("Сейчас не твой ход!", show_alert=True); return
    if actor_key == "opponent" and user_id != state["opponent"]["user_id"]:
        await query.answer("Сейчас не твой ход!", show_alert=True); return

    ult_key = "player_ult" if actor_key == "player" else "opponent_ult"
    if state.get(ult_key, 0) < 100:
        await query.answer("Шкала ультимейта не заполнена!", show_alert=True)
        return

    if state.get("timeout_task"):
        state["timeout_task"].cancel()

    if actor_key == "player":
        attacker, defender = state["player"], state["opponent"]
        def_hp = state["opponent_hp"]
    else:
        attacker, defender = state["opponent"], state["player"]
        def_hp = state["player_hp"]

    # Ультимейт-урон: масштабируется от атаки игрока
    ult_dmg = int(attacker.get("attack", 20) * 4 + 80)
    new_def_hp = max(0, def_hp - ult_dmg)

    if actor_key == "player":
        state["opponent_hp"] = new_def_hp
    else:
        state["player_hp"] = new_def_hp
    state[ult_key] = 0  # сброс шкалы

    await query.answer("⚡🔥 УЛЬТИМАТИВНЫЙ УДАР!")
    state["log"].append(f"⚡🔥 {attacker['wizard_name']} применяет УЛЬТИМЕЙТ! −{ult_dmg} HP!")
    state["log"] = state["log"][-5:]

    flash = "⚡🔥💥 УЛЬТИМАТИВНЫЙ УДАР! 💥🔥⚡"

    # Анимация
    try:
        await query.edit_message_text(
            f"⚡🔥 *{attacker['wizard_name']}* концентрирует всю магическую силу...",
            parse_mode="Markdown")
        await asyncio.sleep(0.9)
    except Exception:
        pass

    # Проверка смерти
    if new_def_hp <= 0:
        winner_id = attacker["user_id"]
        await _end_duel(duel_id, winner_id, ctx)
        return

    state["turn_number"] += 1
    _flip_turn(state)
    await _send_turn(duel_id, ctx, flash=flash)


async def cb_duel_rematch(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Реванш — повторный вызов того же соперника одной кнопкой."""
    query   = update.callback_query
    user_id = query.from_user.id
    target_id = int(query.data.split(":")[1])

    if not user_exists(user_id):
        await query.answer("Сначала зарегистрируйся через /start.", show_alert=True)
        return

    # Проверка дневного лимита
    used = get_daily_limit(user_id, "pvp_duels")
    if used >= DAILY_LIMITS["pvp_duels"]:
        await query.answer("На сегодня дуэли закончились!", show_alert=True)
        return

    target = get_user(target_id)
    if not target:
        await query.answer("Соперник не найден.", show_alert=True)
        return
    if target_id == user_id:
        await query.answer("Нельзя вызвать самого себя.", show_alert=True)
        return

    player = get_user(user_id)
    if abs(player["level"] - target["level"]) > MAX_LEVEL_DIFF_PVP:
        await query.answer(f"Разница в уровнях слишком велика (макс. ±{MAX_LEVEL_DIFF_PVP}).", show_alert=True)
        return

    # Уже есть активный вызов от этого игрока?
    if user_id in _pending_invites:
        await query.answer("У тебя уже есть активный вызов.", show_alert=True)
        return

    await query.answer("🔄 Отправляю вызов на реванш!")

    markup = InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ Принять", callback_data=f"duel_accept:{user_id}"),
        InlineKeyboardButton("❌ Отклонить", callback_data=f"duel_decline:{user_id}"),
    ]])
    try:
        await ctx.bot.send_message(
            target_id,
            f"🔄 *Вызов на РЕВАНШ!*\n\n"
            f"Волшебник *{md_escape(player['wizard_name'])}* "
            f"({HOUSE_EMOJI.get(player['house'], '🏠')}, ур.{player['level']}) "
            f"хочет реванш!\n\nЕсть {DUEL_INVITE_TIMEOUT} секунд.",
            parse_mode="Markdown",
            reply_markup=markup,
        )
    except Exception:
        await query.edit_message_text("❌ Не удалось отправить вызов — соперник недоступен.")
        return

    try:
        await query.edit_message_text(
            f"📨 Вызов на реванш отправлен *{md_escape(target['wizard_name'])}*!",
            parse_mode="Markdown"
        )
    except Exception:
        pass

    async def _expire():
        await asyncio.sleep(DUEL_INVITE_TIMEOUT)
        _pending_invites.pop(user_id, None)
    task = asyncio.get_event_loop().create_task(_expire())
    _pending_invites[user_id] = {"opponent_id": target_id, "task": task}


async def handle_duel_button(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Handles free-text input during duel flow (e.g. target user ID)."""
    if not ctx.user_data.get("awaiting_duel_id"):
        return
    await handle_duel_text_input(update, ctx)


def register_duel_handlers(app):
    app.add_handler(CommandHandler("duel", cmd_duel))
    app.add_handler(CallbackQueryHandler(cb_duel_accept,    pattern=r"^duel_accept:"))
    app.add_handler(CallbackQueryHandler(cb_duel_decline,   pattern=r"^duel_decline:"))
    app.add_handler(CallbackQueryHandler(cb_duel_cast,      pattern=r"^duel_cast:"))
    app.add_handler(CallbackQueryHandler(cb_duel_guard,     pattern=r"^duel_guard:"))
    app.add_handler(CallbackQueryHandler(cb_duel_ult,       pattern=r"^duel_ult:"))
    app.add_handler(CallbackQueryHandler(cb_duel_menu,      pattern=r"^duel_menu:"))
    app.add_handler(CallbackQueryHandler(cb_duel_challenge, pattern=r"^duel_challenge:"))
    app.add_handler(CallbackQueryHandler(cb_duel_rematch,   pattern=r"^duel_rematch:"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_duel_button), group=4)
