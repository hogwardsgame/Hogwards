"""
Комната Требований — ежедневные события.
Типы событий: загадка, поиск предметов, мини-квест, встреча с существом.
Один раз в день. Награды зависят от типа события.
"""
import logging
import random
from datetime import date
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler
from database import (
    get_user, user_exists, get_daily_limit, increment_daily,
    add_xp, add_gold, add_house_points, get_conn, execute, fetchrow,
)
from utils.i18n import t
from config import DAILY_LIMITS, XP_REWARDS, GOLD_REWARDS

logger = logging.getLogger(__name__)

# ── Банк загадок ──────────────────────────────────────────────────────────────
RIDDLES = [
    {
        "text": "Меня нельзя взять в руки, но можно потерять. Меня нельзя купить, но можно заслужить. Что я такое?",
        "options": ["Доверие", "Слава", "Время", "Знание"],
        "answer": 0,
        "xp": 60, "gold": 30,
    },
    {
        "text": "У меня нет рта, но я говорю. Нет ног, но я иду вперёд. Что я такое?",
        "options": ["Время", "Ветер", "Вода", "Тень"],
        "answer": 0,
        "xp": 50, "gold": 25,
    },
    {
        "text": "Чем больше берёшь, тем больше становится. Что это?",
        "options": ["Яма", "Долг", "Знание", "Возраст"],
        "answer": 0,
        "xp": 45, "gold": 20,
    },
    {
        "text": "Какое заклинание нельзя остановить ни одним Протего?",
        "options": ["Авада Кедавра", "Сектумсемпра", "Фиендфайр", "Крусиатус"],
        "answer": 0,
        "xp": 70, "gold": 35,
    },
    {
        "text": "Что общего у дементора и дроздрозника?",
        "options": [
            "Оба питаются счастьем",
            "Оба обитают в болотах",
            "Оба боятся огня",
            "Оба относятся к бестиям",
        ],
        "answer": 0,
        "xp": 55, "gold": 28,
    },
    {
        "text": "Сколько вращений нужно сделать палочкой для заклинания Акцио?",
        "options": ["Одно", "Два", "Три", "Ни одного — движение прямое"],
        "answer": 3,
        "xp": 65, "gold": 32,
    },
    {
        "text": "Один из Даров Смерти. Делает тебя невидимым. Что это?",
        "options": ["Мантия-невидимка", "Кольцо с Воскрешающим камнем", "Бузинная палочка", "Шапка-невидимка"],
        "answer": 0,
        "xp": 50, "gold": 25,
    },
    {
        "text": "Какое существо можно убить только взглядом петуха?",
        "options": ["Василиск", "Дементор", "Акромантул", "Гиппогриф"],
        "answer": 0,
        "xp": 55, "gold": 28,
    },
    {
        "text": "Какой факультет Хогвартса основан в честь смелости?",
        "options": ["Гриффиндор", "Слизерин", "Когтевран", "Пуффендуй"],
        "answer": 0,
        "xp": 40, "gold": 20,
    },
    {
        "text": "Из чего сделана сердцевина палочки Гарри Поттера?",
        "options": [
            "Перо феникса",
            "Волос единорога",
            "Сердцевина дракона",
            "Волос фестрала",
        ],
        "answer": 0,
        "xp": 55, "gold": 28,
    },
]

# ── События: встречи с существами ─────────────────────────────────────────────
CREATURE_EVENTS = [
    {
        "name": "Боурты",
        "emoji": "🌿",
        "desc": "Маленький Боурты сидит на ветке и смотрит на тебя. Он держит в лапах блестящий камешек.",
        "choice_a": "Предложить что-нибудь взамен",
        "choice_b": "Попытаться схватить камешек",
        "outcome_a": {"xp": 40, "gold": 15, "msg": "Боурты доволен обменом и уходит. Ты нашёл у него ингредиент!"},
        "outcome_b": {"xp": 10, "gold": 0,  "msg": "Боурты царапает тебя и убегает. Больно, но урока не забудешь."},
    },
    {
        "name": "Гиппогриф",
        "emoji": "🦅",
        "desc": "Величественный Гиппогриф смотрит на тебя пронзительным взглядом. Нужно поклониться.",
        "choice_a": "Поклониться и ждать",
        "choice_b": "Подойти сразу",
        "outcome_a": {"xp": 80, "gold": 40, "msg": "Гиппогриф кланяется в ответ! Ты можешь погладить его и получаешь награду."},
        "outcome_b": {"xp": 5,  "gold": 0,  "msg": "Гиппогриф отпрыгивает и угрожающе кричит. Хорошо, что убежал вовремя."},
    },
    {
        "name": "Нюхлер",
        "emoji": "🦡",
        "desc": "Нюхлер смотрит на твои монеты голодными глазами. Он явно что-то нашёл в норе.",
        "choice_a": "Бросить монету как приманку",
        "choice_b": "Попробовать найти нору самому",
        "outcome_a": {"xp": 50, "gold": 60, "msg": "Нюхлер берёт монету и уводит тебя к своей спрятанной коллекции золота!"},
        "outcome_b": {"xp": 20, "gold": 5,  "msg": "Нюхлер убегает, но ты находишь монету, которую он обронил."},
    },
    {
        "name": "Домовой эльф",
        "emoji": "🧦",
        "desc": "Домовой эльф испуганно смотрит на тебя. Он несёт старую книгу с потрёпанной обложкой.",
        "choice_a": "Спросить о книге",
        "choice_b": "Предложить носок в подарок",
        "outcome_a": {"xp": 60, "gold": 20, "msg": "Эльф рассказывает о секретном проходе и даёт подсказку о скрытом сокровище."},
        "outcome_b": {"xp": 100, "gold": 50, "msg": "Освобождённый эльф с радостью делится со своим благодетелем всем что имел!"},
    },
    {
        "name": "Феникс",
        "emoji": "🔥",
        "desc": "Феникс сидит на золотом насесте. Его перья мерцают как огонь. Он смотрит мудро.",
        "choice_a": "Попросить перо",
        "choice_b": "Просто поговорить с ним",
        "outcome_a": {"xp": 40, "gold": 100, "msg": "Феникс даёт тебе перо! Оно стоит целое состояние."},
        "outcome_b": {"xp": 120, "gold": 30, "msg": "Феникс поёт тебе. Магическая мелодия даёт прилив сил и опыта."},
    },
]

# ── Мини-квесты комнаты ───────────────────────────────────────────────────────
MINI_QUESTS = [
    {
        "title": "Библиотека теней",
        "desc": "Комната стала огромной библиотекой с исчезающими книгами. Найди нужный том за 3 попытки!",
        "shelves": ["Левая", "Центральная", "Правая", "Верхняя"],
        "answer_idx": None,  # рандомный
        "xp_win": 80, "gold_win": 40,
        "xp_lose": 15, "gold_lose": 5,
    },
    {
        "title": "Чаша артефактов",
        "desc": "Перед тобой три чаши. Под одной спрятан ключ от сокровищницы. Выбери!",
        "shelves": ["Золотая чаша", "Серебряная чаша", "Бронзовая чаша"],
        "answer_idx": None,
        "xp_win": 70, "gold_win": 60,
        "xp_lose": 10, "gold_lose": 0,
    },
    {
        "title": "Три двери",
        "desc": "Три двери. За одной — сокровище. За двумя — ловушки. Выбирай мудро.",
        "shelves": ["Дверь с луной", "Дверь с солнцем", "Дверь со звёздами"],
        "answer_idx": None,
        "xp_win": 90, "gold_win": 70,
        "xp_lose": 10, "gold_lose": 0,
    },
]

# ── Поиск предметов ───────────────────────────────────────────────────────────
SEARCH_EVENTS = [
    {
        "desc": "Комната завалена старыми вещами. Где-то здесь спрятан магический артефакт.",
        "spots": ["Старый сундук", "Под половицей", "За гобеленом", "В дымоходе"],
        "answer_idx": None,
        "xp_win": 60, "gold_win": 50, "item_chance": 0.3,
        "xp_lose": 10, "gold_lose": 5,
    },
    {
        "desc": "Комната наполнена зеркалами. В одном отражается карта скрытого клада.",
        "spots": ["Зеркало слева", "Зеркало в центре", "Зеркало справа", "Зеркало на полу"],
        "answer_idx": None,
        "xp_win": 70, "gold_win": 45, "item_chance": 0.2,
        "xp_lose": 10, "gold_lose": 5,
    },
]


def _generate_daily_event() -> dict:
    """Генерирует случайное событие дня."""
    event_type = random.choices(
        ["riddle", "creature", "quest", "search"],
        weights=[0.30, 0.25, 0.25, 0.20],
        k=1
    )[0]

    if event_type == "riddle":
        riddle = random.choice(RIDDLES).copy()
        return {"type": "riddle", "data": riddle}

    elif event_type == "creature":
        creature = random.choice(CREATURE_EVENTS).copy()
        return {"type": "creature", "data": creature}

    elif event_type == "quest":
        quest = random.choice(MINI_QUESTS).copy()
        quest["answer_idx"] = random.randint(0, len(quest["shelves"]) - 1)
        quest["attempts"]   = 0
        quest["max_attempts"] = 2
        return {"type": "quest", "data": quest}

    else:  # search
        search = random.choice(SEARCH_EVENTS).copy()
        search["answer_idx"] = random.randint(0, len(search["spots"]) - 1)
        return {"type": "search", "data": search}


_room_sessions: dict[int, dict] = {}


async def cmd_room(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """/room — войти в Комнату Требований."""
    user_id = update.effective_user.id
    if not user_exists(user_id):
        await update.message.reply_text(t(user_id, "not_registered"))
        return

    used = get_daily_limit(user_id, "room_req")
    if used >= DAILY_LIMITS["room_req"]:
        await update.message.reply_text(
            "🚪 Комната Требований сегодня уже была открыта.\n"
            "Возвращайся завтра — она предстанет в новом облике!"
        )
        return

    event = _generate_daily_event()
    _room_sessions[user_id] = event

    await _show_event(update.message, user_id, event)


async def _show_event(msg_or_query, user_id: int, event: dict):
    """Показать событие комнаты."""
    etype = event["type"]
    data  = event["data"]

    if etype == "riddle":
        letters = ["А", "Б", "В", "Г"]
        buttons = []
        for i, opt in enumerate(data["options"]):
            buttons.append([InlineKeyboardButton(
                f"{letters[i]}) {opt}",
                callback_data=f"room_riddle:{i}"
            )])
        markup = InlineKeyboardMarkup(buttons)
        text = (
            "🚪 *Комната Требований*\n\n"
            "🧩 *Загадка!*\n\n"
            f"_{data['text']}_\n\n"
            "Выбери правильный ответ:"
        )

    elif etype == "creature":
        markup = InlineKeyboardMarkup([[
            InlineKeyboardButton(f"✅ {data['choice_a']}", callback_data="room_creature:a"),
            InlineKeyboardButton(f"❌ {data['choice_b']}", callback_data="room_creature:b"),
        ]])
        text = (
            f"🚪 *Комната Требований*\n\n"
            f"{data['emoji']} *Встреча: {data['name']}*\n\n"
            f"{data['desc']}\n\n"
            "Что ты сделаешь?"
        )

    elif etype == "quest":
        buttons = [[
            InlineKeyboardButton(shelf, callback_data=f"room_quest:{i}")
        ] for i, shelf in enumerate(data["shelves"])]
        markup = InlineKeyboardMarkup(buttons)
        text = (
            f"🚪 *Комната Требований*\n\n"
            f"📜 *{data['title']}*\n\n"
            f"{data['desc']}\n\n"
            f"Попыток осталось: {data['max_attempts'] - data.get('attempts', 0) + 1}"
        )

    else:  # search
        buttons = [[
            InlineKeyboardButton(spot, callback_data=f"room_search:{i}")
        ] for i, spot in enumerate(data["spots"])]
        markup = InlineKeyboardMarkup(buttons)
        text = (
            "🚪 *Комната Требований*\n\n"
            f"🔍 *Поиск предмета*\n\n"
            f"{data['desc']}\n\n"
            "Где искать?"
        )

    if hasattr(msg_or_query, 'reply_text'):
        await msg_or_query.reply_text(text, parse_mode="Markdown", reply_markup=markup)
    else:
        await msg_or_query.edit_message_text(text, parse_mode="Markdown", reply_markup=markup)


async def cb_room_riddle(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query   = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    answer  = int(query.data.split(":")[1])

    session = _room_sessions.pop(user_id, None)
    if not session or session["type"] != "riddle":
        await query.edit_message_text("❌ Сессия истекла. Попробуй /room снова.")
        return

    data    = session["data"]
    correct = (answer == data["answer"])

    if correct:
        add_xp(user_id, data["xp"])
        add_gold(user_id, data["gold"])
        user = get_user(user_id)
        add_house_points(user_id, user["house"], 5, "room_req")
        increment_daily(user_id, "room_req")
        text = (
            f"✅ *Верно!*\n\n"
            f"+{data['xp']} XP | +{data['gold']} 💰 | +5 очков факультету\n\n"
            f"🚪 Комната исчезает до завтра..."
        )
    else:
        correct_ans = data["options"][data["answer"]]
        add_xp(user_id, 10)
        increment_daily(user_id, "room_req")
        text = (
            f"❌ *Неверно!*\n\n"
            f"Правильный ответ: *{correct_ans}*\n\n"
            f"+10 XP за попытку\n"
            f"🚪 Комната исчезает до завтра..."
        )

    await query.edit_message_text(text, parse_mode="Markdown")


async def cb_room_creature(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query   = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    choice  = query.data.split(":")[1]  # "a" или "b"

    session = _room_sessions.pop(user_id, None)
    if not session or session["type"] != "creature":
        await query.edit_message_text("❌ Сессия истекла. Попробуй /room снова.")
        return

    data    = session["data"]
    outcome = data["outcome_a"] if choice == "a" else data["outcome_b"]

    add_xp(user_id, outcome["xp"])
    if outcome["gold"] > 0:
        add_gold(user_id, outcome["gold"])
    increment_daily(user_id, "room_req")

    text = (
        f"{data['emoji']} *{data['name']}*\n\n"
        f"{outcome['msg']}\n\n"
        f"+{outcome['xp']} XP"
        + (f" | +{outcome['gold']} 💰" if outcome["gold"] > 0 else "")
        + "\n\n🚪 Комната исчезает до завтра..."
    )
    await query.edit_message_text(text, parse_mode="Markdown")


async def cb_room_quest(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query   = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    chosen  = int(query.data.split(":")[1])

    session = _room_sessions.get(user_id)
    if not session or session["type"] != "quest":
        await query.edit_message_text("❌ Сессия истекла.")
        return

    data = session["data"]
    data["attempts"] = data.get("attempts", 0) + 1
    correct = (chosen == data["answer_idx"])

    if correct:
        _room_sessions.pop(user_id, None)
        add_xp(user_id, data["xp_win"])
        add_gold(user_id, data["gold_win"])
        increment_daily(user_id, "room_req")
        text = (
            f"✅ *Нашёл!*\n\n"
            f"+{data['xp_win']} XP | +{data['gold_win']} 💰\n"
            "🚪 Комната исчезает до завтра..."
        )
        await query.edit_message_text(text, parse_mode="Markdown")
    elif data["attempts"] >= data["max_attempts"] + 1:
        _room_sessions.pop(user_id, None)
        add_xp(user_id, data["xp_lose"])
        increment_daily(user_id, "room_req")
        correct_name = data["shelves"][data["answer_idx"]]
        text = (
            f"❌ *Не нашёл!*\n\n"
            f"Правильный вариант: *{correct_name}*\n"
            f"+{data['xp_lose']} XP за попытку\n"
            "🚪 Комната исчезает до завтра..."
        )
        await query.edit_message_text(text, parse_mode="Markdown")
    else:
        remaining = data["max_attempts"] + 1 - data["attempts"]
        wrong_name = data["shelves"][chosen]
        buttons = [[
            InlineKeyboardButton(shelf, callback_data=f"room_quest:{i}")
        ] for i, shelf in enumerate(data["shelves"]) if i != chosen]
        markup = InlineKeyboardMarkup(buttons)
        text = (
            f"❌ *{wrong_name}* — не то!\n\n"
            f"Попыток осталось: {remaining}\n\n"
            f"{data['desc']}"
        )
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=markup)


async def cb_room_search(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query   = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    chosen  = int(query.data.split(":")[1])

    session = _room_sessions.pop(user_id, None)
    if not session or session["type"] != "search":
        await query.edit_message_text("❌ Сессия истекла.")
        return

    data    = session["data"]
    correct = (chosen == data["answer_idx"])
    increment_daily(user_id, "room_req")

    if correct:
        add_xp(user_id, data["xp_win"])
        add_gold(user_id, data["gold_win"])

        item_found = ""
        if random.random() < data.get("item_chance", 0.2):
            from game.items import roll_equipment
            item = roll_equipment("uncommon")
            item_found = f"\n🎁 *Найден предмет:* {item.get('name', {}).get('ru', item['id'])}!"

        text = (
            f"✅ *Нашёл!*\n\n"
            f"+{data['xp_win']} XP | +{data['gold_win']} 💰"
            f"{item_found}\n\n"
            "🚪 Комната исчезает до завтра..."
        )
    else:
        add_xp(user_id, data["xp_lose"])
        add_gold(user_id, data["gold_lose"])
        spot_name = data["spots"][chosen]
        text = (
            f"🔍 *{spot_name}* — пусто!\n\n"
            f"+{data['xp_lose']} XP\n"
            "🚪 Комната исчезает до завтра..."
        )

    await query.edit_message_text(text, parse_mode="Markdown")


def register_room_handlers(app):
    app.add_handler(CommandHandler("room", cmd_room))
    app.add_handler(CallbackQueryHandler(cb_room_riddle,   pattern=r"^room_riddle:"))
    app.add_handler(CallbackQueryHandler(cb_room_creature, pattern=r"^room_creature:"))
    app.add_handler(CallbackQueryHandler(cb_room_quest,    pattern=r"^room_quest:"))
    app.add_handler(CallbackQueryHandler(cb_room_search,   pattern=r"^room_search:"))

