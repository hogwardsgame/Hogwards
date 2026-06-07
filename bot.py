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
from telegram import Update
from telegram.ext import Application, MessageHandler, CallbackQueryHandler, filters, ContextTypes
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


async def maintenance_message_guard(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Block text messages during maintenance (except admins).
    Returns True to stop further processing, None to pass through.
    """
    from handlers.admin import is_maintenance
    from config import ADMIN_IDS
    if not is_maintenance():
        return  # pass through
    user_id = update.effective_user.id
    if user_id in ADMIN_IDS:
        return  # pass through for admins

    # Check if user is mid-registration (ConversationHandler state)
    # We allow /start through so a new user can always register
    if update.message and update.message.text and update.message.text.startswith("/start"):
        return  # pass through

    await update.message.reply_text("🛠 Бот на тех. обслуживании. Скоро вернёмся!")
    ctx.application.stop_processing = True  # signal (handled below)


async def maintenance_callback_guard(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Block callback queries during maintenance (except admins)."""
    from handlers.admin import is_maintenance
    from config import ADMIN_IDS
    if not is_maintenance():
        return
    user_id = update.effective_user.id
    if user_id in ADMIN_IDS:
        return
    await update.callback_query.answer("🛠 Бот на тех. обслуживании!", show_alert=True)


async def post_init(app: Application):
    init_db()

    with get_conn() as conn:
        rows = fetchall(conn, "SELECT user_id, lang FROM users")
        for row in rows:
            set_cached_lang(row["user_id"], row["lang"])
    logger.info(f"Loaded lang cache for {len(rows)} users.")

    setup_scheduler(bot=app.bot)


def main():
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN is not set!")

    app = Application.builder().token(BOT_TOKEN).post_init(post_init).build()

    # Maintenance guards run first (group -1, before ConversationHandlers)
    # Text guard — only for non-command messages so /start still works
    app.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, maintenance_message_guard),
        group=-1
    )
    # Callback guard — covers all inline buttons
    app.add_handler(
        CallbackQueryHandler(maintenance_callback_guard),
        group=-1
    )

    # Core handlers (group 1+, run after guards)
    register_start_handlers(app)
    register_profile_handlers(app)
    register_rating_handlers(app)
    register_admin_handlers(app)
    register_settings_handlers(app)

    # Game handlers
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
