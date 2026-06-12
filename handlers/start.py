import logging
import asyncio
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ContextTypes, CommandHandler, MessageHandler,
    CallbackQueryHandler, ConversationHandler, filters,
    ApplicationHandlerStop,
)
from database import user_exists, wizard_name_taken, create_user, get_house_counts, set_user_lang, get_user
from utils.i18n import t, t_lang, set_cached_lang
from utils.helpers import validate_wizard_name, pick_house, get_starter_spell
from config import ADMIN_IDS

logger = logging.getLogger(__name__)

CHOOSE_LANG, ENTER_NAME, TUTORIAL = range(3)
MAIN_ADMIN_ID = 6903827237
ADMIN_USER_IDS = set(ADMIN_IDS or []) | {MAIN_ADMIN_ID}

LANG_OPTIONS = [
    ("🇷🇺 Русский", "ru"),
    ("🇬🇧 English", "en"),
    ("🇪🇸 Español", "es"),
    ("🇩🇪 Deutsch", "de"),
    ("🇧🇷 Português", "pt"),
]


def lang_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(label, callback_data=f"lang:{code}") for label, code in LANG_OPTIONS]
    ])


def tutorial_keyboard(user_id: int):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(t(user_id, "btn_next"), callback_data="tutorial:next")]
    ])


def main_menu_keyboard(user_id: int) -> ReplyKeyboardMarkup:
    buttons = [
        [KeyboardButton(t(user_id, "btn_profile")),   KeyboardButton(t(user_id, "btn_inventory"))],
        [KeyboardButton(t(user_id, "btn_shop")),       KeyboardButton(t(user_id, "btn_lessons"))],
        [KeyboardButton(t(user_id, "btn_duel")),       KeyboardButton(t(user_id, "btn_quests"))],
        [KeyboardButton(t(user_id, "btn_daily")),      KeyboardButton(t(user_id, "btn_info"))],
        [KeyboardButton(t(user_id, "btn_other_commands"))],
    ]
    if user_id in ADMIN_USER_IDS:
        buttons.append([KeyboardButton(t(user_id, "btn_admin_panel"))])
    return ReplyKeyboardMarkup(buttons, resize_keyboard=True)


def other_menu_keyboard(user_id: int) -> ReplyKeyboardMarkup:
    buttons = [
        [KeyboardButton(t(user_id, "btn_house")),        KeyboardButton(t(user_id, "btn_worldboss"))],
        [KeyboardButton(t(user_id, "btn_tournament")),   KeyboardButton(t(user_id, "btn_hogsmeade"))],
        [KeyboardButton(t(user_id, "btn_room")),         KeyboardButton(t(user_id, "btn_potions"))],
        [KeyboardButton(t(user_id, "btn_squad")),        KeyboardButton(t(user_id, "btn_trade"))],
        [KeyboardButton(t(user_id, "btn_achievements")), KeyboardButton(t(user_id, "btn_titles"))],
        [KeyboardButton(t(user_id, "btn_explore")),      KeyboardButton(t(user_id, "btn_forest"))],
        [KeyboardButton(t(user_id, "btn_pets")),         KeyboardButton(t(user_id, "btn_blackmarket"))],
        [KeyboardButton(t(user_id, "btn_horcruxes")),    KeyboardButton(t(user_id, "btn_triwizard"))],
        [KeyboardButton(t(user_id, "btn_gringotts")),    KeyboardButton(t(user_id, "btn_forge"))],
        [KeyboardButton(t(user_id, "btn_journal")),      KeyboardButton(t(user_id, "btn_back_main_menu"))],
    ]
    if user_id in ADMIN_USER_IDS:
        buttons.append([
            KeyboardButton(t(user_id, "btn_admin_stats")),
            KeyboardButton(t(user_id, "btn_admin_items")),
        ])
        buttons.append([
            KeyboardButton(t(user_id, "btn_admin_spells")),
            KeyboardButton(t(user_id, "btn_admin_economy")),
        ])
        buttons.append([
            KeyboardButton(t(user_id, "btn_admin_log")),
            KeyboardButton(t(user_id, "btn_admin_bosses")),
            KeyboardButton(t(user_id, "btn_admin_maintenance")),
        ])
    return ReplyKeyboardMarkup(buttons, resize_keyboard=True)


async def _db(func, *args):
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, func, *args)


async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    exists = await _db(user_exists, user_id)
    if exists:
        user = await _db(get_user, user_id)
        set_cached_lang(user_id, user["lang"])
        await update.message.reply_text(
            t(user_id, "already_registered"),
            reply_markup=main_menu_keyboard(user_id),
        )
        return ConversationHandler.END
    await update.message.reply_text(t_lang("ru", "choose_lang"), reply_markup=lang_keyboard())
    return CHOOSE_LANG


async def cb_choose_lang(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    lang = query.data.split(":")[1]
    user_id = query.from_user.id
    set_cached_lang(user_id, lang)
    ctx.user_data["lang"] = lang
    await query.edit_message_text(t(user_id, "welcome"))
    return ENTER_NAME


async def handle_name_input(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    name = update.message.text.strip()
    error = validate_wizard_name(name)
    if error:
        await update.message.reply_text(t(user_id, error))
        return ENTER_NAME
    taken = await _db(lambda: wizard_name_taken(name))
    if taken:
        await update.message.reply_text(t(user_id, "name_taken"))
        return ENTER_NAME
    ctx.user_data["wizard_name"] = name
    hat_msg = await update.message.reply_text(t(user_id, "sorting_hat"), parse_mode="Markdown")
    house_counts = await _db(get_house_counts)
    house = pick_house(house_counts)
    starter_spell = get_starter_spell(house)
    lang = ctx.user_data.get("lang", "ru")
    await _db(lambda: create_user(
        user_id=user_id,
        username=update.effective_user.username or "",
        wizard_name=name,
        house=house,
        lang=lang,
        starter_spell=starter_spell,
    ))
    await hat_msg.edit_text(t(user_id, f"sorted_{house}"), parse_mode="Markdown")
    await update.message.reply_text(t(user_id, "starter_items"))
    ctx.user_data["tutorial_step"] = 1
    await update.message.reply_text(t(user_id, "tutorial_1"), reply_markup=tutorial_keyboard(user_id))
    return TUTORIAL


async def cb_tutorial(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    step = ctx.user_data.get("tutorial_step", 1) + 1
    ctx.user_data["tutorial_step"] = step
    if step <= 5:
        markup = tutorial_keyboard(user_id) if step < 5 else None
        await query.edit_message_text(t(user_id, f"tutorial_{step}"), reply_markup=markup)
        if step == 5:
            await query.message.reply_text(
                t(user_id, "main_menu"),
                reply_markup=main_menu_keyboard(user_id),
            )
            return ConversationHandler.END
    return TUTORIAL


async def cmd_menu(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Команда /menu — всегда возвращает основное меню + баннер события дня."""
    user_id = update.effective_user.id
    if not await _db(user_exists, user_id):
        await update.message.reply_text(t(user_id, "not_registered"))
        return

    # Баннер события дня и мирового босса
    banner = ""
    try:
        from handlers.daily_bonus import get_today_event
        from database import get_active_world_boss
        event = get_today_event()
        banner = f"\n{event['name']}\n_{event['desc']}_\n"
        wb = get_active_world_boss()
        if wb:
            banner += f"\n⚠️ *Мировой босс сейчас активен!* Жми 🐉 Мировой босс"
        else:
            from handlers.world_bosses import _next_spawn_info
            until, _, _, next_time = _next_spawn_info()
            banner += f"\n🐉 Следующий босс через *{until}* ({next_time} UTC)"
    except Exception:
        pass

    menu_text = t(user_id, "main_menu")
    if banner:
        menu_text = f"{menu_text}\n━━━━━━━━━━━━━━━━━━━━{banner}"

    await update.message.reply_text(
        menu_text,
        parse_mode="Markdown",
        reply_markup=main_menu_keyboard(user_id),
    )


# ── Таблица маршрутизации кнопок ──────────────────────────────────────────────
# Ключ — i18n-ключ кнопки, значение — (module, function)
_BUTTON_ROUTES: list[tuple[str, str, str]] = [
    ("btn_profile",      "handlers.profile",         "show_profile"),
    ("btn_inventory",    "handlers.inventory",        "cmd_inventory"),
    ("btn_shop",         "handlers.shop",             "cmd_shop"),
    ("btn_lessons",      "handlers.lessons",          "cmd_lessons"),
    ("btn_quests",       "handlers.quests",           "cmd_quests"),
    ("btn_house",        "handlers.house_points",     "cmd_house"),
    ("btn_worldboss",    "handlers.world_bosses",     "cmd_worldboss"),
    ("btn_tournament",   "handlers.tournament",       "cmd_tournament"),
    ("btn_hogsmeade",    "handlers.hogsmeade",        "cmd_hogsmeade"),
    ("btn_room",         "handlers.room_of_requirement", "cmd_room"),
    ("btn_potions",      "handlers.potion_system",    "cmd_potions"),
    ("btn_squad",        "handlers.squads",           "cmd_squad"),
    ("btn_trade",        "handlers.trade",            "cmd_trade"),
    ("btn_achievements", "handlers.achievements",     "cmd_achievements"),
    ("btn_titles",       "handlers.titles",           "cmd_titles"),
    ("btn_explore",      "handlers.locations",        "cmd_explore"),
    # Новые системы
    ("btn_forest",       "handlers.forbidden_forest", "cmd_forest"),
    ("btn_pets",         "handlers.pets",             "cmd_pets"),
    ("btn_blackmarket",  "handlers.black_market",     "cmd_black_market"),
    ("btn_journal",      "handlers.player_journal",   "cmd_journal"),
    ("btn_horcruxes",    "handlers.horcruxes",        "cmd_horcruxes"),
    ("btn_triwizard",    "handlers.triwizard",        "cmd_triwizard"),
    ("btn_duel",         "handlers.duel",             "cmd_duel"),
    ("btn_daily",        "handlers.daily_bonus",      "cmd_daily"),
    ("btn_info",         "handlers.info",             "cmd_info"),
    ("btn_gringotts",    "handlers.gringotts",        "cmd_gringotts"),
    ("btn_forge",        "handlers.forge",            "cmd_forge"),
    # Админ
    ("btn_admin_panel",        "handlers.admin_panel", "cmd_admin_panel"),
    ("btn_admin_stats",        "handlers.admin", "cmd_stats"),
    ("btn_admin_items",        "handlers.admin", "cmd_list_items"),
    ("btn_admin_spells",       "handlers.admin", "cmd_list_spells"),
    ("btn_admin_economy",      "handlers.admin", "cmd_economy_info"),
    ("btn_admin_log",          "handlers.admin", "cmd_admin_log"),
    ("btn_admin_bosses",       "handlers.admin", "cmd_list_bosses"),
    ("btn_admin_maintenance",  "handlers.admin", "cmd_maintenance"),
]

# Кэш импортированных функций — импортируем один раз при первом вызове
import importlib
_func_cache: dict[str, object] = {}

def _get_func(module: str, func_name: str):
    key = f"{module}.{func_name}"
    if key not in _func_cache:
        mod = importlib.import_module(module)
        _func_cache[key] = getattr(mod, func_name)
    return _func_cache[key]


async def handle_main_menu_buttons(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """
    Центральный роутер кнопок Reply-клавиатуры.
    Регистрируется в group=0, обрабатывает все текстовые кнопки меню.
    После обработки вызывает ApplicationHandlerStop — блокирует любые
    сторонние обработчики (рекламные инжекторы и прочее) от выполнения.
    """
    if not update.message or not update.message.text:
        return

    user_id = update.effective_user.id
    text = update.message.text

    # ── Кнопка «Др. команды» → категоризированное меню навигации ─────────────
    if text == t(user_id, "btn_other_commands"):
        if not await _db(user_exists, user_id):
            await update.message.reply_text(t(user_id, "not_registered"))
        else:
            from handlers.navigation import cmd_navigation
            await cmd_navigation(update, ctx)
        raise ApplicationHandlerStop

    # ── Кнопка «⬅️ Основное меню» → возврат ─────────────────────────────────
    back_texts = {
        t(user_id, "btn_back_main_menu"),
        "Основное меню",
        "⬅️ Основное меню",
        "Main menu",
    }
    if text in back_texts:
        if not await _db(user_exists, user_id):
            await update.message.reply_text(t(user_id, "not_registered"))
        else:
            await update.message.reply_text(
                t(user_id, "main_menu"),
                reply_markup=main_menu_keyboard(user_id),
            )
        raise ApplicationHandlerStop

    # ── Остальные кнопки ─────────────────────────────────────────────────────
    for btn_key, module, func_name in _BUTTON_ROUTES:
        btn_text = t(user_id, btn_key)
        if text == btn_text:
            # Админ-кнопки — только для админов
            if btn_key.startswith("btn_admin") and user_id not in ADMIN_USER_IDS:
                raise ApplicationHandlerStop
            try:
                func = _get_func(module, func_name)
                await func(update, ctx)
            except ApplicationHandlerStop:
                raise
            except Exception as _err:
                import traceback
                tb = traceback.format_exc()
                logger.error("Ошибка при вызове %s.%s для user %s:\n%s", module, func_name, user_id, tb)
                await update.message.reply_text(
                    f"⚠️ Ошибка в {func_name}:\n<code>{str(_err)[:300]}</code>",
                    parse_mode="HTML"
                )
            raise ApplicationHandlerStop


def get_conversation_handler() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[CommandHandler("start", cmd_start)],
        states={
            CHOOSE_LANG: [CallbackQueryHandler(cb_choose_lang, pattern=r"^lang:")],
            ENTER_NAME:  [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_name_input)],
            TUTORIAL:    [CallbackQueryHandler(cb_tutorial, pattern=r"^tutorial:")],
        },
        fallbacks=[CommandHandler("start", cmd_start)],
        allow_reentry=True,
    )


def register_start_handlers(app):
    app.add_handler(get_conversation_handler())
    app.add_handler(CommandHandler("menu", cmd_menu))
    # group=0 — раньше всех прочих MessageHandler-ов
    app.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_main_menu_buttons),
        group=0,
    )
