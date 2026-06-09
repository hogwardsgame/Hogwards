"""
House War — война факультетов + рейтинги.
Команды: /war /ratings /season
"""
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler
from database import (
    get_user, user_exists, get_house_points, get_conn,
    fetchall, fetchrow, fetchval,
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

RATING_CATEGORIES = {
    "level": "🏆 По уровню",
    "gold":  "💰 По золоту",
    "pvp":   "⚔️ По PvP победам",
    "pve":   "🐉 По PvE убийствам",
}


async def cmd_war(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """/war — состояние войны факультетов."""
    rows   = get_house_points()
    season = rows[0]["season"] if rows else 1

    sorted_rows = sorted(rows, key=lambda r: r["points"], reverse=True)
    medals = ["🥇", "🥈", "🥉", "4️⃣"]
    max_pts = sorted_rows[0]["points"] if sorted_rows else 1

    lines = [f"⚔️ *Война факультетов — Сезон {season}*\n"]
    for i, row in enumerate(sorted_rows):
        house    = row["house"]
        pts      = row["points"]
        name     = HOUSE_NAMES_RU.get(house, house)
        emoji    = HOUSE_EMOJIS.get(house, "🏠")
        medal    = medals[i] if i < len(medals) else f"{i+1}."
        bar_fill = int(12 * pts / max(1, max_pts))
        bar      = "█" * bar_fill + "░" * (12 - bar_fill)
        lines.append(f"{medal} {emoji} *{name}*\n   `[{bar}]` {pts:,} очков")

    lines.append("\n*Очки начисляются за:*")
    lines.append("📚 Уроки • ⚔️ PvP • 🐉 PvE • 👑 Боссы • 🌍 Мировые боссы • 📜 Квесты • 🏆 Турниры")
    lines.append("\nСброс каждый понедельник 00:00 UTC — победители получают награды!")

    markup = InlineKeyboardMarkup([
        [InlineKeyboardButton("📊 Топ вкладчиков", callback_data="war_top_contributors")],
        [InlineKeyboardButton("📜 Мой вклад",       callback_data="war_my_contrib")],
    ])
    await update.message.reply_text(
        "\n\n".join(lines), parse_mode="Markdown", reply_markup=markup
    )


async def cb_war_top(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    with get_conn() as conn:
        rows = fetchall(conn, """
            SELECT u.wizard_name, u.house, SUM(l.points) as total
            FROM house_points_log l
            JOIN users u ON l.user_id = u.user_id
            GROUP BY u.wizard_name, u.house
            ORDER BY total DESC
            LIMIT 10
        """)

    medals = ["🥇","🥈","🥉","4️⃣","5️⃣","6️⃣","7️⃣","8️⃣","9️⃣","🔟"]
    lines  = ["📊 *Топ вкладчиков в Кубок*\n"]
    for i, r in enumerate(rows):
        emoji = HOUSE_EMOJIS.get(r["house"], "🏠")
        lines.append(f"{medals[i]} {emoji} {r['wizard_name']} — {r['total']:,} очков")

    await query.edit_message_text(
        "\n".join(lines), parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("🔙 Назад", callback_data="war_back")
        ]])
    )


async def cb_war_contrib(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query   = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    if not user_exists(user_id):
        await query.edit_message_text("❌ Ты не зарегистрирован.")
        return

    with get_conn() as conn:
        rows = fetchall(conn, """
            SELECT reason, SUM(points) as total
            FROM house_points_log WHERE user_id = %s
            GROUP BY reason ORDER BY total DESC
        """, user_id)

    REASONS = {
        "lesson_correct": "📚 Уроки",
        "pvp_win":        "⚔️ PvP победы",
        "pvp_kill":       "⚔️ PvP",
        "pve_kill":       "🐉 PvE монстры",
        "pve_boss_kill":  "👑 Боссы",
        "world_boss":     "🌍 Мировые боссы",
        "quest_done":     "📜 Квесты",
        "tournament_win": "🏆 Турниры",
        "explore":        "🗺️ Исследование",
    }
    lines = ["📜 *Твой вклад в войну факультетов*\n"]
    total = 0
    for r in rows:
        label  = REASONS.get(r["reason"], r["reason"])
        total += r["total"]
        lines.append(f"{label}: *{r['total']}*")
    lines.append(f"\n*Итого: {total} очков*")

    await query.edit_message_text(
        "\n".join(lines), parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("🔙 Назад", callback_data="war_back")
        ]])
    )


async def cb_war_back(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    rows   = get_house_points()
    season = rows[0]["season"] if rows else 1
    sorted_rows = sorted(rows, key=lambda r: r["points"], reverse=True)
    medals  = ["🥇","🥈","🥉","4️⃣"]
    max_pts = sorted_rows[0]["points"] if sorted_rows else 1
    lines   = [f"⚔️ *Война факультетов — Сезон {season}*\n"]
    for i, row in enumerate(sorted_rows):
        house = row["house"]
        pts   = row["points"]
        name  = HOUSE_NAMES_RU.get(house, house)
        emoji = HOUSE_EMOJIS.get(house, "🏠")
        medal = medals[i] if i < len(medals) else f"{i+1}."
        bar   = "█" * int(12 * pts / max(1, max_pts)) + "░" * (12 - int(12 * pts / max(1, max_pts)))
        lines.append(f"{medal} {emoji} *{name}*\n   `[{bar}]` {pts:,} очков")

    markup = InlineKeyboardMarkup([
        [InlineKeyboardButton("📊 Топ вкладчиков", callback_data="war_top_contributors")],
        [InlineKeyboardButton("📜 Мой вклад",       callback_data="war_my_contrib")],
    ])
    await query.edit_message_text("\n\n".join(lines), parse_mode="Markdown", reply_markup=markup)


async def cmd_ratings(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """/ratings — выбор категории рейтинга."""
    buttons = [[
        InlineKeyboardButton(label, callback_data=f"rating_show:{cat}")
    ] for cat, label in RATING_CATEGORIES.items()]
    buttons.append([InlineKeyboardButton("🏰 По факультетам", callback_data="rating_show:house")])

    await update.message.reply_text(
        "📊 *Рейтинги Хогвартса*\n\nВыбери категорию:",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(buttons)
    )


async def cb_rating_show(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query    = update.callback_query
    await query.answer()
    category = query.data.split(":")[1]

    from database import get_leaderboard
    medals = ["🥇","🥈","🥉","4️⃣","5️⃣","6️⃣","7️⃣","8️⃣","9️⃣","🔟"]

    if category == "house":
        rows  = get_house_points()
        srows = sorted(rows, key=lambda r: r["points"], reverse=True)
        lines = ["🏰 *Рейтинг факультетов*\n"]
        for i, r in enumerate(srows):
            name  = HOUSE_NAMES_RU.get(r["house"], r["house"])
            emoji = HOUSE_EMOJIS.get(r["house"], "🏠")
            lines.append(f"{medals[i]} {emoji} {name}: *{r['points']:,}* очков")
    else:
        rows  = get_leaderboard(category, 10)
        title = RATING_CATEGORIES.get(category, category)
        lines = [f"{title}\n"]

        for i, r in enumerate(rows):
            emoji = HOUSE_EMOJIS.get(r.get("house", ""), "🏠")
            name  = r.get("wizard_name", "?")
            if category == "level":
                val = f"Ур.{r['level']} ({r['xp']} XP)"
            elif category == "gold":
                val = f"{r['gold']:,} 💰"
            elif category == "pvp":
                val = f"{r['pvp_wins']} побед"
            elif category == "pve":
                val = f"{r['pve_kills']} убийств"
            else:
                val = ""
            lines.append(f"{medals[i]} {emoji} {name} — {val}")

    markup = InlineKeyboardMarkup([[
        InlineKeyboardButton("🔙 Назад", callback_data="rating_back")
    ]])
    await query.edit_message_text(
        "\n".join(lines), parse_mode="Markdown", reply_markup=markup
    )


async def cb_rating_back(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    buttons = [[
        InlineKeyboardButton(label, callback_data=f"rating_show:{cat}")
    ] for cat, label in RATING_CATEGORIES.items()]
    buttons.append([InlineKeyboardButton("🏰 По факультетам", callback_data="rating_show:house")])
    await query.edit_message_text(
        "📊 *Рейтинги Хогвартса*\n\nВыбери категорию:",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(buttons)
    )


def register_house_war_handlers(app):
    app.add_handler(CommandHandler("war",     cmd_war))
    app.add_handler(CommandHandler("ratings", cmd_ratings))
    app.add_handler(CallbackQueryHandler(cb_war_top,    pattern=r"^war_top_contributors$"))
    app.add_handler(CallbackQueryHandler(cb_war_contrib,pattern=r"^war_my_contrib$"))
    app.add_handler(CallbackQueryHandler(cb_war_back,   pattern=r"^war_back$"))
    app.add_handler(CallbackQueryHandler(cb_rating_show,pattern=r"^rating_show:"))
    app.add_handler(CallbackQueryHandler(cb_rating_back,pattern=r"^rating_back$"))
