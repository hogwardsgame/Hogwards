import threading
from http.server import HTTPServer, BaseHTTPRequestHandler

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
    def log_message(self, *args):
        pass
threading.Thread(target=lambda: HTTPServer(('0.0.0.0', 8080), Handler).serve_forever(), daemon=True).start()

import logging
import asyncio
from concurrent.futures import ThreadPoolExecutor
from telegram import Update
from telegram.ext import Application, CallbackQueryHandler, filters, ContextTypes, PicklePersistence
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

# Глобальный executor для синхронных вызовов к БД (чтобы не блокировать event loop)
db_executor = ThreadPoolExecutor(max_workers=10)


async def run_in_executor(func, *args):
    """Запускает синхронную функцию в thread pool, не блокируя event loop."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(db_executor, func, *args)


async def maintenance_callback_guard(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    from handlers.admin import is_maintenance
    from config import ADMIN_IDS
    if not is_maintenance():
        return
    if update.effective_user.id in ADMIN_IDS:
        return
    await update.callback_query.answer("🛠 Бот на тех. обслуживании. Скоро вернёмся!", show_alert=True)


async def post_init(app: Application):
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(db_executor, init_db)

    def load_langs():
        with get_conn() as conn:
            return fetchall(conn, "SELECT user_id, lang FROM users")

    rows = await loop.run_in_executor(db_executor, load_langs)
    for row in rows:
        set_cached_lang(row["user_id"], row["lang"])
    logger.info(f"Loaded lang cache for {len(rows)} users.")

    setup_scheduler(bot=app.bot)


def main():
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN is not set!")

    persistence = PicklePersistence(filepath="bot_persistence.pkl")

    app = (
        Application.builder()
        .token(BOT_TOKEN)
        .persistence(persistence)
        .post_init(post_init)
        .build()
    )

    app.add_handler(CallbackQueryHandler(maintenance_callback_guard), group=-1)

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

    logger.info("Starting Hogwarts Bot...")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
