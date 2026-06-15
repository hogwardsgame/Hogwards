"""
Заглушка бота: вся игра переехала в Mini App.

Для обычных игроков любое сообщение/команда в боте (кроме /start)
отвечает приветствием с кнопкой «Открыть приложение» и НЕ пропускает
обработку дальше к игровым хендлерам.

Администраторы (ADMIN_IDS) проходят свободно — у них работает всё,
включая админ-панель.
"""
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import TypeHandler, ApplicationHandlerStop, ContextTypes

from config import ADMIN_IDS

logger = logging.getLogger(__name__)

MINIAPP_URL = "https://hogwardsgame.github.io/hogwarts-app/"

# Команды, которые остаются доступными всем (вход + помощь)
ALLOWED_FOR_ALL = {"/start", "/app"}


def _app_keyboard():
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("🪄 Открыть игру", web_app=WebAppInfo(url=MINIAPP_URL))
    ]])


async def _gate(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Перехватчик: пускает админов и регистрацию, всех остальных — в Mini App."""
    user = update.effective_user
    if not user:
        return  # системные апдейты пропускаем

    # Админы играют в боте как раньше
    if ADMIN_IDS and user.id in ADMIN_IDS:
        return

    # Незарегистрированных пропускаем — иначе они не пройдут регистрацию
    # (выбор языка, ввод имени, выбор факультета через /start).
    try:
        from database import user_exists
        if not user_exists(user.id):
            return
    except Exception:
        return  # при сбое БД лучше пропустить, чем сломать вход

    # Разрешённые команды (вход) — пропускаем к их обычным хендлерам.
    msg = update.effective_message
    if msg and msg.text:
        cmd = msg.text.split()[0].split("@")[0].lower()
        if cmd in ALLOWED_FOR_ALL:
            return

    # Всё остальное от обычного игрока — показываем кнопку приложения и СТОП.
    try:
        if msg:
            await msg.reply_text(
                "🎮 <b>Игра переехала в приложение!</b>\n\n"
                "Весь Хогвартс теперь внутри Mini App: бои, дуэли, магазин, "
                "питомцы, турниры и всё остальное.\n\n"
                "Нажми кнопку ниже, чтобы играть 👇",
                parse_mode="HTML",
                reply_markup=_app_keyboard(),
            )
        elif update.callback_query:
            # старые инлайн-кнопки из прежних сообщений
            await update.callback_query.answer("Игра переехала в приложение 🪄", show_alert=True)
    except Exception as e:
        logger.warning("gate reply: %s", e)

    # Останавливаем дальнейшую обработку — игровые хендлеры не сработают.
    raise ApplicationHandlerStop


def register_gate_handler(app):
    """Регистрирует заглушку в группе -10 (раньше всех игровых хендлеров)."""
    app.add_handler(TypeHandler(Update, _gate), group=-10)
