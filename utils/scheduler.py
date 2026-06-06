from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
import logging

logger = logging.getLogger(__name__)
scheduler = AsyncIOScheduler(timezone="Europe/Moscow")


def reset_house_cup():
    from database import reset_house_cup_points
    reset_house_cup_points()
    logger.info("House Cup reset done.")


def setup_scheduler():
    scheduler.add_job(reset_house_cup, CronTrigger(day=1, hour=0, minute=0),
                      id="house_cup_reset", replace_existing=True)
    scheduler.start()
    logger.info("Scheduler started.")
