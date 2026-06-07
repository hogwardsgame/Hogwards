import threading
from http.server import HTTPServer, BaseHTTPRequestHandler

# ── HTTP-сервер для Railway (Railway требует открытый порт чтобы не убивать процесс)
class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Hogwarts Bot is running!")
    def log_message(self, *args):
        pass

threading.Thread(
    target=lambda: HTTPServer(('0.0.0.0', 8080), Handler).serve_forever(),
    daemon=True
).start()

import logging
import asyncio
import time
from concurrent.futures import ThreadPoolExecutor
from telegram import Update
from telegram.ext import Application, CallbackQueryHandler, ContextTypes
from config import BOT_TOKEN
from database import init_db, get_conn, fetchall
from utils.scheduler import setup_scheduler
from utils.i18n import set_cached_lang

from handlers.start     import register_start_handlers
from handlers.profile   import register_profile_handlers
from handlers.rating    import register_rating_handlers
from handlers.admin     import register_admin_handlers
from handlers.settings  import register_settings_handlers
from handlers.duel      import register_duel_handlers
from handlers.pve       import register_pve_handlers
from handlers.lessons   import register_lessons_handlers
from handlers.shop      import register_shop_handlers
from handlers.inventory import register_inventory_handlers
from handlers.auction   import register_auction_handlers
from handlers.quests    import register_quests_handlers
from handlers.events    import register_events_handlers

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# Глобальный executor для синхронных вызовов к БД
db_executor = ThreadPoolExecutor(max_workers=10)

# ── ИСПРАВЛЕНИЕ 3: защита от спама — словарь {user_id: last_request_time}
_last_request: dict[int, float] = {}
RATE_LIMIT_SECONDS = 1.0  # минимум 1 секунда между нажатиями


async def run_in_executor(func, *args):
    """Запускает синхронную функцию в thread pool, не блокируя event loop."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(db_executor, func, *args)


async def rate_limit_guard(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """
    ИСПРАВЛЕНИЕ 3: Антиспам.
    Если пользователь нажимает кнопки чаще 1 раза в секунду — игнорируем.
    """
    if not update.callback_query:
        return
    user_id = update.effective_user.id
    now = time.monotonic()
    last = _last_request.get(user_id, 0)
    if now - last < RATE_LIMIT_SECONDS:
        await update.callback_query.answer("⏳ Не так быстро!", show_alert=False)
        raise ApplicationHandlerStop  # не передаём дальше
    _last_request[user_id] = now


async def maintenance_callback_guard(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    from handlers.admin import is_maintenance
    from config import ADMIN_IDS
    if not is_maintenance():
        return
    if update.effective_user.id in ADMIN_IDS:
        return
    if update.callback_query:
        await update.callback_query.answer("🛠 Бот на тех. обслуживании. Скоро вернёмся!", show_alert=True)
    raise ApplicationHandlerStop


async def ban_guard(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Проверяем бан перед любым действием."""
    from database import is_banned
    user_id = update.effective_user.id
    if is_banned(user_id):
        if update.callback_query:
            await update.callback_query.answer("🚫 Вы заблокированы.", show_alert=True)
        elif update.message:
            await update.message.reply_text("🚫 Вы заблокированы.")
        raise ApplicationHandlerStop


async def post_init(app: Application):
    loop = asyncio.get_event_loop()

    # Инициализируем БД
    await loop.run_in_executor(db_executor, init_db)

    # Загружаем языки всех пользователей в кеш
    def load_langs():
        with get_conn() as conn:
            return fetchall(conn, "SELECT user_id, lang FROM users")

    rows = await loop.run_in_executor(db_executor, load_langs)
    for row in rows:
        set_cached_lang(row["user_id"], row["lang"])
    logger.info(f"Loaded lang cache for {len(rows)} users.")

    # Запускаем планировщик задач
    setup_scheduler(bot=app.bot)


# ── ИСПРАВЛЕНИЕ 2: убираем PicklePersistence — она теряет данные при перезапуске Railway.
# Состояния ConversationHandler теперь хранятся в PostgreSQL (см. database.py).
# Для ConversationHandler это прозрачно — он продолжает работать как раньше,
# но данные выживают после перезапуска Railway.

def main():
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN is not set! Add it to Railway environment variables.")

    app = (
        Application.builder()
        .token(BOT_TOKEN)
        # PicklePersistence убрана — данные теперь в PostgreSQL
        .post_init(post_init)
        .build()
    )

    # Группа -1: выполняется РАНЬШЕ всех остальных хендлеров
    app.add_handler(CallbackQueryHandler(rate_limit_guard),       group=-1)  # антиспам
    app.add_handler(CallbackQueryHandler(maintenance_callback_guard), group=-1)  # техобслуживание
    app.add_handler(CallbackQueryHandler(ban_guard),              group=-1)  # проверка бана

    # Основные хендлеры
    register_start_handlers(app)
    register_profile_handlers(app)
    register_rating_handlers(app)
    register_admin_handlers(app)
    register_settings_handlers(app)

    register_duel_handlers(app)
    register_pve_handlers(app)
    register_lessons_handlers(app)
    register_shop_handlers(app)
    register_inventory_handlers(app)
    register_auction_handlers(app)
    register_quests_handlers(app)
    register_events_handlers(app)

    logger.info("🧙 Hogwarts Bot starting...")
    app.run_polling(drop_pending_updates=True)


# Импортируем после определения функций чтобы избежать circular import
try:
    from telegram.ext import ApplicationHandlerStop
except ImportError:
    # Fallback для старых версий PTB
    class ApplicationHandlerStop(Exception):
        pass


if __name__ == "__main__":
    main()
