"""
Система уведомлений:
• За 15 минут до спавна мирового босса
• Зелье сварилось
• Еженедельный рейтинг с наградами
"""
import logging
import asyncio
from datetime import datetime, timezone, timedelta
from telegram.ext import ContextTypes
from database import get_conn, execute, fetchrow, fetchall, add_xp, add_gold
from config import WORLD_BOSS_SCHEDULE_HOURS, WORLD_BOSS_DURATION_MINUTES

logger = logging.getLogger(__name__)


async def notify_boss_upcoming(bot):
    """Уведомить всех игроков за 15 минут до спавна босса."""
    import random
    from handlers.world_bosses import WORLD_BOSSES
    now = datetime.now(timezone.utc)
    schedule = sorted(WORLD_BOSS_SCHEDULE_HOURS)

    # Проверяем каждый слот расписания
    for h in schedule:
        spawn_time = now.replace(hour=h, minute=0, second=0, microsecond=0)
        diff = (spawn_time - now).total_seconds()
        # Уведомляем если до спавна 14-16 минут
        if 840 <= diff <= 960:
            try:
                with get_conn() as conn:
                    users = fetchall(conn,
                        "SELECT user_id, lang FROM users WHERE is_banned=FALSE LIMIT 500")
            except Exception:
                return

            # Случайный босс для анонса (реальный спавн выбирается планировщиком)
            boss_id, boss_data = random.choice(list(WORLD_BOSSES.items()))
            name_ru = boss_data["names"]["ru"]

            for row in users:
                uid  = row["user_id"]
                lang = row.get("lang") or "ru"
                name = boss_data["names"].get(lang) or name_ru
                try:
                    await bot.send_message(uid,
                        f"⚠️ *Внимание!*\n\n"
                        f"Через 15 минут появится мировой босс:\n"
                        f"{boss_data['emoji']} *{name}*\n"
                        f"❤️ {boss_data['hp']:,} HP\n\n"
                        f"Приготовь заклинания! Используй /worldboss",
                        parse_mode="Markdown"
                    )
                except Exception:
                    pass
            break


async def notify_potion_ready(bot):
    """Уведомить игроков о готовых зельях."""
    try:
        with get_conn() as conn:
            rows = fetchall(conn, """
                SELECT bq.user_id, bq.recipe_id, bq.ready_at, bq.notified
                FROM brew_queue bq
                WHERE bq.ready_at <= NOW()
                  AND (bq.notified = FALSE OR bq.notified IS NULL)
                  AND bq.collected = FALSE
                LIMIT 100
            """)
    except Exception:
        return

    for row in rows:
        uid       = row["user_id"]
        recipe_id = row["recipe_id"]
        try:
            try:
                from handlers.potion_system import RECIPES
                recipe = RECIPES.get(recipe_id, {})
                name   = recipe.get("name", {}).get("ru", recipe_id)
            except Exception:
                name = recipe_id

            await bot.send_message(uid,
                f"🧪 *Зелье готово!*\n\n"
                f"*{name}* сварилось и ждёт тебя!\n"
                f"Открой 🧪 Зелья → Очередь → Собрать.",
                parse_mode="Markdown"
            )
            with get_conn() as conn:
                execute(conn,
                    "UPDATE brew_queue SET notified=TRUE WHERE user_id=%s AND recipe_id=%s AND ready_at=%s",
                    uid, recipe_id, row["ready_at"])
        except Exception as e:
            logger.warning("potion notify uid=%s: %s", uid, e)


async def weekly_rating_rewards(bot):
    """Еженедельный рейтинг — награды топ-игрокам (запускать каждый понедельник 00:01)."""
    try:
        with get_conn() as conn:
            top = fetchall(conn, """
                SELECT u.user_id, u.wizard_name, u.lang,
                       COALESCE(ws.xp_week, 0) as xp_week
                FROM users u
                LEFT JOIN weekly_stats ws ON ws.user_id = u.user_id
                WHERE COALESCE(u.is_banned, FALSE) = FALSE
                ORDER BY ws.xp_week DESC NULLS LAST
                LIMIT 10
            """)
    except Exception:
        logger.warning("weekly_rating: no weekly_stats table")
        return

    rewards = [
        {"place": 1, "xp": 2000, "gold": 1000, "label": "🥇 1-е место"},
        {"place": 2, "xp": 1200, "gold": 600,  "label": "🥈 2-е место"},
        {"place": 3, "xp": 800,  "gold": 400,  "label": "🥉 3-е место"},
    ]
    extra = {"xp": 200, "gold": 100, "label": "🏅 Топ-10"}

    for i, row in enumerate(top[:10]):
        uid  = row["user_id"]
        lang = row.get("lang") or "ru"
        r    = rewards[i] if i < 3 else extra

        add_xp(uid, r["xp"])
        add_gold(uid, r["gold"])

        try:
            await bot.send_message(uid,
                f"🏆 *Еженедельный рейтинг*\n\n"
                f"{r['label']} по XP за неделю!\n"
                f"XP за неделю: {row['xp_week']:,}\n\n"
                f"Награда: +{r['xp']} XP | +{r['gold']} 💰\n\n"
                f"Новая неделя началась — вперёд к новым победам!",
                parse_mode="Markdown"
            )
        except Exception:
            pass

    # Сброс недельной статистики
    try:
        with get_conn() as conn:
            execute(conn, "UPDATE weekly_stats SET xp_week=0")
    except Exception:
        pass


def setup_notification_jobs(scheduler, bot):
    """Добавить задачи уведомлений в планировщик."""
    from apscheduler.triggers.cron import CronTrigger

    # Проверка боссов каждые 5 минут
    scheduler.add_job(
        lambda: asyncio.get_event_loop().create_task(notify_boss_upcoming(bot)),
        "interval", minutes=5,
        id="boss_notify", replace_existing=True
    )
    # Проверка зелий каждые 2 минуты
    scheduler.add_job(
        lambda: asyncio.get_event_loop().create_task(notify_potion_ready(bot)),
        "interval", minutes=2,
        id="potion_notify", replace_existing=True
    )
    # Недельный рейтинг — каждый понедельник в 00:01 UTC
    scheduler.add_job(
        lambda: asyncio.get_event_loop().create_task(weekly_rating_rewards(bot)),
        CronTrigger(day_of_week="mon", hour=0, minute=1, timezone="UTC"),
        id="weekly_rating", replace_existing=True
    )
    logger.info("Notification jobs registered")
