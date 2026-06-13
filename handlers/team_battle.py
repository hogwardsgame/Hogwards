"""
Командные бои 3×3 — отряд против отряда.
Симулируется автоматически с синергией заклинаний, ролями и общим зрелищем.
Запускается лидером отряда, который вызывает другой отряд.
"""
import logging
import random
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler
from database import (
    user_exists, get_user, get_conn, execute, fetchrow, fetchall,
    add_xp, add_gold, get_squad, get_squad_members,
)
from utils.i18n import t
from utils.helpers import md_escape, house_emoji, progress_bar
from game.battle_engine import HOUSE_EMOJI

logger = logging.getLogger(__name__)

TEAM_SIZE = 3
_pending_team_challenges: dict[int, dict] = {}  # squad_id -> {opponent_squad, task}

def _squad_of(user_id: int):
    u = get_user(user_id)
    return u.get("squad_id") if u else None

def _team_power(members: list) -> int:
    """Суммарная боевая мощь команды."""
    total = 0
    for m in members:
        u = get_user(m["user_id"])
        if u:
            total += u["attack"] * 2 + u["defense"] + u["max_hp"] // 5 + u["level"] * 3
    return total

def _team_roster(members: list) -> str:
    lines = []
    for m in members[:TEAM_SIZE]:
        u = get_user(m["user_id"])
        if u:
            lines.append(f"  {house_emoji(u['house'])} {md_escape(u['wizard_name'])} (ур.{u['level']}, ⚔️{u['attack']})")
    return "\n".join(lines)

async def cmd_team_battle(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not user_exists(user_id):
        await update.message.reply_text(t(user_id, "not_registered"))
        return

    squad_id = _squad_of(user_id)
    if not squad_id:
        await update.message.reply_text(
            "🛡️ *Командные бои 3×3*\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "Тебе нужен отряд! Вступи или создай отряд через раздел «Отряд».\n\n"
            "В командном бою три волшебника твоего отряда сражаются против "
            "трёх из вражеского — с синергией заклинаний и общей славой!",
            parse_mode="Markdown"
        )
        return

    squad = get_squad(squad_id)
    members = get_squad_members(squad_id)
    if len(members) < TEAM_SIZE:
        await update.message.reply_text(
            f"🛡️ *Командные бои 3×3*\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"В твоём отряде «{md_escape(squad['name'])}» только {len(members)} "
            f"из {TEAM_SIZE} нужных бойцов.\n\n"
            f"Набери минимум {TEAM_SIZE} участников чтобы участвовать в боях 3×3!",
            parse_mode="Markdown"
        )
        return

    # Лидер может вызвать другой отряд
    is_leader = (squad.get("leader_id") == user_id)
    text = (
        f"🛡️ *Командные бои 3×3*\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"Отряд: *{md_escape(squad['name'])}*\n"
        f"Бойцов: {len(members)}\n\n"
        f"{_team_roster(members)}\n\n"
    )
    if is_leader:
        text += "Ты лидер — можешь вызвать другой отряд на бой!"
        markup = InlineKeyboardMarkup([[
            InlineKeyboardButton("⚔️ Найти соперника", callback_data="team_find")
        ]])
    else:
        text += "_Только лидер отряда может начинать командные бои._"
        markup = None
    await update.message.reply_text(text, parse_mode="Markdown", reply_markup=markup)

async def cb_team_find(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query   = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    squad_id = _squad_of(user_id)
    if not squad_id:
        await query.answer("У тебя нет отряда.", show_alert=True)
        return

    # Ищем другие отряды с >= 3 бойцами
    try:
        with get_conn() as conn:
            squads = fetchall(conn, """
                SELECT s.id, s.name, COUNT(u.user_id) as cnt
                FROM squads s JOIN users u ON u.squad_id = s.id
                WHERE s.id != %s
                GROUP BY s.id, s.name
                HAVING COUNT(u.user_id) >= %s
                ORDER BY RANDOM() LIMIT 5
            """, squad_id, TEAM_SIZE)
    except Exception:
        squads = []

    if not squads:
        await query.edit_message_text(
            "😔 Сейчас нет других отрядов с 3+ бойцами для боя.\n"
            "Попробуй позже, когда наберётся больше команд!"
        )
        return

    buttons = [[InlineKeyboardButton(
        f"⚔️ {s['name']} ({s['cnt']} бойцов)", callback_data=f"team_fight:{s['id']}"
    )] for s in squads]
    await query.edit_message_text(
        "⚔️ *Выбери отряд-соперника:*\n━━━━━━━━━━━━━━━━━━━━",
        parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(buttons)
    )

async def cb_team_fight(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query   = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    enemy_squad_id = int(query.data.split(":")[1])

    my_squad_id = _squad_of(user_id)
    if not my_squad_id:
        await query.answer("У тебя нет отряда.", show_alert=True)
        return

    my_squad    = get_squad(my_squad_id)
    enemy_squad = get_squad(enemy_squad_id)
    if not enemy_squad:
        await query.edit_message_text("Отряд-соперник не найден.")
        return

    my_members    = get_squad_members(my_squad_id)[:TEAM_SIZE]
    enemy_members = get_squad_members(enemy_squad_id)[:TEAM_SIZE]

    await query.edit_message_text(
        f"⚔️ *БИТВА ОТРЯДОВ 3×3*\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🛡️ {md_escape(my_squad['name'])}\n"
        f"        ⚔️ VS ⚔️\n"
        f"🛡️ {md_escape(enemy_squad['name'])}\n\n"
        f"_Бой начинается..._",
        parse_mode="Markdown"
    )
    await asyncio.sleep(1.5)

    # Симуляция боя с синергией
    result = await _simulate_team_battle(my_squad, my_members, enemy_squad, enemy_members, ctx)

    # Награды
    won = result["winner_squad_id"] == my_squad_id
    win_members = my_members if won else enemy_members
    lose_members = enemy_members if won else my_members

    for m in win_members:
        add_xp(m["user_id"], 150)
        add_gold(m["user_id"], 80)
    for m in lose_members:
        add_xp(m["user_id"], 40)
        add_gold(m["user_id"], 15)

    # Очки факультету победителей (через лидера)
    winner_squad_name = my_squad["name"] if won else enemy_squad["name"]

    # Шлём итог всем участникам обоих отрядов
    all_uids = [m["user_id"] for m in my_members + enemy_members]
    for uid in all_uids:
        try:
            await ctx.bot.send_message(uid, result["log"], parse_mode="Markdown")
        except Exception:
            pass

async def _simulate_team_battle(sq_a, members_a, sq_b, members_b, ctx):
    """Симуляция 3×3 с синергией. Возвращает итог."""
    power_a = _team_power(members_a)
    power_b = _team_power(members_b)

    # Синергия: одинаковые факультеты в команде дают бонус
    def _synergy(members):
        houses = [get_user(m["user_id"]).get("house") for m in members if get_user(m["user_id"])]
        bonus = 0
        for h in set(houses):
            cnt = houses.count(h)
            if cnt >= 2:
                bonus += cnt * 15  # бонус за слаженность факультета
        return bonus

    syn_a = _synergy(members_a)
    syn_b = _synergy(members_b)
    total_a = power_a + syn_a + random.randint(0, 50)
    total_b = power_b + syn_b + random.randint(0, 50)

    winner_squad = sq_a if total_a >= total_b else sq_b
    win_members  = members_a if total_a >= total_b else members_b
    lose_squad   = sq_b if total_a >= total_b else sq_a

    # Раунды-зрелище: 3 схватки
    log_lines = [
        f"⚔️ *БИТВА ОТРЯДОВ 3×3*",
        f"━━━━━━━━━━━━━━━━━━━━",
        f"🛡️ {md_escape(sq_a['name'])} (мощь {power_a}{'+'+str(syn_a)+' синергия' if syn_a else ''})",
        f"🛡️ {md_escape(sq_b['name'])} (мощь {power_b}{'+'+str(syn_b)+' синергия' if syn_b else ''})",
        f"━━━━━━━━━━━━━━━━━━━━",
    ]
    # Поединки бойцов
    for i in range(TEAM_SIZE):
        a = get_user(members_a[i]["user_id"]) if i < len(members_a) else None
        b = get_user(members_b[i]["user_id"]) if i < len(members_b) else None
        if a and b:
            a_roll = a["attack"] + a["level"]*2 + random.randint(0,30)
            b_roll = b["attack"] + b["level"]*2 + random.randint(0,30)
            if a_roll >= b_roll:
                log_lines.append(f"⚔️ {house_emoji(a['house'])} {md_escape(a['wizard_name'])} победил {md_escape(b['wizard_name'])}")
            else:
                log_lines.append(f"⚔️ {house_emoji(b['house'])} {md_escape(b['wizard_name'])} победил {md_escape(a['wizard_name'])}")

    log_lines.append("━━━━━━━━━━━━━━━━━━━━")
    log_lines.append(f"🏆 *Победил отряд {md_escape(winner_squad['name'])}!*")
    log_lines.append(f"Победители: +150 XP, +80 💰  •  Проигравшие: +40 XP, +15 💰")
    if max(syn_a, syn_b) > 0:
        log_lines.append(f"\n_💡 Синергия факультетов решила исход! Собирай отряд из одного факультета._")

    return {
        "winner_squad_id": winner_squad["id"],
        "log": "\n".join(log_lines),
    }

def register_team_battle_handlers(app):
    app.add_handler(CommandHandler("teambattle", cmd_team_battle))
    app.add_handler(CommandHandler("team3v3", cmd_team_battle))
    app.add_handler(CallbackQueryHandler(cb_team_find,  pattern=r"^team_find$"))
    app.add_handler(CallbackQueryHandler(cb_team_fight, pattern=r"^team_fight:"))
