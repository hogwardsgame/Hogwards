"""
APScheduler tasks — TZ sections 5, 9, 11.2, 12.
"""
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
import logging

logger = logging.getLogger(__name__)
scheduler = AsyncIOScheduler(timezone="Europe/Moscow")
_bot = None  # set in setup_scheduler


def reset_house_cup():
    from database import reset_house_cup_points
    reset_house_cup_points()
    logger.info("House Cup reset done.")


def reset_shop():
    """Clear old shop items so they regenerate tomorrow."""
    from database import get_conn, execute
    with get_conn() as conn:
        execute(conn, "DELETE FROM shop_items WHERE available_until < NOW()")
    logger.info("Shop stock cleared for daily refresh.")


async def finalize_auctions():
    from handlers.auction import finalize_expired_lots
    if _bot:
        await finalize_expired_lots(_bot)


async def start_weekly_event_task():
    from handlers.events import start_weekly_event
    if _bot:
        await start_weekly_event(_bot)


async def end_weekly_event_task():
    from handlers.events import end_weekly_event
    if _bot:
        await end_weekly_event(_bot)


async def reward_lessons_task():
    """Every 6 hours reward enrolled lesson attendees."""
    from database import get_conn, fetchall, fetchrow, execute
    from handlers.lessons import reward_lesson
    import logging
    log = logging.getLogger(__name__)

    with get_conn() as conn:
        rows = fetchall(conn, """
            SELECT la.user_id, l.subject
            FROM lesson_attendance la
            JOIN lessons l ON la.lesson_id = l.id
            WHERE la.rewarded = FALSE
              AND l.ends_at <= NOW()
        """)
    for row in rows:
        try:
            if _bot:
                await reward_lesson(row["user_id"], row["subject"], _bot)
        except Exception as e:
            log.error(f"reward_lesson error uid={row['user_id']}: {e}")


def setup_scheduler(bot=None):
    global _bot
    _bot = bot

    # House Cup reset — 1st of each month at 00:00 Moscow
    scheduler.add_job(reset_house_cup, CronTrigger(day=1, hour=0, minute=0),
                      id="house_cup_reset", replace_existing=True)

    # Shop daily refresh at 06:00 Moscow
    scheduler.add_job(reset_shop, CronTrigger(hour=6, minute=0),
                      id="shop_reset", replace_existing=True)

    # Auction finalization every 5 minutes
    scheduler.add_job(finalize_auctions, "interval", minutes=5,
                      id="auction_finalize", replace_existing=True)

    # Weekly event: start every Friday 18:00, end every Monday 06:00 Moscow
    scheduler.add_job(start_weekly_event_task, CronTrigger(day_of_week="fri", hour=18, minute=0),
                      id="weekly_event_start", replace_existing=True)
    scheduler.add_job(end_weekly_event_task, CronTrigger(day_of_week="mon", hour=6, minute=0),
                      id="weekly_event_end", replace_existing=True)

    # Lesson rewards every 30 minutes check
    scheduler.add_job(reward_lessons_task, "interval", minutes=30,
                      id="lesson_rewards", replace_existing=True)

    scheduler.start()
    logger.info("Scheduler started with all jobs.")
