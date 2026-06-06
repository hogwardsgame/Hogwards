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
from telegram.ext import Application
from config import BOT_TOKEN
from database import init_db, get_conn, fetchall
from utils.scheduler import setup_scheduler
from utils.i18n import set_cached_lang

from handlers.start import register_start_handlers
from handlers.profile import register_profile_handlers
from handlers.rating import register_rating_handlers
from handlers.admin import register_admin_handlers
from handlers.settings import register_settings_handlers

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


async def post_init(app: Application):
    init_db()

    with get_conn() as conn:
        rows = fetchall(conn, "SELECT user_id, lang FROM users")
        for row in rows:
            set_cached_lang(row["user_id"], row["lang"])
    logger.info(f"Loaded lang cache for {len(rows)} users.")

    setup_scheduler()


def main():
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN is not set!")

    app = Application.builder().token(BOT_TOKEN).post_init(post_init).build()

    register_start_handlers(app)
    register_profile_handlers(app)
    register_rating_handlers(app)
    register_admin_handlers(app)
    register_settings_handlers(app)

    logger.info("Starting Hogwarts Bot...")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
