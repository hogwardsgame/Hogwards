"""
Auction handler — TZ section 11.2.
Players list items, others bid; 5% commission on final price.
Max 3 active lots per player. No consumables or quest items.

Исправление: убран первый query.answer() в cb_auc_bid — двойной вызов роняет хендлер.
"""
import logging
from datetime import datetime, timedelta, timezone
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ContextTypes, CommandHandler, CallbackQueryHandler,
    MessageHandler, ConversationHandler, filters,
)
from database import (
    get_user, user_exists, get_conn, execute, fetchrow, fetchall,
    get_daily_limit, increment_daily, add_gold,
)
from utils.i18n import t
from game.items import ITEMS, item_display_name, RARITY_NAMES
from config import DAILY_LIMITS

logger = logging.getLogger(__name__)

AUCTION_COMMISSION = 0.05
MAX_ACTIVE_LOTS    = 3

# ConversationHandler states
SEL_ITEM, SET_PRICE, SET_DURATION = range(3)

DURATION_OPTIONS = [
    ("1 час",   1),
    ("6 часов", 6),
    ("24 часа", 24),
]


def _allowed_for_auction(item: dict) -> bool:
    """Per TZ: no consumables, no quest items."""
    return item.get("type") not in ("consumable", "quest")


def _active_lots(user_id: int | None = None) -> list:
    with get_conn() as conn:
        if user_id:
            return fetchall(conn,
                "SELECT * FROM auction_lots WHERE status='active' AND ends_at > NOW() AND seller_id=%s",
                user_id)
        return fetchall(conn,
            "SELECT * FROM auction_lots WHERE status='active' AND ends_at > NOW() ORDER BY ends_at ASC")


def _lot_text(lot: dict) -> str:
    item = ITEMS.get(lot["item_id"])
    name = item_display_name(item, "ru") if item else lot["item_id"]
    rarity_emoji = RARITY_NAMES.get(item.get("rarity", "common"), "⬜") if item else "📦"
    ends = lot["ends_at"]
    if hasattr(ends, "strftime"):
        ends_str = ends.strftime("%d.%m %H:%M")
    else:
        ends_str = str(ends)
    return (
        f"{rarity_emoji} *{name}*\n"
        f"💰 Текущая цена: {lot['current_price']} золота\n"
        f"⏰ До: {ends_str}"
    )


def _lots_keyboard(lots: list, offset: int = 0) -> InlineKeyboardMarkup:
    buttons = []
    for lot in lots[offset:offset + 5]:
        item = ITEMS.get(lot["item_id"])
        name = item_display_name(item, "ru") if item else lot["item_id"]
        buttons.append([InlineKeyboardButton(
            f"💰 {lot['current_price']} — {name}",
            callback_data=f"auc_view:{lot['id']}"
        )])
    nav = []
    if offset > 0:
        nav.append(InlineKeyboardButton("⬅️", callback_data=f"auc_page:{offset-5}"))
    if offset + 5 < len(lots):
        nav.append(InlineKeyboardButton("➡️", callback_data=f"auc_page:{offset+5}"))
    if nav:
        buttons.append(nav)
    buttons.append([InlineKeyboardButton("➕ Выставить предмет", callback_data="auc_sell_start")])
    return InlineKeyboardMarkup(buttons)


async def cmd_auction(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not user_exists(user_id):
        await update.message.reply_text(t(user_id, "not_registered"))
        return

    lots   = _active_lots()
    markup = _lots_keyboard(lots)
    text   = f"🏛️ *Аукцион*\n━━━━━━━━━━━━━━━━━━━━\nАктивных лотов: {len(lots)}\n\nВыбери лот для ставки:"
    await update.message.reply_text(text, parse_mode="Markdown", reply_markup=markup)


async def cb_auc_page(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query  = update.callback_query
    await query.answer()
    offset = int(query.data.split(":")[1])
    lots   = _active_lots()
    markup = _lots_keyboard(lots, offset)
    await query.edit_message_reply_markup(reply_markup=markup)


async def cb_auc_view(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query   = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    lot_id  = int(query.data.split(":")[1])

    with get_conn() as conn:
        lot = fetchrow(conn, "SELECT * FROM auction_lots WHERE id=%s", lot_id)
    if not lot or lot["status"] != "active":
        await query.edit_message_text("❌ Лот недоступен.")
        return

    user = get_user(user_id)
    text = _lot_text(lot)
    min_bid = lot["current_price"] + 1

    buttons = []
    if lot["seller_id"] != user_id:
        for amount in [min_bid, min_bid + 10, min_bid + 50, min_bid + 100]:
            buttons.append([InlineKeyboardButton(
                f"💰 Ставка {amount}", callback_data=f"auc_bid:{lot_id}:{amount}"
            )])
    else:
        text += "\n\n_(Это твой лот)_"
    buttons.append([InlineKeyboardButton("◀️ Назад", callback_data="auc_back")])
    markup = InlineKeyboardMarkup(buttons)
    await query.edit_message_text(text, parse_mode="Markdown", reply_markup=markup)


async def cb_auc_bid(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query   = update.callback_query
    # НЕ вызываем query.answer() здесь — он будет вызван ровно один раз ниже
    user_id = query.from_user.id
    _, lot_id_s, amount_s = query.data.split(":")
    lot_id = int(lot_id_s)
    amount = int(amount_s)

    with get_conn() as conn:
        lot = fetchrow(conn, "SELECT * FROM auction_lots WHERE id=%s AND status='active' AND ends_at > NOW()", lot_id)
    if not lot:
        await query.answer("❌ Лот закрыт.", show_alert=True)
        return
    if lot["seller_id"] == user_id:
        await query.answer("❌ Нельзя делать ставку на свой лот.", show_alert=True)
        return

    user = get_user(user_id)
    if user["gold"] < amount:
        await query.answer(t(user_id, "shop_not_enough_gold"), show_alert=True)
        return
    if amount <= lot["current_price"]:
        await query.answer(f"❌ Ставка должна быть > {lot['current_price']}", show_alert=True)
        return

    # Refund previous highest bidder
    with get_conn() as conn:
        prev_bid = fetchrow(conn,
            "SELECT * FROM auction_bids WHERE lot_id=%s ORDER BY amount DESC LIMIT 1", lot_id)
        if prev_bid and prev_bid["bidder_id"] != user_id:
            execute(conn, "UPDATE users SET gold = gold + %s WHERE user_id=%s",
                    prev_bid["amount"], prev_bid["bidder_id"])

        # Deduct gold
        execute(conn, "UPDATE users SET gold = gold - %s WHERE user_id=%s", amount, user_id)
        execute(conn, "INSERT INTO auction_bids (lot_id, bidder_id, amount) VALUES (%s,%s,%s)",
                lot_id, user_id, amount)
        execute(conn, "UPDATE auction_lots SET current_price=%s, buyer_id=%s WHERE id=%s",
                amount, user_id, lot_id)

    await query.answer(f"✅ Ставка {amount} принята!", show_alert=True)
    await cb_auc_view(update, ctx)


async def cb_auc_back(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query  = update.callback_query
    await query.answer()
    lots   = _active_lots()
    markup = _lots_keyboard(lots)
    text   = f"🏛️ *Аукцион*\n━━━━━━━━━━━━━━━━━━━━\nАктивных лотов: {len(lots)}"
    await query.edit_message_text(text, parse_mode="Markdown", reply_markup=markup)


# ── Sell flow (ConversationHandler) ───────────────────────────────────────────

async def cb_auc_sell_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query   = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    # Check daily limit
    used = get_daily_limit(user_id, "auction_lots")
    if used >= DAILY_LIMITS["auction_lots"]:
        await query.edit_message_text(t(user_id, "daily_limit_reached"))
        return ConversationHandler.END

    # Check active lots count
    my_lots = _active_lots(user_id)
    if len(my_lots) >= MAX_ACTIVE_LOTS:
        await query.edit_message_text(t(user_id, "auction_max_lots"))
        return ConversationHandler.END

    # Show inventory (auction-eligible items only)
    with get_conn() as conn:
        inv = fetchall(conn, "SELECT * FROM inventory WHERE user_id=%s", user_id)

    eligible = [(row, ITEMS.get(row["item_id"])) for row in inv
                if ITEMS.get(row["item_id"]) and _allowed_for_auction(ITEMS[row["item_id"]])]

    if not eligible:
        await query.edit_message_text(t(user_id, "auction_no_items"))
        return ConversationHandler.END

    buttons = []
    for inv_row, item in eligible[:10]:
        rarity_emoji = RARITY_NAMES.get(item.get("rarity", "common"), "⬜")
        name = item_display_name(item, "ru")
        buttons.append([InlineKeyboardButton(
            f"{rarity_emoji} {name}",
            callback_data=f"auc_pick:{inv_row['id']}"
        )])
    ctx.user_data["sell_eligible"] = {inv_row["id"]: inv_row for inv_row, _ in eligible}
    await query.edit_message_text(
        "📦 Выбери предмет для продажи:",
        reply_markup=InlineKeyboardMarkup(buttons)
    )
    return SEL_ITEM


async def cb_auc_pick(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query   = update.callback_query
    await query.answer()
    inv_id  = int(query.data.split(":")[1])
    ctx.user_data["sell_inv_id"] = inv_id
    await query.edit_message_text("💰 Введи стартовую цену (число):")
    return SET_PRICE


async def auc_set_price(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    try:
        price = int(update.message.text.strip())
        if price < 1:
            raise ValueError
    except ValueError:
        await update.message.reply_text("❌ Введи положительное число.")
        return SET_PRICE

    ctx.user_data["sell_price"] = price
    buttons = [[InlineKeyboardButton(label, callback_data=f"auc_dur:{hours}")]
               for label, hours in DURATION_OPTIONS]
    await update.message.reply_text(
        "⏰ Выбери длительность:",
        reply_markup=InlineKeyboardMarkup(buttons)
    )
    return SET_DURATION


async def cb_auc_duration(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query   = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    hours   = int(query.data.split(":")[1])
    price   = ctx.user_data.get("sell_price", 1)
    inv_id  = ctx.user_data.get("sell_inv_id")

    with get_conn() as conn:
        inv_row = fetchrow(conn, "SELECT * FROM inventory WHERE id=%s AND user_id=%s", inv_id, user_id)
    if not inv_row:
        await query.edit_message_text("❌ Предмет не найден.")
        return ConversationHandler.END

    ends_at = datetime.now(timezone.utc) + timedelta(hours=hours)
    with get_conn() as conn:
        execute(conn, """
            INSERT INTO auction_lots (seller_id, item_id, start_price, current_price, ends_at)
            VALUES (%s, %s, %s, %s, %s)
        """, user_id, inv_row["item_id"], price, price, ends_at)
        # Remove from inventory
        execute(conn, "DELETE FROM inventory WHERE id=%s", inv_id)

    increment_daily(user_id, "auction_lots")
    item = ITEMS.get(inv_row["item_id"])
    name = item_display_name(item, "ru") if item else inv_row["item_id"]
    await query.edit_message_text(
        f"✅ *{name}* выставлен на аукцион!\n"
        f"Стартовая цена: {price} 💰\n"
        f"Длительность: {hours} ч.",
        parse_mode="Markdown"
    )
    return ConversationHandler.END


def _sell_conversation() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[CallbackQueryHandler(cb_auc_sell_start, pattern=r"^auc_sell_start")],
        states={
            SEL_ITEM:    [CallbackQueryHandler(cb_auc_pick,     pattern=r"^auc_pick:")],
            SET_PRICE:   [MessageHandler(filters.TEXT & ~filters.COMMAND, auc_set_price)],
            SET_DURATION:[CallbackQueryHandler(cb_auc_duration, pattern=r"^auc_dur:")],
        },
        fallbacks=[CommandHandler("auction", cmd_auction)],
        per_message=False,
    )


async def finalize_expired_lots(bot):
    """Called by APScheduler — resolves expired lots."""
    with get_conn() as conn:
        expired = fetchall(conn,
            "SELECT * FROM auction_lots WHERE status='active' AND ends_at <= NOW()")

    for lot in expired:
        commission = int(lot["current_price"] * AUCTION_COMMISSION)
        payout     = lot["current_price"] - commission

        with get_conn() as conn:
            execute(conn, "UPDATE auction_lots SET status='finished' WHERE id=%s", lot["id"])

        if lot["buyer_id"]:
            # Give item to winner
            with get_conn() as conn:
                execute(conn, "INSERT INTO inventory (user_id, item_id) VALUES (%s,%s)",
                        lot["buyer_id"], lot["item_id"])
                execute(conn, "UPDATE users SET gold = gold + %s WHERE user_id=%s",
                        payout, lot["seller_id"])
            try:
                item = ITEMS.get(lot["item_id"])
                name = item_display_name(item, "ru") if item else lot["item_id"]
                await bot.send_message(lot["buyer_id"],  f"🏛️ Ты выиграл лот: *{name}*!", parse_mode="Markdown")
                await bot.send_message(lot["seller_id"], f"🏛️ Продано: *{name}* за {payout} 💰 (комиссия {commission})", parse_mode="Markdown")
            except Exception as e:
                logger.error(f"auction notify error: {e}")
        else:
            # Return item to seller
            with get_conn() as conn:
                execute(conn, "INSERT INTO inventory (user_id, item_id) VALUES (%s,%s)",
                        lot["seller_id"], lot["item_id"])
            try:
                item = ITEMS.get(lot["item_id"])
                name = item_display_name(item, "ru") if item else lot["item_id"]
                await bot.send_message(lot["seller_id"], f"🏛️ Лот *{name}* не продан — предмет возвращён.", parse_mode="Markdown")
            except Exception as e:
                logger.error(f"auction notify error: {e}")


async def handle_auction_button(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return
    user_id = update.effective_user.id
    if update.message.text == t(user_id, "btn_auction"):
        await cmd_auction(update, ctx)


def register_auction_handlers(app):
    app.add_handler(_sell_conversation())
    app.add_handler(CommandHandler("auction", cmd_auction))
    app.add_handler(CallbackQueryHandler(cb_auc_page, pattern=r"^auc_page:"))
    app.add_handler(CallbackQueryHandler(cb_auc_view, pattern=r"^auc_view:"))
    app.add_handler(CallbackQueryHandler(cb_auc_bid,  pattern=r"^auc_bid:"))
    app.add_handler(CallbackQueryHandler(cb_auc_back, pattern=r"^auc_back"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_auction_button), group=9)
