import threading
from http.server import HTTPServer, BaseHTTPRequestHandler

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

from handlers.start       import register_start_handlers
from handlers.profile     import register_profile_handlers
from handlers.rating      import register_rating_handlers
from handlers.admin       import register_admin_handlers
from handlers.settings    import register_settings_handlers
from handlers.duel        import register_duel_handlers
from handlers.pve         import register_pve_handlers
from handlers.lessons     import register_lessons_handlers
from handlers.shop        import register_shop_handlers
from handlers.inventory   import register_inventory_handlers
from handlers.auction     import register_auction_handlers
from handlers.quests      import register_quests_handlers
from handlers.events      import register_events_handlers
# ── Новые хендлеры (Этапы 3–6) ────────────────────────────────────────────────
from handlers.house_points        import register_house_points_handlers
from handlers.room_of_requirement import register_room_handlers
from handlers.hogsmeade           import register_hogsmeade_handlers
from handlers.squads              import register_squads_handlers
from handlers.tournament          import register_tournament_handlers
from handlers.trade               import register_trade_handlers
from handlers.achievements        import register_achievements_handlers
from handlers.titles              import register_titles_handlers
from handlers.locations           import register_locations_handlers
from handlers.potion_system       import register_potion_handlers
from handlers.world_bosses        import register_world_boss_handlers
from handlers.house_war           import register_house_war_handlers

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

db_executor = ThreadPoolExecutor(max_workers=10)
_last_request: dict[int, float] = {}
RATE_LIMIT_SECONDS = 1.0


async def run_in_executor(func, *args):
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(db_executor, func, *args)


async def rate_limit_guard(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not update.callback_query:
        return

    # Ответы в уроках нельзя блокировать общим антиспамом.
    # Часто игрок сразу нажимает первый вариант, а большинство правильных
    # ответов в базе уроков находятся именно на первой кнопке. Из-за этого
    # guard успевал остановить обработчик lesson_answer до начисления XP,
    # золота и очков факультета. Неправильные ответы обычно нажимались
    # медленнее, поэтому казалось, что ломается только правильный ответ.
    data = update.callback_query.data or ""
    if data.startswith("lesson_answer:"):
        return

    user_id = update.effective_user.id
    now  = time.monotonic()
    last = _last_request.get(user_id, 0)
    if now - last < RATE_LIMIT_SECONDS:
        await update.callback_query.answer("⏳ Не так быстро!", show_alert=False)
        raise ApplicationHandlerStop
    _last_request[user_id] = now


async def maintenance_callback_guard(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    from handlers.admin import is_maintenance
    from config import ADMIN_IDS
    if not is_maintenance():
        return
    if update.effective_user.id in ADMIN_IDS:
        return
    if update.callback_query:
        await update.callback_query.answer("🛠 Бот на тех. обслуживании!", show_alert=True)
    raise ApplicationHandlerStop


async def ban_guard(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
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
    await loop.run_in_executor(db_executor, init_db)

    def load_langs():
        with get_conn() as conn:
            return fetchall(conn, "SELECT user_id, lang FROM users")

    rows = await loop.run_in_executor(db_executor, load_langs)
    for row in rows:
        set_cached_lang(row["user_id"], row["lang"])
    logger.info(f"Lang cache loaded for {len(rows)} users.")
    setup_scheduler(bot=app.bot)


def main():
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN is not set!")

    app = (
        Application.builder()
        .token(BOT_TOKEN)
        .post_init(post_init)
        .build()
    )

    # Гарды — группа -1, выполняются раньше всех
    app.add_handler(CallbackQueryHandler(rate_limit_guard),           group=-1)
    app.add_handler(CallbackQueryHandler(maintenance_callback_guard), group=-1)
    app.add_handler(CallbackQueryHandler(ban_guard),                  group=-1)

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
    # ── Новые (Этапы 3–6) ──────────────────────────────────────────────────────
    register_house_points_handlers(app)
    register_room_handlers(app)
    register_hogsmeade_handlers(app)
    register_squads_handlers(app)
    register_tournament_handlers(app)
    register_trade_handlers(app)
    register_achievements_handlers(app)
    register_titles_handlers(app)
    register_locations_handlers(app)
    register_potion_handlers(app)
    register_world_boss_handlers(app)
    register_house_war_handlers(app)

    logger.info("🧙 Hogwarts Bot starting...")
    app.run_polling(drop_pending_updates=True)


try:
    from telegram.ext import ApplicationHandlerStop
except ImportError:
    class ApplicationHandlerStop(Exception):
        pass


if __name__ == "__main__":
    main()
