"""
Tournament — автоматические PvP-турниры.
Сетка на 8 участников. Раз в 48 часов. Награды победителям.
Команды: /tournament
"""
import asyncio
import logging
import random
from datetime import datetime, timezone
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler
from database import (
    get_user, user_exists, add_xp, add_gold, add_house_points,
    get_conn, execute, fetchrow, fetchall, fetchval,
)
from game.battle_engine import fresh_status, resolve_turn, tick_status, determine_turn_order
from game.spells import SPELLS
from utils.i18n import t
from utils.helpers import md_escape
from config import TOURNAMENT_ENTRY_FEE, XP_REWARDS, GOLD_REWARDS, HOUSE_POINTS_REWARDS

logger = logging.getLogger(__name__)

TOURNAMENT_MAX_PLAYERS = 8

TOURNAMENT_REWARDS = {
    1: {"xp": 800,  "gold": 400, "title": "🏆 Чемпион турнира"},
    2: {"xp": 400,  "gold": 200, "title": "🥈 Финалист"},
    3: {"xp": 200,  "gold": 100, "title": "🥉 Полуфиналист"},
}

# in-memory: активный турнир
_active_tournament: dict | None = None
_registration_open: bool = False
_registrants: list[int] = []


def _get_active_tournament_id() -> int | None:
    with get_conn() as conn:
        row = fetchrow(conn, "SELECT id FROM tournaments WHERE status IN ('pending','active') ORDER BY id DESC LIMIT 1")
        return row["id"] if row else None


async def cmd_tournament(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not user_exists(user_id):
        await update.message.reply_text(t(user_id, "not_registered"))
        return

    user = get_user(user_id)

    # Проверяем регистрацию
    already_in = user_id in _registrants

    if _registration_open:
        text = (
            f"🏆 *Турнир волшебников*\n\n"
            f"📋 Регистрация открыта!\n"
            f"Участников: {len(_registrants)}/{TOURNAMENT_MAX_PLAYERS}\n"
            f"Взнос: {TOURNAMENT_ENTRY_FEE} 💰\n\n"
            f"*Призы:*\n"
            f"🥇 1-е место: {TOURNAMENT_REWARDS[1]['xp']} XP + {TOURNAMENT_REWARDS[1]['gold']} 💰\n"
            f"🥈 2-е место: {TOURNAMENT_REWARDS[2]['xp']} XP + {TOURNAMENT_REWARDS[2]['gold']} 💰\n"
            f"🥉 3-е место: {TOURNAMENT_REWARDS[3]['xp']} XP + {TOURNAMENT_REWARDS[3]['gold']} 💰"
        )
        if already_in:
            markup = InlineKeyboardMarkup([[
                InlineKeyboardButton("✅ Ты уже зарегистрирован", callback_data="tour_already")
            ]])
        elif user["gold"] < TOURNAMENT_ENTRY_FEE:
            markup = InlineKeyboardMarkup([[
                InlineKeyboardButton(f"❌ Мало золота ({user['gold']}/{TOURNAMENT_ENTRY_FEE})", callback_data="tour_no_gold")
            ]])
        else:
            markup = InlineKeyboardMarkup([[
                InlineKeyboardButton(f"⚔️ Зарегистрироваться ({TOURNAMENT_ENTRY_FEE} 💰)", callback_data="tour_register")
            ]])
        await update.message.reply_text(text, parse_mode="Markdown", reply_markup=markup)
        return

    # Нет открытой регистрации — показываем последний турнир
    t_id = _get_active_tournament_id()
    if t_id:
        with get_conn() as conn:
            tour = fetchrow(conn, "SELECT * FROM tournaments WHERE id = %s", t_id)
            parts = fetchall(conn, """
                SELECT u.wizard_name, u.house, p.wins, p.losses, p.eliminated
                FROM tournament_participants p
                JOIN users u ON p.user_id = u.user_id
                WHERE p.tournament_id = %s
                ORDER BY p.wins DESC, p.losses ASC
            """, t_id)

        lines = []
        for p in parts:
            status = "❌" if p["eliminated"] else "✅"
            lines.append(f"{status} {md_escape(p['wizard_name'])} — {p['wins']}П/{p['losses']}П")

        await update.message.reply_text(
            f"🏆 *Турнир #{t_id}* — {tour['status']}\n\n"
            + ("\n".join(lines) if lines else "Нет участников"),
            parse_mode="Markdown"
        )
    else:
        await update.message.reply_text(
            "🏆 *Турнир волшебников*\n\n"
            "Сейчас нет активного турнира.\n"
            "Следующий начнётся автоматически.\n\n"
            "💡 Администратор может запустить турнир командой /admin_tournament",
            parse_mode="Markdown"
        )


async def cb_tour_register(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query   = update.callback_query
    user_id = query.from_user.id

    if not _registration_open:
        await query.edit_message_text("❌ Регистрация закрыта.")
        return
    if user_id in _registrants:
        await query.answer("✅ Ты уже зарегистрирован!", show_alert=True)
        return

    user = get_user(user_id)
    if user["gold"] < TOURNAMENT_ENTRY_FEE:
        await query.answer(f"❌ Нужно {TOURNAMENT_ENTRY_FEE} 💰", show_alert=True)
        return

    with get_conn() as conn:
        execute(conn, "UPDATE users SET gold = gold - %s WHERE user_id = %s", TOURNAMENT_ENTRY_FEE, user_id)

    _registrants.append(user_id)
    await query.edit_message_text(
        f"✅ *{md_escape(user['wizard_name'])}* зарегистрирован!\n\n"
        f"Участников: {len(_registrants)}/{TOURNAMENT_MAX_PLAYERS}\n"
        f"Взнос {TOURNAMENT_ENTRY_FEE} 💰 списан.",
        parse_mode="Markdown"
    )

    if len(_registrants) >= TOURNAMENT_MAX_PLAYERS:
        asyncio.get_event_loop().create_task(_start_tournament(ctx))


async def cb_tour_already(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("✅ Ты уже зарегистрирован!", show_alert=True)


async def cb_tour_no_gold(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("❌ Недостаточно золота.", show_alert=True)


def _simulate_duel(player_a: dict, player_b: dict) -> dict:
    """Симулирует дуэль между двумя игроками. Возвращает {winner, loser, log}."""
    spells_a = [r["spell_id"] for r in _get_player_spells(player_a["user_id"])]
    spells_b = [r["spell_id"] for r in _get_player_spells(player_b["user_id"])]

    if not spells_a:
        spells_a = ["expelliarmus", "stupefy"]
    if not spells_b:
        spells_b = ["expelliarmus", "stupefy"]

    hp_a   = player_a["hp"]
    hp_b   = player_b["hp"]
    mana_a = player_a["mana"]
    mana_b = player_b["mana"]
    st_a   = fresh_status()
    st_b   = fresh_status()
    log    = []
    turn   = determine_turn_order(player_a["speed"], player_b["speed"])

    for _ in range(30):
        if hp_a <= 0 or hp_b <= 0:
            break

        if turn == "a":
            spell_id = random.choice(spells_a)
            result   = resolve_turn(spell_id, player_a, player_b, st_a, st_b, hp_a, hp_b, mana_a)
            hp_a     = result["attacker_hp"]
            hp_b     = result["defender_hp"]
            mana_a   = max(0, mana_a - result["mana_cost"])
            st_a     = result["new_atk_status"]
            st_b     = result["new_def_status"]
            log.append(f"{player_a['wizard_name']}: {result['log']}")
            if result.get("instant_kill") or hp_b <= 0:
                break
            st_a, dot_a = tick_status(st_a)
            st_b, dot_b = tick_status(st_b)
            hp_a = max(0, hp_a - dot_a)
            hp_b = max(0, hp_b - dot_b)
            turn = "b"
        else:
            spell_id = random.choice(spells_b)
            result   = resolve_turn(spell_id, player_b, player_a, st_b, st_a, hp_b, hp_a, mana_b)
            hp_b     = result["attacker_hp"]
            hp_a     = result["defender_hp"]
            mana_b   = max(0, mana_b - result["mana_cost"])
            st_b     = result["new_atk_status"]
            st_a     = result["new_def_status"]
            log.append(f"{player_b['wizard_name']}: {result['log']}")
            if result.get("instant_kill") or hp_a <= 0:
                break
            st_a, dot_a = tick_status(st_a)
            st_b, dot_b = tick_status(st_b)
            hp_a = max(0, hp_a - dot_a)
            hp_b = max(0, hp_b - dot_b)
            turn = "a"

    # Победитель — у кого больше HP (или рандом при ничье)
    if hp_a > hp_b:
        winner, loser = player_a, player_b
    elif hp_b > hp_a:
        winner, loser = player_b, player_a
    else:
        winner, loser = random.choice([(player_a, player_b), (player_b, player_a)])

    return {"winner": winner, "loser": loser, "log": log[-3:]}


def _get_player_spells(user_id: int) -> list:
    with get_conn() as conn:
        return fetchall(conn, "SELECT spell_id FROM user_spells WHERE user_id = %s", user_id)


async def _start_tournament(ctx, registrant_ids: list | None = None):
    """Запуск турнира. Вызывается автоматически или администратором."""
    global _active_tournament, _registration_open, _registrants

    ids = registrant_ids or _registrants[:]
    _registration_open = False
    _registrants.clear()

    if len(ids) < 2:
        logger.warning("Турнир: недостаточно участников.")
        return

    # Перемешиваем и берём первых 8
    random.shuffle(ids)
    ids = ids[:TOURNAMENT_MAX_PLAYERS]

    with get_conn() as conn:
        execute(conn, "INSERT INTO tournaments (status, started_at) VALUES ('active', NOW())")
        tour_row = fetchrow(conn, "SELECT id FROM tournaments ORDER BY id DESC LIMIT 1")
        tour_id  = tour_row["id"]
        for uid in ids:
            execute(conn, """
                INSERT INTO tournament_participants (tournament_id, user_id)
                VALUES (%s, %s) ON CONFLICT DO NOTHING
            """, tour_id, uid)

    # Уведомляем участников
    players = [get_user(uid) for uid in ids]
    players = [p for p in players if p]

    announce = (
        f"🏆 *Турнир #{tour_id} начинается!*\n\n"
        f"Участников: {len(players)}\n\n"
        + "\n".join(f"⚔️ {md_escape(p['wizard_name'])} (ур.{p['level']})" for p in players)
    )
    for p in players:
        try:
            await ctx.bot.send_message(p["user_id"], announce, parse_mode="Markdown")
        except Exception:
            pass
    await asyncio.sleep(3)

    # Олимпийская сетка
    remaining = list(players)
    round_num = 1

    while len(remaining) > 1:
        random.shuffle(remaining)
        next_round = []
        round_results = [f"⚔️ *Раунд {round_num}*"]

        pairs = [(remaining[i], remaining[i+1]) for i in range(0, len(remaining)-1, 2)]
        if len(remaining) % 2 == 1:
            # Нечётный — автопроход
            bye = remaining[-1]
            next_round.append(bye)
            round_results.append(f"🎯 {md_escape(bye['wizard_name'])} — проходит автоматически")

        for a, b in pairs:
            result = _simulate_duel(a, b)
            winner = result["winner"]
            loser  = result["loser"]
            next_round.append(winner)

            # Обновляем статистику
            with get_conn() as conn:
                execute(conn, """
                    UPDATE tournament_participants
                    SET wins = wins + 1
                    WHERE tournament_id = %s AND user_id = %s
                """, tour_id, winner["user_id"])
                execute(conn, """
                    UPDATE tournament_participants
                    SET losses = losses + 1, eliminated = TRUE
                    WHERE tournament_id = %s AND user_id = %s
                """, tour_id, loser["user_id"])

            round_results.append(
                f"✅ {md_escape(winner['wizard_name'])} победил {md_escape(loser['wizard_name'])}\n"
                + "\n".join(f"  _{l}_" for l in result["log"])
            )

        round_text = "\n\n".join(round_results)
        for p in remaining:
            try:
                await ctx.bot.send_message(p["user_id"], round_text, parse_mode="Markdown")
            except Exception:
                pass

        remaining = next_round
        round_num += 1
        await asyncio.sleep(2)

    # Победитель
    if not remaining:
        return

    champion = remaining[0]
    with get_conn() as conn:
        execute(conn, "UPDATE tournaments SET status = 'finished', ended_at = NOW(), winner_id = %s WHERE id = %s",
                champion["user_id"], tour_id)

    # Выдаём призы
    for place, reward in TOURNAMENT_REWARDS.items():
        if place == 1:
            uid = champion["user_id"]
        else:
            # 2-3 места — из выбывших с наибольшим числом побед
            with get_conn() as conn:
                rows = fetchall(conn, """
                    SELECT user_id FROM tournament_participants
                    WHERE tournament_id = %s AND eliminated = TRUE
                    ORDER BY wins DESC LIMIT 1
                """, tour_id)
            if not rows:
                continue
            uid = rows[0]["user_id"]

        add_xp(uid, reward["xp"])
        add_gold(uid, reward["gold"])
        u = get_user(uid)
        if u:
            add_house_points(uid, u["house"], HOUSE_POINTS_REWARDS["tournament_win"], "tournament_win")
            with get_conn() as conn:
                execute(conn, """
                    INSERT INTO user_titles (user_id, title_id) VALUES (%s, %s) ON CONFLICT DO NOTHING
                """, uid, f"tournament_{tour_id}_place{place}")
        try:
            await ctx.bot.send_message(uid,
                f"🏆 *Турнир #{tour_id} завершён!*\n\n"
                f"Твоё место: {place}\n"
                f"+{reward['xp']} XP | +{reward['gold']} 💰\n"
                f"Титул: {reward['title']}",
                parse_mode="Markdown")
        except Exception:
            pass

    # Финальное объявление
    final_text = (
        f"🏆 *Турнир #{tour_id} завершён!*\n\n"
        f"👑 Чемпион: *{md_escape(champion['wizard_name'])}*\n"
        f"Поздравляем!"
    )
    for p in players:
        try:
            await ctx.bot.send_message(p["user_id"], final_text, parse_mode="Markdown")
        except Exception:
            pass


async def open_tournament_registration(ctx, bot=None):
    """Открыть регистрацию. Вызывается планировщиком или /admin_tournament."""
    global _registration_open, _registrants
    _registration_open = True
    _registrants.clear()

    b = bot or ctx.bot
    with get_conn() as conn:
        users = fetchall(conn, "SELECT user_id FROM users WHERE is_banned = FALSE ORDER BY RANDOM() LIMIT 200")
    for row in users:
        try:
            await b.send_message(row["user_id"],
                f"🏆 *Регистрация на турнир открыта!*\n\n"
                f"Взнос: {TOURNAMENT_ENTRY_FEE} 💰\n"
                f"Максимум участников: {TOURNAMENT_MAX_PLAYERS}\n\n"
                f"Напиши /tournament для участия!",
                parse_mode="Markdown")
        except Exception:
            pass

    # Автозакрытие через 30 минут
    async def _auto_close():
        await asyncio.sleep(30 * 60)
        if _registration_open and len(_registrants) >= 2:
            await _start_tournament(ctx, _registrants[:])

    asyncio.get_event_loop().create_task(_auto_close())


def register_tournament_handlers(app):
    app.add_handler(CommandHandler("tournament", cmd_tournament))
    app.add_handler(CallbackQueryHandler(cb_tour_register, pattern=r"^tour_register$"))
    app.add_handler(CallbackQueryHandler(cb_tour_already,  pattern=r"^tour_already$"))
    app.add_handler(CallbackQueryHandler(cb_tour_no_gold,  pattern=r"^tour_no_gold$"))
