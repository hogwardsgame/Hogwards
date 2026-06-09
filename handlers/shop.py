"""
Shop handler (Diagon Alley) — магазин.
Теперь предметы показывают фиксированную характеристику без разброса, понятные кнопки,
а смена факультета всегда доступна за 50000 золота.
"""
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler, MessageHandler, filters
from database import get_user, user_exists, get_conn, execute, fetchrow, fetchall, add_item_to_inventory
from utils.i18n import t
from utils.helpers import house_emoji
from game.items import (
    ITEMS, generate_shop_inventory, item_display_name, item_description, item_bonus_text,
    RARITY_NAMES, RARITY_NAMES_RU, rarity_label, type_label
)

logger = logging.getLogger(__name__)

SHOP_SIZE = 8
HOUSE_CHANGE_PRICE = 50_000
HOUSES = [
    ("gryffindor", "🦁 Гриффиндор"),
    ("slytherin", "🐍 Слизерин"),
    ("ravenclaw", "🦅 Когтевран"),
    ("hufflepuff", "🦡 Пуффендуй"),
]


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
        bonus = item_bonus_text(item, "ru").replace("📈 Характеристика: ", "") if item.get("type") == "equipment" else ""
        bonus_tag = f" · {bonus}" if bonus else ""
        stock_tag = f" · {stock} шт." if stock > 0 else " · нет"
        buttons.append([InlineKeyboardButton(
            f"{rarity_emoji} {name} — {price}💰{bonus_tag}{stock_tag}",
            callback_data=f"shop_view:{row['id']}"
        )])
    buttons.append([InlineKeyboardButton(
        f"🔄 Сменить факультет — {HOUSE_CHANGE_PRICE}💰",
        callback_data="shop_house_change"
    )])
    return InlineKeyboardMarkup(buttons)


def _shop_item_keyboard(shop_row_id: int, item: dict, price: int) -> InlineKeyboardMarkup:
    name = item_display_name(item, "ru")
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(f"✅ Купить «{name}» за {price}💰", callback_data=f"shop_buy:{shop_row_id}")],
        [InlineKeyboardButton("◀️ Назад к товарам", callback_data="shop_back")],
    ])


def _house_keyboard(current_house: str) -> InlineKeyboardMarkup:
    buttons = []
    for house, label in HOUSES:
        suffix = " · текущий" if house == current_house else ""
        buttons.append([InlineKeyboardButton(f"{label}{suffix}", callback_data=f"shop_house_pick:{house}")])
    buttons.append([InlineKeyboardButton("◀️ Назад в магазин", callback_data="shop_back")])
    return InlineKeyboardMarkup(buttons)


def _stock_text(stock: int) -> str:
    return "∞" if stock < 0 else str(stock)


def _render_shop_item(user_id: int, row: dict) -> tuple[str, InlineKeyboardMarkup]:
    item = ITEMS.get(row["item_id"])
    user = get_user(user_id)
    rarity = item.get("rarity", "common")
    name = item_display_name(item, "ru")
    desc = item_description(item, "ru")
    bonus_text = item_bonus_text(item, "ru")
    bonus_block = f"\n{bonus_text}" if bonus_text else ""
    text = (
        f"{RARITY_NAMES.get(rarity, '⬜')} *{name}*\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"📜 {desc}\n"
        f"⭐ Редкость: {RARITY_NAMES_RU.get(rarity, rarity)}\n"
        f"📌 Тип: {type_label(item.get('type','item'), 'ru')}\n"
        f"💰 Цена: {row['price_gold']} золота\n"
        f"📦 Осталось: {_stock_text(row['stock'])}\n"
        f"💼 У тебя: {user['gold']} золота\n"
        f"{bonus_block}"
    )
    return text, _shop_item_keyboard(row["id"], item, row["price_gold"])


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
        f"Выбери товар: на кнопках сразу показаны цена, остаток и понятный бонус.\n"
        f"Смена факультета всегда доступна внизу магазина."
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

    if row["item_id"] not in ITEMS:
        await query.edit_message_text("❌ Предмет не найден в базе предметов.")
        return

    text, markup = _render_shop_item(user_id, row)
    await query.edit_message_text(text, parse_mode="Markdown", reply_markup=markup)


async def cb_shop_buy(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
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
    with get_conn() as conn:
        fresh = fetchrow(conn, "SELECT * FROM shop_items WHERE id = %s", shop_row_id)
    text, markup = _render_shop_item(user_id, fresh)
    await query.edit_message_text(text, parse_mode="Markdown", reply_markup=markup)


async def cb_shop_house_change(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    user = get_user(user_id)
    current_house_name = t(user_id, f"house_{user['house']}")
    text = (
        f"🔄 *Смена факультета*\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"Текущий факультет: {house_emoji(user['house'])} {current_house_name}\n"
        f"Стоимость: {HOUSE_CHANGE_PRICE} золота\n"
        f"У тебя: {user['gold']} золота\n\n"
        f"Выбери новый факультет. После выбора золото спишется сразу."
    )
    await query.edit_message_text(text, parse_mode="Markdown", reply_markup=_house_keyboard(user["house"]))


async def cb_shop_house_pick(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    house = query.data.split(":")[1]
    if house not in {h for h, _ in HOUSES}:
        await query.answer("❌ Неизвестный факультет.", show_alert=True)
        return
    user = get_user(user_id)
    if user["house"] == house:
        await query.answer("Это уже твой факультет.", show_alert=True)
        return
    if user["gold"] < HOUSE_CHANGE_PRICE:
        await query.answer(f"❌ Нужно {HOUSE_CHANGE_PRICE} золота.", show_alert=True)
        return
    with get_conn() as conn:
        execute(conn, "UPDATE users SET gold = gold - %s, house = %s WHERE user_id = %s", HOUSE_CHANGE_PRICE, house, user_id)
    await query.answer("✅ Факультет изменён!", show_alert=True)
    await query.edit_message_text(
        f"✅ Теперь ты в факультете: {house_emoji(house)} *{t(user_id, f'house_{house}')}*\n"
        f"💰 Списано: {HOUSE_CHANGE_PRICE} золота.",
        parse_mode="Markdown"
    )


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
        f"Выбери товар: на кнопках сразу показаны цена, остаток и понятный бонус."
    )
    await query.edit_message_text(text, parse_mode="Markdown", reply_markup=_shop_keyboard(stock))


async def handle_shop_button(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return
    user_id = update.effective_user.id
    if update.message.text == t(user_id, "btn_shop"):
        await cmd_shop(update, ctx)


def register_shop_handlers(app):
    app.add_handler(CommandHandler("shop", cmd_shop))
    app.add_handler(CallbackQueryHandler(cb_shop_view, pattern=r"^shop_view:"))
    app.add_handler(CallbackQueryHandler(cb_shop_buy,  pattern=r"^shop_buy:"))
    app.add_handler(CallbackQueryHandler(cb_shop_house_change, pattern=r"^shop_house_change$"))
    app.add_handler(CallbackQueryHandler(cb_shop_house_pick, pattern=r"^shop_house_pick:"))
    app.add_handler(CallbackQueryHandler(cb_shop_back, pattern=r"^shop_back$"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_shop_button), group=7)
