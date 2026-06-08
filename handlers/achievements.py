"""
Achievements — система достижений.
Проверка триггерится из других модулей через check_achievements().
Команда: /achievements
"""
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler
from database import (
    get_user, user_exists, get_user_achievements, unlock_achievement,
    add_xp, add_gold, get_conn, execute, fetchrow, fetchall,
)
from utils.i18n import t
from config import ACHIEVEMENT_THRESHOLDS

logger = logging.getLogger(__name__)

# ── Каталог достижений ─────────────────────────────────────────────────────────
ACHIEVEMENTS: dict[str, dict] = {
    # ── Бои с монстрами ────────────────────────────────────────────────────────
    "monster_slayer": {
        "name":     "Охотник на монстров",
        "emoji":    "⚔️",
        "desc":     "Победи {n} монстров",
        "tiers":    [10, 50, 100, 500],
        "rewards":  [
            {"xp": 100,  "gold": 50,  "title": None},
            {"xp": 300,  "gold": 150, "title": None},
            {"xp": 600,  "gold": 300, "title": "Истребитель"},
            {"xp": 1500, "gold": 750, "title": "Гроза тварей"},
        ],
        "stat": "pve_kills",
    },
    "boss_hunter": {
        "name":     "Охотник на боссов",
        "emoji":    "👑",
        "desc":     "Победи {n} боссов",
        "tiers":    [1, 5, 20],
        "rewards":  [
            {"xp": 200,  "gold": 100, "title": None},
            {"xp": 600,  "gold": 300, "title": "Победитель боссов"},
            {"xp": 1500, "gold": 750, "title": "Гроза боссов"},
        ],
        "stat": "boss_kills",
    },
    "world_boss_hero": {
        "name":     "Герой мировых боссов",
        "emoji":    "🌍",
        "desc":     "Участвуй в победах над {n} мировыми боссами",
        "tiers":    [1, 5, 20],
        "rewards":  [
            {"xp": 300,  "gold": 150, "title": None},
            {"xp": 800,  "gold": 400, "title": "Защитник мира"},
            {"xp": 2000, "gold": 1000,"title": "Легенда Хогвартса"},
        ],
        "stat": "world_boss_kills",
    },
    # ── PvP ────────────────────────────────────────────────────────────────────
    "pvp_winner": {
        "name":     "Дуэлянт",
        "emoji":    "🤺",
        "desc":     "Победи {n} игроков в дуэлях",
        "tiers":    [5, 25, 100, 500],
        "rewards":  [
            {"xp": 150,  "gold": 75,  "title": None},
            {"xp": 400,  "gold": 200, "title": "Дуэлянт"},
            {"xp": 800,  "gold": 400, "title": "Мастер дуэлей"},
            {"xp": 2000, "gold": 1000,"title": "Непобедимый"},
        ],
        "stat": "pvp_wins",
    },
    "pvp_veteran": {
        "name":     "Ветеран арены",
        "emoji":    "🛡️",
        "desc":     "Проведи {n} дуэлей",
        "tiers":    [10, 50, 200],
        "rewards":  [
            {"xp": 100,  "gold": 50,  "title": None},
            {"xp": 300,  "gold": 150, "title": None},
            {"xp": 800,  "gold": 400, "title": "Ветеран арены"},
        ],
        "stat": "pvp_total",
    },
    # ── Учёба ──────────────────────────────────────────────────────────────────
    "lesson_master": {
        "name":     "Прилежный ученик",
        "emoji":    "📚",
        "desc":     "Пройди {n} уроков",
        "tiers":    [10, 50, 100, 500],
        "rewards":  [
            {"xp": 100,  "gold": 50,  "title": None},
            {"xp": 300,  "gold": 150, "title": None},
            {"xp": 600,  "gold": 300, "title": "Отличник"},
            {"xp": 1500, "gold": 750, "title": "Профессор"},
        ],
        "stat": "lessons_done",
    },
    # ── Богатство ──────────────────────────────────────────────────────────────
    "gold_collector": {
        "name":     "Гоблин-ростовщик",
        "emoji":    "💰",
        "desc":     "Заработай {n} золота суммарно",
        "tiers":    [500, 5000, 50000, 500000],
        "rewards":  [
            {"xp": 100,  "gold": 0,   "title": None},
            {"xp": 300,  "gold": 0,   "title": None},
            {"xp": 800,  "gold": 0,   "title": "Богач"},
            {"xp": 2000, "gold": 0,   "title": "Миллионер Хогвартса"},
        ],
        "stat": "gold_earned",
    },
    # ── Зельеварение ────────────────────────────────────────────────────────────
    "potion_brewer": {
        "name":     "Зельевар",
        "emoji":    "🧪",
        "desc":     "Свари {n} зелий",
        "tiers":    [5, 25, 100],
        "rewards":  [
            {"xp": 100,  "gold": 50,  "title": None},
            {"xp": 300,  "gold": 150, "title": "Зельевар"},
            {"xp": 800,  "gold": 400, "title": "Мастер зелий"},
        ],
        "stat": "potions_brewed",
    },
    # ── Комбо ────────────────────────────────────────────────────────────────
    "combo_master": {
        "name":     "Мастер комбо",
        "emoji":    "✨",
        "desc":     "Выполни {n} комбо-заклинаний",
        "tiers":    [5, 25, 100],
        "rewards":  [
            {"xp": 100,  "gold": 50,  "title": None},
            {"xp": 300,  "gold": 150, "title": "Комбинатор"},
            {"xp": 800,  "gold": 400, "title": "Мастер комбо"},
        ],
        "stat": "combo_used",
    },
    # ── Квесты ────────────────────────────────────────────────────────────────
    "quest_hero": {
        "name":     "Искатель приключений",
        "emoji":    "📜",
        "desc":     "Выполни {n} квестов",
        "tiers":    [5, 25, 100],
        "rewards":  [
            {"xp": 100,  "gold": 50,  "title": None},
            {"xp": 300,  "gold": 150, "title": None},
            {"xp": 800,  "gold": 400, "title": "Путешественник"},
        ],
        "stat": "quests_done",
    },
    # ── Особые ────────────────────────────────────────────────────────────────
    "first_steps": {
        "name":     "Первые шаги",
        "emoji":    "🎓",
        "desc":     "Зарегистрируйся в игре",
        "tiers":    [1],
        "rewards":  [{"xp": 50, "gold": 0, "title": "Первокурсник"}],
        "stat":     None,
        "one_time": True,
    },
    "first_duel": {
        "name":     "Первая дуэль",
        "emoji":    "⚔️",
        "desc":     "Проведи первую дуэль",
        "tiers":    [1],
        "rewards":  [{"xp": 100, "gold": 50, "title": None}],
        "stat":     "pvp_total",
        "one_time": True,
    },
    "first_boss": {
        "name":     "Убийца боссов",
        "emoji":    "💀",
        "desc":     "Победи первого босса",
        "tiers":    [1],
        "rewards":  [{"xp": 200, "gold": 100, "title": None}],
        "stat":     "boss_kills",
        "one_time": True,
    },
    "legendary_item": {
        "name":     "Легендарная находка",
        "emoji":    "⭐",
        "desc":     "Найди легендарный предмет",
        "tiers":    [1],
        "rewards":  [{"xp": 500, "gold": 250, "title": "Коллекционер"}],
        "stat":     None,
        "one_time": True,
        "trigger":  "legendary_item",
    },
    "reach_level_10": {
        "name":     "Подающий надежды",
        "emoji":    "🌟",
        "desc":     "Достигни 10 уровня",
        "tiers":    [1],
        "rewards":  [{"xp": 300, "gold": 150, "title": None}],
        "stat":     None,
        "one_time": True,
        "trigger":  "level_10",
    },
    "reach_level_25": {
        "name":     "Опытный волшебник",
        "emoji":    "🌟",
        "desc":     "Достигни 25 уровня",
        "tiers":    [1],
        "rewards":  [{"xp": 800, "gold": 400, "title": "Опытный волшебник"}],
        "stat":     None,
        "one_time": True,
        "trigger":  "level_25",
    },
    "reach_level_50": {
        "name":     "Мастер магии",
        "emoji":    "💫",
        "desc":     "Достигни 50 уровня",
        "tiers":    [1],
        "rewards":  [{"xp": 2000, "gold": 1000, "title": "Мастер Магии"}],
        "stat":     None,
        "one_time": True,
        "trigger":  "level_50",
    },
}

TIER_LABELS = ["I", "II", "III", "IV"]


def _tier_label(tier: int) -> str:
    return TIER_LABELS[tier - 1] if 1 <= tier <= len(TIER_LABELS) else str(tier)


async def check_achievements(user_id: int, ctx=None):
    """
    Вызывается после любого действия игрока.
    Проверяет все достижения и выдаёт новые если условие выполнено.
    """
    from database import get_user_stats
    stats  = get_user_stats(user_id)
    user   = get_user(user_id)
    if not stats or not user:
        return

    earned = {r["achievement"]: r["tier"] for r in get_user_achievements(user_id)}

    for ach_id, ach in ACHIEVEMENTS.items():
        stat_key = ach.get("stat")
        if stat_key is None:
            continue  # триггерные достижения выдаются отдельно

        current_val = stats.get(stat_key, 0) or 0
        tiers       = ach["tiers"]
        current_tier = earned.get(ach_id, 0)

        for tier_idx, threshold in enumerate(tiers):
            tier_num = tier_idx + 1
            if current_tier >= tier_num:
                continue
            if current_val >= threshold:
                await _grant_achievement(user_id, user, ach_id, ach, tier_num, ctx)
                earned[ach_id] = tier_num


async def trigger_achievement(user_id: int, trigger: str, ctx=None):
    """Выдать триггерное (одноразовое) достижение."""
    user = get_user(user_id)
    if not user:
        return
    earned = {r["achievement"] for r in get_user_achievements(user_id)}

    for ach_id, ach in ACHIEVEMENTS.items():
        if ach.get("trigger") == trigger and ach_id not in earned:
            await _grant_achievement(user_id, user, ach_id, ach, 1, ctx)


async def _grant_achievement(user_id: int, user: dict, ach_id: str, ach: dict, tier: int, ctx=None):
    """Выдать достижение и уведомить игрока."""
    unlock_achievement(user_id, ach_id, tier)
    rewards = ach["rewards"][tier - 1]

    if rewards["xp"]:
        add_xp(user_id, rewards["xp"])
    if rewards["gold"]:
        add_gold(user_id, rewards["gold"])

    # Выдать титул если есть
    if rewards.get("title"):
        with get_conn() as conn:
            execute(conn, """
                INSERT INTO user_titles (user_id, title_id)
                VALUES (%s, %s) ON CONFLICT DO NOTHING
            """, user_id, rewards["title"])

    if ctx:
        tier_label = _tier_label(tier)
        text = (
            f"🏅 *Новое достижение!*\n\n"
            f"{ach['emoji']} *{ach['name']}* — Уровень {tier_label}\n"
            f"_{ach['desc'].format(n=ach['tiers'][tier-1])}_\n\n"
            f"+{rewards['xp']} XP"
            + (f" | +{rewards['gold']} 💰" if rewards["gold"] else "")
            + (f"\n🎭 Титул: *{rewards['title']}*" if rewards.get("title") else "")
        )
        try:
            await ctx.bot.send_message(user_id, text, parse_mode="Markdown")
        except Exception:
            pass


async def cmd_achievements(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """/achievements — список достижений игрока."""
    user_id = update.effective_user.id
    if not user_exists(user_id):
        await update.message.reply_text(t(user_id, "not_registered"))
        return

    await check_achievements(user_id, ctx)

    earned   = {r["achievement"]: r["tier"] for r in get_user_achievements(user_id)}
    stats    = get_conn()

    categories = {
        "Боевые":   ["monster_slayer", "boss_hunter", "world_boss_hero", "first_boss"],
        "PvP":      ["pvp_winner", "pvp_veteran", "first_duel"],
        "Учёба":    ["lesson_master", "quest_hero"],
        "Прогресс": ["reach_level_10", "reach_level_25", "reach_level_50", "first_steps"],
        "Богатство":["gold_collector"],
        "Мастерство":["potion_brewer", "combo_master", "legendary_item"],
    }

    buttons = []
    for cat_name, ids in categories.items():
        done  = sum(1 for i in ids if i in earned)
        total = len(ids)
        buttons.append([InlineKeyboardButton(
            f"{'✅' if done == total else '📋'} {cat_name} ({done}/{total})",
            callback_data=f"ach_cat:{cat_name}"
        )])

    total_done  = len(earned)
    total_count = len(ACHIEVEMENTS)
    await update.message.reply_text(
        f"🏅 *Достижения*\n\n"
        f"Получено: {total_done}/{total_count}\n\n"
        f"Выбери категорию:",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(buttons)
    )


async def cb_ach_cat(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query    = update.callback_query
    await query.answer()
    user_id  = query.from_user.id
    cat_name = query.data.split(":", 1)[1]

    categories = {
        "Боевые":    ["monster_slayer", "boss_hunter", "world_boss_hero", "first_boss"],
        "PvP":       ["pvp_winner", "pvp_veteran", "first_duel"],
        "Учёба":     ["lesson_master", "quest_hero"],
        "Прогресс":  ["reach_level_10", "reach_level_25", "reach_level_50", "first_steps"],
        "Богатство": ["gold_collector"],
        "Мастерство":["potion_brewer", "combo_master", "legendary_item"],
    }

    ids    = categories.get(cat_name, [])
    earned = {r["achievement"]: r["tier"] for r in get_user_achievements(user_id)}
    with get_conn() as conn:
        stats_row = fetchrow(conn, "SELECT * FROM user_stats WHERE user_id = %s", user_id)
    stats = dict(stats_row) if stats_row else {}

    lines = [f"📋 *{cat_name}*\n"]
    for ach_id in ids:
        ach   = ACHIEVEMENTS.get(ach_id)
        if not ach:
            continue
        tier  = earned.get(ach_id, 0)
        tiers = ach["tiers"]
        stat  = ach.get("stat")
        cur   = stats.get(stat, 0) if stat else 0

        if tier >= len(tiers):
            status = f"✅ *{ach['name']}* — Макс. уровень"
        elif tier > 0:
            next_thresh = tiers[tier]
            status = (
                f"🔶 *{ach['name']}* [{_tier_label(tier)}]\n"
                f"   Прогресс: {cur}/{next_thresh}"
            )
        else:
            first_thresh = tiers[0]
            status = (
                f"⬜ *{ach['name']}*\n"
                f"   {ach['desc'].format(n=first_thresh)} ({cur}/{first_thresh})"
            )
        lines.append(f"{ach['emoji']} {status}")

    markup = InlineKeyboardMarkup([[
        InlineKeyboardButton("🔙 Назад", callback_data="ach_back")
    ]])
    await query.edit_message_text(
        "\n\n".join(lines),
        parse_mode="Markdown",
        reply_markup=markup
    )


async def cb_ach_back(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query   = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    earned      = {r["achievement"]: r["tier"] for r in get_user_achievements(user_id)}
    total_done  = len(earned)
    total_count = len(ACHIEVEMENTS)

    categories = {
        "Боевые":    ["monster_slayer", "boss_hunter", "world_boss_hero", "first_boss"],
        "PvP":       ["pvp_winner", "pvp_veteran", "first_duel"],
        "Учёба":     ["lesson_master", "quest_hero"],
        "Прогресс":  ["reach_level_10", "reach_level_25", "reach_level_50", "first_steps"],
        "Богатство": ["gold_collector"],
        "Мастерство":["potion_brewer", "combo_master", "legendary_item"],
    }
    buttons = []
    for cat_name, ids in categories.items():
        done  = sum(1 for i in ids if i in earned)
        total = len(ids)
        buttons.append([InlineKeyboardButton(
            f"{'✅' if done == total else '📋'} {cat_name} ({done}/{total})",
            callback_data=f"ach_cat:{cat_name}"
        )])

    await query.edit_message_text(
        f"🏅 *Достижения*\n\nПолучено: {total_done}/{total_count}\n\nВыбери категорию:",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(buttons)
    )


def register_achievements_handlers(app):
    app.add_handler(CommandHandler("achievements", cmd_achievements))
    app.add_handler(CallbackQueryHandler(cb_ach_cat,  pattern=r"^ach_cat:"))
    app.add_handler(CallbackQueryHandler(cb_ach_back, pattern=r"^ach_back$"))

