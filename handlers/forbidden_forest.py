"""
Запретный лес — исследования, события, NPC.
Ночной бонус 20:00–06:00 UTC.
"""
import logging
import random
from datetime import datetime, timezone
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler
from database import (
    get_user, user_exists, add_xp, add_gold, add_house_points,
    get_daily_limit, increment_daily, add_item_to_inventory,
    get_conn, execute, fetchrow, fetchall,
)
from utils.i18n import t
from game.items import ITEMS, item_display_name
from config import DAILY_LIMITS

logger = logging.getLogger(__name__)

FOREST_EVENTS = [
    {
        "id": "aragog_lair",
        "title": "🕷️ Логово Арагога",
        "desc": (
            "Ты слышишь тихое шуршание в темноте. Сотни глаз смотрят на тебя с деревьев. "
            "Арагог и его потомство охраняют это место."
        ),
        "min_level": 5,
        "options": ["⚔️ Вступить в бой", "🏃 Бежать", "🎵 Запеть (Рон бы не советовал)"],
        "outcomes": [
            {"xp": 150, "gold": 80,  "item": "boomslang_skin",   "qty": 2,
             "msg": "Ты победил отряд акромантулов! Нашёл кожу — ценный ингредиент для Оборотного зелья."},
            {"xp": 20,  "gold": 0,   "item": None,               "qty": 0,
             "msg": "Ты успел сбежать. Позади слышен недовольный клёкот паучьих лап."},
            {"xp": 0,   "gold": 0,   "item": None,               "qty": 0,
             "msg": "Пауки остановились и уставились на тебя. Потом медленно ушли. Странно."},
        ],
    },
    {
        "id": "centaur_meeting",
        "title": "🏹 Встреча с кентаврами",
        "desc": (
            "Перед тобой появляются три кентавра — Бейн, Ронан и Магориан. "
            "Они изучают звёзды и говорят загадками о твоей судьбе."
        ),
        "min_level": 1,
        "options": ["🌟 Попросить предсказание", "🎁 Предложить дары", "🚶 Уйти с уважением"],
        "outcomes": [
            {"xp": 60,  "gold": 0,  "item": "phoenix_feather", "qty": 1,
             "msg": "Кентавр видит в звёздах твою победу и дарит перо феникса — знак судьбы."},
            {"xp": 80,  "gold": 50, "item": None,              "qty": 0,
             "msg": "Кентавры приняли дары и открыли тебе тайную тропу с ингредиентами."},
            {"xp": 30,  "gold": 0,  "item": None,              "qty": 0,
             "msg": "Кентавры кивнули и скрылись в лесу. Уважение важно."},
        ],
    },
    {
        "id": "unicorn_grove",
        "title": "🦄 Роща единорогов",
        "desc": (
            "Ты вышел на поляну, залитую серебристым светом. "
            "Молодой единорог осторожно приближается к тебе."
        ),
        "min_level": 1,
        "options": ["🤲 Протянуть руку", "📸 Наблюдать издали", "🩸 Собрать кровь (тёмный путь)"],
        "outcomes": [
            {"xp": 120, "gold": 0,   "item": "dragon_heartstring", "qty": 1,
             "msg": "Единорог доверяет тебе и оставляет волос из гривы — редкий ингредиент."},
            {"xp": 50,  "gold": 30,  "item": None,                 "qty": 0,
             "msg": "Ты наблюдал за единорогом. Это незабываемо. +30 золота за зарисовки для Хагрида."},
            {"xp": 200, "gold": 100, "item": "felix_felicis",       "qty": 1,
             "msg": "⚠️ Тёмный путь принёс тебе редкое зелье удачи. Но цена высока."},
        ],
    },
    {
        "id": "hagrid_hut",
        "title": "🏠 Хижина Хагрида",
        "desc": (
            "Тропинка выводит тебя к знакомой каменной хижине. "
            "Хагрид выглядывает из окна с кружкой чая."
        ),
        "min_level": 1,
        "options": ["☕ Зайти на чай", "📦 Помочь с животными", "📚 Спросить о лесе"],
        "outcomes": [
            {"xp": 40,  "gold": 60, "item": "lacewing_flies",    "qty": 3,
             "msg": "Хагрид угостил тебя чаем и дал крылатых жуков для зельеварения."},
            {"xp": 100, "gold": 40, "item": None,                "qty": 0,
             "msg": "Ты помог Хагриду покормить нарвала. Он растроган и дал золото."},
            {"xp": 70,  "gold": 0,  "item": "flobberworm_mucus", "qty": 2,
             "msg": "Хагрид рассказал о тайных тропах и дал слизь флаббервурма."},
        ],
    },
    {
        "id": "dark_creature",
        "title": "🌑 Тёмное существо",
        "desc": (
            "Что-то огромное движется между деревьями. "
            "Не акромантул, не единорог — что-то, чего нет в учебниках Хагрида."
        ),
        "min_level": 8,
        "options": ["⚔️ Атаковать первым", "🔮 Применить заклинание", "🕯️ Зажечь Люмос"],
        "outcomes": [
            {"xp": 200, "gold": 120, "item": "dragon_blood",        "qty": 1,
             "msg": "Это был молодой дракон! Ты победил его и нашёл кровь дракона."},
            {"xp": 150, "gold": 80,  "item": "basilisk_fang",       "qty": 1,
             "msg": "Заклинание ударило точно. Существо скрылось, оставив редкий трофей."},
            {"xp": 80,  "gold": 40,  "item": None,                  "qty": 0,
             "msg": "Свет Люмос испугал существо. Оно убежало, но уронило мешок с золотом."},
        ],
    },
    {
        "id": "potion_ingredients",
        "title": "🌿 Поляна ингредиентов",
        "desc": (
            "Ты наткнулся на нетронутую поляну с редкими магическими растениями. "
            "Снейп заплатил бы за это состояние."
        ),
        "min_level": 1,
        "options": ["🌱 Собрать всё", "🎯 Выбрать лучшее", "📝 Записать местонахождение"],
        "outcomes": [
            {"xp": 60, "gold": 0,  "item": "mandrake_root", "qty": 2,
             "msg": "Ты набрал корней мандрагоры. Осторожно — они кусаются!"},
            {"xp": 80, "gold": 0,  "item": "bezoar",        "qty": 1,
             "msg": "Ты нашёл безоар среди растений — редкая удача!"},
            {"xp": 50, "gold": 80, "item": None,            "qty": 0,
             "msg": "Координаты поляны стоят дорого. Апотекарь в Хогсмиде хорошо заплатил."},
        ],
    },
    {
        "id": "hidden_treasure",
        "title": "💰 Тайный клад",
        "desc": (
            "Под старым дубом ты заметил необычный камень. "
            "Под ним — заржавевшая шкатулка с магическими артефактами."
        ),
        "min_level": 3,
        "options": ["🔓 Вскрыть заклинанием", "🪓 Открыть силой", "📖 Изучить надписи"],
        "outcomes": [
            {"xp": 100, "gold": 150, "item": "polyjuice_ready", "qty": 1,
             "msg": "Заклинание сработало! Внутри — золото и готовое оборотное зелье."},
            {"xp": 60,  "gold": 200, "item": None,              "qty": 0,
             "msg": "Сила помогла! Шкатулка открылась. Внутри много золота."},
            {"xp": 150, "gold": 50,  "item": "dark_arts_tome",  "qty": 1,
             "msg": "Надписи указали на скрытый отдел — там оказалась запрещённая книга!"},
        ],
    },
    {
        "id": "night_special",
        "title": "🌙 Ночная встреча",
        "desc": (
            "В полночь лес оживает иначе. Призрачные огни мерцают меж деревьев. "
            "Только самые смелые ходят здесь ночью."
        ),
        "min_level": 3,
        "night_only": True,
        "options": ["👻 Идти на огни", "🔥 Разжечь костёр", "🏃 Уйти домой"],
        "outcomes": [
            {"xp": 250, "gold": 150, "item": "gillyweed", "qty": 2,
             "msg": "Огни привели к магическому источнику! Жабья трава здесь особенно сильна."},
            {"xp": 80,  "gold": 50,  "item": None,       "qty": 0,
             "msg": "Костёр отпугнул тёмных существ. Ночь прошла спокойно."},
            {"xp": 30,  "gold": 0,   "item": None,       "qty": 0,
             "msg": "Мудрое решение. Ночной лес не для новичков."},
        ],
    },
]

NIGHT_BONUS = 1.5

def _is_night() -> bool:
    h = datetime.now(timezone.utc).hour
    return h >= 20 or h < 6

def _get_available_events(user_level: int) -> list:
    now_is_night = _is_night()
    result = []
    for ev in FOREST_EVENTS:
        if ev.get("night_only") and not now_is_night:
            continue
        if ev.get("min_level", 1) > user_level:
            continue
        result.append(ev)
    return result if result else FOREST_EVENTS[:3]

def _forest_keyboard(events: list) -> InlineKeyboardMarkup:
    buttons = [[InlineKeyboardButton(e["title"], callback_data=f"ff_event:{e['id']}")] for e in events[:5]]
    buttons.append([InlineKeyboardButton("📊 Статистика леса", callback_data="ff_stats")])
    return InlineKeyboardMarkup(buttons)

def _event_keyboard(event: dict) -> InlineKeyboardMarkup:
    """Клавиатура вариантов — каждая кнопка на отдельной строке для читаемости."""
    buttons = []
    for i, opt in enumerate(event["options"]):
        buttons.append([InlineKeyboardButton(opt, callback_data=f"ff_choice:{event['id']}:{i}")])
    buttons.append([InlineKeyboardButton("◀️ Назад", callback_data="ff_back")])
    return InlineKeyboardMarkup(buttons)

async def cmd_forest(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not user_exists(user_id):
        await update.message.reply_text(t(user_id, "not_registered"))
        return

    used  = get_daily_limit(user_id, "forest")
    limit = DAILY_LIMITS.get("forest", 5)
    if used >= limit:
        await update.message.reply_text(
            f"🌲 *Запретный лес*\n\n"
            f"Ты слишком устал для дальнейших вылазок сегодня ({used}/{limit}).\n"
            f"Возвращайся завтра!",
            parse_mode="Markdown"
        )
        return

    user   = get_user(user_id)
    events = _get_available_events(user["level"])
    night  = _is_night()
    night_str = "🌙 *Ночь — бонус ×1.5 к наградам!*\n\n" if night else ""

    await update.message.reply_text(
        f"🌲 *Запретный лес*\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"{night_str}"
        f"Тёмный, опасный, полный тайн лес у стен Хогвартса.\n"
        f"Только смелые находят здесь сокровища.\n\n"
        f"Вылазок сегодня: {used}/{limit}\n\n"
        f"Выбери событие:",
        parse_mode="Markdown",
        reply_markup=_forest_keyboard(events)
    )

async def cb_ff_event(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query    = update.callback_query
    await query.answer()
    user_id  = query.from_user.id
    event_id = query.data.split(":")[1]

    event = next((e for e in FOREST_EVENTS if e["id"] == event_id), None)
    if not event:
        await query.edit_message_text("❌ Событие не найдено.")
        return

    used  = get_daily_limit(user_id, "forest")
    limit = DAILY_LIMITS.get("forest", 5)
    if used >= limit:
        await query.edit_message_text(f"🌲 Лимит вылазок на сегодня исчерпан ({used}/{limit}).")
        return

    night_note = "\n🌙 _Ночной бонус активен!_" if _is_night() else ""
    await query.edit_message_text(
        f"{event['title']}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"{event['desc']}{night_note}\n\n"
        f"Что ты делаешь?",
        parse_mode="Markdown",
        reply_markup=_event_keyboard(event)
    )

async def cb_ff_choice(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query    = update.callback_query
    await query.answer()          # ← обязательно первым, иначе Telegram «завис»
    user_id  = query.from_user.id
    parts    = query.data.split(":")
    event_id = parts[1]
    choice   = int(parts[2])

    event = next((e for e in FOREST_EVENTS if e["id"] == event_id), None)
    if not event or choice >= len(event["outcomes"]):
        await query.edit_message_text("❌ Ошибка: событие не найдено.")
        return

    used  = get_daily_limit(user_id, "forest")
    limit = DAILY_LIMITS.get("forest", 5)
    if used >= limit:
        await query.edit_message_text(
            f"🌲 Лимит вылазок на сегодня исчерпан ({used}/{limit}).\n"
            f"Возвращайся завтра!"
        )
        return

    outcome = event["outcomes"][choice]
    night   = _is_night()
    mult    = NIGHT_BONUS if night else 1.0

    xp   = int(outcome.get("xp",   0) * mult)
    gold = int(outcome.get("gold", 0) * mult)
    item = outcome.get("item")   # может быть None
    qty  = outcome.get("qty",  1)
    msg  = outcome.get("msg",  "Хорошая работа!")

    # Начисляем награды — каждый шаг в try/except чтобы одна ошибка не ломала всё
    try:
        if xp:   add_xp(user_id, xp)
    except Exception as e:
        logger.error("forest add_xp: %s", e)

    try:
        if gold: add_gold(user_id, gold)
    except Exception as e:
        logger.error("forest add_gold: %s", e)

    try:
        if item and qty > 0:
            add_item_to_inventory(user_id, item, qty)
    except Exception as e:
        logger.error("forest add_item %s: %s", item, e)
        item = None  # не показываем предмет в наградах если не удалось добавить

    try:
        user = get_user(user_id)
        if user and user.get("house") and xp > 0:
            add_house_points(user_id, user["house"], max(1, xp // 10), "forest")
    except Exception as e:
        logger.error("forest house_points: %s", e)

    try:
        increment_daily(user_id, "forest")
    except Exception as e:
        logger.error("forest increment_daily: %s", e)

    # Журнал
    try:
        with get_conn() as conn:
            execute(conn, """
                INSERT INTO player_journal
                    (user_id, event_type, title, description, xp_gained, gold_gained, item_gained)
                VALUES (%s, 'forest', %s, %s, %s, %s, %s)
            """, user_id, event["title"], msg, xp, gold, item or "")
    except Exception:
        pass

    # Обновляем счётчик после increment
    try:
        used_now  = get_daily_limit(user_id, "forest")
        remaining = limit - used_now
    except Exception:
        remaining = 0

    rewards = []
    if xp:   rewards.append(f"+{xp} XP")
    if gold: rewards.append(f"+{gold} 💰")
    if item and qty > 0:
        _item_data = ITEMS.get(item, {})
        _item_name = item_display_name(_item_data, "ru") if _item_data else item
        _item_emoji = _item_data.get("emoji", "📦")
        rewards.append(f"+{qty}× {_item_emoji} {_item_name}")
    reward_str = "  •  ".join(rewards) if rewards else "Без наград"
    night_str  = "\n🌙 _Ночной бонус ×1.5 применён_" if night else ""

    markup = None
    if remaining > 0:
        markup = InlineKeyboardMarkup([[
            InlineKeyboardButton("🌲 Ещё одна вылазка", callback_data="ff_back")
        ]])

    await query.edit_message_text(
        f"🌲 *{event['title']}*\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"{msg}\n\n"
        f"🎁 {reward_str}{night_str}\n\n"
        f"Осталось вылазок: {remaining}/{limit}",
        parse_mode="Markdown",
        reply_markup=markup,
    )

async def cb_ff_back(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query   = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    used   = get_daily_limit(user_id, "forest")
    limit  = DAILY_LIMITS.get("forest", 5)
    user   = get_user(user_id)
    events = _get_available_events(user["level"])
    night  = _is_night()
    night_str = "🌙 *Ночной бонус ×1.5 активен!*\n\n" if night else ""

    await query.edit_message_text(
        f"🌲 *Запретный лес*\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"{night_str}"
        f"Вылазок сегодня: {used}/{limit}\n\n"
        f"Выбери событие:",
        parse_mode="Markdown",
        reply_markup=_forest_keyboard(events),
    )

async def cb_ff_stats(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query   = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    cnt, xp_sum, gold_sum = 0, 0, 0
    try:
        with get_conn() as conn:
            row = fetchrow(conn,
                "SELECT COUNT(*) as cnt, COALESCE(SUM(xp_gained),0) as xp, "
                "COALESCE(SUM(gold_gained),0) as gold "
                "FROM player_journal WHERE user_id=%s AND event_type='forest'",
                user_id)
        if row:
            cnt      = row["cnt"]
            xp_sum   = row["xp"]
            gold_sum = row["gold"]
    except Exception:
        pass

    await query.edit_message_text(
        f"📊 *Статистика — Запретный лес*\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🌲 Вылазок всего: {cnt}\n"
        f"✨ Опыта получено: {xp_sum}\n"
        f"💰 Золота найдено: {gold_sum}",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("◀️ Назад в лес", callback_data="ff_back")
        ]])
    )

def register_forest_handlers(app):
    app.add_handler(CommandHandler("forest", cmd_forest))
    app.add_handler(CallbackQueryHandler(cb_ff_event,  pattern=r"^ff_event:"))
    app.add_handler(CallbackQueryHandler(cb_ff_choice, pattern=r"^ff_choice:"))
    app.add_handler(CallbackQueryHandler(cb_ff_back,   pattern=r"^ff_back$"))
    app.add_handler(CallbackQueryHandler(cb_ff_stats,  pattern=r"^ff_stats$"))
