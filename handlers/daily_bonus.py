"""
Ежедневный бонус за вход + событие дня + мини-задания.
"""
import logging
import random
from datetime import datetime, timezone, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler
from database import (
    get_user, user_exists, add_xp, add_gold, add_item_to_inventory,
    get_conn, execute, fetchrow, fetchall,
)
from utils.i18n import t

logger = logging.getLogger(__name__)

# ── Таблица наград за серию входов ────────────────────────────────────────────
LOGIN_REWARDS = {
    1:  {"gold": 50,   "xp": 20,   "item": None,              "label": "50 💰"},
    2:  {"gold": 100,  "xp": 30,   "item": None,              "label": "100 💰"},
    3:  {"gold": 150,  "xp": 50,   "item": "hp_potion_small", "label": "150 💰 + зелье HP"},
    4:  {"gold": 200,  "xp": 60,   "item": None,              "label": "200 💰"},
    5:  {"gold": 250,  "xp": 80,   "item": "hp_potion_medium", "label": "250 💰 + зелье HP"},
    6:  {"gold": 300,  "xp": 100,  "item": None,              "label": "300 💰"},
    7:  {"gold": 500,  "xp": 200,  "item": "hp_potion_large", "label": "500 💰 + 200 XP + зелье HP (большое)"},
    14: {"gold": 1000, "xp": 500,  "item": "strength_potion", "label": "1000 💰 + 500 XP + зелье силы"},
    30: {"gold": 3000, "xp": 1500, "item": "felix_felicis",   "label": "3000 💰 + 1500 XP + Феликс Фелицис 🍀"},
}

# ── События дня (меняются каждый день) ────────────────────────────────────────
DAILY_EVENTS = [
    {"id": "double_xp",    "name": "🌟 День двойного опыта",      "desc": "Весь опыт ×2 сегодня!",                   "effect": "xp_mult",    "value": 2.0},
    {"id": "double_gold",  "name": "💰 День богатства",            "desc": "Всё золото ×2 сегодня!",                  "effect": "gold_mult",  "value": 2.0},
    {"id": "rare_drop",    "name": "✨ День редких находок",       "desc": "Шанс редкого дропа ×3 в лесу и подземельях!", "effect": "drop_mult", "value": 3.0},
    {"id": "shop_sale",    "name": "🏪 День скидок",               "desc": "Скидка 25% в магазине!",                  "effect": "shop_disc",  "value": 0.25},
    {"id": "potion_fast",  "name": "🧪 День зельеварения",         "desc": "Зелья варятся в 2 раза быстрее!",         "effect": "brew_speed", "value": 2.0},
    {"id": "boss_bonus",   "name": "💀 День охоты на боссов",      "desc": "Награды за боссов ×1.5!",                 "effect": "boss_mult",  "value": 1.5},
    {"id": "duel_bonus",   "name": "⚔️ День дуэлей",              "desc": "+10 лимит дуэлей и ×1.5 награда за победу!", "effect": "duel_bonus", "value": 1.5},
    {"id": "lesson_bonus", "name": "📚 День знаний",               "desc": "Уроки дают ×2 XP и очки факультета!",    "effect": "lesson_mult","value": 2.0},
]

# ── Мини-задания дня ──────────────────────────────────────────────────────────
MINI_TASKS_POOL = [
    {"id": "kill_3",      "desc": "Победи 3 монстра в подземельях",    "stat": "pve_kills",  "target": 3,  "gold": 80,  "xp": 50},
    {"id": "lesson_2",    "desc": "Правильно ответь на 2 урока",       "stat": "lessons_correct", "target": 2, "gold": 60, "xp": 80},
    {"id": "feed_pet",    "desc": "Покорми питомца",                    "stat": "pet_feeds",  "target": 1,  "gold": 40,  "xp": 30},
    {"id": "duel_1",      "desc": "Проведи 1 дуэль",                   "stat": "pvp_total",  "target": 1,  "gold": 100, "xp": 60},
    {"id": "forest_2",    "desc": "Соверши 2 вылазки в Запретный лес", "stat": "forest_runs","target": 2,  "gold": 70,  "xp": 50},
    {"id": "brew_1",      "desc": "Свари 1 зелье",                     "stat": "potions_brewed","target": 1,"gold": 90,  "xp": 70},
    {"id": "quest_1",     "desc": "Выполни 1 квест",                   "stat": "quests_done","target": 1,  "gold": 120, "xp": 100},
    {"id": "spend_gold",  "desc": "Потрать 100 золота в магазине",     "stat": "gold_spent", "target": 100,"gold": 50,  "xp": 30},
    {"id": "boss_try",    "desc": "Атакуй мирового босса",             "stat": "wb_attacks", "target": 1,  "gold": 150, "xp": 120},
    {"id": "forest_3",    "desc": "Соверши 3 вылазки в Запретный лес", "stat": "forest_runs","target": 3,  "gold": 100, "xp": 80},
]

def _ensure_tables():
    try:
        with get_conn() as conn:
            execute(conn, """
                CREATE TABLE IF NOT EXISTS login_streaks (
                    user_id      BIGINT PRIMARY KEY,
                    streak       INT DEFAULT 0,
                    last_login   DATE,
                    total_logins INT DEFAULT 0
                )
            """)
            execute(conn, """
                CREATE TABLE IF NOT EXISTS daily_tasks (
                    user_id   BIGINT NOT NULL,
                    task_id   TEXT NOT NULL,
                    date      DATE NOT NULL,
                    progress  INT DEFAULT 0,
                    done      BOOLEAN DEFAULT FALSE,
                    PRIMARY KEY (user_id, task_id, date)
                )
            """)
    except Exception as e:
        logger.warning("daily_bonus tables: %s", e)

def _get_today_event() -> dict:
    """Одно событие дня — меняется каждые сутки по seed от даты."""
    seed = int(datetime.now(timezone.utc).strftime("%Y%m%d"))
    rng  = random.Random(seed)
    return rng.choice(DAILY_EVENTS)

def _get_today_tasks(user_id: int) -> list[dict]:
    """3 случайных задания на сегодня — seed от user_id + дата."""
    seed = int(f"{user_id}{datetime.now(timezone.utc).strftime('%Y%m%d')}")
    rng  = random.Random(seed)
    return rng.sample(MINI_TASKS_POOL, 3)

def _get_login_streak(user_id: int) -> dict:
    try:
        with get_conn() as conn:
            row = fetchrow(conn, "SELECT * FROM login_streaks WHERE user_id=%s", user_id)
        return row or {"user_id": user_id, "streak": 0, "last_login": None, "total_logins": 0}
    except Exception:
        return {"user_id": user_id, "streak": 0, "last_login": None, "total_logins": 0}

def _get_login_reward(streak: int) -> dict:
    """Возвращает награду для нужного дня серии."""
    # Ищем точное совпадение, потом ближайшее меньшее
    for day in sorted(LOGIN_REWARDS.keys(), reverse=True):
        if streak >= day:
            return LOGIN_REWARDS[day]
    return LOGIN_REWARDS[1]

def _get_reward_preview() -> str:
    """Предпросмотр наград на 7 дней."""
    lines = []
    for day in [1,2,3,4,5,6,7]:
        r = LOGIN_REWARDS[day]
        lines.append(f"День {day}: {r['label']}")
    lines.append("День 14: 1000 💰 + 500 XP + зелье силы")
    lines.append("День 30: 3000 💰 + 1500 XP + Феликс Фелицис 🍀")
    return "\n".join(lines)

def _get_tasks_progress(user_id: int, tasks: list) -> list[dict]:
    """Получает прогресс заданий на сегодня."""
    today = datetime.now(timezone.utc).date()
    result = []
    try:
        with get_conn() as conn:
            for task in tasks:
                row = fetchrow(conn,
                    "SELECT progress, done FROM daily_tasks WHERE user_id=%s AND task_id=%s AND date=%s",
                    user_id, task["id"], today)
                result.append({**task,
                    "progress": row["progress"] if row else 0,
                    "done":     row["done"]     if row else False})
    except Exception:
        result = [{**t, "progress": 0, "done": False} for t in tasks]
    return result

def _format_daily_screen(user_id: int) -> tuple[str, InlineKeyboardMarkup]:
    _ensure_tables()
    streak_row = _get_login_streak(user_id)
    streak     = streak_row.get("streak", 0)
    today      = datetime.now(timezone.utc).date()
    last_login = streak_row.get("last_login")
    already_claimed = (last_login == today)

    event = _get_today_event()
    tasks = _get_today_tasks(user_id)
    tasks_progress = _get_tasks_progress(user_id, tasks)

    # Бонус за вход
    reward    = _get_login_reward(streak + (0 if already_claimed else 1))
    streak_display = streak + (0 if already_claimed else 1)

    login_section = (
        f"🔥 *Ежедневный бонус*\n"
        f"Серия входов: {streak_display} дней {'🔥' * min(streak_display, 7)}\n"
    )
    if already_claimed:
        login_section += "✅ Бонус за сегодня получен!\n"
    else:
        login_section += f"🎁 Сегодня: *{reward['label']}*\n"

    # Событие дня
    event_section = (
        f"\n🌍 *Событие дня*\n"
        f"{event['name']}\n"
        f"_{event['desc']}_\n"
    )

    # Мини-задания
    tasks_lines = ["\n📋 *Задания дня*"]
    all_done = True
    for tp in tasks_progress:
        check = "✅" if tp["done"] else f"{tp['progress']}/{tp['target']}"
        tasks_lines.append(f"{check} {tp['desc']}")
        tasks_lines.append(f"   → +{tp['gold']} 💰 +{tp['xp']} XP")
        if not tp["done"]:
            all_done = False
    if all_done:
        tasks_lines.append("\n🎉 Все задания выполнены!")
    tasks_section = "\n".join(tasks_lines)

    # Таблица наград
    preview_section = f"\n\n📅 *Награды за серию:*\n_{_get_reward_preview()}_"

    text = login_section + event_section + tasks_section + preview_section

    buttons = []
    if not already_claimed:
        buttons.append([InlineKeyboardButton("🎁 Получить бонус!", callback_data="daily_claim")])
    buttons.append([InlineKeyboardButton("📋 Обновить прогресс", callback_data="daily_refresh")])
    return text, InlineKeyboardMarkup(buttons)

async def cmd_daily(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not user_exists(user_id):
        await update.message.reply_text(t(user_id, "not_registered"))
        return
    text, markup = _format_daily_screen(user_id)
    await update.message.reply_text(text, parse_mode="Markdown", reply_markup=markup)

async def cb_daily_claim(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query   = update.callback_query
    user_id = query.from_user.id
    _ensure_tables()

    today      = datetime.now(timezone.utc).date()
    streak_row = _get_login_streak(user_id)
    last_login = streak_row.get("last_login")

    if last_login == today:
        await query.answer("Ты уже получил бонус сегодня!", show_alert=True)
        return

    yesterday = today - timedelta(days=1)
    if last_login == yesterday:
        new_streak = streak_row.get("streak", 0) + 1
    else:
        new_streak = 1  # серия сброшена

    reward = _get_login_reward(new_streak)

    # Начислить
    if reward["gold"]: add_gold(user_id, reward["gold"])
    if reward["xp"]:   add_xp(user_id, reward["xp"])
    if reward["item"]: add_item_to_inventory(user_id, reward["item"], 1)

    # Обновить streak
    try:
        with get_conn() as conn:
            execute(conn, """
                INSERT INTO login_streaks (user_id, streak, last_login, total_logins)
                VALUES (%s, %s, %s, 1)
                ON CONFLICT (user_id) DO UPDATE
                SET streak=EXCLUDED.streak, last_login=EXCLUDED.last_login,
                    total_logins=login_streaks.total_logins+1
            """, user_id, new_streak, today)
    except Exception as e:
        logger.error("login_streak update: %s", e)

    # Запись в журнал
    try:
        with get_conn() as conn:
            execute(conn, """
                INSERT INTO player_journal (user_id, event_type, title, description, xp_gained, gold_gained)
                VALUES (%s,'other','Ежедневный бонус',%s,%s,%s)
            """, user_id, f"День {new_streak} серии входов", reward["xp"], reward["gold"])
    except Exception:
        pass

    await query.answer(f"✅ Получено: {reward['label']}", show_alert=True)
    text, markup = _format_daily_screen(user_id)
    await query.edit_message_text(text, parse_mode="Markdown", reply_markup=markup)

async def cb_daily_refresh(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query   = update.callback_query
    await query.answer("Обновлено!")
    user_id = query.from_user.id
    text, markup = _format_daily_screen(user_id)
    await query.edit_message_text(text, parse_mode="Markdown", reply_markup=markup)

def update_task_progress(user_id: int, stat: str, amount: int = 1):
    """Вызывается из других модулей для обновления прогресса заданий."""
    _ensure_tables()
    today = datetime.now(timezone.utc).date()
    tasks = _get_today_tasks(user_id)
    for task in tasks:
        if task["stat"] != stat:
            continue
        try:
            with get_conn() as conn:
                existing = fetchrow(conn,
                    "SELECT progress, done FROM daily_tasks WHERE user_id=%s AND task_id=%s AND date=%s",
                    user_id, task["id"], today)
                if existing and existing["done"]:
                    continue
                cur = existing["progress"] if existing else 0
                new_progress = cur + amount
                done = new_progress >= task["target"]
                execute(conn, """
                    INSERT INTO daily_tasks (user_id, task_id, date, progress, done)
                    VALUES (%s,%s,%s,%s,%s)
                    ON CONFLICT (user_id, task_id, date) DO UPDATE
                    SET progress=EXCLUDED.progress, done=EXCLUDED.done
                """, user_id, task["id"], today, new_progress, done)
                if done:
                    add_gold(user_id, task["gold"])
                    add_xp(user_id, task["xp"])
        except Exception as e:
            logger.warning("task_progress: %s", e)

def get_today_event() -> dict:
    """Публичная функция для получения события дня из других модулей."""
    return _get_today_event()

def register_daily_handlers(app):
    app.add_handler(CommandHandler("daily", cmd_daily))
    app.add_handler(CallbackQueryHandler(cb_daily_claim,   pattern=r"^daily_claim$"))
    app.add_handler(CallbackQueryHandler(cb_daily_refresh, pattern=r"^daily_refresh$"))
