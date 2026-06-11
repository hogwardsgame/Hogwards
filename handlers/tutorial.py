"""
Туториал для новых игроков.
Запускается автоматически после выбора факультета.
"""
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CallbackQueryHandler
from database import user_exists, get_user, get_conn, execute, fetchrow
from utils.i18n import t

logger = logging.getLogger(__name__)

STEPS = [
    {
        "title": "👋 Добро пожаловать в Хогвартс!",
        "text": (
            "Ты новый волшебник Хогвартса. Давай я покажу как здесь всё устроено.\n\n"
            "Это займёт меньше минуты, но поможет тебе быстро освоиться!"
        ),
    },
    {
        "title": "📱 Главное меню",
        "text": (
            "Внизу экрана всегда есть кнопки меню:\n\n"
            "👤 *Профиль* — твои характеристики, уровень и ID\n"
            "🎒 *Инвентарь* — все твои предметы и снаряжение\n"
            "🏪 *Магазин* — ежедневный ассортимент товаров\n"
            "📚 *Уроки* — отвечай на вопросы, получай XP\n"
            "📜 *Квесты* — задания с историей и наградами\n\n"
            "📌 Кнопка *«Др. команды»* открывает расширенное меню!"
        ),
    },
    {
        "title": "⚡ Первые шаги",
        "text": (
            "Вот что нужно сделать прямо сейчас:\n\n"
            "1️⃣ Нажми *📚 Уроки* → ответь на 3 вопроса\n"
            "   → получишь XP, золото и очки факультета\n\n"
            "2️⃣ Нажми *🎁 /daily* → получи ежедневный бонус\n"
            "   → заходи каждый день чтобы серия не прервалась!\n\n"
            "3️⃣ Нажми *📜 Квесты* → возьми дневные задания\n"
            "   → быстрые задания на 5-10 минут\n\n"
            "4️⃣ Зайди в *🏪 Магазин* → купи первое снаряжение\n"
            "   → надень через Инвентарь!"
        ),
    },
    {
        "title": "⚔️ Бои и дуэли",
        "text": (
            "В Хогвартсе можно сражаться!\n\n"
            "🏰 *Подземелья* — бои с монстрами, лут и XP\n"
            "🌲 *Запретный лес* — события, ингредиенты, ночной бонус ×1.5\n"
            "⚔️ *Дуэли* — сражения с другими игроками\n"
            "   Вызов по ID: /duel [ID противника]\n"
            "   Свой ID виден в /profile и меню дуэлей\n\n"
            "🐉 *Мировой босс* — появляется в 12:00 и 20:00 UTC\n"
            "   Все игроки бьют вместе — награды зависят от вклада!\n\n"
            "💡 Надень снаряжение перед боем — атака важна!"
        ),
    },
    {
        "title": "🌍 Большой мир",
        "text": (
            "В Хогвартсе есть много всего интересного:\n\n"
            "🧪 *Зелья* — вари зелья из ингредиентов\n"
            "🐾 *Питомцы* — сова, кошка, жаба — дают бонусы\n"
            "💎 *Крестражи* — серверный квест на всю игру\n"
            "🕯️ *Чёрный рынок* — редкие предметы (с 5 уровня)\n"
            "🏠 *Факультет* — зарабатывай очки за любые действия\n"
            "📖 *История* — журнал всех твоих приключений\n\n"
            "📚 *Не знаешь что делать?*\n"
            "Нажми кнопку *ℹ️ Инфо* — там полный справочник!"
        ),
    },
    {
        "title": "✅ Готово! Ты настоящий волшебник!",
        "text": (
            "Туториал завершён. Удачи в Хогвартсе!\n\n"
            "🎁 Начни с */daily* — получи бонус за первый вход\n"
            "📚 Пройди уроки — быстрый старт для уровня\n"
            "ℹ️ Жми *Инфо* если что-то непонятно\n\n"
            "⚡ Hogwarts Legacy ждёт тебя!"
        ),
    },
]

def _tutorial_keyboard(step: int) -> InlineKeyboardMarkup:
    buttons = []
    if step < len(STEPS) - 1:
        buttons.append([InlineKeyboardButton("Далее ➡️", callback_data=f"tutorial_step:{step+1}")])
        buttons.append([InlineKeyboardButton("Пропустить туториал", callback_data="tutorial_skip")])
    else:
        buttons.append([InlineKeyboardButton("🚀 Начать игру!", callback_data="tutorial_done")])
    return InlineKeyboardMarkup(buttons)

def _step_text(step: int) -> str:
    s = STEPS[step]
    progress = f"Шаг {step+1}/{len(STEPS)}\n{'▓' * (step+1)}{'░' * (len(STEPS)-step-1)}\n\n"
    return f"{progress}*{s['title']}*\n\n{s['text']}"

async def start_tutorial(user_id: int, bot):
    """Запустить туториал для нового игрока."""
    try:
        with get_conn() as conn:
            execute(conn, """
                CREATE TABLE IF NOT EXISTS tutorial_done (user_id BIGINT PRIMARY KEY)
            """)
            existing = fetchrow(conn, "SELECT 1 FROM tutorial_done WHERE user_id=%s", user_id)
        if existing:
            return
        await bot.send_message(
            user_id,
            _step_text(0),
            parse_mode="Markdown",
            reply_markup=_tutorial_keyboard(0)
        )
    except Exception as e:
        logger.warning("start_tutorial: %s", e)

async def cb_tutorial_step(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    step  = int(query.data.split(":")[1])
    await query.edit_message_text(
        _step_text(step),
        parse_mode="Markdown",
        reply_markup=_tutorial_keyboard(step)
    )

async def cb_tutorial_done(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query   = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    try:
        with get_conn() as conn:
            execute(conn, "INSERT INTO tutorial_done (user_id) VALUES (%s) ON CONFLICT DO NOTHING", user_id)
    except Exception:
        pass
    await query.edit_message_text(
        "🎉 *Добро пожаловать в Hogwarts Legacy Game!*\n\n"
        "Используй меню внизу для навигации.\n"
        "Начни с 📚 Уроков или получи 🎁 /daily бонус!",
        parse_mode="Markdown"
    )

async def cb_tutorial_skip(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query   = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    try:
        with get_conn() as conn:
            execute(conn, "INSERT INTO tutorial_done (user_id) VALUES (%s) ON CONFLICT DO NOTHING", user_id)
    except Exception:
        pass
    await query.edit_message_text(
        "👍 Туториал пропущен.\n\nИспользуй *ℹ️ Инфо* если что-то непонятно.",
        parse_mode="Markdown"
    )

def register_tutorial_handlers(app):
    app.add_handler(CallbackQueryHandler(cb_tutorial_step, pattern=r"^tutorial_step:"))
    app.add_handler(CallbackQueryHandler(cb_tutorial_done, pattern=r"^tutorial_done$"))
    app.add_handler(CallbackQueryHandler(cb_tutorial_skip, pattern=r"^tutorial_skip$"))
