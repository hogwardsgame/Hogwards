"""
Mini App — открытие веб-приложения (профиль волшебника) внутри Telegram.
Веб-страница хостится на GitHub Pages.
"""
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import ContextTypes, CommandHandler
from database import user_exists
from utils.i18n import t

logger = logging.getLogger(__name__)

# Адрес Mini App на GitHub Pages
MINIAPP_URL = "https://hogwardsgame.github.io/hogwarts-app/"

async def cmd_app(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not user_exists(user_id):
        await update.message.reply_text(t(user_id, "not_registered"))
        return
    markup = InlineKeyboardMarkup([[
        InlineKeyboardButton("🪄 Открыть профиль", web_app=WebAppInfo(url=MINIAPP_URL))
    ]])
    await update.message.reply_text(
        "✨ *Паспорт волшебника*\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "Открой красивую визуальную версию своего профиля прямо в Telegram!",
        parse_mode="Markdown",
        reply_markup=markup
    )

def register_miniapp_handlers(app):
    app.add_handler(CommandHandler("app", cmd_app))
    app.add_handler(CommandHandler("profile_app", cmd_app))
