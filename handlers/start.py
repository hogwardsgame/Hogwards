import logging
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import (
    ContextTypes, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ConversationHandler,
)
from database import (
    user_exists, wizard_name_taken, create_user,
    get_house_counts, set_user_lang, get_user,
)
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

# ─── Языковые клавиатуры ──────────────────────────────
def lang_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(label, callback_data=f"lang:{code}")]
        for label, code in LANG_OPTIONS
    ])

def settings_lang_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(label, callback_data=f"setlang:{code}")]
        for label, code in LANG_OPTIONS
    ])

def tutorial_keyboard(user_id: int):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(t(user_id, "btn_next"), callback_data="tutorial:next")]
    ])

# ─── Главное меню ───────────────────────────────────────────────
def main_menu_keyboard(user_id: int) -> ReplyKeyboardMarkup:
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add(
        KeyboardButton(t(user_id, "btn_profile")),
        KeyboardButton(t(user_id, "btn_inventory"))
    )
    kb.add(
        KeyboardButton(t(user_id, "btn_shop")),
        KeyboardButton(t(user_id, "btn_lessons"))
    )
    kb.add(
        KeyboardButton(t(user_id, "btn_quests")),
        KeyboardButton(t(user_id, "btn_other_commands"))
    )
    if user_id in ADMIN_USER_IDS:
        kb.add(KeyboardButton(t(user_id, "btn_admin_panel")))
    return kb

# ─── Вторая страница кнопок ─────────────────────────────────────
def other_menu_keyboard(user_id: int) -> ReplyKeyboardMarkup:
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add(
        KeyboardButton(t(user_id, "btn_house")),
        KeyboardButton(t(user_id, "btn_worldboss"))
    )
    kb.add(
        KeyboardButton(t(user_id, "btn_tournament")),
        KeyboardButton(t(user_id, "btn_hogsmeade"))
    )
    kb.add(
        KeyboardButton(t(user_id, "btn_room")),
        KeyboardButton(t(user_id, "btn_potions"))
    )
    kb.add(
        KeyboardButton(t(user_id, "btn_squad")),
        KeyboardButton(t(user_id, "btn_trade"))
    )
    kb.add(
        KeyboardButton(t(user_id, "btn_achievements")),
        KeyboardButton(t(user_id, "btn_titles"))
    )
    kb.add(
        KeyboardButton(t(user_id, "btn_explore")),
        KeyboardButton(t(user_id, "btn_back_main_menu"))
    )
    if user_id in ADMIN_USER_IDS:
        kb.add(
            KeyboardButton(t(user_id, "btn_admin_stats")),
            KeyboardButton(t(user_id, "btn_admin_items")),
            KeyboardButton(t(user_id, "btn_admin_economy")),
            KeyboardButton(t(user_id, "btn_admin_log")),
            KeyboardButton(t(user_id, "btn_admin_bosses")),
            KeyboardButton(t(user_id, "btn_admin_spells")),
            KeyboardButton(t(user_id, "btn_admin_maintenance"))
        )
    return kb

# ─── DB wrapper ───────────────────────────────────────────────
async def _db(func, *args):
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, func, *args)

# ─── Команды /start и меню ─────────────────────────────────────
async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    exists = await _db(user_exists, user_id)
    if exists:
        user = await _db(get_user, user_id)
        set_cached_lang(user_id, user["lang"])
        await update.message.reply_text(t(user_id, "already_registered"))
        await update.message.reply_text(t(user_id, "main_menu"), reply_markup=main_menu_keyboard(user_id))
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

    await _db(
        lambda: create_user(
            user_id=user_id,
            username=update.effective_user.username or "",
            wizard_name=name,
            house=house,
            lang=lang,
            starter_spell=starter_spell,
        )
    )
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
            await query.message.reply_text(t(user_id, "main_menu"), reply_markup=main_menu_keyboard(user_id))
            return ConversationHandler.END
    return TUTORIAL

async def cmd_menu(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    exists = await _db(user_exists, user_id)
    if not exists:
        await update.message.reply_text(t(user_id, "not_registered"))
        return
    await update.message.reply_text(t(user_id, "main_menu"), reply_markup=main_menu_keyboard(user_id))

# ─── Обработка всех кнопок ─────────────────────────────────────
async def handle_other_commands(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return
    user_id = update.effective_user.id
    text = update.message.text

    # словарь действий для игроков
    player_actions = {
        t(user_id, "btn_profile"): "handlers.profile.cmd_profile",
        t(user_id, "btn_inventory"): "handlers.inventory.cmd_inventory",
        t(user_id, "btn_shop"): "handlers.shop.cmd_shop",
        t(user_id, "btn_lessons"): "handlers.lessons.cmd_lessons",
        t(user_id, "btn_quests"): "handlers.quests.cmd_quests",
        t(user_id, "btn_house"): "handlers.house_points.cmd_house",
        t(user_id, "btn_worldboss"): "handlers.world_bosses.cmd_worldboss",
        t(user_id, "btn_tournament"): "handlers.tournament.cmd_tournament",
        t(user_id, "btn_hogsmeade"): "handlers.hogsmeade.cmd_hogsmeade",
        t(user_id, "btn_room"): "handlers.room_of_requirement.cmd_room",
        t(user_id, "btn_potions"): "handlers.potion_system.cmd_potions",
        t(user_id, "btn_squad"): "handlers.squads.cmd_squad",
        t(user_id, "btn_trade"): "handlers.trade.cmd_trade",
        t(user_id, "btn_achievements"): "handlers.achievements.cmd_achievements",
        t(user_id, "btn_titles"): "handlers.titles.cmd_titles",
        t(user_id, "btn_explore"): "handlers.locations.cmd_explore",
        t(user_id, "btn_back_main_menu"): None,
    }

    admin_actions = {
        t(user_id, "btn_admin_panel"): "handlers.admin.cmd_admin",
        t(user_id, "btn_admin_stats"): "handlers.admin.cmd_stats",
        t(user_id, "btn_admin_items"): "handlers.admin.cmd_list_items",
        t(user_id, "btn_admin_spells"): "handlers.admin.cmd_list_spells",
        t(user_id, "btn_admin_economy"): "handlers.admin.cmd_economy_info",
        t(user_id, "btn_admin_log"): "handlers.admin.cmd_admin_log",
        t(user_id, "btn_admin_bosses"): "handlers.admin.cmd_list_bosses",
        t(user_id, "btn_admin_maintenance"): "handlers.admin.cmd_maintenance",
    }

    action = player_actions.get(text)
    if action is None and user_id in ADMIN_USER_IDS:
        action = admin_actions.get(text)

    if action is None:
        if text == t(user_id, "btn_back_main_menu"):
            await update.message.reply_text(t(user_id, "main_menu"), reply_markup=main_menu_keyboard(user_id))
        return

    # динамический импорт и вызов функции
    try:
        module_name, func_name = action.rsplit(".", 1)
        import importlib
        func = getattr(importlib.import_module(module_name), func_name)
        await func(update, ctx)
    except Exception:
        logger.exception("Failed to handle menu button %s for user %s", text, user_id)
        await update.message.reply_text(t(user_id, "menu_action_error"))

# ─── Регистрация хендлеров ─────────────────────────────────────
def get_conversation_handler() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[CommandHandler("start", cmd_start)],
        states={
            CHOOSE_LANG: [CallbackQueryHandler(cb_choose_lang, pattern=r"^lang:")],
            ENTER_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_name_input)],
            TUTORIAL: [CallbackQueryHandler(cb_tutorial, pattern=r"^tutorial:")],
        },
        fallbacks=[CommandHandler("start", cmd_start)],
        allow_reentry=True,
    )

def register_start_handlers(app):
    app.add_handler(get_conversation_handler())
    app.add_handler(CommandHandler("menu", cmd_menu))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_other_commands), group=0)
    app.add_handler(CallbackQueryHandler(cb_settings, pattern=r"^settings:"))
    app.add_handler(CallbackQueryHandler(cb_set_lang, pattern=r"^setlang:"))
