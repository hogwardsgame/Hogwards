"""
Хогсмид — особый магазин с редкими товарами.
Ассортимент обновляется ежедневно. Есть обычные и редкие предложения.
Команда: /hogsmeade
"""
import logging
import random
from datetime import date
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler
from database import (
    get_user, user_exists, get_conn, execute, fetchrow, fetchall,
)
from utils.i18n import t
from game.items import ITEMS, item_display_name, RARITY_NAMES, RARITY_NAMES_RU
from game.spells import SPELLS, spell_display_name, RARITY_NAMES_RU as SPELL_RARITY_RU

logger = logging.getLogger(__name__)

# ── Постоянные лавки Хогсмида ─────────────────────────────────────────────────
SHOPS = {
    "honeydukes": {
        "name": "🍬 Сладкая лавка Хонейдьюкс",
        "desc": "Волшебные сладости и их побочные эффекты.",
        "items": [
            {"id": "hp_potion_small",  "price": 35,  "stock": 10},
            {"id": "hp_potion_medium", "price": 80,  "stock": 5},
            {"id": "antidote",         "price": 70,  "stock": 3},
        ],
    },
    "zonkos": {
        "name": "🎭 Шутки Зонко",
        "desc": "Магические шутки и розыгрыши. Иногда полезны в бою.",
        "items": [
            {"id": "mana_potion",   "price": 55, "stock": 5},
            {"id": "shield_potion", "price": 90, "stock": 3},
            {"id": "luck_potion",   "price": 280, "stock": 1},
        ],
    },
    "tomes": {
        "name": "📚 Книжная лавка Спинтвита",
        "desc": "Редкие тома с заклинаниями и рецептами.",
        "items": [],   # заполняется динамически — редкие заклинания
    },
    "borgin": {
        "name": "⬛ Лавка Борджина и Буркса",
        "desc": "Предметы тёмной магии. Только для смельчаков.",
        "items": [],   # редкие предметы
    },
}

# Редкие товары дня (генерируются)
_daily_rare_cache: dict[str, list] = {}


def _get_daily_seed() -> int:
    """Детерминированное зерно по дате — одинаковые товары для всех."""
    d = date.today()
    return d.year * 10000 + d.month * 100 + d.day


def _generate_daily_rare_items() -> list[dict]:
    """Генерирует 3-5 редких предметов дня."""
    rng = random.Random(_get_daily_seed())
    rare_pool = [
        item for item in ITEMS.values()
        if item.get("rarity") in ("rare", "very_rare", "epic")
        and item.get("type") == "equipment"
    ]
    count = rng.randint(3, 5)
    picks = rng.sample(rare_pool, min(count, len(rare_pool)))
    result = []
    for item in picks:
        base_price = {"rare": 300, "very_rare": 600, "epic": 1200}.get(item.get("rarity", "rare"), 300)
        price = base_price + rng.randint(-50, 100)
        result.append({
            "item": item,
            "price": price,
            "stock": rng.randint(1, 3),
            "is_rare": True,
        })
    return result


def _generate_daily_rare_spells() -> list[dict]:
    """Генерирует 1-2 редких заклинания дня."""
    rng = random.Random(_get_daily_seed() + 1)
    pool = [s for s in SPELLS.values() if s.get("rarity") in ("rare", "very_rare")]
    if not pool:
        return []
    picks = rng.sample(pool, min(2, len(pool)))
    result = []
    for spell in picks:
        base = {"rare": 500, "very_rare": 1200}.get(spell.get("rarity", "rare"), 500)
        result.append({
            "spell":   spell,
            "price":   base + rng.randint(-100, 200),
            "stock":   1,
            "is_rare": True,
        })
    return result


def _hogsmeade_main_keyboard() -> InlineKeyboardMarkup:
    buttons = []
    for shop_id, shop in SHOPS.items():
        buttons.append([InlineKeyboardButton(shop["name"], callback_data=f"hm_shop:{shop_id}")])
    buttons.append([InlineKeyboardButton("🌟 Редкие товары дня", callback_data="hm_rare")])
    return InlineKeyboardMarkup(buttons)


async def cmd_hogsmeade(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not user_exists(user_id):
        await update.message.reply_text(t(user_id, "not_registered"))
        return

    user = get_user(user_id)
    await update.message.reply_text(
        f"🏘️ *Добро пожаловать в Хогсмид!*\n\n"
        f"Твой кошелёк: {user['gold']} 💰\n\n"
        f"Ассортимент обновляется каждый день.\n"
        f"Выбери лавку:",
        parse_mode="Markdown",
        reply_markup=_hogsmeade_main_keyboard()
    )


async def cb_hm_shop(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query   = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    shop_id = query.data.split(":")[1]

    shop = SHOPS.get(shop_id)
    if not shop:
        await query.edit_message_text("❌ Лавка не найдена.")
        return

    user = get_user(user_id)
    items = list(shop["items"])

    # Динамические товары
    if shop_id == "tomes":
        items = _generate_daily_rare_spells()
    elif shop_id == "borgin":
        rare_items = _generate_daily_rare_items()
        items = [ri for ri in rare_items if ri["item"].get("rarity") in ("very_rare", "epic")]

    if not items:
        await query.edit_message_text(
            f"{shop['name']}\n\n_{shop['desc']}_\n\nСегодня ничего нет.",
            parse_mode="Markdown"
        )
        return

    buttons = []
    for entry in items:
        if "item" in entry:
            # Предмет
            item  = entry["item"]
            price = entry["price"]
            name  = item_display_name(item, "ru")
            rarity = RARITY_NAMES.get(item.get("rarity", "common"), "")
            rarity_ru = RARITY_NAMES_RU.get(item.get("rarity", "common"), "")
            stock = entry.get("stock", 1)
            can_buy = user["gold"] >= price
            mark    = "✅" if can_buy else "❌"
            buttons.append([InlineKeyboardButton(
                f"{mark} {rarity} {name} — {price} 💰 (x{stock})",
                callback_data=f"hm_buy_item:{shop_id}:{item['id']}:{price}"
            )])
        elif "spell" in entry:
            # Заклинание
            spell = entry["spell"]
            price = entry["price"]
            name  = spell_display_name(spell["id"], "ru")
            rarity_ru = SPELL_RARITY_RU.get(spell.get("rarity", "common"), "")
            can_buy = user["gold"] >= price
            mark    = "✅" if can_buy else "❌"
            buttons.append([InlineKeyboardButton(
                f"{mark} 📖 {name} ({rarity_ru}) — {price} 💰",
                callback_data=f"hm_buy_spell:{shop_id}:{spell['id']}:{price}"
            )])
        else:
            # Простой предмет из словаря (Honeydukes/Zonko's)
            item_id = entry["id"]
            price   = entry["price"]
            stock   = entry.get("stock", 1)
            item    = ITEMS.get(item_id)
            if not item:
                continue
            name    = item_display_name(item, "ru")
            can_buy = user["gold"] >= price
            mark    = "✅" if can_buy else "❌"
            buttons.append([InlineKeyboardButton(
                f"{mark} {name} — {price} 💰 (x{stock})",
                callback_data=f"hm_buy_item:{shop_id}:{item_id}:{price}"
            )])

    buttons.append([InlineKeyboardButton("🔙 Назад", callback_data="hm_back")])
    markup = InlineKeyboardMarkup(buttons)

    await query.edit_message_text(
        f"{shop['name']}\n\n_{shop['desc']}_\n\n"
        f"💰 У тебя: {user['gold']} золота",
        parse_mode="Markdown",
        reply_markup=markup
    )


async def cb_hm_rare(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query   = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    user        = get_user(user_id)
    rare_items  = _generate_daily_rare_items()
    rare_spells = _generate_daily_rare_spells()

    buttons = []
    for entry in rare_items:
        item  = entry["item"]
        price = entry["price"]
        name  = item_display_name(item, "ru")
        rarity = RARITY_NAMES.get(item.get("rarity", "common"), "")
        rarity_ru = RARITY_NAMES_RU.get(item.get("rarity", "common"), "")
        can_buy = user["gold"] >= price
        mark    = "✅" if can_buy else "❌"
        buttons.append([InlineKeyboardButton(
            f"{mark} {rarity} {name} ({rarity_ru}) — {price} 💰",
            callback_data=f"hm_buy_item:rare:{item['id']}:{price}"
        )])
    for entry in rare_spells:
        spell = entry["spell"]
        price = entry["price"]
        name  = spell_display_name(spell["id"], "ru")
        rarity_ru = SPELL_RARITY_RU.get(spell.get("rarity", "common"), "")
        can_buy = user["gold"] >= price
        mark    = "✅" if can_buy else "❌"
        buttons.append([InlineKeyboardButton(
            f"{mark} 📖 {name} ({rarity_ru}) — {price} 💰",
            callback_data=f"hm_buy_spell:rare:{spell['id']}:{price}"
        )])

    buttons.append([InlineKeyboardButton("🔙 Назад", callback_data="hm_back")])

    await query.edit_message_text(
        f"🌟 *Редкие товары дня*\n\n"
        f"Обновляются каждый день в 00:00 UTC\n"
        f"💰 У тебя: {user['gold']} золота",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(buttons)
    )


async def cb_hm_buy_item(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query   = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    parts   = query.data.split(":")
    item_id = parts[2]
    price   = int(parts[3])

    user = get_user(user_id)
    if user["gold"] < price:
        await query.answer(f"❌ Недостаточно золота! Нужно {price} 💰", show_alert=True)
        return

    item = ITEMS.get(item_id)
    if not item:
        await query.answer("❌ Предмет не найден.", show_alert=True)
        return

    with get_conn() as conn:
        execute(conn, "UPDATE users SET gold = gold - %s WHERE user_id = %s", price, user_id)
        execute(conn, """
            INSERT INTO inventory (user_id, item_id, quantity)
            VALUES (%s, %s, 1)
            ON CONFLICT (user_id, item_id) DO UPDATE SET quantity = inventory.quantity + 1
        """, user_id, item_id)

    name = item_display_name(item, "ru")
    await query.answer(f"✅ Куплено: {name} за {price} 💰", show_alert=True)


async def cb_hm_buy_spell(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query   = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    parts    = query.data.split(":")
    spell_id = parts[2]
    price    = int(parts[3])

    user = get_user(user_id)
    if user["gold"] < price:
        await query.answer(f"❌ Недостаточно золота! Нужно {price} 💰", show_alert=True)
        return

    spell = SPELLS.get(spell_id)
    if not spell:
        await query.answer("❌ Заклинание не найдено.", show_alert=True)
        return

    with get_conn() as conn:
        # Проверяем, уже ли есть это заклинание
        existing = fetchrow(conn,
            "SELECT 1 FROM user_spells WHERE user_id = %s AND spell_id = %s",
            user_id, spell_id)
        if existing:
            await query.answer("❌ Это заклинание уже изучено!", show_alert=True)
            return
        execute(conn, "UPDATE users SET gold = gold - %s WHERE user_id = %s", price, user_id)
        execute(conn, "INSERT INTO user_spells (user_id, spell_id) VALUES (%s, %s)", user_id, spell_id)

    name = spell_display_name(spell_id, "ru")
    await query.answer(f"✅ Изучено: {name} за {price} 💰", show_alert=True)


async def cb_hm_back(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query   = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    user    = get_user(user_id)

    await query.edit_message_text(
        f"🏘️ *Хогсмид*\n\nТвой кошелёк: {user['gold']} 💰\n\nВыбери лавку:",
        parse_mode="Markdown",
        reply_markup=_hogsmeade_main_keyboard()
    )


def register_hogsmeade_handlers(app):
    app.add_handler(CommandHandler("hogsmeade", cmd_hogsmeade))
    app.add_handler(CallbackQueryHandler(cb_hm_shop,       pattern=r"^hm_shop:"))
    app.add_handler(CallbackQueryHandler(cb_hm_rare,       pattern=r"^hm_rare"))
    app.add_handler(CallbackQueryHandler(cb_hm_buy_item,   pattern=r"^hm_buy_item:"))
    app.add_handler(CallbackQueryHandler(cb_hm_buy_spell,  pattern=r"^hm_buy_spell:"))
    app.add_handler(CallbackQueryHandler(cb_hm_back,       pattern=r"^hm_back"))

