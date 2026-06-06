# handlers/duel.py

import random
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup
)
from telegram.ext import ContextTypes

from database import (
    get_user,
    add_xp,
    add_gold,
    execute,
    get_conn
)

from game.battle_engine import BattleState, apply_spell, next_turn, is_finished, get_winner
from game.spells import SPELLS


# ─────────────────────────────────────────────
# 🧠 ВРЕМЕННОЕ ХРАНИЛИЩЕ БОЁВ (в памяти)
# позже заменим на Redis или БД
# ─────────────────────────────────────────────

BATTLES = {}


# ─────────────────────────────────────────────
# ⚔️ ВЫЗОВ НА ДУЭЛЬ
# ─────────────────────────────────────────────

async def duel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    user = get_user(user_id)
    if not user:
        await update.message.reply_text("Ты ещё не зарегистрирован.")
        return

    keyboard = [
        [InlineKeyboardButton("🎯 Случайный соперник", callback_data="duel_random")]
    ]

    await update.message.reply_text(
        "⚔️ Дуэльная арена\nВыбери соперника:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


# ─────────────────────────────────────────────
# 🎯 ПОИСК СОПЕРНИКА
# ─────────────────────────────────────────────

async def duel_random(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    challenger_id = query.from_user.id

    with get_conn() as conn:
        opponent = conn.cursor()
        opponent.execute(
            "SELECT * FROM users WHERE user_id != %s ORDER BY RANDOM() LIMIT 1",
            (challenger_id,)
        )
        enemy = opponent.fetchone()

    if not enemy:
        await query.edit_message_text("Нет доступных соперников.")
        return

    # ─────────────────────────────
    # СОЗДАЁМ БОЙ
    # ─────────────────────────────

    p1 = get_user(challenger_id)
    p2 = get_user(enemy["user_id"])

    battle = BattleState(p1, p2)

    battle_id = f"{challenger_id}_{enemy['user_id']}_{random.randint(1000,9999)}"
    BATTLES[battle_id] = battle

    # ─────────────────────────────
    # ПЕРВЫЙ ХОД
    # ─────────────────────────────

    await send_battle_message(query, battle_id, battle)


# ─────────────────────────────────────────────
# ⚔️ ОТПРАВКА БОЯ В TELEGRAM
# ─────────────────────────────────────────────

async def send_battle_message(query, battle_id, battle: BattleState):

    user1 = battle.p1
    user2 = battle.p2

    text = f"""
⚔️ ДУЭЛЬ

🧙 {user1['wizard_name']} vs {user2['wizard_name']}

❤️ {battle.hp[user1['user_id']]} HP  |  ❤️ {battle.hp[user2['user_id']]} HP
💧 {battle.mana[user1['user_id']]} MP | 💧 {battle.mana[user2['user_id']]} MP

🎯 Ход: {battle.turn}
"""

    keyboard = []

    for spell_id, spell in list(SPELLS.items())[:6]:
        keyboard.append([
            InlineKeyboardButton(
                f"{spell.name} ({spell.mana_cost})",
                callback_data=f"cast:{battle_id}:{spell_id}"
            )
        ])

    await query.edit_message_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


# ─────────────────────────────────────────────
# 🔮 ИСПОЛЬЗОВАНИЕ ЗАКЛИНАНИЯ
# ─────────────────────────────────────────────

async def cast_spell(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    _, battle_id, spell_id = query.data.split(":")

    battle = BATTLES.get(battle_id)
    if not battle:
        await query.edit_message_text("Бой не найден.")
        return

    attacker_id = query.from_user.id

    # определяем врага
    if attacker_id == battle.p1["user_id"]:
        defender_id = battle.p2["user_id"]
    else:
        defender_id = battle.p1["user_id"]

    # ─────────────────────────────
    # ХОД
    # ─────────────────────────────

    result = apply_spell(battle, attacker_id, defender_id, spell_id)

    if "error" in result:
        await query.answer(result["error"], show_alert=True)
        return

    # следующий ход
    next_turn(battle)

    # победа?
    if is_finished(battle):
        winner_id = get_winner(battle)

        reward_winner(winner_id)

        await query.edit_message_text(
            f"🏆 Дуэль завершена!\nПобедитель: {winner_id}"
        )
        return

    # обновляем экран
    await send_battle_message(query, battle_id, battle)


# ─────────────────────────────────────────────
# 🏆 НАГРАДЫ
# ─────────────────────────────────────────────

def reward_winner(user_id: int):
    xp = random.randint(50, 150)
    gold = random.randint(20, 80)

    add_xp(user_id, xp)
    add_gold(user_id, gold)


# ─────────────────────────────────────────────
# 🔗 РЕГИСТРАЦИЯ HANDLER'ОВ
# ─────────────────────────────────────────────

def register_duel_handlers(app):
    from telegram.ext import CallbackQueryHandler, CommandHandler

    app.add_handler(CommandHandler("duel", duel_command))
    app.add_handler(CallbackQueryHandler(duel_random, pattern="^duel_random$"))
    app.add_handler(CallbackQueryHandler(cast_spell, pattern="^cast:"))
