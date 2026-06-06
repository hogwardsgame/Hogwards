from telegram import Update
from telegram.ext import ContextTypes, MessageHandler, filters
from utils.i18n import t
from handlers.start import handle_settings


async def handle_settings_button(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if update.message.text == t(user_id, "btn_settings"):
        await handle_settings(update, ctx)


def register_settings_handlers(app):
    app.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND,
        handle_settings_button
    ), group=3)
