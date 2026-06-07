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

logger = logging.getLogger(__name__)

CHOOSE_LANG, ENTER_NAME, TUTORIAL = range(3)

LANG_OPTIONS = [
    ("🇷🇺 Русский", "ru"),
    ("🇬🇧 English", "en"),
    ("🇪🇸 Español", "es"),
    ("🇩🇪 Deutsch", "de"),
    ("🇧🇷 Português", "pt"),
]


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


def main_menu_keyboard(user_id: int) -> ReplyKeyboardMarkup:
    buttons = [
        [KeyboardButton(t(user_id, "btn_profile")), KeyboardButton(t(user_id, "btn_duel"))],
        [KeyboardButton(t(user_id, "btn_dungeon")), KeyboardButton(t(user_id, "btn_shop"))],
        [KeyboardButton(t(user_id, "btn_lessons")), KeyboardButton(t(user_id, "btn_inventory"))],
        [KeyboardButton(t(user_id, "btn_quests")), KeyboardButton(t(user_id, "btn_auction"))],
        [KeyboardButton(t(user_id, "btn_events")), KeyboardButton(t(user_id, "btn_rating"))],
        [KeyboardButton(t(user_id, "btn_settings"))],
    ]
    return ReplyKeyboardMarkup(buttons, resize_keyboard=True)


async def _db(func, *args):
    """Запускает синхронный DB-вызов не блокируя event loop."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, func, *args)


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

    taken = await _db(wizard_name_taken, name)
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


async def handle_settings(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    exists = await _db(user_exists, user_id)
    if not exists:
        await update.message.reply_text(t(user_id, "not_registered"))
        return
    await update.message.reply_text(
        t(user_id, "settings_menu"),
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton(t(user_id, "btn_change_lang"), callback_data="settings:lang")]
        ])
    )


async def cb_settings(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        t_lang("ru", "choose_lang"),
        reply_markup=settings_lang_keyboard(),
    )


async def cb_set_lang(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    lang = query.data.split(":")[1]
    set_cached_lang(user_id, lang)
    await _db(set_user_lang, user_id, lang)

    messages = {
        "ru": "✅ Язык изменён!\n\nНажми /start чтобы обновить меню.",
        "en": "✅ Language changed!\n\nPress /start to refresh the menu.",
        "es": "✅ ¡Idioma cambiado!\n\nPresiona /start para actualizar el menú.",
        "de": "✅ Sprache geändert!\n\nDrücke /start, um das Menü zu aktualisieren.",
        "pt": "✅ Idioma alterado!\n\nPressione /start para atualizar o menu.",
    }
    await query.edit_message_text(messages.get(lang, messages["en"]))


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
    app.add_handler(CallbackQueryHandler(cb_settings, pattern=r"^settings:"))
    app.add_handler(CallbackQueryHandler(cb_set_lang, pattern=r"^setlang:"))
