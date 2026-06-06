from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
import logging

logger = logging.getLogger(__name__)
scheduler = AsyncIOScheduler(timezone="Europe/Moscow")


async def reset_house_cup():
    """Reset house cup on the 1st of each month at 00:00 MSK."""
    from database import get_pool
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("UPDATE house_points SET points = 0")
    logger.info("House Cup reset done.")


def setup_scheduler():
    # House cup reset: 1st of every month at 00:00 MSK
    scheduler.add_job(
        reset_house_cup,
        CronTrigger(day=1, hour=0, minute=0),
        id="house_cup_reset",
        replace_existing=True,
    )
    scheduler.start()
    logger.info("Scheduler started.")
