"""
Shop handler (Diagon Alley) — магазин.
Теперь предмет сначала открывается с описанием, а покупка делается отдельной кнопкой.
"""
import logging
from datetime import date
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler, MessageHandler, filters
from database import get_user, user_exists, get_conn, execute, fetchrow, fetchall, add_item_to_inventory
from utils.i18n import t
from game.items import ITEMS, generate_shop_inventory, item_display_name, RARITY_NAMES, RARITY_NAMES_RU

logger = logging.getLogger(__name__)

SHOP_SIZE = 8


def _ensure_daily_shop():
    """Создаёт ассортимент магазина на сегодня, если его ещё нет."""
    with get_conn() as conn:
        rows = fetchall(conn, "SELECT * FROM shop_items WHERE available_until::date >= CURRENT_DATE ORDER BY id")
        if rows:
            return rows

        stock = generate_shop_inventory(SHOP_SIZE)
        for item in stock:
            price = _base_price(item)
            execute(conn, """
                INSERT INTO shop_items (item_id, price_gold, stock, available_until)
                VALUES (%s, %s, %s, (CURRENT_DATE + INTERVAL '1 day'))
            """, item["id"], price, 10)

        return fetchall(conn, "SELECT * FROM shop_items WHERE available_until::date >= CURRENT_DATE ORDER BY id")


def _base_price(item: dict) -> int:
    rarity_prices = {
        "common": 50,
        "uncommon": 120,
        "rare": 300,
        "very_rare": 700,
        "epic": 1500,
        "legendary": 4000,
        "mythical": 10000,
        "abyssal": 25000,
    }
    base = rarity_prices.get(item.get("rarity", "common"), 100)
    if item.get("type") == "consumable":
        base = item.get("price", base)
    return int(base)


def _item_description(item: dict) -> str:
    return item.get("desc_ru") or item.get("description") or "Описание пока не добавлено."


def _item_bonus_text(item: dict) -> str:
    if item.get("type") == "equipment":
        stat = item.get("stat", "?")
        return f"\n📈 Бонус: +{item.get('stat_min', 0)}–{item.get('stat_max', 0)} к {stat}"
    if item.get("type") == "consumable":
        effect = item.get("effect", "эффект")
        value = item.get("value")
        if value is not None:
            return f"\n✨ Эффект: {effect}, значение {value}"
        return f"\n✨ Эффект: {effect}"
    return ""


def _shop_keyboard(shop_rows: list) -> InlineKeyboardMarkup:
    buttons = []
    for row in shop_rows:
        item = ITEMS.get(row["item_id"])
        if not item:
            continue
        rarity_emoji = RARITY_NAMES.get(item.get("rarity", "common"), "⬜")
        name = item_display_name(item, "ru")
        price = row["price_gold"]
        stock = row["stock"]
        stock_tag = f" [{stock} шт.]" if stock > 0 else " [нет]"
        buttons.append([InlineKeyboardButton(
            f"{rarity_emoji} {name} — {price}💰{stock_tag}",
            callback_data=f"shop_view:{row['id']}"
        )])
    return InlineKeyboardMarkup(buttons)


def _shop_item_keyboard(shop_row_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Купить", callback_data=f"shop_buy:{shop_row_id}")],
        [InlineKeyboardButton("◀️ Назад в магазин", callback_data="shop_back")],
    ])


async def cmd_shop(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not user_exists(user_id):
        await update.message.reply_text(t(user_id, "not_registered"))
        return

    user = get_user(user_id)
    stock = _ensure_daily_shop()
    text = (
        f"🏪 *Косой переулок*\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"💰 У тебя: {user['gold']} золота\n\n"
        f"Нажми на предмет, чтобы увидеть описание и купить его."
    )
    await update.message.reply_text(text, parse_mode="Markdown", reply_markup=_shop_keyboard(stock))


async def cb_shop_view(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    shop_row_id = int(query.data.split(":")[1])

    with get_conn() as conn:
        row = fetchrow(conn, "SELECT * FROM shop_items WHERE id = %s AND available_until::date >= CURRENT_DATE", shop_row_id)

    if not row:
        await query.edit_message_text("❌ Этот товар уже недоступен.")
        return

    item = ITEMS.get(row["item_id"])
    if not item:
        await query.edit_message_text("❌ Предмет не найден в базе предметов.")
        return

    user = get_user(user_id)
    rarity = item.get("rarity", "common")
    rarity_text = RARITY_NAMES_RU.get(rarity, rarity)
    name = item_display_name(item, "ru")
    desc = _item_description(item)
    stock_text = "∞" if row["stock"] < 0 else str(row["stock"])

    text = (
        f"{RARITY_NAMES.get(rarity, '⬜')} *{name}*\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"📜 {desc}\n"
        f"⭐ Редкость: {rarity_text}\n"
        f"💰 Цена: {row['price_gold']} золота\n"
        f"📦 Осталось: {stock_text}\n"
        f"💼 У тебя: {user['gold']} золота"
        f"{_item_bonus_text(item)}"
    )
    await query.edit_message_text(text, parse_mode="Markdown", reply_markup=_shop_item_keyboard(shop_row_id))


async def cb_shop_buy(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    shop_row_id = int(query.data.split(":")[1])

    with get_conn() as conn:
        row = fetchrow(conn, "SELECT * FROM shop_items WHERE id = %s AND available_until::date >= CURRENT_DATE", shop_row_id)

    if not row:
        await query.answer(t(user_id, "shop_item_expired"), show_alert=True)
        return

    item = ITEMS.get(row["item_id"])
    if not item:
        await query.answer("❌ Предмет не найден.", show_alert=True)
        return

    user = get_user(user_id)
    price = row["price_gold"]

    if user["gold"] < price:
        await query.answer(t(user_id, "shop_not_enough_gold"), show_alert=True)
        return

    if row["stock"] == 0:
        await query.answer(t(user_id, "shop_out_of_stock"), show_alert=True)
        return

    with get_conn() as conn:
        execute(conn, "UPDATE users SET gold = gold - %s WHERE user_id = %s", price, user_id)
        if row["stock"] > 0:
            execute(conn, "UPDATE shop_items SET stock = stock - 1 WHERE id = %s", shop_row_id)

    add_item_to_inventory(user_id, row["item_id"], 1)

    name = item_display_name(item, "ru")
    await query.answer(f"✅ Куплено: {name}", show_alert=True)
    await cb_shop_view(update, ctx)


async def cb_shop_back(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    user = get_user(user_id)
    stock = _ensure_daily_shop()
    text = (
        f"🏪 *Косой переулок*\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"💰 У тебя: {user['gold']} золота\n\n"
        f"Нажми на предмет, чтобы увидеть описание и купить его."
    )
    await query.edit_message_text(text, parse_mode="Markdown", reply_markup=_shop_keyboard(stock))


async def handle_shop_button(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if update.message.text == t(user_id, "btn_shop"):
        await cmd_shop(update, ctx)


def register_shop_handlers(app):
    app.add_handler(CommandHandler("shop", cmd_shop))
    app.add_handler(CallbackQueryHandler(cb_shop_view, pattern=r"^shop_view:"))
    app.add_handler(CallbackQueryHandler(cb_shop_buy, pattern=r"^shop_buy:"))
    app.add_handler(CallbackQueryHandler(cb_shop_back, pattern=r"^shop_back$"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_shop_button), group=7)
