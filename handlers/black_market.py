"""
Чёрный рынок — Knockturn Alley (Косой Канавка).
Ротация раз в 3 дня. Анонимные сделки. Редкие предметы.
Доступен только если уровень >= 5.
"""
import logging
import random
from datetime import datetime, timezone, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler
from database import (
    get_user, user_exists, add_item_to_inventory,
    get_conn, execute, fetchrow, fetchall,
)
from game.items import ITEMS, item_display_name, item_description, item_bonus_text, RARITY_NAMES, RARITY_NAMES_RU
from utils.i18n import t

logger = logging.getLogger(__name__)

MIN_LEVEL   = 5
ROTATION_DAYS = 3   # Ассортимент меняется каждые 3 дня

# Предметы эксклюзивно для чёрного рынка
BLACK_MARKET_ITEMS = [
    {"item_id": "wand_elder",         "price": 8000,  "stock": 1,  "desc": "Бузинная палочка — самая мощная в мире. Единственный экземпляр."},
    {"item_id": "cloak_invisibility",  "price": 5000,  "stock": 2,  "desc": "Мантия-невидимка. Скрывает от взглядов людей и существ."},
    {"item_id": "marauders_map",       "price": 3000,  "stock": 3,  "desc": "Карта Мародёров. Показывает всех в Хогвартсе."},
    {"item_id": "time_turner",         "price": 10000, "stock": 1,  "desc": "Маховик времени. Легальное использование... ограничено."},
    {"item_id": "amulet_horcrux",      "price": 6000,  "stock": 1,  "desc": "Амулет-крестраж. Тёмный артефакт огромной силы."},
    {"item_id": "robe_auror",          "price": 2500,  "stock": 3,  "desc": "Мантия Авроров. Легендарная защита."},
    {"item_id": "gloves_basilisk",     "price": 2000,  "stock": 3,  "desc": "Перчатки из кожи Василиска."},
    {"item_id": "dark_arts_tome",      "price": 1500,  "stock": 5,  "desc": "Запрещённый том тёмных искусств. Хранится под стеклом."},
    {"item_id": "polyjuice_ready",     "price": 800,   "stock": 5,  "desc": "Готовое оборотное зелье. Уже готово к употреблению."},
    {"item_id": "felix_felicis",       "price": 1200,  "stock": 3,  "desc": "Феликс Фелицис — жидкая удача. Очень редко."},
    {"item_id": "dragon_heartstring",  "price": 700,   "stock": 5,  "desc": "Струна драконьего сердца — мощный компонент для палочек."},
    {"item_id": "basilisk_fang",       "price": 900,   "stock": 4,  "desc": "Клык Василиска. Единственное что уничтожает крестражи."},
]

SLOT_SIZE = 6   # 6 предметов в ротации

def _get_rotation_seed() -> int:
    """Seed меняется каждые ROTATION_DAYS дней."""
    epoch = datetime(2024, 1, 1, tzinfo=timezone.utc)
    days  = (datetime.now(timezone.utc) - epoch).days
    return days // ROTATION_DAYS

def _get_current_stock() -> list[dict]:
    seed = _get_rotation_seed()
    rng  = random.Random(seed)
    pool = BLACK_MARKET_ITEMS.copy()
    rng.shuffle(pool)
    return pool[:SLOT_SIZE]

def _next_rotation_str() -> str:
    epoch     = datetime(2024, 1, 1, tzinfo=timezone.utc)
    now       = datetime.now(timezone.utc)
    days_gone = (now - epoch).days
    next_rot  = epoch + timedelta(days=((days_gone // ROTATION_DAYS) + 1) * ROTATION_DAYS)
    delta     = next_rot - now
    h, rem    = divmod(int(delta.total_seconds()), 3600)
    m         = rem // 60
    return f"{h} ч {m} мин"

def _ensure_bm_table():
    try:
        with get_conn() as conn:
            execute(conn, """
                CREATE TABLE IF NOT EXISTS bm_purchases (
                    id         SERIAL PRIMARY KEY,
                    user_id    BIGINT NOT NULL,
                    item_id    TEXT NOT NULL,
                    rotation   INT NOT NULL,
                    bought_at  TIMESTAMPTZ DEFAULT NOW()
                )
            """)
    except Exception as e:
        logger.warning("bm_purchases table: %s", e)

def _user_bought_this_rotation(user_id: int, item_id: str) -> bool:
    rotation = _get_rotation_seed()
    try:
        with get_conn() as conn:
            row = fetchrow(conn,
                "SELECT 1 FROM bm_purchases WHERE user_id=%s AND item_id=%s AND rotation=%s",
                user_id, item_id, rotation)
            return row is not None
    except Exception:
        return False

def _bm_text(user: dict, stock: list) -> str:
    lines = [
        "🕯️ *Косой Канавка — Чёрный рынок*",
        "━━━━━━━━━━━━━━━━━━━━",
        "_Здесь продают то, чего нет в официальных магазинах._",
        "_Ассортимент меняется, торопись._\n",
        f"💰 Твоё золото: {user['gold']:,}",
        f"⏳ Смена ассортимента через: {_next_rotation_str()}\n",
    ]
    for i, slot in enumerate(stock, 1):
        item_data = ITEMS.get(slot["item_id"])
        name = item_display_name(item_data, "ru") if item_data else slot["item_id"]
        desc = slot["desc"]
        rarity = item_data.get("rarity", "rare") if item_data else "rare"
        re     = RARITY_NAMES.get(rarity, "🟣")
        rru    = RARITY_NAMES_RU.get(rarity, rarity)
        lines.append(
            f"*{i}. {re} {name}*\n"
            f"   📜 {desc}\n"
            f"   ⭐ {rru}  •  💰 {slot['price']:,}  •  📦 {slot['stock']} шт.\n"
        )
    lines.append("━━━━━━━━━━━━━━━━━━━━\nВыбери товар:")
    return "\n".join(lines)

def _bm_keyboard(stock: list, user_id: int) -> InlineKeyboardMarkup:
    buttons = []
    for i, slot in enumerate(stock, 1):
        item_data = ITEMS.get(slot["item_id"])
        name  = item_display_name(item_data, "ru") if item_data else slot["item_id"]
        price = slot["price"]
        already = _user_bought_this_rotation(user_id, slot["item_id"])
        label = f"{i}. {name} — {price:,}💰" + (" ✅" if already else "")
        buttons.append([InlineKeyboardButton(label, callback_data=f"bm_buy:{i-1}")])
    return InlineKeyboardMarkup(buttons)

async def cmd_black_market(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not user_exists(user_id):
        await update.message.reply_text(t(user_id, "not_registered"))
        return

    user = get_user(user_id)
    if user["level"] < MIN_LEVEL:
        await update.message.reply_text(
            f"🕯️ *Косой Канавка*\n\n"
            f"Этот рынок доступен только с {MIN_LEVEL}-го уровня.\n"
            f"Твой уровень: {user['level']}",
            parse_mode="Markdown"
        )
        return

    _ensure_bm_table()
    stock = _get_current_stock()
    text  = _bm_text(user, stock)
    await update.message.reply_text(text, parse_mode="Markdown", reply_markup=_bm_keyboard(stock, user_id))

async def cb_bm_buy(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query   = update.callback_query
    user_id = query.from_user.id
    idx     = int(query.data.split(":")[1])

    _ensure_bm_table()
    stock = _get_current_stock()
    if idx >= len(stock):
        await query.answer("❌ Товар не найден.", show_alert=True)
        return

    slot = stock[idx]
    if _user_bought_this_rotation(user_id, slot["item_id"]):
        await query.answer("Ты уже купил этот предмет в этой ротации.", show_alert=True)
        return

    user = get_user(user_id)
    if user["gold"] < slot["price"]:
        await query.answer(f"❌ Нужно {slot['price']:,} золота.", show_alert=True)
        return
    if slot["stock"] <= 0:
        await query.answer("❌ Товар закончился.", show_alert=True)
        return

    with get_conn() as conn:
        execute(conn, "UPDATE users SET gold = gold - %s WHERE user_id = %s", slot["price"], user_id)
        execute(conn, "INSERT INTO bm_purchases (user_id, item_id, rotation) VALUES (%s,%s,%s)",
                user_id, slot["item_id"], _get_rotation_seed())

    add_item_to_inventory(user_id, slot["item_id"], 1)

    item_data = ITEMS.get(slot["item_id"])
    name = item_display_name(item_data, "ru") if item_data else slot["item_id"]
    await query.answer(f"✅ Куплено: {name} за {slot['price']:,}💰", show_alert=True)

    user_fresh = get_user(user_id)
    text       = _bm_text(user_fresh, stock)
    await query.edit_message_text(text, parse_mode="Markdown", reply_markup=_bm_keyboard(stock, user_id))

def register_black_market_handlers(app):
    app.add_handler(CommandHandler("blackmarket", cmd_black_market))
    app.add_handler(CallbackQueryHandler(cb_bm_buy, pattern=r"^bm_buy:"))
