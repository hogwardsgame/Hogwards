"""
Навигация — категоризированное меню «Др. команды», кнопка «Что дальше?»,
прогрессивная разблокировка контента по уровню.
Цель: новичок не теряется среди 20+ кнопок.
"""
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler
from database import user_exists, get_user, get_conn, fetchrow
from utils.i18n import t

logger = logging.getLogger(__name__)

# ── Требования по уровню для контента ─────────────────────────────────────────
LEVEL_REQUIREMENTS = {
    "blackmarket": 5,
    "triwizard":   5,
    "horcruxes":   10,
    "worldboss":   3,
}

# ── Категории меню: (callback_id, эмодзи+название, [список действий]) ──────────
# Каждое действие: (command_key, label, min_level)
CATEGORIES = {
    "adventure": {
        "title": "🗺️ Приключения",
        "desc":  "Сражайся с монстрами, исследуй мир и находи сокровища.",
        "items": [
            ("forest",    "🌲 Запретный лес",   1),
            ("explore",   "🧭 Исследовать",      1),
            ("worldboss", "🐉 Мировой босс",     3),
            ("hogsmeade", "🍺 Хогсмид",          1),
            ("room",      "🚪 Выручай-комната",  1),
        ],
    },
    "combat": {
        "title": "⚔️ Сражения",
        "desc":  "Дуэли с игроками и турниры.",
        "items": [
            ("duel",       "⚔️ Дуэль",            1),
            ("league",     "🎖️ Дуэльная лига",   1),
            ("tournament", "🏆 Турнир",           1),
            ("triwizard",  "🏅 Турнир Трёх",      5),
        ],
    },
    "economy": {
        "title": "🏛️ Экономика",
        "desc":  "Зарабатывай, копи и улучшай снаряжение.",
        "items": [
            ("gringotts",   "🏦 Гринготтс",      1),
            ("forge",       "⚒️ Кузница",        1),
            ("wandcraft",   "🪄 Мастерская палочек", 1),
            ("trade",       "🤝 Обмен",          1),
            ("blackmarket", "🕯️ Чёрный рынок",  5),
        ],
    },
    "social": {
        "title": "👥 Социальное",
        "desc":  "Отряды, факультет и совместная игра.",
        "items": [
            ("squad", "🛡️ Отряд",          1),
            ("house", "🏠 Мой факультет",   1),
        ],
    },
    "personal": {
        "title": "🎮 Личное",
        "desc":  "Питомцы, зелья, достижения и история.",
        "items": [
            ("pets",         "🐾 Питомцы",      1),
            ("myroom",       "🏠 Моя комната",  1),
            ("potions",      "🧪 Зелья",        1),
            ("achievements", "🎖️ Достижения",  1),
            ("collections",  "📦 Коллекции",    1),
            ("titles",       "🏷️ Титулы",      1),
            ("journal",      "📖 История",      1),
            ("horcruxes",    "💎 Крестражи",    10),
        ],
    },
}

# Сопоставление command_key → (module, function) для исполнения
COMMAND_MAP = {
    "forest":      ("handlers.forbidden_forest", "cmd_forest"),
    "explore":     ("handlers.locations",        "cmd_explore"),
    "worldboss":   ("handlers.world_bosses",     "cmd_worldboss"),
    "hogsmeade":   ("handlers.hogsmeade",        "cmd_hogsmeade"),
    "room":        ("handlers.room_of_requirement","cmd_room"),
    "duel":        ("handlers.duel",             "cmd_duel"),
    "tournament":  ("handlers.tournament",       "cmd_tournament"),
    "triwizard":   ("handlers.triwizard",        "cmd_triwizard"),
    "gringotts":   ("handlers.gringotts",        "cmd_gringotts"),
    "forge":       ("handlers.forge",            "cmd_forge"),
    "trade":       ("handlers.trade",            "cmd_trade"),
    "blackmarket": ("handlers.black_market",     "cmd_black_market"),
    "squad":       ("handlers.squads",           "cmd_squad"),
    "house":       ("handlers.house_points",     "cmd_house"),
    "pets":        ("handlers.pets",             "cmd_pets"),
    "potions":     ("handlers.potion_system",    "cmd_potions"),
    "achievements":("handlers.achievements",     "cmd_achievements"),
    "titles":      ("handlers.titles",           "cmd_titles"),
    "journal":     ("handlers.player_journal",   "cmd_journal"),
    "horcruxes":   ("handlers.horcruxes",        "cmd_horcruxes"),
    "collections": ("handlers.collections",      "cmd_collections"),
    "league":      ("handlers.duel_league",       "cmd_league"),
    "myroom":      ("handlers.my_room",           "cmd_my_room"),
    "wandcraft":   ("handlers.wandcraft",         "cmd_wandcraft"),
}

def _categories_keyboard() -> InlineKeyboardMarkup:
    buttons = []
    cats = list(CATEGORIES.items())
    # По 1 категории в строке для читаемости
    for cat_id, cat in cats:
        buttons.append([InlineKeyboardButton(cat["title"], callback_data=f"nav_cat:{cat_id}")])
    buttons.append([InlineKeyboardButton("🎯 Что мне делать дальше?", callback_data="nav_next")])
    return InlineKeyboardMarkup(buttons)

def _category_items_keyboard(cat_id: str, user_level: int) -> InlineKeyboardMarkup:
    cat = CATEGORIES.get(cat_id)
    buttons = []
    for cmd_key, label, min_level in cat["items"]:
        if user_level >= min_level:
            buttons.append([InlineKeyboardButton(label, callback_data=f"nav_go:{cmd_key}")])
        else:
            buttons.append([InlineKeyboardButton(
                f"🔒 {label} (ур. {min_level})",
                callback_data=f"nav_locked:{min_level}"
            )])
    buttons.append([InlineKeyboardButton("◀️ К разделам", callback_data="nav_main")])
    return InlineKeyboardMarkup(buttons)

async def cmd_navigation(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Открыть категоризированное меню (заменяет старое «Др. команды»)."""
    user_id = update.effective_user.id
    if not user_exists(user_id):
        await update.message.reply_text(t(user_id, "not_registered"))
        return
    await update.message.reply_text(
        "🗺️ *Другие команды*\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "Выбери раздел — всё разложено по полочкам:",
        parse_mode="Markdown",
        reply_markup=_categories_keyboard()
    )

async def cb_nav_main(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        "🗺️ *Другие команды*\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "Выбери раздел — всё разложено по полочкам:",
        parse_mode="Markdown",
        reply_markup=_categories_keyboard()
    )

async def cb_nav_cat(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query   = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    cat_id  = query.data.split(":")[1]
    cat     = CATEGORIES.get(cat_id)
    if not cat:
        await query.edit_message_text("❌ Раздел не найден.")
        return
    user  = get_user(user_id)
    level = user["level"]
    await query.edit_message_text(
        f"{cat['title']}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"_{cat['desc']}_\n\n"
        f"🔒 — откроется на указанном уровне (твой: {level})",
        parse_mode="Markdown",
        reply_markup=_category_items_keyboard(cat_id, level)
    )

async def cb_nav_go(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query   = update.callback_query
    await query.answer()
    cmd_key = query.data.split(":")[1]

    mapping = COMMAND_MAP.get(cmd_key)
    if not mapping:
        await query.answer("❌ Команда не найдена.", show_alert=True)
        return

    module_name, func_name = mapping
    try:
        import importlib
        module = importlib.import_module(module_name)
        func   = getattr(module, func_name)
        # Передаём «псевдо-update»: effective_user реальный, message = сообщение из callback.
        # cmd_-функции вызовут message.reply_text → отправят новое сообщение (это и нужно).
        wrapper = _CallbackUpdate(update)
        await func(wrapper, ctx)
    except Exception as e:
        logger.exception("nav_go %s: %s", cmd_key, e)
        await query.message.reply_text(f"⚠️ Не удалось открыть раздел. Попробуй ещё раз.")


class _CallbackUpdate:
    """Обёртка: позволяет вызывать cmd_-функции (ждут update.message) из callback."""
    def __init__(self, real_update):
        self._u = real_update
    @property
    def effective_user(self):
        return self._u.effective_user
    @property
    def effective_chat(self):
        return self._u.effective_chat
    @property
    def message(self):
        return self._u.callback_query.message
    @property
    def callback_query(self):
        return None

async def cb_nav_locked(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    min_level = query.data.split(":")[1]
    await query.answer(
        f"🔒 Этот раздел откроется на {min_level}-м уровне.\n"
        f"Проходи уроки, квесты и подземелья чтобы расти!",
        show_alert=True
    )

async def cb_nav_next(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Умная подсказка «что делать дальше» на основе прогресса игрока."""
    query   = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    user    = get_user(user_id)

    suggestions = _build_suggestions(user_id, user)
    text = (
        f"🎯 *Что делать дальше, {user['wizard_name']}?*\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"Уровень: {user['level']}  •  💰 {user['gold']}\n\n"
        + "\n\n".join(suggestions)
    )
    await query.edit_message_text(
        text, parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("◀️ К разделам", callback_data="nav_main")
        ]])
    )

def _build_suggestions(user_id: int, user: dict) -> list[str]:
    """Генерирует персональные советы по прогрессу."""
    sugg = []
    level = user["level"]

    # 1. Ежедневный бонус
    try:
        with get_conn() as conn:
            from datetime import datetime, timezone
            row = fetchrow(conn, "SELECT last_login FROM login_streaks WHERE user_id=%s", user_id)
        today = datetime.now(timezone.utc).date()
        if not row or row.get("last_login") != today:
            sugg.append("🎁 *Забери ежедневный бонус!*\nЖми кнопку «Бонус дня» в главном меню — серия входов даёт всё лучшие награды.")
    except Exception:
        pass

    # 2. Снаряжение
    try:
        with get_conn() as conn:
            eq = fetchrow(conn, "SELECT COUNT(*) as cnt FROM equipped_items WHERE user_id=%s", user_id)
        if not eq or eq["cnt"] == 0:
            sugg.append("⚙️ *Надень снаряжение!*\nКупи предмет в 🏪 Магазине и надень через 🎒 Инвентарь — вырастут атака и защита.")
    except Exception:
        pass

    # 3. По уровню
    if level < 5:
        sugg.append("📚 *Проходи уроки и подземелья!*\nЭто самый быстрый способ набрать опыт на первых уровнях.")
    elif level < 10:
        sugg.append("🐉 *Попробуй мирового босса!*\nОн появляется в 12:00 и 20:00 UTC — бей вместе с другими за крупные награды.")
    else:
        sugg.append("💎 *Займись Крестражами!*\nСерверный квест: найди и уничтожь 7 крестражей Волдеморта.")

    # 4. Питомец
    try:
        with get_conn() as conn:
            pet = fetchrow(conn, "SELECT 1 FROM user_pets WHERE user_id=%s", user_id)
        if not pet:
            sugg.append("🐾 *Заведи питомца!*\nСова, кошка или жаба дают постоянный бонус. Раздел «Личное».")
    except Exception:
        pass

    # 5. Банк если много золота
    if user["gold"] >= 1000:
        sugg.append("🏦 *Положи золото в Гринготтс!*\nПод 1% в день — деньги работают пока ты отдыхаешь.")

    if not sugg:
        sugg.append("✨ Ты молодец! Продолжай в том же духе — проверь достижения и попробуй турниры.")

    return sugg[:4]  # не перегружаем

def register_navigation_handlers(app):
    app.add_handler(CommandHandler("nav", cmd_navigation))
    app.add_handler(CallbackQueryHandler(cb_nav_main,   pattern=r"^nav_main$"))
    app.add_handler(CallbackQueryHandler(cb_nav_cat,    pattern=r"^nav_cat:"))
    app.add_handler(CallbackQueryHandler(cb_nav_go,     pattern=r"^nav_go:"))
    app.add_handler(CallbackQueryHandler(cb_nav_locked, pattern=r"^nav_locked:"))
    app.add_handler(CallbackQueryHandler(cb_nav_next,   pattern=r"^nav_next$"))
