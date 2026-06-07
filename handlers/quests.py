"""
Quests handler — TZ section 8.3.
Story (once), daily (3 random from pool of 30), weekly (1).
"""
import logging
import random
from datetime import date
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler, MessageHandler, filters
from database import (
    get_user, user_exists, get_daily_limit, increment_daily,
    add_xp, add_gold, get_conn, execute, fetchrow, fetchall,
)
from utils.i18n import t
from game.quests_data import QUESTS, daily_quest_pool, story_quest_ids, get_weekly_quest
from config import DAILY_LIMITS

logger = logging.getLogger(__name__)

DAILY_QUEST_COUNT = 3


def _get_user_completed_stories(user_id: int) -> set:
    with get_conn() as conn:
        rows = fetchall(conn,
            "SELECT quest_id FROM user_quests WHERE user_id=%s AND status='done'", user_id)
    return {r["quest_id"] for r in rows}


def _get_today_daily_quests(user_id: int) -> list[dict]:
    """Return today's 3 daily quests — seeded by user_id + date for consistency."""
    pool = daily_quest_pool()
    seed = hash(f"{user_id}_{date.today().isoformat()}")
    rng  = random.Random(seed)
    chosen = rng.sample(pool, min(DAILY_QUEST_COUNT, len(pool)))
    return [QUESTS[qid] for qid in chosen]


def _get_active_quest(user_id: int, quest_id: str) -> dict | None:
    with get_conn() as conn:
        return fetchrow(conn,
            "SELECT * FROM user_quests WHERE user_id=%s AND quest_id=%s AND status='active'",
            user_id, quest_id)


def _quest_display_name(quest: dict, lang: str = "ru") -> str:
    name = quest.get("name", {})
    return name.get(lang, name.get("en", quest["id"]))


def _quests_keyboard(quests: list[dict], user_id: int, completed: set) -> InlineKeyboardMarkup:
    buttons = []
    for quest in quests:
        qid  = quest["id"]
        name = _quest_display_name(quest, "ru")
        if qid in completed:
            label = f"✅ {name}"
        else:
            active = _get_active_quest(user_id, qid)
            label  = f"▶️ {name}" if active else f"📜 {name}"
        buttons.append([InlineKeyboardButton(label, callback_data=f"quest_open:{qid}")])
    return InlineKeyboardMarkup(buttons)


async def cmd_quests(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not user_exists(user_id):
        await update.message.reply_text(t(user_id, "not_registered"))
        return

    completed = _get_user_completed_stories(user_id)

    # Story quests
    story_quests   = [QUESTS[qid] for qid in story_quest_ids()]
    daily_quests   = _get_today_daily_quests(user_id)
    weekly_quest   = get_weekly_quest()

    markup_story  = _quests_keyboard(story_quests,  user_id, completed)
    markup_daily  = _quests_keyboard(daily_quests,  user_id, completed)
    markup_weekly = _quests_keyboard([weekly_quest], user_id, completed)

    used_quests = get_daily_limit(user_id, "pve_quests")
    await update.message.reply_text(
        f"📜 *Квесты*\n━━━━━━━━━━━━━━━━━━━━\n"
        f"Выполнено сегодня: {used_quests}/{DAILY_LIMITS['pve_quests']}\n\n"
        f"*📖 Сюжетные:*",
        parse_mode="Markdown",
        reply_markup=markup_story,
    )
    await update.message.reply_text("*📅 Ежедневные:*", parse_mode="Markdown", reply_markup=markup_daily)
    await update.message.reply_text("*📆 Еженедельный:*", parse_mode="Markdown", reply_markup=markup_weekly)


async def cb_quest_open(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query   = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    qid     = query.data.split(":")[1]

    quest = QUESTS.get(qid)
    if not quest:
        await query.edit_message_text("❌ Квест не найден.")
        return

    completed = _get_user_completed_stories(user_id)
    if qid in completed and not quest.get("repeatable"):
        await query.edit_message_text(
            f"✅ Квест *{_quest_display_name(quest)}* уже пройден!",
            parse_mode="Markdown"
        )
        return

    # Check daily limit for non-story quests
    if quest["type"] != "story":
        used = get_daily_limit(user_id, "pve_quests")
        if used >= DAILY_LIMITS["pve_quests"]:
            await query.edit_message_text(t(user_id, "daily_limit_reached"))
            return

    # Start or resume quest
    active = _get_active_quest(user_id, qid)
    if not active:
        with get_conn() as conn:
            execute(conn,
                "INSERT INTO user_quests (user_id, quest_id, step, status) VALUES (%s,%s,0,'active')",
                user_id, qid)
        step = 0
    else:
        step = active["step"]

    steps = quest.get("steps", [])
    if not steps:
        # Quest with no steps (story quests 6-10 simplified)
        await _complete_quest(query, user_id, quest)
        return

    await _show_quest_step(query, user_id, quest, step)


async def _show_quest_step(query, user_id: int, quest: dict, step: int):
    steps = quest.get("steps", [])
    if step >= len(steps):
        await _complete_quest(query, user_id, quest)
        return

    step_data = steps[step]
    text = step_data["text"].get("ru", step_data["text"].get("en", ""))
    choices = step_data.get("choices", [])

    buttons = []
    for i, choice in enumerate(choices):
        label = choice["text"].get("ru", choice["text"].get("en", f"Вариант {i+1}"))
        buttons.append([InlineKeyboardButton(
            label, callback_data=f"quest_choice:{quest['id']}:{step}:{i}"
        )])

    name = _quest_display_name(quest)
    await query.edit_message_text(
        f"📜 *{name}*\n━━━━━━━━━━━━━━━━━━━━\n{text}",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(buttons),
    )


async def cb_quest_choice(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query   = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    parts   = query.data.split(":")
    qid, step_s, choice_s = parts[1], int(parts[2]), int(parts[3])

    quest = QUESTS.get(qid)
    if not quest:
        await query.edit_message_text("❌")
        return

    steps  = quest.get("steps", [])
    if step_s >= len(steps):
        await _complete_quest(query, user_id, quest)
        return

    step_data = steps[step_s]
    choices   = step_data.get("choices", [])
    if choice_s >= len(choices):
        return

    chosen = choices[choice_s]
    bonus  = chosen.get("bonus")
    next_step = chosen.get("next")

    # Apply step bonus
    if bonus:
        await _apply_quest_bonus(user_id, bonus)

    if next_step == "end" or next_step is None:
        await _complete_quest(query, user_id, quest)
        return

    # Advance step
    new_step = next_step
    with get_conn() as conn:
        execute(conn,
            "UPDATE user_quests SET step=%s WHERE user_id=%s AND quest_id=%s AND status='active'",
            new_step, user_id, qid)

    await _show_quest_step(query, user_id, quest, new_step)


async def _apply_quest_bonus(user_id: int, bonus: str):
    if bonus.startswith("xp_"):
        xp = int(bonus.split("_")[1])
        add_xp(user_id, xp)
    elif bonus.startswith("gold_"):
        gold = int(bonus.split("_")[1])
        add_gold(user_id, gold)
    elif bonus == "spell_random":
        from game.drop_system import roll_spell_drop
        spell_id = roll_spell_drop(min_rarity="uncommon")
        if spell_id:
            with get_conn() as conn:
                execute(conn,
                    "INSERT INTO user_spells (user_id, spell_id) VALUES (%s,%s) ON CONFLICT DO NOTHING",
                    user_id, spell_id)
    elif bonus == "item_potion":
        with get_conn() as conn:
            execute(conn,
                "INSERT INTO inventory (user_id, item_id) VALUES (%s,'hp_potion_medium')", user_id)


async def _complete_quest(query, user_id: int, quest: dict):
    qid    = quest["id"]
    reward = quest.get("final_reward", {})
    xp     = reward.get("xp", 50)
    gold   = reward.get("gold", 20)

    add_xp(user_id, xp)
    add_gold(user_id, gold)

    with get_conn() as conn:
        execute(conn,
            "UPDATE user_quests SET status='done', completed_at=NOW() WHERE user_id=%s AND quest_id=%s",
            user_id, qid)

    if quest["type"] != "story":
        increment_daily(user_id, "pve_quests")

    # House points per quest
    with get_conn() as conn:
        execute(conn,
            "UPDATE house_points SET points=points+3 WHERE house=(SELECT house FROM users WHERE user_id=%s)",
            user_id)

    name = _quest_display_name(quest)
    await query.edit_message_text(
        f"🏆 *Квест завершён: {name}*\n+{xp} XP  +{gold} 💰  +3 очка факультету",
        parse_mode="Markdown",
    )


async def handle_quest_button(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if update.message.text == t(user_id, "btn_quests"):
        await cmd_quests(update, ctx)


def register_quests_handlers(app):
    app.add_handler(CommandHandler("quests", cmd_quests))
    app.add_handler(CallbackQueryHandler(cb_quest_open,   pattern=r"^quest_open:"))
    app.add_handler(CallbackQueryHandler(cb_quest_choice, pattern=r"^quest_choice:"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_quest_button), group=10)
