"""
House Points — очки факультетов, еженедельные рейтинги, награды победителям.
Команды: /house — текущие очки, /housecup — история кубка.
Сброс каждый понедельник через планировщик.
"""
import logging
from datetime import datetime, timezone
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler
from database import (
    get_user, user_exists, get_house_points, reset_house_cup_points,
    add_xp, add_gold, get_conn, execute, fetchall,
)
from utils.i18n import t
from config import HOUSE_EMOJIS

logger = logging.getLogger(__name__)

HOUSE_NAMES_RU = {
    "gryffindor": "Гриффиндор",
    "slytherin":  "Слизерин",
    "ravenclaw":  "Когтевран",
    "hufflepuff": "Пуффендуй",
}

HOUSE_COLORS = {
    "gryffindor": "🔴🟡",
    "slytherin":  "🟢⬜",
    "ravenclaw":  "🔵🟡",
    "hufflepuff": "🟡⬛",
}

# Награды за 1-е место в недельном рейтинге
WEEKLY_WINNER_REWARDS = {
    1: {"xp": 500,  "gold": 200, "title": "🏆 Чемпион недели"},
    2: {"xp": 250,  "gold": 100, "title": "🥈 Вице-чемпион"},
    3: {"xp": 100,  "gold": 50,  "title": "🥉 Третье место"},
}


def _build_standings_text(rows: list, season: int) -> str:
    """Формирует текст таблицы очков факультетов."""
    medals = ["🥇", "🥈", "🥉", "4️⃣"]
    lines  = []
    for i, row in enumerate(rows):
        house    = row["house"]
        points   = row["points"]
        name     = HOUSE_NAMES_RU.get(house, house)
        emoji    = HOUSE_EMOJIS.get(house, "🏠")
        color    = HOUSE_COLORS.get(house, "")
        medal    = medals[i] if i < len(medals) else f"{i+1}."
        bar_fill = int(10 * points / max(1, rows[0]["points"])) if rows else 0
        bar      = "█" * bar_fill + "░" * (10 - bar_fill)
        lines.append(f"{medal} {emoji} *{name}* {color}\n   `[{bar}]` {points} очков")

    return (
        f"🏆 *Кубок Хогвартса* — Сезон {season}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        + "\n\n".join(lines)
        + "\n\n━━━━━━━━━━━━━━━━━━━━\n"
        f"Сброс каждый понедельник в 00:00 UTC"
    )


async def cmd_house(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """/house — текущий счёт Кубка Хогвартса."""
    user_id = update.effective_user.id
    rows    = get_house_points()

    if not rows:
        await update.message.reply_text("🏆 Данные о Кубке пока недоступны.")
        return

    season = rows[0]["season"] if rows else 1
    text   = _build_standings_text(rows, season)

    # Показываем очки игрока и его вклад
    if user_exists(user_id):
        user = get_user(user_id)
        with get_conn() as conn:
            personal = fetchall(conn, """
                SELECT SUM(points) as total, reason
                FROM house_points_log
                WHERE user_id = %s
                GROUP BY reason
                ORDER BY total DESC
                LIMIT 5
            """, user_id)
        my_pts = sum(r["total"] for r in personal) if personal else 0
        house_name = HOUSE_NAMES_RU.get(user["house"], user["house"])
        text += f"\n\n👤 *Твой вклад* ({house_name}): {my_pts} очков"

    markup = InlineKeyboardMarkup([[
        InlineKeyboardButton("📊 Мой вклад", callback_data="house_my_contrib"),
        InlineKeyboardButton("📜 История",   callback_data="house_history"),
    ]])
    await update.message.reply_text(text, parse_mode="Markdown", reply_markup=markup)


async def cb_house_contrib(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query   = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    if not user_exists(user_id):
        await query.edit_message_text("❌ Ты не зарегистрирован.")
        return

    with get_conn() as conn:
        rows = fetchall(conn, """
            SELECT reason, SUM(points) as total
            FROM house_points_log
            WHERE user_id = %s
            GROUP BY reason
            ORDER BY total DESC
        """, user_id)

    REASON_NAMES = {
        "lesson_correct":  "📚 Правильные ответы",
        "pvp_win":         "⚔️ Победы в PvP",
        "pvp_kill":        "⚔️ PvP",
        "pve_kill":        "🐉 Победы над монстрами",
        "pve_boss_kill":   "👑 Победы над боссами",
        "world_boss":      "🌍 Мировые боссы",
        "quest_done":      "📜 Выполненные квесты",
        "tournament_win":  "🏆 Турниры",
    }

    lines = []
    total = 0
    for r in rows:
        label  = REASON_NAMES.get(r["reason"], r["reason"])
        pts    = r["total"]
        total += pts
        lines.append(f"{label}: *{pts}* очков")

    text = "📊 *Твой вклад в Кубок Хогвартса*\n\n"
    text += "\n".join(lines) if lines else "Ты ещё не принёс очков факультету."
    text += f"\n\n*Итого:* {total} очков"

    await query.edit_message_text(text, parse_mode="Markdown")


async def cb_house_history(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query   = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    with get_conn() as conn:
        rows = fetchall(conn, """
            SELECT house, SUM(points) as pts
            FROM house_points_log
            WHERE created_at > NOW() - INTERVAL '7 days'
            GROUP BY house
            ORDER BY pts DESC
        """)

    if not rows:
        await query.edit_message_text("📜 История за эту неделю пока пуста.")
        return

    lines = []
    medals = ["🥇", "🥈", "🥉", "4️⃣"]
    for i, r in enumerate(rows):
        name  = HOUSE_NAMES_RU.get(r["house"], r["house"])
        emoji = HOUSE_EMOJIS.get(r["house"], "🏠")
        lines.append(f"{medals[i]} {emoji} {name}: *{r['pts']}* очков за неделю")

    await query.edit_message_text(
        "📜 *Очки за последние 7 дней*\n\n" + "\n".join(lines),
        parse_mode="Markdown"
    )


async def cmd_housecup(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """/housecup — полная информация о Кубке."""
    await cmd_house(update, ctx)


def award_weekly_winners(bot=None):
    """Вызывается планировщиком каждый понедельник. Выдаёт награды и сбрасывает очки."""
    rows = get_house_points()
    if not rows:
        return

    ranked = sorted(rows, key=lambda r: r["points"], reverse=True)
    season = rows[0]["season"]

    logger.info(f"🏆 House Cup Season {season} ending. Winner: {ranked[0]['house']}")

    # Выдаём награды игрокам победившего факультета
    with get_conn() as conn:
        for place, row in enumerate(ranked[:3], start=1):
            house   = row["house"]
            rewards = WEEKLY_WINNER_REWARDS[place]
            players = fetchall(conn,
                "SELECT user_id FROM users WHERE house = %s AND is_banned = FALSE",
                house)
            for p in players:
                uid = p["user_id"]
                add_xp(uid, rewards["xp"])
                add_gold(uid, rewards["gold"])
                # Записываем титул сезона
                execute(conn, """
                    INSERT INTO user_titles (user_id, title_id)
                    VALUES (%s, %s) ON CONFLICT DO NOTHING
                """, uid, f"housecup_s{season}_place{place}")

            if bot and players:
                import asyncio
                winner_name = HOUSE_NAMES_RU.get(house, house)
                emoji       = HOUSE_EMOJIS.get(house, "🏠")
                rewards_text = (
                    f"🏆 *Кубок Хогвартса — Сезон {season} завершён!*\n\n"
                    f"{emoji} *{winner_name}* — {place}-е место!\n"
                    f"+{rewards['xp']} XP | +{rewards['gold']} 💰\n"
                    f"Титул: {rewards['title']}"
                )
                for p in players[:50]:  # не спамим слишком много
                    try:
                        asyncio.get_event_loop().create_task(
                            bot.send_message(p["user_id"], rewards_text, parse_mode="Markdown")
                        )
                    except Exception:
                        pass

    reset_house_cup_points()
    logger.info("House Cup points reset for new season.")


def register_house_points_handlers(app):
    app.add_handler(CommandHandler("house",    cmd_house))
    app.add_handler(CommandHandler("housecup", cmd_housecup))
    app.add_handler(CallbackQueryHandler(cb_house_contrib, pattern=r"^house_my_contrib"))
    app.add_handler(CallbackQueryHandler(cb_house_history, pattern=r"^house_history"))
