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
from telegram.ext import Application, CallbackQueryHandler, filters, ContextTypes
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


async def maintenance_callback_guard(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Block ALL inline button presses during maintenance (except admins).
    Registered in group -1 so it runs before game handlers.
    Uses answer() with show_alert — does NOT consume the update for ConversationHandler
    callbacks because it's in a separate group.
    """
    from handlers.admin import is_maintenance
    from config import ADMIN_IDS
    if not is_maintenance():
        return
    if update.effective_user.id in ADMIN_IDS:
        return
    await update.callback_query.answer("🛠 Бот на тех. обслуживании. Скоро вернёмся!", show_alert=True)


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

    # Callback maintenance guard in group -1 (before all game handlers).
    # NOTE: We do NOT add a global MessageHandler for maintenance here — that would
    # compete with ConversationHandler in group 0 and break new-user registration.
    # Text-message maintenance check happens inside handle_name_input (start.py).
    app.add_handler(CallbackQueryHandler(maintenance_callback_guard), group=-1)

    # Core handlers
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
