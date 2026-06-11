"""
Личная история игрока — журнал событий.
Записывает ключевые события: победы над боссами, уроки, достижения,
питомцев, исследования, дуэли.
"""
import logging
from datetime import datetime, timezone
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler
from database import user_exists, get_conn, execute, fetchrow, fetchall
from utils.i18n import t

logger = logging.getLogger(__name__)

EVENT_TYPE_EMOJI = {
    "forest":     "🌲",
    "boss":       "💀",
    "duel":       "⚔️",
    "lesson":     "📚",
    "pet":        "🐾",
    "achievement":"🏆",
    "quest":      "📜",
    "brew":       "🧪",
    "explore":    "🗺️",
    "tournament": "🏅",
    "horcrux":    "💎",
    "triwizard":  "🏆",
    "shop":       "🛒",
    "other":      "📖",
}

PAGE_SIZE = 10

def _ensure_journal_table():
    try:
        with get_conn() as conn:
            execute(conn, """
                CREATE TABLE IF NOT EXISTS player_journal (
                    id          SERIAL PRIMARY KEY,
                    user_id     BIGINT NOT NULL,
                    event_type  TEXT   NOT NULL DEFAULT 'other',
                    title       TEXT   NOT NULL,
                    description TEXT   NOT NULL DEFAULT '',
                    xp_gained   INT    DEFAULT 0,
                    gold_gained INT    DEFAULT 0,
                    item_gained TEXT   DEFAULT '',
                    created_at  TIMESTAMPTZ DEFAULT NOW()
                )
            """)
            execute(conn, "CREATE INDEX IF NOT EXISTS pj_user_idx ON player_journal(user_id, created_at DESC)")
    except Exception as e:
        logger.warning("journal table: %s", e)

def add_journal_entry(user_id: int, event_type: str, title: str, description: str = "",
                      xp: int = 0, gold: int = 0, item: str = ""):
    """Публичная функция для записи в журнал из других модулей."""
    _ensure_journal_table()
    try:
        with get_conn() as conn:
            execute(conn, """
                INSERT INTO player_journal (user_id, event_type, title, description, xp_gained, gold_gained, item_gained)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, user_id, event_type, title, description, xp, gold, item)
    except Exception as e:
        logger.warning("journal write: %s", e)

def _format_entry(row: dict) -> str:
    emoji    = EVENT_TYPE_EMOJI.get(row.get("event_type", "other"), "📖")
    created  = row.get("created_at")
    if created:
        if created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)
        date_str = created.strftime("%d.%m %H:%M")
    else:
        date_str = "—"

    rewards = []
    if row.get("xp_gained"):   rewards.append(f"+{row['xp_gained']} XP")
    if row.get("gold_gained"):  rewards.append(f"+{row['gold_gained']} 💰")
    if row.get("item_gained"):  rewards.append(f"📦 {row['item_gained']}")
    reward_str = "  ".join(rewards)

    desc = row.get("description", "")
    desc_line = f"\n   _{desc}_" if desc else ""
    reward_line = f"\n   {reward_str}" if reward_str else ""

    return f"{emoji} *{row['title']}*  `{date_str}`{desc_line}{reward_line}"

async def cmd_journal(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not user_exists(user_id):
        await update.message.reply_text(t(user_id, "not_registered"))
        return

    _ensure_journal_table()
    await _show_journal(update.message, user_id, page=0, edit=False)

async def _show_journal(message_or_query, user_id: int, page: int, edit: bool):
    try:
        with get_conn() as conn:
            total = fetchrow(conn, "SELECT COUNT(*) as cnt FROM player_journal WHERE user_id=%s", user_id)
            total_count = total["cnt"] if total else 0
            rows = fetchall(conn, """
                SELECT * FROM player_journal WHERE user_id=%s
                ORDER BY created_at DESC
                LIMIT %s OFFSET %s
            """, user_id, PAGE_SIZE, page * PAGE_SIZE)
    except Exception:
        rows = []
        total_count = 0

    if not rows:
        text = (
            "📖 *Личная история*\n\n"
            "Здесь будут записаны твои приключения.\n"
            "Исследуй мир, побеждай боссов, учись — и история заполнится!"
        )
        if edit:
            await message_or_query.edit_message_text(text, parse_mode="Markdown")
        else:
            await message_or_query.reply_text(text, parse_mode="Markdown")
        return

    entries = "\n\n".join(_format_entry(r) for r in rows)
    total_pages = max(1, (total_count + PAGE_SIZE - 1) // PAGE_SIZE)
    header = (
        f"📖 *Личная история*\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"Страница {page+1}/{total_pages}  •  Всего событий: {total_count}\n\n"
    )

    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton("◀️", callback_data=f"journal_page:{page-1}"))
    if (page + 1) < total_pages:
        nav_buttons.append(InlineKeyboardButton("▶️", callback_data=f"journal_page:{page+1}"))

    markup = InlineKeyboardMarkup([nav_buttons]) if nav_buttons else None
    text   = header + entries

    if edit:
        await message_or_query.edit_message_text(text, parse_mode="Markdown", reply_markup=markup)
    else:
        await message_or_query.reply_text(text, parse_mode="Markdown", reply_markup=markup)

async def cb_journal_page(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query   = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    page    = int(query.data.split(":")[1])
    _ensure_journal_table()
    await _show_journal(query, user_id, page=page, edit=True)

def register_journal_handlers(app):
    app.add_handler(CommandHandler("journal",  cmd_journal))
    app.add_handler(CommandHandler("history",  cmd_journal))
    app.add_handler(CallbackQueryHandler(cb_journal_page, pattern=r"^journal_page:"))
