import asyncio
import logging
from telegram.ext import Application
from config import BOT_TOKEN
from database import init_db, get_pool
from utils.scheduler import setup_scheduler
from utils.i18n import set_cached_lang

# Handlers
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
    """Called after bot starts — init DB and preload user langs."""
    await init_db()
    logger.info("Database initialised.")

    # Preload language preferences into memory cache
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT user_id, lang FROM users")
        for row in rows:
            set_cached_lang(row["user_id"], row["lang"])
    logger.info(f"Loaded language cache for {len(rows)} users.")

    setup_scheduler()


def main():
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN environment variable is not set!")

    app = (
        Application.builder()
        .token(BOT_TOKEN)
        .post_init(post_init)
        .build()
    )

    # Register all handlers
    register_start_handlers(app)
    register_profile_handlers(app)
    register_rating_handlers(app)
    register_admin_handlers(app)
    register_settings_handlers(app)

    logger.info("Starting Hogwarts Bot...")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
