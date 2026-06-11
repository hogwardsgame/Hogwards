"""
Rating — рейтинги с вкладками.
По уровню, по XP за неделю, по PvP победам, по PvE убийствам.
"""
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler
from database import get_leaderboard, get_house_points, user_exists, get_conn, fetchall, get_user
from utils.i18n import t
from utils.helpers import house_emoji, medal

TABS = [
    ("level",    "🏆 Уровень"),
    ("xp_week",  "✨ XP за неделю"),
    ("pvp",      "⚔️ PvP победы"),
    ("pve",      "🐉 PvE убийства"),
    ("gold",     "💰 Золото"),
]

def _tab_keyboard(active: str) -> InlineKeyboardMarkup:
    buttons = []
    for key, label in TABS:
        prefix = "▶️ " if key == active else ""
        buttons.append(InlineKeyboardButton(f"{prefix}{label}", callback_data=f"rating_tab:{key}"))
    # Split into 2-3 per row
    rows = [buttons[i:i+2] for i in range(0, len(buttons), 2)]
    rows.append([InlineKeyboardButton("🏠 Война факультетов", callback_data="rating_tab:houses")])
    return InlineKeyboardMarkup(rows)

def _get_leaderboard_by(category: str, limit: int = 10) -> list:
    try:
        with get_conn() as conn:
            if category == "xp_week":
                return fetchall(conn, """
                    SELECT u.wizard_name, u.house, u.level,
                           COALESCE(ws.xp_week, 0) as score
                    FROM users u
                    LEFT JOIN weekly_stats ws ON ws.user_id = u.user_id
                    WHERE COALESCE(u.is_banned, FALSE) = FALSE
                    ORDER BY score DESC NULLS LAST
                    LIMIT %s
                """, limit)
            elif category == "pvp":
                return fetchall(conn, """
                    SELECT u.wizard_name, u.house, u.level,
                           COALESCE(us.pvp_wins, 0) as score
                    FROM users u
                    LEFT JOIN user_stats us ON us.user_id = u.user_id
                    WHERE COALESCE(u.is_banned, FALSE) = FALSE
                    ORDER BY score DESC NULLS LAST
                    LIMIT %s
                """, limit)
            elif category == "pve":
                return fetchall(conn, """
                    SELECT u.wizard_name, u.house, u.level,
                           COALESCE(us.pve_kills, 0) as score
                    FROM users u
                    LEFT JOIN user_stats us ON us.user_id = u.user_id
                    WHERE COALESCE(u.is_banned, FALSE) = FALSE
                    ORDER BY score DESC NULLS LAST
                    LIMIT %s
                """, limit)
            elif category == "gold":
                return fetchall(conn, """
                    SELECT wizard_name, house, level, gold as score
                    FROM users
                    WHERE COALESCE(is_banned, FALSE) = FALSE
                    ORDER BY gold DESC NULLS LAST
                    LIMIT %s
                """, limit)
            else:  # level
                return fetchall(conn, """
                    SELECT wizard_name, house, level, xp as score
                    FROM users
                    WHERE COALESCE(is_banned, FALSE) = FALSE
                    ORDER BY level DESC, xp DESC
                    LIMIT %s
                """, limit)
    except Exception:
        return []

def _format_leaderboard(rows: list, category: str, user_id: int) -> str:
    tab_names = {
        "level":   "🏆 Топ по уровню",
        "xp_week": "✨ Топ по XP за неделю",
        "pvp":     "⚔️ Топ по PvP победам",
        "pve":     "🐉 Топ по PvE убийствам",
        "gold":    "💰 Топ по золоту",
    }
    score_suffix = {
        "level":   " ур.",
        "xp_week": " XP",
        "pvp":     " побед",
        "pve":     " убийств",
        "gold":    " 💰",
    }
    title  = tab_names.get(category, "Рейтинг")
    suffix = score_suffix.get(category, "")
    lines  = [f"*{title}*\n━━━━━━━━━━━━━━━━━━━━"]
    if not rows:
        lines.append("_Нет данных_")
        return "\n".join(lines)
    for i, row in enumerate(rows, 1):
        m     = medal(i)
        he    = house_emoji(row["house"])
        name  = row["wizard_name"]
        score = row.get("score", row.get("level", 0))
        lines.append(f"{m} {he} {name} — {score}{suffix}")
    return "\n".join(lines)

async def show_rating(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not user_exists(user_id):
        await update.message.reply_text(t(user_id, "not_registered"))
        return
    rows = _get_leaderboard_by("level")
    text = _format_leaderboard(rows, "level", user_id)
    # Найти позицию текущего игрока
    try:
        user = get_user(user_id)
        text += f"\n\n👤 Твой уровень: {user['level']}"
    except Exception:
        pass
    await update.message.reply_text(text, parse_mode="Markdown",
                                    reply_markup=_tab_keyboard("level"))

async def cb_rating_tab(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query   = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    tab     = query.data.split(":")[1]

    if tab == "houses":
        rows = get_house_points()
        lines = ["🏠 *Война факультетов*\n━━━━━━━━━━━━━━━━━━━━"]
        for i, row in enumerate(sorted(rows, key=lambda r: r["points"], reverse=True), 1):
            he    = house_emoji(row["house"])
            hname = {"gryffindor":"Гриффиндор","slytherin":"Слизерин",
                     "ravenclaw":"Когтевран","hufflepuff":"Пуффендуй"}.get(row["house"], row["house"])
            pts   = row["points"]
            bar   = "█" * min(int(pts / max(r["points"] for r in rows) * 10), 10) if rows else ""
            lines.append(f"{medal(i)} {he} {hname}: {pts} очков {bar}")
        text = "\n".join(lines)
    else:
        rows = _get_leaderboard_by(tab)
        text = _format_leaderboard(rows, tab, user_id)

    await query.edit_message_text(text, parse_mode="Markdown",
                                  reply_markup=_tab_keyboard(tab if tab != "houses" else "level"))

async def show_house_cup(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    rows = get_house_points()
    text = t(user_id, "house_cup_header")
    for i, row in enumerate(rows, 1):
        house = row["house"]
        text += t(user_id, "house_cup_row",
                  pos=medal(i), emoji=house_emoji(house),
                  house=t(user_id, f"house_{house}"),
                  points=row["points"]) + "\n"
    await update.message.reply_text(text)

def register_rating_handlers(app):
    app.add_handler(CommandHandler("rating", show_rating))
    app.add_handler(CommandHandler("housecup", show_house_cup))
    app.add_handler(CallbackQueryHandler(cb_rating_tab, pattern=r"^rating_tab:"))
