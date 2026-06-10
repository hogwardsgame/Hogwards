# handlers/settings.py
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackQueryHandler, CommandHandler, ContextTypes
from utils.i18n import t, set_cached_lang
from database import set_user_lang

LANG_OPTIONS = [
    ("🇷🇺 Русский", "ru"),
    ("🇬🇧 English", "en"),
    ("🇪🇸 Español", "es"),
    ("🇩🇪 Deutsch", "de"),
    ("🇧🇷 Português", "pt"),
]


async def handle_settings(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    await update.message.reply_text(
        t(user_id, "settings_menu"),
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton(t(user_id, "btn_change_lang"), callback_data="settings:lang")]
        ]),
    )


async def cb_settings(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    await query.edit_message_text(
        t(user_id, "choose_lang"),
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton(label, callback_data=f"setlang:{code}")]
            for label, code in LANG_OPTIONS
        ]),
    )


async def cb_set_lang(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    lang = query.data.split(":")[1]
    set_cached_lang(user_id, lang)
    # set_user_lang синхронная — НЕ await
    set_user_lang(user_id, lang)
    await query.edit_message_text(f"✅ {t(user_id, 'language_changed')}")


def register_settings_handlers(app):
    app.add_handler(CommandHandler("settings", handle_settings))
    app.add_handler(CallbackQueryHandler(cb_settings, pattern=r"^settings:"))
    app.add_handler(CallbackQueryHandler(cb_set_lang, pattern=r"^setlang:"))
