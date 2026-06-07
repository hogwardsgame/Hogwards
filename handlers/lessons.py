"""
NPC Lessons handler — TZ section 9.
4 lessons/day every 6 hours; player enrolls, APScheduler awards rewards after 3 hours.
"""
import logging
from datetime import datetime, timedelta, timezone
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler, MessageHandler, filters
from database import (
    get_user, user_exists, get_daily_limit, increment_daily,
    add_xp, add_gold, get_conn, execute, fetchrow, fetchall,
)
from utils.i18n import t
from game.drop_system import lesson_drop
from config import DAILY_LIMITS

logger = logging.getLogger(__name__)

SUBJECTS = [
    {"id": "potions",         "teacher": "Профессор Снейп",       "emoji": "🧪", "name": {"ru": "Зельеварение",    "en": "Potions"},          "bonus_type": "potion"},
    {"id": "transfiguration", "teacher": "Профессор МакГонагалл", "emoji": "🔮", "name": {"ru": "Трансфигурация",  "en": "Transfiguration"},   "bonus_type": "spell_chance"},
    {"id": "dada",            "teacher": "Профессор Люпин",       "emoji": "⚔️",  "name": {"ru": "ЗОТС",            "en": "DADA"},              "bonus_type": "pve_bonus"},
    {"id": "charms",          "teacher": "Профессор Флитвик",     "emoji": "✨",  "name": {"ru": "Чары",            "en": "Charms"},            "bonus_type": "mana_buff"},
    {"id": "divination",      "teacher": "Профессор Трелони",     "emoji": "🔮", "name": {"ru": "Прорицания",       "en": "Divination"},        "bonus_type": "random"},
]


def _get_today_lessons() -> list[dict]:
    """Return the 4 scheduled lessons for today (fixed times per TZ: every 6h)."""
    now  = datetime.now(timezone.utc)
    date = now.date()
    lessons = []
    for i, subject in enumerate(SUBJECTS[:4]):
        hour = i * 6  # 00, 06, 12, 18
        start = datetime(date.year, date.month, date.day, hour, 0, tzinfo=timezone.utc)
        end   = start + timedelta(hours=3)
        lessons.append({**subject, "starts_at": start, "ends_at": end, "slot": i})
    return lessons


def _lessons_keyboard(lessons: list[dict], user_id: int, enrolled_slots: set) -> InlineKeyboardMarkup:
    buttons = []
    now = datetime.now(timezone.utc)
    for lesson in lessons:
        start   = lesson["starts_at"]
        end     = lesson["ends_at"]
        enroll_deadline = end - timedelta(minutes=10)
        slot    = lesson["slot"]
        name    = lesson["name"].get("ru", lesson["name"]["en"])
        teacher = lesson["teacher"]

        if slot in enrolled_slots:
            label = f"✅ {lesson['emoji']} {name}"
        elif now < start:
            label = f"🕐 {lesson['emoji']} {name} — {start.strftime('%H:%M')} UTC"
        elif now > enroll_deadline:
            label = f"🔒 {lesson['emoji']} {name} — закрыта"
        else:
            label = f"📚 {lesson['emoji']} {name} | {teacher}"
        buttons.append([InlineKeyboardButton(label, callback_data=f"lesson_enroll:{slot}")])
    return InlineKeyboardMarkup(buttons)


async def cmd_lessons(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not user_exists(user_id):
        await update.message.reply_text(t(user_id, "not_registered"))
        return

    used = get_daily_limit(user_id, "lessons")
    if used >= DAILY_LIMITS["lessons"]:
        await update.message.reply_text(t(user_id, "lessons_daily_limit"))
        return

    lessons = _get_today_lessons()
    # Find enrolled lessons
    with get_conn() as conn:
        rows = fetchall(conn, """
            SELECT la.*, l.subject FROM lesson_attendance la
            JOIN lessons l ON la.lesson_id = l.id
            WHERE la.user_id = %s AND la.joined_at::date = CURRENT_DATE
        """, user_id)
    enrolled_subjects = {r["subject"] for r in rows}
    enrolled_slots    = {i for i, les in enumerate(lessons) if les["id"] in enrolled_subjects}

    markup = _lessons_keyboard(lessons, user_id, enrolled_slots)
    text = (
        f"📚 *Расписание уроков*\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"Использовано: {used}/{DAILY_LIMITS['lessons']} урока сегодня\n\n"
        f"Запишись на урок — через 3 часа получишь награду!"
    )
    await update.message.reply_text(text, parse_mode="Markdown", reply_markup=markup)


async def cb_lesson_enroll(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query   = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    slot    = int(query.data.split(":")[1])

    used = get_daily_limit(user_id, "lessons")
    if used >= DAILY_LIMITS["lessons"]:
        await query.answer(t(user_id, "lessons_daily_limit"), show_alert=True)
        return

    lessons = _get_today_lessons()
    if slot >= len(lessons):
        await query.answer("❌ Урок не найден", show_alert=True)
        return

    lesson = lessons[slot]
    now = datetime.now(timezone.utc)
    deadline = lesson["ends_at"] - timedelta(minutes=10)

    if now < lesson["starts_at"]:
        await query.answer(t(user_id, "lesson_not_started"), show_alert=True)
        return
    if now > deadline:
        await query.answer(t(user_id, "lesson_closed"), show_alert=True)
        return

    # Check already enrolled in this subject today
    with get_conn() as conn:
        existing = fetchrow(conn, """
            SELECT la.id FROM lesson_attendance la
            JOIN lessons l ON la.lesson_id = l.id
            WHERE la.user_id = %s AND l.subject = %s AND la.joined_at::date = CURRENT_DATE
        """, user_id, lesson["id"])
    if existing:
        await query.answer(t(user_id, "lesson_already_enrolled"), show_alert=True)
        return

    # Ensure lesson row exists
    with get_conn() as conn:
        lesson_row = fetchrow(conn,
            "SELECT id FROM lessons WHERE subject=%s AND starts_at::date=CURRENT_DATE", lesson["id"])
        if not lesson_row:
            execute(conn, """
                INSERT INTO lessons (subject, teacher, starts_at, ends_at)
                VALUES (%s, %s, %s, %s)
            """, lesson["id"], lesson["teacher"], lesson["starts_at"], lesson["ends_at"])
            lesson_row = fetchrow(conn,
                "SELECT id FROM lessons WHERE subject=%s AND starts_at::date=CURRENT_DATE", lesson["id"])

    lesson_db_id = lesson_row["id"]
    with get_conn() as conn:
        execute(conn, "INSERT INTO lesson_attendance (lesson_id, user_id) VALUES (%s, %s)", lesson_db_id, user_id)

    increment_daily(user_id, "lessons")

    name = lesson["name"].get("ru", lesson["name"]["en"])
    await query.edit_message_text(
        t(user_id, "lesson_enrolled", subject=name, teacher=lesson["teacher"]),
        parse_mode="Markdown"
    )


async def reward_lesson(user_id: int, lesson_id: str, bot):
    """Called by APScheduler 3 hours after lesson start."""
    with get_conn() as conn:
        row = fetchrow(conn, """
            SELECT la.id, la.rewarded FROM lesson_attendance la
            JOIN lessons l ON la.lesson_id = l.id
            WHERE la.user_id = %s AND l.subject = %s AND la.joined_at::date = CURRENT_DATE
        """, user_id, lesson_id)
        if not row or row["rewarded"]:
            return
        execute(conn, "UPDATE lesson_attendance SET rewarded=TRUE WHERE id=%s", row["id"])

    user = get_user(user_id)
    xp   = 80 + (user["level"] * 2)
    add_xp(user_id, xp)
    add_gold(user_id, 10)

    # House points
    with get_conn() as conn:
        execute(conn, "UPDATE house_points SET points = points + 5 WHERE house = (SELECT house FROM users WHERE user_id=%s)", user_id)

    # Spell drop (15% chance)
    luck_mod = 1.0 + (user.get("luck", 5) - 5) * 0.01
    drop = lesson_drop(luck_modifier=luck_mod)

    text = (
        f"📚 *Урок завершён!*\n"
        f"+{xp} XP  +10 💰  +5 очков факультету\n"
    )
    if drop:
        text += f"✨ Выучено заклинание: `{drop}`!"
        with get_conn() as conn:
            execute(conn, """
                INSERT INTO user_spells (user_id, spell_id)
                VALUES (%s, %s) ON CONFLICT DO NOTHING
            """, user_id, drop)

    try:
        await bot.send_message(user_id, text, parse_mode="Markdown")
    except Exception as e:
        logger.error(f"reward_lesson notify error: {e}")


async def handle_lessons_button(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if update.message.text == t(user_id, "btn_lessons"):
        await cmd_lessons(update, ctx)


def register_lessons_handlers(app):
    app.add_handler(CommandHandler("lessons", cmd_lessons))
    app.add_handler(CallbackQueryHandler(cb_lesson_enroll, pattern=r"^lesson_enroll:"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_lessons_button), group=6)
