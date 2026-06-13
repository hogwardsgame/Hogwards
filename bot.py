import logging
import asyncio
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from concurrent.futures import ThreadPoolExecutor

from telegram.ext import ApplicationBuilder
from config import BOT_TOKEN
from database import init_db, get_conn, fetchall
from utils.i18n import set_cached_lang
from utils.scheduler import setup_scheduler

from handlers.start           import register_start_handlers
from handlers.settings        import register_settings_handlers
from handlers.profile         import register_profile_handlers
from handlers.rating          import register_rating_handlers
from handlers.admin           import register_admin_handlers
from handlers.duel            import register_duel_handlers
from handlers.pve             import register_pve_handlers
from handlers.lessons         import register_lessons_handlers
from handlers.shop            import register_shop_handlers
from handlers.inventory       import register_inventory_handlers
from handlers.auction         import register_auction_handlers
from handlers.events          import register_events_handlers
from handlers.house_points    import register_house_points_handlers
from handlers.room_of_requirement import register_room_handlers
from handlers.hogsmeade       import register_hogsmeade_handlers
from handlers.squads          import register_squads_handlers
from handlers.tournament      import register_tournament_handlers
from handlers.trade           import register_trade_handlers
from handlers.achievements    import register_achievements_handlers
from handlers.titles          import register_titles_handlers
from handlers.locations       import register_locations_handlers
from handlers.potion_system   import register_potion_handlers
from handlers.world_bosses    import register_world_boss_handlers
from handlers.house_war       import register_house_war_handlers
from handlers.forbidden_forest import register_forest_handlers
from handlers.pets             import register_pets_handlers
from handlers.black_market     import register_black_market_handlers
from handlers.player_journal   import register_journal_handlers
from handlers.horcruxes        import register_horcrux_handlers
from handlers.triwizard        import register_triwizard_handlers
from handlers.daily_bonus      import register_daily_handlers
from handlers.info             import register_info_handlers
from handlers.tutorial         import register_tutorial_handlers
from handlers.gringotts        import register_gringotts_handlers
from handlers.forge            import register_forge_handlers
from handlers.navigation       import register_navigation_handlers
from handlers.ambush           import register_ambush_handlers
from handlers.collections     import register_collections_handlers
from handlers.duel_league     import register_duel_league_handlers
from handlers.my_room         import register_my_room_handlers
from handlers.wandcraft       import register_wandcraft_handlers
from handlers.images         import register_images_handlers
from handlers.admin_panel      import register_admin_panel_handlers

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# Healthcheck для Railway
class _HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Hogwarts Bot is running!")
    def log_message(self, *args):
        pass

threading.Thread(
    target=lambda: HTTPServer(("0.0.0.0", 8080), _HealthHandler).serve_forever(),
    daemon=True,
).start()

db_executor = ThreadPoolExecutor(max_workers=10)


async def post_init(app):
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(db_executor, init_db)

    def load_langs():
        with get_conn() as conn:
            return fetchall(conn, "SELECT user_id, lang FROM users")

    rows = await loop.run_in_executor(db_executor, load_langs)
    for row in rows:
        set_cached_lang(row["user_id"], row["lang"])
    logger.info(f"Кэш языков загружен для {len(rows)} пользователей.")
    setup_scheduler(bot=app.bot)

    # Подгрузить созданные игроками палочки в каталог предметов
    try:
        from handlers.wandcraft import load_crafted_wands_into_items
        await loop.run_in_executor(db_executor, load_crafted_wands_into_items)
    except Exception as e:
        logger.warning("crafted wands load: %s", e)

    # Подключить уведомления к планировщику
    try:
        from handlers.notifications import setup_notification_jobs
        from utils.scheduler import scheduler
        setup_notification_jobs(scheduler, app.bot)
        from handlers.ambush import setup_ambush_jobs
        setup_ambush_jobs(scheduler, app.bot)
    except Exception as e:
        logger.warning("Notifications scheduler: %s", e)


def main():
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN не задан в переменных окружения!")

    app = (
        ApplicationBuilder()
        .token(BOT_TOKEN)
        .post_init(post_init)
        .build()
    )

    # Порядок важен: group=0 (start/menu) должен быть первым
    register_start_handlers(app)
    register_settings_handlers(app)
    register_profile_handlers(app)
    register_rating_handlers(app)
    register_admin_handlers(app)
    register_duel_handlers(app)
    register_pve_handlers(app)
    register_lessons_handlers(app)
    register_shop_handlers(app)
    register_inventory_handlers(app)
    register_auction_handlers(app)
    register_events_handlers(app)
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
    register_forest_handlers(app)
    register_pets_handlers(app)
    register_black_market_handlers(app)
    register_journal_handlers(app)
    register_horcrux_handlers(app)
    register_triwizard_handlers(app)
    register_daily_handlers(app)
    register_info_handlers(app)
    register_tutorial_handlers(app)
    register_gringotts_handlers(app)
    register_forge_handlers(app)
    register_navigation_handlers(app)
    register_ambush_handlers(app)
    register_collections_handlers(app)
    register_duel_league_handlers(app)
    register_my_room_handlers(app)
    register_wandcraft_handlers(app)
    register_images_handlers(app)
    register_admin_panel_handlers(app)

    # ── Глобальный трекер активности ─────────────────────────────────────────
    # Срабатывает на ЛЮБОЕ обновление от игрока (команды, callback, текст),
    # обновляет last_active. Группа 99 — последняя, ничего не блокирует.
    from telegram.ext import TypeHandler
    from telegram import Update as _Upd

    async def _track_activity(update, ctx):
        try:
            if update.effective_user:
                from database import touch_user_activity
                touch_user_activity(update.effective_user.id)
        except Exception:
            pass

    app.add_handler(TypeHandler(_Upd, _track_activity), group=99)

    logger.info("Hogwarts Bot запускается...")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
