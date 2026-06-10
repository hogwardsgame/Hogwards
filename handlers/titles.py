"""
Titles — система титулов.
Титул отображается в профиле. Игрок выбирает активный титул из заработанных.
Команда: /titles
"""
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler
from database import (
    get_user, user_exists, get_conn, execute, fetchall,
)
from utils.i18n import t

logger = logging.getLogger(__name__)

# Полный каталог титулов с описаниями
ALL_TITLES: dict[str, dict] = {
    # ── Стартовые ─────────────────────────────────────────────────────────────
    "Первокурсник":           {"emoji": "🎓", "desc": "Добро пожаловать в Хогвартс!",          "rarity": "common"},
    "Дуэлянт":                {"emoji": "⚔️", "desc": "25 побед в дуэлях",                    "rarity": "uncommon"},
    "Мастер дуэлей":          {"emoji": "🤺", "desc": "100 побед в дуэлях",                   "rarity": "rare"},
    "Непобедимый":            {"emoji": "🏆", "desc": "500 побед в дуэлях",                   "rarity": "epic"},
    "Ветеран арены":          {"emoji": "🛡️", "desc": "200 дуэлей проведено",                 "rarity": "rare"},
    # ── PvE ───────────────────────────────────────────────────────────────────
    "Истребитель":            {"emoji": "⚔️", "desc": "100 монстров уничтожено",              "rarity": "uncommon"},
    "Гроза тварей":           {"emoji": "🐉", "desc": "500 монстров уничтожено",              "rarity": "rare"},
    "Победитель боссов":      {"emoji": "👑", "desc": "5 боссов побеждено",                   "rarity": "rare"},
    "Гроза боссов":           {"emoji": "💀", "desc": "20 боссов побеждено",                  "rarity": "epic"},
    "Защитник мира":          {"emoji": "🌍", "desc": "5 мировых боссов побеждено",           "rarity": "epic"},
    "Легенда Хогвартса":      {"emoji": "⭐", "desc": "20 мировых боссов побеждено",          "rarity": "legendary"},
    # ── Учёба ─────────────────────────────────────────────────────────────────
    "Отличник":               {"emoji": "📚", "desc": "100 уроков пройдено",                  "rarity": "uncommon"},
    "Профессор":              {"emoji": "🎓", "desc": "500 уроков пройдено",                  "rarity": "rare"},
    "Путешественник":         {"emoji": "🗺️", "desc": "100 квестов выполнено",               "rarity": "rare"},
    # ── Прогресс ──────────────────────────────────────────────────────────────
    "Опытный волшебник":      {"emoji": "🌟", "desc": "25-й уровень",                         "rarity": "uncommon"},
    "Мастер Магии":           {"emoji": "💫", "desc": "50-й уровень",                         "rarity": "epic"},
    "Коллекционер":           {"emoji": "🎁", "desc": "Легендарный предмет найден",           "rarity": "rare"},
    # ── Богатство ─────────────────────────────────────────────────────────────
    "Богач":                  {"emoji": "💰", "desc": "50 000 золота заработано",             "rarity": "rare"},
    "Миллионер Хогвартса":    {"emoji": "💎", "desc": "500 000 золота заработано",            "rarity": "epic"},
    # ── Зельеварение ──────────────────────────────────────────────────────────
    "Зельевар":               {"emoji": "🧪", "desc": "25 зелий сварено",                    "rarity": "uncommon"},
    "Мастер зелий":           {"emoji": "⚗️", "desc": "100 зелий сварено",                   "rarity": "rare"},
    # ── Комбо ─────────────────────────────────────────────────────────────────
    "Комбинатор":             {"emoji": "✨", "desc": "25 комбо выполнено",                   "rarity": "uncommon"},
    "Мастер комбо":           {"emoji": "⚡", "desc": "100 комбо выполнено",                  "rarity": "rare"},
    # ── Турниры ───────────────────────────────────────────────────────────────
    "🏆 Чемпион турнира":     {"emoji": "🏆", "desc": "Победил в турнире",                   "rarity": "epic"},
    "🥈 Финалист":            {"emoji": "🥈", "desc": "2-е место в турнире",                  "rarity": "rare"},
    "🥉 Полуфиналист":        {"emoji": "🥉", "desc": "3-е место в турнире",                  "rarity": "uncommon"},
    # ── Кубок факультетов ────────────────────────────────────────────────────
    "🏆 Чемпион недели":      {"emoji": "🏆", "desc": "Факультет выиграл Кубок",              "rarity": "epic"},
    "🥈 Вице-чемпион":        {"emoji": "🥈", "desc": "2-е место в Кубке",                    "rarity": "rare"},
    "🥉 Третье место":        {"emoji": "🥉", "desc": "3-е место в Кубке",                    "rarity": "uncommon"},
    # ── Особые (выдаются вручную или за уникальные события) ──────────────────
    "Наследник Слизерина":    {"emoji": "🐍", "desc": "Особый титул Слизерина",               "rarity": "legendary"},
    "Хранитель Гриффиндора":  {"emoji": "🦁", "desc": "Особый титул Гриффиндора",             "rarity": "legendary"},
    "Мудрец Когтеврана":      {"emoji": "🦅", "desc": "Особый титул Когтеврана",              "rarity": "legendary"},
    "Хранитель Пуффендуя":    {"emoji": "🦡", "desc": "Особый титул Пуффендуя",               "rarity": "legendary"},
    "Чемпион Хогвартса":      {"emoji": "🌟", "desc": "Лучший из лучших",                     "rarity": "mythical"},
    "Гроза Василисков":       {"emoji": "⚔️", "desc": "Победил Василиска",                   "rarity": "legendary"},
    "Тёмный маг":             {"emoji": "💀", "desc": "Использовал 3 непростительных заклинания в бою", "rarity": "epic"},
    "Чёрный рыцарь":          {"emoji": "⬛", "desc": "100 поражений — и всё равно продолжает", "rarity": "rare"},
}

RARITY_ORDER = {"common": 0, "uncommon": 1, "rare": 2, "epic": 3, "legendary": 4, "mythical": 5}
RARITY_EMOJI = {
    "common":    "⬜",
    "uncommon":  "🟢",
    "rare":      "🔵",
    "epic":      "🟠",
    "legendary": "🔴",
    "mythical":  "⭐",
}
RARITY_RU = {
    "common":    "Обычный",
    "uncommon":  "Необычный",
    "rare":      "Редкий",
    "epic":      "Эпический",
    "legendary": "Легендарный",
    "mythical":  "Мифический",
}


async def cmd_titles(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """/titles — посмотреть и выбрать активный титул."""
    user_id = update.effective_user.id
    if not user_exists(user_id):
        await update.message.reply_text(t(user_id, "not_registered"))
        return

    user = get_user(user_id)
    with get_conn() as conn:
        rows = fetchall(conn,
            "SELECT title_id FROM user_titles WHERE user_id = %s ORDER BY earned_at DESC",
            user_id)

    owned = [r["title_id"] for r in rows]
    if not owned:
        await update.message.reply_text(
            "🎭 *Титулы*\n\n"
            "У тебя пока нет титулов.\n"
            "Получай их за достижения, победы и уроки!",
            parse_mode="Markdown"
        )
        return

    active = user.get("title", "нет")
    buttons = []
    for title_id in owned:
        info    = ALL_TITLES.get(title_id, {})
        emoji   = info.get("emoji", "🎭")
        rarity  = info.get("rarity", "common")
        r_emoji = RARITY_EMOJI.get(rarity, "")
        mark    = "✅ " if title_id == active else ""
        buttons.append([InlineKeyboardButton(
            f"{mark}{emoji} {title_id} {r_emoji}",
            callback_data=f"title_set:{title_id}"
        )])

    await update.message.reply_text(
        f"🎭 *Твои титулы* ({len(owned)} шт.)\n\n"
        f"Активный: *{active}*\n\n"
        f"Нажми для выбора:",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(buttons)
    )


async def cb_title_set(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query    = update.callback_query
    user_id  = query.from_user.id
    title_id = query.data.split(":", 1)[1]

    # Проверяем что титул принадлежит игроку
    with get_conn() as conn:
        row = fetchall(conn,
            "SELECT 1 FROM user_titles WHERE user_id = %s AND title_id = %s",
            user_id, title_id)
    if not row:
        await query.answer("❌ У тебя нет этого титула!", show_alert=True)
        return

    with get_conn() as conn:
        execute(conn, "UPDATE users SET title = %s WHERE user_id = %s", title_id, user_id)

    info  = ALL_TITLES.get(title_id, {})
    emoji = info.get("emoji", "🎭")
    await query.edit_message_text(
        f"✅ Активный титул: {emoji} *{title_id}*\n\n"
        f"_{info.get('desc', '')}_",
        parse_mode="Markdown"
    )


async def cmd_title_catalog(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """/titlecatalog — все существующие титулы."""
    user_id = update.effective_user.id
    with get_conn() as conn:
        owned_rows = fetchall(conn,
            "SELECT title_id FROM user_titles WHERE user_id = %s", user_id)
    owned = {r["title_id"] for r in owned_rows}

    # Группируем по редкости
    groups: dict[str, list] = {}
    for tid, info in ALL_TITLES.items():
        r = info.get("rarity", "common")
        groups.setdefault(r, []).append((tid, info))

    lines = ["📖 *Каталог титулов*\n"]
    for rarity in ["common", "uncommon", "rare", "epic", "legendary", "mythical"]:
        items = groups.get(rarity, [])
        if not items:
            continue
        r_emoji = RARITY_EMOJI[rarity]
        r_name  = RARITY_RU[rarity]
        lines.append(f"\n{r_emoji} *{r_name}*")
        for tid, info in items:
            have = "✅" if tid in owned else "⬜"
            lines.append(f"{have} {info['emoji']} {tid} — _{info['desc']}_")

    # Разбиваем на части если слишком длинно
    text = "\n".join(lines)
    if len(text) > 4000:
        text = text[:4000] + "\n\n_...и другие_"

    await update.message.reply_text(text, parse_mode="Markdown")


def grant_title(user_id: int, title_id: str):
    """Выдать титул игроку (из других модулей)."""
    with get_conn() as conn:
        execute(conn, """
            INSERT INTO user_titles (user_id, title_id)
            VALUES (%s, %s) ON CONFLICT DO NOTHING
        """, user_id, title_id)


def register_titles_handlers(app):
    app.add_handler(CommandHandler("titles",       cmd_titles))
    app.add_handler(CommandHandler("titlecatalog", cmd_title_catalog))
    app.add_handler(CallbackQueryHandler(cb_title_set, pattern=r"^title_set:"))

