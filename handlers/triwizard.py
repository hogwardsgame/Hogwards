"""
Турнир Трёх Волшебников — сезонное событие.
3 испытания: Дракон, Озеро, Лабиринт.
Участвуют добровольцы от каждого факультета.
"""
import logging, random
from datetime import datetime, timezone
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler
from database import (
    get_user, user_exists, add_xp, add_gold, add_house_points,
    get_conn, execute, fetchrow, fetchall,
)
from utils.i18n import t

logger = logging.getLogger(__name__)

TRIALS = [
    {
        "id": "dragon",
        "name": "🐉 Испытание первое: Дракон",
        "desc": "Вырви золотое яйцо у шведского короткорыла. Дракон не рад гостям.",
        "min_level": 5,
        "options": ["⚔️ Атаковать напрямую", "🧙 Отвлечь заклинанием", "🏃 Схитрить и обойти"],
        "outcomes": [
            {"xp": 300, "gold": 200, "score": 40, "msg": "Смелость! Ты вырвал яйцо, получив несколько ожогов."},
            {"xp": 400, "gold": 150, "score": 47, "msg": "Мастерство! Дракон смотрел на иллюзию пока ты взял яйцо."},
            {"xp": 350, "gold": 180, "score": 45, "msg": "Хитрость! Ты обошёл дракона сзади."},
        ],
    },
    {
        "id": "lake",
        "name": "🌊 Испытание второе: Чёрное озеро",
        "desc": "Спасти то, что дорого всего, со дна Чёрного озера. Гриндилоу стерегут путь.",
        "min_level": 8,
        "options": ["🐟 Выпить Жаберную траву", "🧊 Заморозить озеро", "🤿 Использовать Акваментий"],
        "outcomes": [
            {"xp": 450, "gold": 250, "score": 46, "msg": "Жабья трава подействовала! Ты дышал под водой целый час."},
            {"xp": 350, "gold": 200, "score": 38, "msg": "Лёд сковал часть озера. Медленно, но ты добрался."},
            {"xp": 500, "gold": 300, "score": 50, "msg": "Блестяще! Ты проплыл быстрее всех участников."},
        ],
    },
    {
        "id": "maze",
        "name": "🌀 Испытание третье: Лабиринт",
        "desc": "Добраться до Кубка Огня в центре живого лабиринта. Кто знает что скрывается внутри.",
        "min_level": 12,
        "options": ["🗺️ Идти по правой стене", "👁️ Использовать Окулюс Репаро", "⚡ Пробиться силой"],
        "outcomes": [
            {"xp": 500, "gold": 300, "score": 45, "msg": "Старый метод сработал! Ты вышел к Кубку."},
            {"xp": 600, "gold": 350, "score": 49, "msg": "Острое зрение помогло! Ты видел сквозь иллюзии."},
            {"xp": 550, "gold": 320, "score": 47, "msg": "Чистая магическая мощь проложила путь!"},
        ],
    },
]

TRIAL_MAP = {t["id"]: t for t in TRIALS}

def _ensure_triwizard_tables():
    try:
        with get_conn() as conn:
            execute(conn, """
                CREATE TABLE IF NOT EXISTS triwizard_participants (
                    user_id      BIGINT PRIMARY KEY,
                    total_score  INT DEFAULT 0,
                    trial1_done  BOOLEAN DEFAULT FALSE,
                    trial2_done  BOOLEAN DEFAULT FALSE,
                    trial3_done  BOOLEAN DEFAULT FALSE,
                    registered_at TIMESTAMPTZ DEFAULT NOW()
                )
            """)
    except Exception as e:
        logger.warning("triwizard table: %s", e)

def _get_participant(user_id: int) -> dict | None:
    try:
        with get_conn() as conn:
            return fetchrow(conn, "SELECT * FROM triwizard_participants WHERE user_id=%s", user_id)
    except Exception:
        return None

def _leaderboard_text() -> str:
    try:
        with get_conn() as conn:
            rows = fetchall(conn, """
                SELECT u.wizard_name, u.house, tp.total_score,
                       tp.trial1_done, tp.trial2_done, tp.trial3_done
                FROM triwizard_participants tp
                JOIN users u ON u.user_id = tp.user_id
                ORDER BY tp.total_score DESC LIMIT 10
            """)
    except Exception:
        return "_Нет участников пока._"
    if not rows:
        return "_Нет участников пока._"
    medals = ["🥇","🥈","🥉"] + [f"{i}." for i in range(4, 11)]
    lines  = []
    for i, r in enumerate(rows):
        done = sum([r["trial1_done"], r["trial2_done"], r["trial3_done"]])
        lines.append(f"{medals[i]} {r['wizard_name']} — {r['total_score']} очков ({done}/3 испытания)")
    return "\n".join(lines)

async def cmd_triwizard(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not user_exists(user_id):
        await update.message.reply_text(t(user_id, "not_registered"))
        return
    _ensure_triwizard_tables()
    participant = _get_participant(user_id)
    user = get_user(user_id)

    lb = _leaderboard_text()
    if not participant:
        text = (
            f"🏆 *Турнир Трёх Волшебников*\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"Легендарный турнир школ магии.\n"
            f"Три испытания: Дракон, Озеро, Лабиринт.\n\n"
            f"🥇 *Таблица лидеров:*\n{lb}\n\n"
            f"Вступай и пройди все три испытания!"
        )
        markup = InlineKeyboardMarkup([[InlineKeyboardButton("📜 Вступить в турнир", callback_data="tw_register")]])
    else:
        done_flags = [participant["trial1_done"], participant["trial2_done"], participant["trial3_done"]]
        done_count = sum(done_flags)
        text = (
            f"🏆 *Турнир Трёх Волшебников*\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"👤 Участник: {user['wizard_name']}\n"
            f"⭐ Твои очки: {participant['total_score']}\n"
            f"📊 Испытаний пройдено: {done_count}/3\n\n"
            f"🐉 Дракон: {'✅' if participant['trial1_done'] else '❌'}\n"
            f"🌊 Озеро:  {'✅' if participant['trial2_done'] else '❌'}\n"
            f"🌀 Лабиринт: {'✅' if participant['trial3_done'] else '❌'}\n\n"
            f"🥇 *Таблица лидеров:*\n{lb}"
        )
        buttons = []
        for i, trial in enumerate(TRIALS):
            done = done_flags[i]
            if not done:
                req = user["level"] >= trial["min_level"]
                min_lvl = trial["min_level"]
                label = f"{'🔓' if req else f'🔒 ур.{min_lvl}'} {trial['name']}"
                buttons.append([InlineKeyboardButton(label, callback_data=f"tw_trial:{trial['id']}")])
        markup = InlineKeyboardMarkup(buttons) if buttons else None

    await update.message.reply_text(text, parse_mode="Markdown", reply_markup=markup)

async def cb_tw_register(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    _ensure_triwizard_tables()
    existing = _get_participant(user_id)
    if existing:
        await query.answer("Ты уже участник!", show_alert=True)
        return
    with get_conn() as conn:
        execute(conn, "INSERT INTO triwizard_participants (user_id) VALUES (%s) ON CONFLICT DO NOTHING", user_id)
    await query.answer("✅ Ты вступил в Турнир Трёх Волшебников!", show_alert=True)
    await cmd_triwizard(update, ctx)

async def cb_tw_trial(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query    = update.callback_query
    await query.answer()
    user_id  = query.from_user.id
    trial_id = query.data.split(":")[1]
    _ensure_triwizard_tables()

    trial = TRIAL_MAP.get(trial_id)
    if not trial:
        await query.edit_message_text("❌ Испытание не найдено.")
        return

    participant = _get_participant(user_id)
    if not participant:
        await query.answer("Сначала вступи в турнир!", show_alert=True)
        return

    trial_field = f"trial{TRIALS.index(trial)+1}_done"
    if participant.get(trial_field):
        await query.answer("Ты уже прошёл это испытание!", show_alert=True)
        return

    user = get_user(user_id)
    if user["level"] < trial["min_level"]:
        await query.answer(f"Нужен уровень {trial['min_level']}!", show_alert=True)
        return

    markup = InlineKeyboardMarkup([
        [InlineKeyboardButton(opt, callback_data=f"tw_choice:{trial_id}:{i}")]
        for i, opt in enumerate(trial["options"])
    ])
    await query.edit_message_text(
        f"{trial['name']}\n━━━━━━━━━━━━━━━━━━━━\n{trial['desc']}\n\nВыбери подход:",
        parse_mode="Markdown", reply_markup=markup
    )

async def cb_tw_choice(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query    = update.callback_query
    user_id  = query.from_user.id
    parts    = query.data.split(":")
    trial_id = parts[1]
    choice   = int(parts[2])
    _ensure_triwizard_tables()

    trial       = TRIAL_MAP.get(trial_id)
    participant = _get_participant(user_id)
    if not trial or not participant:
        await query.answer("❌ Ошибка.", show_alert=True)
        return

    trial_idx   = TRIALS.index(trial)
    trial_field = f"trial{trial_idx+1}_done"
    if participant.get(trial_field):
        await query.answer("Уже пройдено!", show_alert=True)
        return

    outcome = trial["outcomes"][choice]
    add_xp(user_id, outcome["xp"])
    add_gold(user_id, outcome["gold"])

    with get_conn() as conn:
        execute(conn, f"UPDATE triwizard_participants SET {trial_field}=TRUE, total_score=total_score+%s WHERE user_id=%s",
                outcome["score"], user_id)

    try:
        with get_conn() as conn:
            execute(conn, """
                INSERT INTO player_journal (user_id, event_type, title, description, xp_gained, gold_gained)
                VALUES (%s,'triwizard',%s,%s,%s,%s)
            """, user_id, trial["name"], outcome["msg"], outcome["xp"], outcome["gold"])
    except Exception:
        pass

    participant_fresh = _get_participant(user_id)
    all_done = all([participant_fresh["trial1_done"], participant_fresh["trial2_done"], participant_fresh["trial3_done"]])

    text = (
        f"🏆 *{trial['name']}*\n\n"
        f"{outcome['msg']}\n\n"
        f"🎁 +{outcome['xp']} XP | +{outcome['gold']} 💰 | +{outcome['score']} очков турнира"
    )
    if all_done:
        text += f"\n\n🎉 *Ты прошёл все три испытания!*\nИтого очков: {participant_fresh['total_score']}"

    await query.edit_message_text(text, parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ К турниру", callback_data="tw_back")]]))

async def cb_tw_back(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await cmd_triwizard(update, ctx)

def register_triwizard_handlers(app):
    app.add_handler(CommandHandler("triwizard", cmd_triwizard))
    app.add_handler(CallbackQueryHandler(cb_tw_register, pattern=r"^tw_register$"))
    app.add_handler(CallbackQueryHandler(cb_tw_trial,    pattern=r"^tw_trial:"))
    app.add_handler(CallbackQueryHandler(cb_tw_choice,   pattern=r"^tw_choice:"))
    app.add_handler(CallbackQueryHandler(cb_tw_back,     pattern=r"^tw_back$"))
