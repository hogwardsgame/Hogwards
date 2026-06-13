"""
Питомцы — система питомцев с прокачкой и эволюцией.
Питомец получает опыт когда игрок сражается. На ключевых уровнях эволюционирует,
усиливая бонусы. Кормить раз в 6ч, иначе бонус неактивен.
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
from utils.helpers import progress_bar

logger = logging.getLogger(__name__)

# ── Каталог питомцев с эволюциями ─────────────────────────────────────────────
# Каждый питомец имеет 3 стадии. Эволюция на уровнях 5 и 12.
# bonus_mult растёт со стадией: стадия 0 = ×1, стадия 1 = ×1.6, стадия 2 = ×2.5
PETS: dict[str, dict] = {
    "owl": {
        "name": "Сова", "emoji": "🦉", "price": 500,
        "desc": "Верный почтовый помощник. Умная птица с острыми когтями.",
        "base_bonus": {"xp_mult": 0.08},
        "bonus_label": "к опыту",
        "stages": [
            {"name": "Совёнок",       "emoji": "🐤"},
            {"name": "Сова",          "emoji": "🦉"},
            {"name": "Полярная сова", "emoji": "🦉❄️"},
        ],
    },
    "cat": {
        "name": "Кошка", "emoji": "🐱", "price": 400,
        "desc": "Независимая и загадочная. Чувствует магию лучше любого прибора.",
        "base_bonus": {"luck": 2},
        "bonus_label": "к удаче",
        "stages": [
            {"name": "Котёнок",         "emoji": "🐈"},
            {"name": "Кошка",           "emoji": "🐱"},
            {"name": "Книззл",          "emoji": "🐈‍⬛"},
        ],
    },
    "toad": {
        "name": "Жаба", "emoji": "🐸", "price": 200,
        "desc": "Незаменима для зельеварения. Её слизь — ценный ингредиент.",
        "base_bonus": {"potion_speed": 0.12},
        "bonus_label": "к скорости варки",
        "stages": [
            {"name": "Головастик",   "emoji": "🐛"},
            {"name": "Жаба",         "emoji": "🐸"},
            {"name": "Королевская жаба", "emoji": "🐸👑"},
        ],
    },
    "rat": {
        "name": "Крыса", "emoji": "🐀", "price": 150,
        "desc": "Хитрый грызун. Иногда находит монетки в неожиданных местах.",
        "base_bonus": {"gold_mult": 0.07},
        "bonus_label": "к золоту",
        "stages": [
            {"name": "Крысёнок",  "emoji": "🐁"},
            {"name": "Крыса",     "emoji": "🐀"},
            {"name": "Крыса-вор", "emoji": "🐀💰"},
        ],
    },
    "phoenix": {
        "name": "Феникс", "emoji": "🔥🦅", "price": 5000, "rare": True,
        "desc": "Легендарная птица возрождения. Её слёзы исцеляют раны.",
        "base_bonus": {"hp_regen": 4, "xp_mult": 0.10},
        "bonus_label": "к опыту и реген HP",
        "stages": [
            {"name": "Птенец феникса", "emoji": "🐣🔥"},
            {"name": "Феникс",          "emoji": "🔥🦅"},
            {"name": "Древний феникс",   "emoji": "🔥🦅✨"},
        ],
    },
}

# Уровни эволюции и множители бонуса по стадиям
EVOLVE_LEVELS   = [5, 12]          # стадия 1 на ур.5, стадия 2 на ур.12
STAGE_MULT      = [1.0, 1.6, 2.5]  # множитель бонуса для каждой стадии
PET_MAX_LEVEL   = 20

HAPPINESS_DECAY_PER_DAY = 20
FEED_HAPPINESS_GAIN     = 30
FEED_PET_XP             = 15        # кормление тоже даёт немного опыта питомцу

def _pet_xp_needed(level: int) -> int:
    """Опыт для следующего уровня питомца."""
    return int(50 * level * 1.3)

def _get_stage(level: int) -> int:
    stage = 0
    for i, lvl in enumerate(EVOLVE_LEVELS):
        if level >= lvl:
            stage = i + 1
    return stage

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
    try:
        with get_conn() as conn:
            execute(conn, """
                CREATE TABLE IF NOT EXISTS user_pets (
                    user_id     BIGINT PRIMARY KEY,
                    pet_id      TEXT NOT NULL,
                    happiness   INT  DEFAULT 100,
                    level       INT  DEFAULT 1,
                    xp          INT  DEFAULT 0,
                    fed_at      TIMESTAMPTZ DEFAULT NOW(),
                    adopted_at  TIMESTAMPTZ DEFAULT NOW()
                )
            """)
            # Миграция для старых таблиц
            execute(conn, "ALTER TABLE user_pets ADD COLUMN IF NOT EXISTS level INT DEFAULT 1")
            execute(conn, "ALTER TABLE user_pets ADD COLUMN IF NOT EXISTS xp INT DEFAULT 0")
    except Exception as e:
        logger.warning("pets table: %s", e)

def _current_bonus(pet_id: str, level: int) -> dict:
    """Бонус питомца с учётом стадии эволюции."""
    pet = PETS.get(pet_id, {})
    base = pet.get("base_bonus", {})
    stage = _get_stage(level)
    mult  = STAGE_MULT[stage]
    return {k: (round(v * mult, 2) if isinstance(v, float) else int(v * mult)) for k, v in base.items()}

def _bonus_desc(pet_id: str, level: int) -> str:
    pet = PETS.get(pet_id, {})
    bonus = _current_bonus(pet_id, level)
    parts = []
    for k, v in bonus.items():
        if k.endswith("_mult"):
            parts.append(f"+{int(v*100)}%")
        elif k == "potion_speed":
            parts.append(f"-{int(v*100)}% времени")
        else:
            parts.append(f"+{v}")
    return f"{' '.join(parts)} {pet.get('bonus_label','')}"

def _pet_panel(pet_row: dict) -> tuple[str, InlineKeyboardMarkup]:
    pet_id    = pet_row["pet_id"]
    pet       = PETS.get(pet_id, {})
    happiness = pet_row.get("happiness", 100)
    level     = pet_row.get("level", 1)
    xp        = pet_row.get("xp", 0)
    fed_at    = pet_row.get("fed_at")
    active    = _pet_active(happiness)
    stage     = _get_stage(level)

    stage_info = pet.get("stages", [{}])[min(stage, len(pet.get("stages",[1]))-1)]
    pet_emoji  = stage_info.get("emoji", pet.get("emoji", "🐾"))
    pet_name   = stage_info.get("name", pet.get("name", pet_id))

    if fed_at:
        if fed_at.tzinfo is None:
            fed_at = fed_at.replace(tzinfo=timezone.utc)
        delta = datetime.now(timezone.utc) - fed_at
        fed_str = f"{int(delta.total_seconds()//3600)} ч назад" if delta.total_seconds() > 3600 else "Недавно"
    else:
        fed_str = "Неизвестно"

    xp_need = _pet_xp_needed(level)
    xp_bar  = progress_bar(xp, xp_need)
    happy_bar = progress_bar(happiness, 100)

    # Подсказка о следующей эволюции
    evolve_hint = ""
    for lvl in EVOLVE_LEVELS:
        if level < lvl:
            evolve_hint = f"\n🔮 Эволюция на {lvl} уровне!"
            break

    bonus_status = "✅ Активен" if active else "❌ Неактивен (покорми!)"

    text = (
        f"{pet_emoji} *{pet_name}*\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"⭐ Уровень: {level}{'  (МАКС)' if level >= PET_MAX_LEVEL else ''}\n"
        f"✨ Опыт:    {xp_bar}  {xp}/{xp_need}\n"
        f"😊 Счастье: {happy_bar}  {happiness}/100\n"
        f"   {_pet_happiness_text(happiness)}\n"
        f"🍽️ Кормление: {fed_str}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🎁 Бонус: {_bonus_desc(pet_id, level)}\n"
        f"📊 Статус: {bonus_status}"
        f"{evolve_hint}\n\n"
        f"_{pet.get('desc','')}_"
    )
    markup = InlineKeyboardMarkup([
        [InlineKeyboardButton("🍖 Покормить", callback_data="pet_feed")],
        [InlineKeyboardButton("🎓 Тренировать (50💰)", callback_data="pet_train")],
        [InlineKeyboardButton("❌ Отпустить питомца", callback_data="pet_release")],
    ])
    return text, markup

def _shop_keyboard() -> InlineKeyboardMarkup:
    buttons = []
    for pid, pet in PETS.items():
        rare = " 🌟" if pet.get("rare") else ""
        buttons.append([InlineKeyboardButton(
            f"{pet['emoji']} {pet['name']} — {pet['price']}💰{rare}",
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
        try:
            from handlers.images import send_with_image
            await send_with_image(update.get_bot(), update.effective_chat.id, "pets", text, reply_markup=markup)
        except Exception:
            await update.message.reply_text(text, parse_mode="Markdown", reply_markup=markup)
    else:
        user = get_user(user_id)
        text = (
            f"🐾 *Питомцы*\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"У тебя пока нет питомца.\n"
            f"Питомцы получают опыт в боях, растут в уровне и *эволюционируют*, "
            f"усиливая свой бонус! Но их нужно кормить.\n\n"
            f"💰 Твоё золото: {user['gold']}\n\n"
            f"Выбери питомца:"
        )
        await update.message.reply_text(text, parse_mode="Markdown", reply_markup=_shop_keyboard())

async def cb_pet_adopt(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query   = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    pet_id  = query.data.split(":")[1]
    pet = PETS.get(pet_id)
    if not pet:
        await query.answer("❌ Питомец не найден.", show_alert=True)
        return
    _ensure_pets_table()
    if _get_pet(user_id):
        await query.answer("У тебя уже есть питомец! Сначала отпусти его.", show_alert=True)
        return
    user = get_user(user_id)
    if user["gold"] < pet["price"]:
        await query.answer(f"❌ Нужно {pet['price']} золота.", show_alert=True)
        return
    with get_conn() as conn:
        execute(conn, "UPDATE users SET gold = gold - %s WHERE user_id = %s", pet["price"], user_id)
        execute(conn, """
            INSERT INTO user_pets (user_id, pet_id, happiness, level, xp, fed_at, adopted_at)
            VALUES (%s, %s, 100, 1, 0, NOW(), NOW())
            ON CONFLICT (user_id) DO UPDATE SET pet_id=%s, happiness=100, level=1, xp=0, fed_at=NOW(), adopted_at=NOW()
        """, user_id, pet_id, pet_id)
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
    await query.answer()
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
        if delta.total_seconds() < 3600 * 6:
            hours_left = int((3600*6 - delta.total_seconds()) // 3600) + 1
            await query.answer(f"Питомец не голоден. Покормить можно через ~{hours_left} ч.", show_alert=True)
            return
    new_happiness = min(100, pet_row.get("happiness", 50) + FEED_HAPPINESS_GAIN)
    with get_conn() as conn:
        execute(conn, "UPDATE user_pets SET happiness=%s, fed_at=NOW() WHERE user_id=%s", new_happiness, user_id)
    # Кормление даёт питомцу опыт
    leveled, evolved, new_level = _add_pet_xp(user_id, FEED_PET_XP)
    pet = PETS.get(pet_row["pet_id"], {})
    msg = f"✅ Покормил! Счастье: {new_happiness}/100"
    if evolved:
        msg = f"🎉 {pet.get('name','Питомец')} эволюционировал до {new_level} уровня!"
    await query.answer(msg, show_alert=True)
    text, markup = _pet_panel(_get_pet(user_id))
    await query.edit_message_text(text, parse_mode="Markdown", reply_markup=markup)

async def cb_pet_train(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query   = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    _ensure_pets_table()
    pet_row = _get_pet(user_id)
    if not pet_row:
        await query.answer("У тебя нет питомца.", show_alert=True)
        return
    user = get_user(user_id)
    if user["gold"] < 50:
        await query.answer("❌ Нужно 50 золота для тренировки.", show_alert=True)
        return
    if pet_row.get("level", 1) >= PET_MAX_LEVEL:
        await query.answer("Питомец уже достиг максимального уровня!", show_alert=True)
        return
    with get_conn() as conn:
        execute(conn, "UPDATE users SET gold = gold - 50 WHERE user_id = %s", user_id)
    leveled, evolved, new_level = _add_pet_xp(user_id, 40)
    pet = PETS.get(pet_row["pet_id"], {})
    if evolved:
        msg = f"🎉 Эволюция! {pet.get('name','Питомец')} достиг {new_level} уровня!"
    elif leveled:
        msg = f"⬆️ Питомец вырос до {new_level} уровня!"
    else:
        msg = "✅ Тренировка прошла успешно! +40 опыта питомцу."
    await query.answer(msg, show_alert=True)
    text, markup = _pet_panel(_get_pet(user_id))
    await query.edit_message_text(text, parse_mode="Markdown", reply_markup=markup)

async def cb_pet_release(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query   = update.callback_query
    await query.answer()
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
        parse_mode="Markdown", reply_markup=_shop_keyboard()
    )

def _add_pet_xp(user_id: int, amount: int) -> tuple[bool, bool, int]:
    """Добавить опыт питомцу. Возвращает (leveled_up, evolved, new_level)."""
    _ensure_pets_table()
    pet_row = _get_pet(user_id)
    if not pet_row:
        return False, False, 0
    level = pet_row.get("level", 1)
    xp    = pet_row.get("xp", 0) + amount
    if level >= PET_MAX_LEVEL:
        return False, False, level
    old_stage = _get_stage(level)
    leveled = False
    while level < PET_MAX_LEVEL:
        need = _pet_xp_needed(level)
        if xp >= need:
            xp -= need
            level += 1
            leveled = True
        else:
            break
    new_stage = _get_stage(level)
    evolved = new_stage > old_stage
    try:
        with get_conn() as conn:
            execute(conn, "UPDATE user_pets SET level=%s, xp=%s WHERE user_id=%s", level, xp, user_id)
    except Exception:
        pass
    return leveled, evolved, level

def add_pet_xp(user_id: int, amount: int):
    """Публичная функция — вызывается из боёв чтобы дать питомцу опыт."""
    try:
        _add_pet_xp(user_id, amount)
    except Exception:
        pass

def get_pet_bonuses(user_id: int) -> dict:
    """Активные бонусы питомца с учётом уровня/эволюции."""
    _ensure_pets_table()
    pet_row = _get_pet(user_id)
    if not pet_row:
        return {}
    if not _pet_active(pet_row.get("happiness", 0)):
        return {}
    return _current_bonus(pet_row["pet_id"], pet_row.get("level", 1))

def register_pets_handlers(app):
    app.add_handler(CommandHandler("pets", cmd_pets))
    app.add_handler(CallbackQueryHandler(cb_pet_adopt,   pattern=r"^pet_adopt:"))
    app.add_handler(CallbackQueryHandler(cb_pet_feed,    pattern=r"^pet_feed$"))
    app.add_handler(CallbackQueryHandler(cb_pet_train,   pattern=r"^pet_train$"))
    app.add_handler(CallbackQueryHandler(cb_pet_release, pattern=r"^pet_release$"))
