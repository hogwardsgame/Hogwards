# handlers/duel.py

import random
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler

from database import get_user, add_xp, add_gold, get_conn
from game.battle_engine import BattleState, apply_spell, next_turn, is_finished, get_winner
from game.spells import SPELLS


# ─────────────────────────────────────────────
# 🧠 БОИ В ПАМЯТИ
# ─────────────────────────────────────────────

BATTLES = {}


# ─────────────────────────────────────────────
# ⚔️ /duel
# ─────────────────────────────────────────────

async def duel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = get_user(user_id)

    if not user:
        await update.message.reply_text("Ты не зарегистрирован.")
        return

    keyboard = [
        [InlineKeyboardButton("🎯 Найти соперника", callback_data="duel_find")]
    ]

    await update.message.reply_text(
        "⚔️ Дуэльная арена\nНажми кнопку для поиска боя",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


# ─────────────────────────────────────────────
# 🎯 ПОИСК СОПЕРНИКА
# ─────────────────────────────────────────────

async def duel_find(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id

    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT * FROM users WHERE user_id != %s ORDER BY RANDOM() LIMIT 1",
            (user_id,)
        )
        enemy = cur.fetchone()

    if not enemy:
        await query.edit_message_text("Нет соперников.")
        return

    p1 = get_user(user_id)
    p2 = get_user(enemy["user_id"])

    battle = BattleState(p1, p2)

    battle_id = f"{user_id}_{enemy['user_id']}_{random.randint(1000,9999)}"
    BATTLES[battle_id] = battle

    await send_battle(query, battle_id, battle)


# ─────────────────────────────────────────────
# ⚔️ ОТОБРАЖЕНИЕ БОЯ
# ─────────────────────────────────────────────

async def send_battle(query, battle_id, battle: BattleState):

    p1 = battle.p1
    p2 = battle.p2

    def format_status(uid):
        if not battle.status[uid]:
            return "—"
        return ", ".join(battle.status[uid])

    text = f"""
⚔️ ДУЭЛЬ

🧙 {p1['wizard_name']} vs {p2['wizard_name']}

❤️ HP: {battle.hp[p1['user_id']]} | {battle.hp[p2['user_id']]}
💧 MP: {battle.mana[p1['user_id']]} | {battle.mana[p2['user_id']]}

⚡ Ход: {battle.turn}

🔥 Статусы:
- {p1['wizard_name']}: {format_status(p1['user_id'])}
- {p2['wizard_name']}: {format_status(p2['user_id'])}
"""

    keyboard = []

    # ───────────── ЗАКЛИНАНИЯ ─────────────
    for spell_id, spell in SPELLS.items():
        keyboard.append([
            InlineKeyboardButton(
                f"{spell.name} ({spell.mana_cost})",
                callback_data=f"cast:{battle_id}:{spell_id}"
            )
        ])

    # ───────────── ЗАЩИТА ─────────────
    keyboard.append([
        InlineKeyboardButton("🛡 Протего", callback_data=f"cast:{battle_id}:protego")
    ])

    await query.edit_message_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


# ─────────────────────────────────────────────
# 🔮 ХОД
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

    # ───────────── ПРОВЕРКА УЧАСТИЯ ─────────────
    if attacker_id not in [battle.p1["user_id"], battle.p2["user_id"]]:
        await query.answer("Ты не участвуешь в этом бою", show_alert=True)
        return

    defender_id = (
        battle.p2["user_id"]
        if attacker_id == battle.p1["user_id"]
        else battle.p1["user_id"]
    )

    # ───────────── ХОД ─────────────
    result = apply_spell(battle, attacker_id, defender_id, spell_id)

    if "error" in result:
        await query.answer(result["error"], show_alert=True)
        return

    next_turn(battle)

    # ───────────── ПОБЕДА ─────────────
    if is_finished(battle):
        winner = get_winner(battle)
        reward(winner)

        await query.edit_message_text(
            f"🏆 Победитель: {winner}"
        )
        return

    await send_battle(query, battle_id, battle)


# ─────────────────────────────────────────────
# 🏆 НАГРАДА
# ─────────────────────────────────────────────

def reward(user_id: int):
    xp = random.randint(50, 150)
    gold = random.randint(20, 80)

    add_xp(user_id, xp)
    add_gold(user_id, gold)


# ─────────────────────────────────────────────
# 🔗 РЕГИСТРАЦИЯ
# ─────────────────────────────────────────────

def register_duel_handlers(app):
    app.add_handler(CommandHandler("duel", duel_command))
    app.add_handler(CallbackQueryHandler(duel_find, pattern="^duel_find$"))
    app.add_handler(CallbackQueryHandler(cast_spell, pattern="^cast:"))
