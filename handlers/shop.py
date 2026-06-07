"""
Shop handler (Diagon Alley) — TZ section 11.1.
Daily refreshing inventory, common–rare items only.
"""
import logging
import json
from datetime import date
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler, MessageHandler, filters
from database import get_user, user_exists, get_conn, execute, fetchrow, fetchall, add_gold
from utils.i18n import t
from game.items import ITEMS, generate_shop_inventory, item_display_name, RARITY_NAMES, get_item

logger = logging.getLogger(__name__)

SHOP_SIZE = 8


def _ensure_daily_shop():
    """Make sure today's shop stock exists in DB."""
    today = date.today().isoformat()
    with get_conn() as conn:
        rows = fetchall(conn, "SELECT * FROM shop_items WHERE available_until::date >= CURRENT_DATE")
        if rows:
            return rows
        # Generate new stock
        stock = generate_shop_inventory(SHOP_SIZE)
        for item in stock:
            price = _base_price(item)
            execute(conn, """
                INSERT INTO shop_items (item_id, price_gold, stock, available_until)
                VALUES (%s, %s, %s, (CURRENT_DATE + INTERVAL '1 day'))
            """, item["id"], price, 10)
        return fetchall(conn, "SELECT * FROM shop_items WHERE available_until::date >= CURRENT_DATE")


def _base_price(item: dict) -> int:
    rarity_prices = {
        "common": 50, "uncommon": 120, "rare": 300,
        "very_rare": 700, "epic": 1500, "legendary": 4000,
        "mythical": 10000, "abyssal": 25000,
    }
    base = rarity_prices.get(item.get("rarity", "common"), 100)
    if item.get("type") == "consumable":
        base = item.get("price", base)
    return base


def _shop_keyboard(shop_rows: list) -> InlineKeyboardMarkup:
    buttons = []
    for row in shop_rows:
        item = ITEMS.get(row["item_id"])
        if not item:
            continue
        rarity_emoji = RARITY_NAMES.get(item.get("rarity", "common"), "⬜")
        name  = item_display_name(item, "ru")
        price = row["price_gold"]
        stock = row["stock"]
        stock_tag = f" [{stock} шт.]" if stock > 0 else ""
        buttons.append([InlineKeyboardButton(
            f"{rarity_emoji} {name} — {price}💰{stock_tag}",
            callback_data=f"shop_buy:{row['id']}"
        )])
    return InlineKeyboardMarkup(buttons)


async def cmd_shop(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not user_exists(user_id):
        await update.message.reply_text(t(user_id, "not_registered"))
        return

    user  = get_user(user_id)
    stock = _ensure_daily_shop()
    markup = _shop_keyboard(stock)
    text = (
        f"🏪 *Косой переулок*\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"💰 У тебя: {user['gold']} золота\n\n"
        f"Обновление магазина каждые 24 часа:"
    )
    await update.message.reply_text(text, parse_mode="Markdown", reply_markup=markup)


async def cb_shop_buy(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query     = update.callback_query
    await query.answer()
    user_id   = query.from_user.id
    shop_row_id = int(query.data.split(":")[1])

    with get_conn() as conn:
        row = fetchrow(conn, "SELECT * FROM shop_items WHERE id = %s AND available_until::date >= CURRENT_DATE", shop_row_id)
    if not row:
        await query.answer(t(user_id, "shop_item_expired"), show_alert=True)
        return

    item  = ITEMS.get(row["item_id"])
    if not item:
        await query.answer("❌ Предмет не найден.", show_alert=True)
        return

    user  = get_user(user_id)
    price = row["price_gold"]

    if user["gold"] < price:
        await query.answer(t(user_id, "shop_not_enough_gold"), show_alert=True)
        return

    if row["stock"] == 0:
        await query.answer(t(user_id, "shop_out_of_stock"), show_alert=True)
        return

    # Deduct gold & give item
    with get_conn() as conn:
        execute(conn, "UPDATE users SET gold = gold - %s WHERE user_id = %s", price, user_id)
        execute(conn, "INSERT INTO inventory (user_id, item_id) VALUES (%s, %s)", user_id, row["item_id"])
        if row["stock"] > 0:
            execute(conn, "UPDATE shop_items SET stock = stock - 1 WHERE id = %s", shop_row_id)

    name = item_display_name(item, "ru")
    await query.answer(f"✅ Куплено: {name}", show_alert=True)


async def handle_shop_button(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if update.message.text == t(user_id, "btn_shop"):
        await cmd_shop(update, ctx)


def register_shop_handlers(app):
    app.add_handler(CommandHandler("shop", cmd_shop))
    app.add_handler(CallbackQueryHandler(cb_shop_buy, pattern=r"^shop_buy:"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_shop_button), group=7)
