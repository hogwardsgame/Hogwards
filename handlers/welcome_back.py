"""
Сводка «Пока тебя не было» — показывается при возвращении после паузы (>6ч).
Втягивает игрока обратно: что произошло, какие ждут награды.
"""
import logging
from datetime import datetime, timezone, timedelta
from database import get_user, get_conn, fetchrow, fetchall
from utils.helpers import house_emoji

logger = logging.getLogger(__name__)

ABSENCE_THRESHOLD_HOURS = 6   # сводка если отсутствовал больше 6 часов

async def build_welcome_back(user_id: int) -> str | None:
    """Собирает сводку событий за время отсутствия. None если игрок был активен."""
    user = get_user(user_id)
    if not user:
        return None

    last_active = user.get("last_active")
    if not last_active:
        return None
    if last_active.tzinfo is None:
        last_active = last_active.replace(tzinfo=timezone.utc)

    away = datetime.now(timezone.utc) - last_active
    hours = away.total_seconds() / 3600
    if hours < ABSENCE_THRESHOLD_HOURS:
        return None  # был недавно — сводка не нужна

    lines = []

    # Сколько отсутствовал
    if hours >= 48:
        away_str = f"{int(hours // 24)} дн."
    elif hours >= 1:
        away_str = f"{int(hours)} ч."
    else:
        away_str = f"{int(hours*60)} мин."

    # 1. Непрочитанные атаки (ambush)
    try:
        with get_conn() as conn:
            ambush_pending = fetchrow(conn,
                "SELECT COUNT(*) as cnt FROM ambushes WHERE user_id=%s AND status='pending' AND expires_at > NOW()",
                user_id)
            ambush_expired = fetchrow(conn,
                "SELECT COUNT(*) as cnt FROM ambushes WHERE user_id=%s AND status='expired'",
                user_id)
        if ambush_pending and ambush_pending["cnt"] > 0:
            lines.append(f"⚔️ На тебя напали — есть {ambush_pending['cnt']} активных нападений! Дай отпор за награды.")
        if ambush_expired and ambush_expired["cnt"] > 0:
            lines.append(f"💨 Ты пропустил {ambush_expired['cnt']} нападений, пока был в отлучке.")
    except Exception:
        pass

    # 2. Готовые зелья
    try:
        with get_conn() as conn:
            potions = fetchrow(conn,
                "SELECT COUNT(*) as cnt FROM brewing_queue WHERE user_id=%s AND ready_at <= NOW() AND collected=FALSE",
                user_id)
        if potions and potions["cnt"] > 0:
            lines.append(f"🧪 Готово зелий: {potions['cnt']}! Загляни в раздел Зелья → собрать.")
    except Exception:
        pass

    # 3. Питомец голоден?
    try:
        with get_conn() as conn:
            pet = fetchrow(conn, "SELECT pet_id, happiness, fed_at FROM user_pets WHERE user_id=%s", user_id)
        if pet:
            fed = pet.get("fed_at")
            if fed:
                if fed.tzinfo is None: fed = fed.replace(tzinfo=timezone.utc)
                if (datetime.now(timezone.utc) - fed).total_seconds() > 3600*6:
                    lines.append("🐾 Твой питомец проголодался — покорми его, чтобы бонус снова заработал!")
    except Exception:
        pass

    # 4. Ежедневный бонус доступен?
    try:
        with get_conn() as conn:
            streak = fetchrow(conn, "SELECT last_login FROM login_streaks WHERE user_id=%s", user_id)
        today = datetime.now(timezone.utc).date()
        if not streak or streak.get("last_login") != today:
            lines.append("🎁 Ежедневный бонус ждёт тебя! Не дай серии прерваться.")
    except Exception:
        pass

    # 5. Положение факультета в войне
    try:
        with get_conn() as conn:
            houses = fetchall(conn, "SELECT house, points FROM house_points ORDER BY points DESC")
        if houses:
            my_house = user.get("house")
            leader = houses[0]
            if my_house == leader["house"]:
                lines.append(f"🏆 Твой факультет {house_emoji(my_house)} лидирует в войне факультетов!")
            else:
                lines.append(f"🏠 Лидирует {house_emoji(leader['house'])} — помоги своему факультету вырваться вперёд!")
    except Exception:
        pass

    # 6. Активен ли сейчас мировой босс
    try:
        from database import get_active_world_boss
        wb = get_active_world_boss()
        if wb:
            lines.append("🐉 Прямо сейчас активен мировой босс! Присоединяйся к рейду.")
    except Exception:
        pass

    if not lines:
        return None  # ничего интересного не накопилось

    body = "\n".join(f"• {l}" for l in lines)
    return (
        f"👋 *С возвращением, {user['wizard_name']}!*\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"Тебя не было {away_str}. Вот что произошло:\n\n"
        f"{body}\n\n"
        f"_Самое время вернуться в игру!_"
    )
