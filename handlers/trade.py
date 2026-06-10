"""
Trade — передача золота между игроками.
Защита от ошибок, подтверждение, журнал операций, комиссия 5%.
Команда: /trade
"""
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler, MessageHandler, filters
from database import (
    get_user, user_exists, transfer_gold, get_conn, fetchrow,
)
from utils.i18n import t
from config import TRADE_MIN_AMOUNT, TRADE_MAX_AMOUNT, TRADE_TAX_PERCENT

logger = logging.getLogger(__name__)

# user_id → {step, target_id, amount}
_trade_sessions: dict[int, dict] = {}


async def cmd_trade(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """/trade — начать перевод золота."""
    user_id = update.effective_user.id
    if not user_exists(user_id):
        await update.message.reply_text(t(user_id, "not_registered"))
        return

    # /trade 123456789 500
    if ctx.args and len(ctx.args) == 2 and ctx.args[0].isdigit() and ctx.args[1].isdigit():
        target_id = int(ctx.args[0])
        amount    = int(ctx.args[1])
        await _confirm_trade(update.message, ctx, user_id, target_id, amount)
        return

    _trade_sessions[user_id] = {"step": "target"}
    await update.message.reply_text(
        "💰 *Перевод золота*\n\n"
        "Введи *Telegram ID* получателя:\n\n"
        "💡 Или сразу: `/trade <ID> <сумма>`",
        parse_mode="Markdown"
    )


async def _confirm_trade(msg, ctx, sender_id: int, target_id: int, amount: int):
    sender = get_user(sender_id)
    target = get_user(target_id)

    if not target:
        await msg.reply_text("❌ Игрок не найден.")
        return
    if target_id == sender_id:
        await msg.reply_text("❌ Нельзя отправить золото самому себе.")
        return
    if amount < TRADE_MIN_AMOUNT or amount > TRADE_MAX_AMOUNT:
        await msg.reply_text(f"❌ Сумма должна быть от {TRADE_MIN_AMOUNT} до {TRADE_MAX_AMOUNT} 💰.")
        return

    tax   = max(1, int(amount * TRADE_TAX_PERCENT / 100))
    total = amount + tax

    if sender["gold"] < total:
        await msg.reply_text(
            f"❌ Недостаточно золота!\n"
            f"Нужно: {total} 💰 (сумма {amount} + комиссия {tax})\n"
            f"Есть: {sender['gold']} 💰"
        )
        return

    _trade_sessions[sender_id] = {
        "step": "confirm",
        "target_id": target_id,
        "amount": amount,
        "tax": tax,
    }

    markup = InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ Подтвердить", callback_data=f"trade_confirm:{sender_id}"),
        InlineKeyboardButton("❌ Отмена",      callback_data=f"trade_cancel:{sender_id}"),
    ]])
    await msg.reply_text(
        f"💰 *Подтверждение перевода*\n\n"
        f"Получатель: *{target['wizard_name']}*\n"
        f"Сумма: *{amount} 💰*\n"
        f"Комиссия ({TRADE_TAX_PERCENT}%): *{tax} 💰*\n"
        f"Итого спишется: *{total} 💰*\n\n"
        f"Твой баланс после: {sender['gold'] - total} 💰",
        parse_mode="Markdown",
        reply_markup=markup
    )


async def handle_trade_text(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    session = _trade_sessions.get(user_id)
    if not session:
        return

    step = session.get("step")
    text = update.message.text.strip()

    if step == "target":
        if not text.isdigit():
            await update.message.reply_text("❌ ID должен быть числом.")
            return
        target_id = int(text)
        target = get_user(target_id)
        if not target:
            await update.message.reply_text("❌ Игрок не найден.")
            _trade_sessions.pop(user_id, None)
            return
        if target_id == user_id:
            await update.message.reply_text("❌ Нельзя отправить самому себе.")
            _trade_sessions.pop(user_id, None)
            return
        session["target_id"] = target_id
        session["step"]      = "amount"
        await update.message.reply_text(
            f"💰 Получатель: *{target['wizard_name']}*\n\n"
            f"Введи *сумму* для перевода ({TRADE_MIN_AMOUNT}–{TRADE_MAX_AMOUNT} 💰):",
            parse_mode="Markdown"
        )

    elif step == "amount":
        if not text.isdigit():
            await update.message.reply_text("❌ Сумма должна быть числом.")
            return
        amount = int(text)
        target_id = session["target_id"]
        _trade_sessions.pop(user_id, None)
        await _confirm_trade(update.message, ctx, user_id, target_id, amount)


async def cb_trade_confirm(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query     = update.callback_query
    sender_id = int(query.data.split(":")[1])

    # Только сам отправитель может подтвердить
    if query.from_user.id != sender_id:
        await query.answer("❌ Это не твоя операция.", show_alert=True)
        return

    session = _trade_sessions.pop(sender_id, None)
    if not session or session.get("step") != "confirm":
        await query.edit_message_text("❌ Сессия истекла. Начни заново через /trade.")
        return

    target_id = session["target_id"]
    amount    = session["amount"]
    tax       = session["tax"]

    sender = get_user(sender_id)
    target = get_user(target_id)

    if not target:
        await query.edit_message_text("❌ Получатель не найден.")
        return
    if sender["gold"] < amount + tax:
        await query.edit_message_text("❌ Недостаточно золота.")
        return

    transfer_gold(sender_id, target_id, amount, tax)

    await query.edit_message_text(
        f"✅ *Перевод выполнен!*\n\n"
        f"→ {target['wizard_name']} получил *{amount} 💰*\n"
        f"Комиссия: {tax} 💰\n"
        f"Твой баланс: {sender['gold'] - amount - tax} 💰",
        parse_mode="Markdown"
    )

    try:
        await ctx.bot.send_message(
            target_id,
            f"💰 *Получен перевод!*\n\n"
            f"От: *{sender['wizard_name']}*\n"
            f"Сумма: *{amount} 💰*",
            parse_mode="Markdown"
        )
    except Exception:
        pass


async def cb_trade_cancel(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query     = update.callback_query
    sender_id = int(query.data.split(":")[1])

    if query.from_user.id != sender_id:
        await query.answer("❌ Это не твоя операция.", show_alert=True)
        return

    _trade_sessions.pop(sender_id, None)
    await query.edit_message_text("❌ Перевод отменён.")


async def cmd_trade_log(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """/tradelog — последние 10 операций."""
    user_id = update.effective_user.id
    if not user_exists(user_id):
        await update.message.reply_text(t(user_id, "not_registered"))
        return

    with get_conn() as conn:
        from database import fetchall
        rows = fetchall(conn, """
            SELECT t.amount, t.tax, t.created_at,
                   s.wizard_name as sender_name,
                   r.wizard_name as receiver_name
            FROM trade_log t
            JOIN users s ON t.sender_id   = s.user_id
            JOIN users r ON t.receiver_id = r.user_id
            WHERE t.sender_id = %s OR t.receiver_id = %s
            ORDER BY t.created_at DESC LIMIT 10
        """, user_id, user_id)

    if not rows:
        await update.message.reply_text("📋 История переводов пуста.")
        return

    lines = ["📋 *Последние переводы:*\n"]
    for r in rows:
        direction = "→" if r["sender_name"] == get_user(user_id)["wizard_name"] else "←"
        other = r["receiver_name"] if direction == "→" else r["sender_name"]
        date  = r["created_at"].strftime("%d.%m %H:%M")
        lines.append(f"{direction} *{other}*: {r['amount']} 💰  _{date}_")

    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


def register_trade_handlers(app):
    app.add_handler(CommandHandler("trade",    cmd_trade))
    app.add_handler(CommandHandler("tradelog", cmd_trade_log))
    app.add_handler(CallbackQueryHandler(cb_trade_confirm, pattern=r"^trade_confirm:"))
    app.add_handler(CallbackQueryHandler(cb_trade_cancel,  pattern=r"^trade_cancel:"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_trade_text), group=13)

