"""
Питомцы — система питомцев.
Сова, кошка, жаба, крыса — каждый даёт пассивный бонус.
Питомца нужно кормить раз в день, иначе бонус пропадает.
"""
import logging
from datetime import datetime, timezone, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler
from database import (
    get_user, user_exists, add_xp, add_gold,
    get_conn, execute, fetchrow, fetchall,
)
from utils.i18n import t

logger = logging.getLogger(__name__)

# ── Каталог питомцев ───────────────────────────────────────────────────────────
PETS: dict[str, dict] = {
    "owl": {
        "name":   "Сова",
        "emoji":  "🦉",
        "desc":   "Верный почтовый помощник. Умная птица с острыми когтями.",
        "bonus":  {"xp_mult": 0.10},         # +10% к XP
        "bonus_desc": "+10% к получаемому опыту",
        "food":   "owl_treats",
        "price":  500,
        "max_happiness": 100,
    },
    "cat": {
        "name":   "Кошка",
        "emoji":  "🐱",
        "desc":   "Независимая и загадочная. Чувствует магию лучше любого прибора.",
        "bonus":  {"luck": 3},               # +3 к удаче
        "bonus_desc": "+3 к удаче",
        "food":   "cat_food",
        "price":  400,
        "max_happiness": 100,
    },
    "toad": {
        "name":   "Жаба",
        "emoji":  "🐸",
        "desc":   "Незаменима для зельеварения. Её слизь — ценный ингредиент.",
        "bonus":  {"potion_speed": 0.15},    # -15% к времени варки
        "bonus_desc": "-15% к времени варки зелий",
        "food":   "toad_flies",
        "price":  200,
        "max_happiness": 100,
    },
    "rat": {
        "name":   "Крыса",
        "emoji":  "🐀",
        "desc":   "Хитрый грызун. Иногда находит монетки в самых неожиданных местах.",
        "bonus":  {"gold_mult": 0.08},       # +8% к золоту
        "bonus_desc": "+8% к получаемому золоту",
        "food":   "rat_cheese",
        "price":  150,
        "max_happiness": 100,
    },
    "phoenix": {
        "name":   "Феникс",
        "emoji":  "🔥🦅",
        "desc":   "Легендарная птица возрождения. Её слёзы исцеляют раны.",
        "bonus":  {"hp_regen": 5, "xp_mult": 0.15},  # +5 HP/день + 15% XP
        "bonus_desc": "+5 HP в день и +15% к опыту",
        "food":   "phoenix_berries",
        "price":  5000,
        "max_happiness": 100,
        "rare": True,
    },
}

HAPPINESS_DECAY_PER_DAY = 20   # Без еды счастье падает на 20/день
FEED_HAPPINESS_GAIN     = 30   # Кормление даёт +30 счастья

def _get_pet(user_id: int) -> dict | None:
    try:
        with get_conn() as conn:
            return fetchrow(conn, "SELECT * FROM user_pets WHERE user_id = %s", user_id)
    except Exception:
        return None

def _pet_happiness_text(happiness: int) -> str:
    if happiness >= 80: return "😊 Счастлив"
    if happiness >= 50: return "😐 Доволен"
    if happiness >= 20: return "😟 Грустит"
    return "😢 Голоден! Бонус неактивен"

def _pet_active(happiness: int) -> bool:
    return happiness >= 20

def _ensure_pets_table():
    """Создаём таблицу питомцев если её нет (кроме init_db)."""
    try:
        with get_conn() as conn:
            execute(conn, """
                CREATE TABLE IF NOT EXISTS user_pets (
                    user_id     BIGINT PRIMARY KEY,
                    pet_id      TEXT NOT NULL,
                    happiness   INT  DEFAULT 100,
                    fed_at      TIMESTAMPTZ DEFAULT NOW(),
                    adopted_at  TIMESTAMPTZ DEFAULT NOW()
                )
            """)
    except Exception as e:
        logger.warning("pets table: %s", e)

def _pet_panel(pet_row: dict) -> tuple[str, InlineKeyboardMarkup]:
    pet_id    = pet_row["pet_id"]
    pet       = PETS.get(pet_id, {})
    happiness = pet_row.get("happiness", 100)
    fed_at    = pet_row.get("fed_at")
    active    = _pet_active(happiness)

    # Когда последний раз кормили
    if fed_at:
        if fed_at.tzinfo is None:
            fed_at = fed_at.replace(tzinfo=timezone.utc)
        delta = datetime.now(timezone.utc) - fed_at
        fed_str = f"{int(delta.total_seconds()//3600)} ч назад" if delta.total_seconds() > 3600 else "Недавно"
    else:
        fed_str = "Неизвестно"

    status = _pet_happiness_text(happiness)
    bonus_status = f"✅ Активен" if active else "❌ Неактивен (нужно покормить)"

    text = (
        f"{pet.get('emoji','🐾')} *{pet.get('name', pet_id)}*\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"😊 Настроение: {happiness}/100 — {status}\n"
        f"🍽️ Последнее кормление: {fed_str}\n"
        f"🎁 Бонус: {pet.get('bonus_desc','—')}\n"
        f"📊 Статус бонуса: {bonus_status}\n\n"
        f"_{pet.get('desc','')}_"
    )
    markup = InlineKeyboardMarkup([
        [InlineKeyboardButton("🍖 Покормить", callback_data=f"pet_feed")],
        [InlineKeyboardButton("❌ Отпустить питомца", callback_data="pet_release")],
    ])
    return text, markup

def _shop_keyboard() -> InlineKeyboardMarkup:
    buttons = []
    for pid, pet in PETS.items():
        rare = " 🌟" if pet.get("rare") else ""
        buttons.append([InlineKeyboardButton(
            f"{pet['emoji']} {pet['name']} — {pet['price']}💰  ({pet['bonus_desc']}){rare}",
            callback_data=f"pet_adopt:{pid}"
        )])
    return InlineKeyboardMarkup(buttons)

async def cmd_pets(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not user_exists(user_id):
        await update.message.reply_text(t(user_id, "not_registered"))
        return
    _ensure_pets_table()

    pet_row = _get_pet(user_id)
    if pet_row:
        text, markup = _pet_panel(pet_row)
        await update.message.reply_text(text, parse_mode="Markdown", reply_markup=markup)
    else:
        user = get_user(user_id)
        text = (
            f"🐾 *Питомцы*\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"У тебя пока нет питомца.\n"
            f"Питомцы дают пассивные бонусы, но их нужно кормить каждый день!\n\n"
            f"💰 Твоё золото: {user['gold']}\n\n"
            f"Выбери питомца:"
        )
        await update.message.reply_text(text, parse_mode="Markdown", reply_markup=_shop_keyboard())

async def cb_pet_adopt(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query   = update.callback_query
    user_id = query.from_user.id
    pet_id  = query.data.split(":")[1]

    pet = PETS.get(pet_id)
    if not pet:
        await query.answer("❌ Питомец не найден.", show_alert=True)
        return

    _ensure_pets_table()
    existing = _get_pet(user_id)
    if existing:
        await query.answer("У тебя уже есть питомец! Сначала отпусти его.", show_alert=True)
        return

    user = get_user(user_id)
    if user["gold"] < pet["price"]:
        await query.answer(f"❌ Нужно {pet['price']} золота.", show_alert=True)
        return

    with get_conn() as conn:
        execute(conn, "UPDATE users SET gold = gold - %s WHERE user_id = %s", pet["price"], user_id)
        execute(conn, """
            INSERT INTO user_pets (user_id, pet_id, happiness, fed_at, adopted_at)
            VALUES (%s, %s, 100, NOW(), NOW())
            ON CONFLICT (user_id) DO UPDATE SET pet_id=%s, happiness=100, fed_at=NOW(), adopted_at=NOW()
        """, user_id, pet_id, pet_id)

    # Запись в журнал
    try:
        with get_conn() as conn:
            execute(conn, """
                INSERT INTO player_journal (user_id, event_type, title, description, xp_gained, gold_gained, item_gained)
                VALUES (%s, 'pet', %s, %s, 0, 0, '')
            """, user_id, f"Новый питомец: {pet['name']}", f"Ты завёл {pet['emoji']} {pet['name']}!")
    except Exception:
        pass

    await query.answer(f"✅ {pet['emoji']} {pet['name']} теперь твой!", show_alert=True)
    pet_row = _get_pet(user_id)
    text, markup = _pet_panel(pet_row)
    await query.edit_message_text(text, parse_mode="Markdown", reply_markup=markup)

async def cb_pet_feed(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query   = update.callback_query
    user_id = query.from_user.id
    _ensure_pets_table()

    pet_row = _get_pet(user_id)
    if not pet_row:
        await query.answer("У тебя нет питомца.", show_alert=True)
        return

    fed_at = pet_row.get("fed_at")
    if fed_at:
        if fed_at.tzinfo is None:
            fed_at = fed_at.replace(tzinfo=timezone.utc)
        delta = datetime.now(timezone.utc) - fed_at
        if delta.total_seconds() < 3600 * 6:  # Не чаще раз в 6 часов
            hours_left = int((3600*6 - delta.total_seconds()) // 3600)
            await query.answer(f"Питомец не голоден. Следующее кормление через ~{hours_left} ч.", show_alert=True)
            return

    new_happiness = min(100, pet_row.get("happiness", 50) + FEED_HAPPINESS_GAIN)
    with get_conn() as conn:
        execute(conn, "UPDATE user_pets SET happiness=%s, fed_at=NOW() WHERE user_id=%s",
                new_happiness, user_id)

    pet = PETS.get(pet_row["pet_id"], {})
    await query.answer(f"✅ Ты покормил {pet.get('emoji','')} {pet.get('name','питомца')}! Счастье: {new_happiness}/100", show_alert=True)
    pet_row_fresh = _get_pet(user_id)
    text, markup  = _pet_panel(pet_row_fresh)
    await query.edit_message_text(text, parse_mode="Markdown", reply_markup=markup)

async def cb_pet_release(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query   = update.callback_query
    user_id = query.from_user.id
    _ensure_pets_table()

    pet_row = _get_pet(user_id)
    if not pet_row:
        await query.answer("У тебя нет питомца.", show_alert=True)
        return

    pet = PETS.get(pet_row["pet_id"], {})
    with get_conn() as conn:
        execute(conn, "DELETE FROM user_pets WHERE user_id=%s", user_id)

    await query.answer(f"😢 {pet.get('name','Питомец')} ушёл на свободу.", show_alert=True)
    user = get_user(user_id)
    await query.edit_message_text(
        f"🐾 *Питомцы*\n\nУ тебя пока нет питомца.\n💰 Золото: {user['gold']}\n\nВыбери питомца:",
        parse_mode="Markdown",
        reply_markup=_shop_keyboard()
    )

def get_pet_bonuses(user_id: int) -> dict:
    """Возвращает активные бонусы питомца для использования в других системах."""
    _ensure_pets_table()
    pet_row = _get_pet(user_id)
    if not pet_row:
        return {}
    if not _pet_active(pet_row.get("happiness", 0)):
        return {}
    pet = PETS.get(pet_row["pet_id"], {})
    return pet.get("bonus", {})

def register_pets_handlers(app):
    app.add_handler(CommandHandler("pets", cmd_pets))
    app.add_handler(CallbackQueryHandler(cb_pet_adopt,   pattern=r"^pet_adopt:"))
    app.add_handler(CallbackQueryHandler(cb_pet_feed,    pattern=r"^pet_feed$"))
    app.add_handler(CallbackQueryHandler(cb_pet_release, pattern=r"^pet_release$"))
