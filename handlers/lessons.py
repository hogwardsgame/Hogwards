"""
Lessons handler — уроки Снейпа, МакГонагалл, Флитвика и других преподавателей.
Механика: вопросы с вариантами ответов по вселенной HP,
награды XP/золото/очки факультета, редкие награды за серии правильных ответов.
"""
import logging
import random
from datetime import datetime, timezone
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ContextTypes, CommandHandler, CallbackQueryHandler, MessageHandler, filters,
)
from database import (
    get_user, user_exists, get_daily_limit, increment_daily,
    add_xp, add_gold, add_house_points, get_conn, execute, fetchrow, fetchall,
)
from utils.i18n import t
from config import DAILY_LIMITS, XP_REWARDS, GOLD_REWARDS, HOUSE_POINTS_REWARDS

logger = logging.getLogger(__name__)

# ── Банк вопросов по предметам ────────────────────────────────────────────────
QUESTIONS: dict[str, list[dict]] = {
    "snape": [
        {
            "q": "Какой ингредиент добавляют в зелье Живой Смерти для усиления?",
            "options": ["Асфодель", "Мандрагора", "Безоар", "Лунная роса"],
            "answer": 0,
            "hint": "Это цветок, упоминаемый Снейпом на первом уроке.",
        },
        {
            "q": "Что такое Безоар и зачем он нужен?",
            "options": [
                "Камень из желудка козы — противоядие от большинства ядов",
                "Особый вид водоросли для усиления зелий",
                "Сушёная летучая мышь из пещер Азкабана",
                "Порошок из рога единорога",
            ],
            "answer": 0,
            "hint": "Снейп спросил об этом Гарри на первом уроке.",
        },
        {
            "q": "Каков правильный способ приготовления зелья Феликс Фелицис?",
            "options": [
                "Шесть месяцев при постоянной температуре",
                "Три часа при полнолунии",
                "Два часа с добавлением лунной росы",
                "Сутки при помешивании против часовой стрелки",
            ],
            "answer": 0,
            "hint": "Это самое сложное зелье из изученных в Хогвартсе.",
        },
        {
            "q": "Что происходит, если добавить слишком много листьев яснотки в зелье?",
            "options": [
                "Зелье взорвётся",
                "Зелье потеряет цвет",
                "Зелье станет ядовитым",
                "Ничего — это необязательный ингредиент",
            ],
            "answer": 2,
            "hint": "Снейп предупреждал об этом в третий раз в этом году.",
        },
        {
            "q": "Как называется заклинание, которое придумал сам Снейп?",
            "options": ["Сектумсемпра", "Ливицорпус", "Мобиликорпус", "Тенебрус"],
            "answer": 0,
            "hint": "Он написал его в своей потрёпанной книге по зельям.",
        },
        {
            "q": "Какой ингредиент нужен для зелья Полижус?",
            "options": [
                "Волосы того, кем хочешь стать",
                "Перо феникса",
                "Кровь лунной жабы",
                "Чешуя дракона",
            ],
            "answer": 0,
            "hint": "Гермиона варила это зелье во втором году.",
        },
        {
            "q": "Что является основным действующим веществом Веритасерума?",
            "options": [
                "Слёзы сфинкса",
                "Вытяжка из корня мандрагоры",
                "Сок лунного цветка",
                "Особый фермент правдивости",
            ],
            "answer": 2,
            "hint": "Снейп угрожал этим зельем Гарри в пятом году.",
        },
        {
            "q": "Чем отличается зелье Амортенция от обычного любовного зелья?",
            "options": [
                "Вызывает истинную любовь",
                "Вызывает лишь одержимость и ненависть",
                "Является сильнейшим любовным зельем",
                "Действует вечно без повторного применения",
            ],
            "answer": 2,
            "hint": "Гермиона рассказывала об этом на уроке зельеварения.",
        },
    ],
    "mcgonagall": [
        {
            "q": "Что такое анимагус?",
            "options": [
                "Волшебник, способный превращаться в животное по желанию",
                "Животное с магическими способностями",
                "Заклинание трансфигурации живых существ",
                "Особый класс магических существ",
            ],
            "answer": 0,
            "hint": "МакГонагалл сама является анимагусом.",
        },
        {
            "q": "В какое животное превращается профессор МакГонагалл?",
            "options": ["Кошку", "Сову", "Рысь", "Лань"],
            "answer": 0,
            "hint": "Гарри увидел это животное перед Тисовой улицей.",
        },
        {
            "q": "Какое первое заклинание трансфигурации изучают в Хогвартсе?",
            "options": [
                "Превращение спички в иглу",
                "Превращение чайника в черепаху",
                "Левитация пера",
                "Трансфигурация камня в хлеб",
            ],
            "answer": 0,
            "hint": "МакГонагалл продемонстрировала это на первом уроке.",
        },
        {
            "q": "Что запрещено при трансфигурации живых существ в неодушевлённые?",
            "options": [
                "Неполная трансфигурация",
                "Применять заклинание без наблюдения",
                "Думать о другом предмете",
                "Использовать чужую палочку",
            ],
            "answer": 0,
            "hint": "Невилл однажды допустил эту ошибку с уткой.",
        },
        {
            "q": "Сколько Отличий по волшебству получила МакГонагалл в своё время?",
            "options": ["Восемь", "Шесть", "Пять", "Семь"],
            "answer": 0,
            "hint": "Она была лучшей ученицей своего времени.",
        },
        {
            "q": "Что такое Трансфигурация Гэмп и её основные законы?",
            "options": [
                "Пять исключений — нельзя создать еду, любовь, жизнь, магию и смерть",
                "Три закона — масса, форма и сознание",
                "Семь принципов равновесия материи",
                "Четыре стихии трансфигурации",
            ],
            "answer": 0,
            "hint": "Гермиона упоминала это во время поисков крестражей.",
        },
        {
            "q": "Какой факультет возглавляет МакГонагалл?",
            "options": ["Гриффиндор", "Когтевран", "Пуффендуй", "Слизерин"],
            "answer": 0,
            "hint": "Это факультет Гарри Поттера.",
        },
    ],
    "flitwick": [
        {
            "q": "Как правильно произносится заклинание Вингардиум Левиоса?",
            "options": [
                "ЛевиОса, а не ЛевиосА",
                "ЛевиосА, а не ЛевиОса",
                "Оба варианта одинаково верны",
                "Ударение не важно",
            ],
            "answer": 0,
            "hint": "Гермиона поправила Рона именно так.",
        },
        {
            "q": "Что такое Ступефай?",
            "options": [
                "Заклинание оглушения",
                "Заклинание трансфигурации",
                "Защитное заклинание",
                "Заклинание призыва",
            ],
            "answer": 0,
            "hint": "Это одно из базовых боевых заклинаний.",
        },
        {
            "q": "Какой размер у профессора Флитвика?",
            "options": [
                "Очень маленький — карлик",
                "Средний рост",
                "Высокий и худой",
                "Средний, но полноватый",
            ],
            "answer": 0,
            "hint": "Он часто стоит на стопке книг за кафедрой.",
        },
        {
            "q": "Кем был Флитвик до преподавания?",
            "options": [
                "Чемпионом по дуэлям",
                "Авроры",
                "Торговцем волшебными артефактами",
                "Исследователем тёмных искусств",
            ],
            "answer": 0,
            "hint": "Его навыки в бою пригодились при защите Хогвартса.",
        },
        {
            "q": "Какое заклинание Флитвик использует для проверки правильности движений?",
            "options": [
                "Риковошет — отслеживает траекторию",
                "Ревелио — раскрывает ошибки",
                "Лумос — освещает слабые места",
                "Акцио — притягивает верные решения",
            ],
            "answer": 1,
            "hint": "Он проверял работы студентов именно так.",
        },
        {
            "q": "Что случится, если неправильно выполнить заклинание Акцио?",
            "options": [
                "Предмет прилетит слишком быстро и ударит",
                "Предмет исчезнет навсегда",
                "Заклинание превратится в Экспульсо",
                "Ничего — оно просто не сработает",
            ],
            "answer": 0,
            "hint": "Гарри почти столкнулся с этим на турнире.",
        },
        {
            "q": "Какое заклинание защищает от Авада Кедавра?",
            "options": [
                "Ничего не защищает — только любовная жертва",
                "Протего Максима",
                "Экспекто Патронум",
                "Протего Тоталум",
            ],
            "answer": 0,
            "hint": "Дамблдор объяснял это Гарри.",
        },
    ],
    "lupin": [
        {
            "q": "Как называется существо, принимающее форму того, чего ты боишься?",
            "options": ["Боггарт", "Дементор", "Инфери", "Доппельгангер"],
            "answer": 0,
            "hint": "На уроке Люпина третьекурсники сражались с ним в шкафу.",
        },
        {
            "q": "Какое заклинание используется против богарта?",
            "options": ["Ридикулус", "Экспекто Патронум", "Ступефай", "Протего"],
            "answer": 0,
            "hint": "Нужно представить что-то смешное.",
        },
        {
            "q": "Чем питаются дементоры?",
            "options": [
                "Счастьем и хорошими воспоминаниями",
                "Магической энергией волшебников",
                "Страхом и тьмой",
                "Кровью живых существ",
            ],
            "answer": 0,
            "hint": "После их прихода остаётся лишь пустота.",
        },
        {
            "q": "Что происходит с человеком после Поцелуя дементора?",
            "options": [
                "Душа навсегда поглощается дементором",
                "Человек умирает мгновенно",
                "Человек превращается в дементора",
                "Наступает временная амнезия",
            ],
            "answer": 0,
            "hint": "Это считается хуже смерти.",
        },
        {
            "q": "Каково единственное защитное заклинание против дементоров?",
            "options": ["Экспекто Патронум", "Протего Тоталум", "Хортикорпус", "Конфундус"],
            "answer": 0,
            "hint": "Нужно думать о самом счастливом воспоминании.",
        },
    ],
    "trelawney": [
        {
            "q": "Какое Великое Пророчество было сделано о Гарри Поттере?",
            "options": [
                "«Тот, кто равен Тёмному Лорду по силе...»",
                "«Избранный победит Тёмного Лорда...»",
                "«Рождённый в конце седьмого месяца...»",
                "«Отмеченный Тёмным Лордом...»",
            ],
            "answer": 2,
            "hint": "Сибилла Трелони произнесла его в трактире Кабаний Клык.",
        },
        {
            "q": "Что означает, если видишь Гримма в чайных листьях?",
            "options": [
                "Смерть и беду",
                "Дальнее путешествие",
                "Неожиданную удачу",
                "Встречу с врагом",
            ],
            "answer": 0,
            "hint": "Трелони предсказала это Гарри, бледнея.",
        },
        {
            "q": "Сколько настоящих пророчеств сделала Трелони за всю карьеру?",
            "options": ["Два", "Одно", "Ни одного", "Три"],
            "answer": 0,
            "hint": "Второе сделано прямо в её кабинете.",
        },
    ],
}


# Дополнительные вопросы: понятные, короткие, с отсылками к известным сценам и фразам.
EXTRA_QUESTIONS = {
    "snape": [
        {"q": "На первом уроке Снейп спрашивал Гарри про Безоар. Где его ищут?", "options": ["В желудке козы", "В перьях феникса", "В корне мандрагоры", "В пепле камина"], "answer": 0, "hint": "Это универсальное противоядие."},
        {"q": "Какой напиток в истории часто связан с правдой и допросами?", "options": ["Правдосыворотка", "Оборотное зелье", "Феликс Фелицис", "Амортенция"], "answer": 0, "hint": "Сыворотка заставляет говорить правду."},
        {"q": "Как называется зелье удачи?", "options": ["Феликс Фелицис", "Амортенция", "Многосущное", "Живая смерть"], "answer": 0, "hint": "Его ещё называют жидкой удачей."},
    ],
    "mcgonagall": [
        {"q": "Какой предмет МакГонагалл превращала на уроках трансфигурации?", "options": ["Спичку в иглу", "Камень в змею", "Кубок в крысу", "Перо в ключ"], "answer": 0, "hint": "Это базовое упражнение для первокурсников."},
        {"q": "Что важнее всего в трансфигурации?", "options": ["Точность формы и концентрация", "Громкость голоса", "Цвет мантии", "Количество золота"], "answer": 0, "hint": "Маленькая ошибка меняет результат."},
        {"q": "Какой анимагической формой известна МакГонагалл?", "options": ["Кошка", "Сова", "Змея", "Выдра"], "answer": 0, "hint": "Её можно увидеть ещё до первого урока."},
    ],
    "flitwick": [
        {"q": "Какая фраза помогает поднять перо в воздух?", "options": ["Вингардиум Левиоса", "Экспеллиармус", "Люмос", "Репаро"], "answer": 0, "hint": "Не забывай правильное движение палочкой."},
        {"q": "Что делает заклинание Люмос?", "options": ["Зажигает свет на конце палочки", "Открывает замок", "Лечит раны", "Вызывает воду"], "answer": 0, "hint": "Полезно в тёмных коридорах."},
        {"q": "Какая короткая фраза гасит свет после Люмос?", "options": ["Нокс", "Акцио", "Силенцио", "Депульсо"], "answer": 0, "hint": "Короткое противоположное заклинание."},
    ],
    "lupin": [
        {"q": "Какое светлое заклинание используют против дементоров?", "options": ["Экспекто Патронум", "Редукто", "Алохомора", "Инцендио"], "answer": 0, "hint": "Нужно сильное счастливое воспоминание."},
        {"q": "Что показывает боггарт?", "options": ["Главный страх человека", "Будущее", "Сокровища", "Настоящее имя врага"], "answer": 0, "hint": "На уроке Люпина все видели разное."},
        {"q": "Каким заклинанием делают боггарта смешным?", "options": ["Ридикулус", "Протего", "Конфундус", "Обливиэйт"], "answer": 0, "hint": "Смех — главное оружие против боггарта."},
    ],
    "trelawney": [
        {"q": "Что смотрят на уроках прорицания в чайной чашке?", "options": ["Узоры чаинок", "Цвет воды", "Температуру чашки", "Трещины на блюдце"], "answer": 0, "hint": "Гримм тоже связан с чаинками."},
        {"q": "Какой предмет чаще всего ассоциируется с прорицанием?", "options": ["Хрустальный шар", "Бузинная палочка", "Мантия-невидимка", "Карта Мародёров"], "answer": 0, "hint": "Он стоит в кабинете Трелони."},
        {"q": "Что значит предупреждение 'опасность близко' в прорицании?", "options": ["Нужно действовать осторожно", "Нужно сразу драться", "Нужно продать предметы", "Нужно сменить факультет"], "answer": 0, "hint": "Прорицание не заменяет здравый смысл."},
    ],
}
for _subject, _questions in EXTRA_QUESTIONS.items():
    QUESTIONS.setdefault(_subject, []).extend(_questions)

# Все предметы с учителями
SUBJECTS_INFO = {
    "snape":       {"name": "Зельеварение",         "teacher": "Профессор Снейп",       "emoji": "🧪"},
    "mcgonagall":  {"name": "Трансфигурация",        "teacher": "Профессор МакГонагалл", "emoji": "🔮"},
    "flitwick":    {"name": "Чары",                  "teacher": "Профессор Флитвик",     "emoji": "✨"},
    "lupin":       {"name": "ЗОТС",                  "teacher": "Профессор Люпин",       "emoji": "⚔️"},
    "trelawney":   {"name": "Прорицания",            "teacher": "Профессор Трелони",     "emoji": "🔮"},
}

# In-memory сессии уроков: user_id → session
_lesson_sessions: dict[int, dict] = {}


def _pick_question(subject: str) -> dict:
    pool = QUESTIONS.get(subject, [])
    if not pool:
        subject = random.choice(list(QUESTIONS.keys()))
        pool = QUESTIONS[subject]
    idx = random.randrange(len(pool))
    question = pool[idx].copy()
    question["__idx"] = idx
    return question


def _get_question_by_index(subject: str, qidx: int) -> dict:
    pool = QUESTIONS.get(subject, [])
    if not pool or qidx < 0 or qidx >= len(pool):
        return _pick_question(subject)
    question = pool[qidx].copy()
    question["__idx"] = qidx
    return question


def _lesson_subject_keyboard() -> InlineKeyboardMarkup:
    buttons = []
    for sid, info in SUBJECTS_INFO.items():
        buttons.append([InlineKeyboardButton(
            f"{info['emoji']} {info['name']} — {info['teacher']}",
            callback_data=f"lesson_start:{sid}"
        )])
    return InlineKeyboardMarkup(buttons)


def _question_keyboard(question: dict, subject: str) -> InlineKeyboardMarkup:
    """В callback кладём номер вопроса и номер выбранного ответа.
    Так бот всегда проверяет именно тот вопрос, который был показан игроку.
    """
    letters = ["А", "Б", "В", "Г"]
    buttons = []
    qidx = int(question.get("__idx", 0))
    for i, opt in enumerate(question["options"]):
        buttons.append([InlineKeyboardButton(
            f"{letters[i]}) {opt}",
            callback_data=f"lesson_answer:{subject}:{qidx}:{i}"
        )])
    return InlineKeyboardMarkup(buttons)


async def cmd_lessons(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not user_exists(user_id):
        await update.message.reply_text(t(user_id, "not_registered"))
        return

    used = get_daily_limit(user_id, "lessons")
    if used >= DAILY_LIMITS["lessons"]:
        await update.message.reply_text(
            f"📚 Уроки на сегодня закончились ({used}/{DAILY_LIMITS['lessons']}).\n"
            f"Возвращайся завтра!"
        )
        return

    await update.message.reply_text(
        f"📚 *Уроки в Хогвартсе*\n\n"
        f"Пройдено сегодня: {used}/{DAILY_LIMITS['lessons']}\n\n"
        f"Выбери предмет:",
        parse_mode="Markdown",
        reply_markup=_lesson_subject_keyboard()
    )


async def cb_lesson_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query   = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    subject = query.data.split(":")[1]

    used = get_daily_limit(user_id, "lessons")
    if used >= DAILY_LIMITS["lessons"]:
        await query.edit_message_text("📚 Лимит уроков на сегодня исчерпан!")
        return

    info = SUBJECTS_INFO.get(subject, {})
    question = _pick_question(subject)

    session = {
        "subject":  subject,
        "question": question,
        "score":    0,
        "total":    0,
        "streak":   0,
    }
    _lesson_sessions[user_id] = session

    markup = _question_keyboard(question, subject)
    await query.edit_message_text(
        f"{info.get('emoji','📚')} *{info.get('name','Урок')}*\n"
        f"👩‍🏫 {info.get('teacher','Преподаватель')}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"❓ {question['q']}",
        parse_mode="Markdown",
        reply_markup=markup
    )


async def cb_lesson_answer(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query   = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    parts      = query.data.split(":")
    subject    = parts[1]
    qidx       = int(parts[2])   # номер вопроса, который был показан игроку
    chosen_idx = int(parts[3])   # что выбрал игрок

    # Берём вопрос по номеру из кнопки. Так правильный ответ не ломается,
    # даже если бот перезапустился или потерял временную память.
    session = _lesson_sessions.get(user_id) or {"subject": subject, "score": 0, "total": 0, "streak": 0}
    question = _get_question_by_index(subject, qidx)

    correct = (chosen_idx == int(question.get("answer", -1)))

    if correct:
        session["score"] = session.get("score", 0) + 1
        session["streak"] = session.get("streak", 0) + 1
        xp_gain = XP_REWARDS.get("lesson_correct", 30)
        gold_gain = GOLD_REWARDS.get("lesson_correct", 8)
        hp_pts = HOUSE_POINTS_REWARDS.get("lesson_correct", 3)

        # Бонус за серию правильных ответов
        streak = session["streak"]
        streak_bonus_xp = 0
        streak_bonus_gold = 0
        streak_msg = ""
        if streak == 3:
            streak_bonus_xp = 20
            streak_bonus_gold = 10
            streak_msg = "\n🔥 Серия 3 подряд! Бонус +20 XP, +10 💰"
        elif streak == 5:
            streak_bonus_xp = 50
            streak_bonus_gold = 25
            streak_msg = "\n⚡ Серия 5 подряд! Бонус +50 XP, +25 💰"
        elif streak >= 10:
            streak_bonus_xp = 100
            streak_bonus_gold = 50
            streak_msg = "\n🌟 Серия 10+! Бонус +100 XP, +50 💰"

        xp_gain += streak_bonus_xp
        gold_gain += streak_bonus_gold

        # ВАЖНО: раньше правильный ответ мог падать на очках факультета
        # или статистике. Игрок нажимал правильный ответ, а бот молчал.
        # Теперь основная награда выдаётся обязательно, а второстепенные
        # действия не ломают ответ бота.
        add_xp(user_id, xp_gain)
        add_gold(user_id, gold_gain)

        user = get_user(user_id)
        if user and user.get("house"):
            try:
                add_house_points(user_id, user["house"], hp_pts, "lesson_correct")
            except Exception:
                logger.exception("Не удалось начислить очки факультета за урок")

        try:
            increment_daily(user_id, "lessons")
        except Exception:
            logger.exception("Не удалось обновить дневной лимит уроков")

        try:
            with get_conn() as conn:
                execute(conn, "UPDATE user_stats SET lessons_done = COALESCE(lessons_done, 0) + 1 WHERE user_id = %s", user_id)
        except Exception:
            logger.exception("Не удалось обновить статистику уроков")

        # Редкая награда: заклинание (1% шанс)
        rare_reward = ""
        try:
            if random.random() < 0.01:
                from game.spells import spells_by_rarity
                rare_spells = spells_by_rarity("rare")
                if rare_spells:
                    spell = random.choice(rare_spells)
                    with get_conn() as conn:
                        execute(conn, "INSERT INTO user_spells (user_id, spell_id) VALUES (%s, %s) ON CONFLICT DO NOTHING", user_id, spell["id"])
                    rare_reward = f"\n\n🌟 Редкая награда: заклинание {spell['id']}!"
        except Exception:
            logger.exception("Не удалось выдать редкую награду за урок")

        result_text = (
            f"✅ Правильно!\n\n"
            f"{question.get('hint','Отличная работа!')}\n\n"
            f"+{xp_gain} XP | +{gold_gain} 💰 | +{hp_pts} очков факультету"
            f"{streak_msg}"
            f"{rare_reward}"
        )
    else:
        session["streak"] = 0
        xp_gain = XP_REWARDS.get("lesson_wrong", 5)
        gold_gain = GOLD_REWARDS.get("lesson_wrong", 0)

        add_xp(user_id, xp_gain)
        if gold_gain:
            add_gold(user_id, gold_gain)

        try:
            increment_daily(user_id, "lessons")
        except Exception:
            logger.exception("Не удалось обновить дневной лимит уроков")

        correct_text = question["options"][int(question.get("answer", 0))]
        result_text = (
            f"❌ Неверно!\n\n"
            f"Правильный ответ: {correct_text}\n"
            f"{question.get('hint','Продолжай учиться!')}\n\n"
            f"+{xp_gain} XP за участие"
        )

    _lesson_sessions.pop(user_id, None)

    used = get_daily_limit(user_id, "lessons")
    remaining = DAILY_LIMITS["lessons"] - used

    if remaining > 0:
        markup = InlineKeyboardMarkup([[
            InlineKeyboardButton("📚 Следующий вопрос", callback_data=f"lesson_start:{subject}"),
            InlineKeyboardButton("📋 Другой предмет",   callback_data="lesson_menu"),
        ]])
        result_text += f"\n\nОсталось уроков сегодня: {remaining}"
    else:
        markup = None
        result_text += "\n\n📚 На сегодня всё! Возвращайся завтра."

    await query.edit_message_text(result_text, reply_markup=markup)


async def cb_lesson_menu(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query   = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    used = get_daily_limit(user_id, "lessons")
    await query.edit_message_text(
        f"📚 *Уроки в Хогвартсе*\n\nПройдено: {used}/{DAILY_LIMITS['lessons']}\n\nВыбери предмет:",
        parse_mode="Markdown",
        reply_markup=_lesson_subject_keyboard()
    )


async def handle_lessons_button(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if update.message.text == t(user_id, "btn_lessons"):
        await cmd_lessons(update, ctx)


def register_lessons_handlers(app):
    app.add_handler(CommandHandler("lessons", cmd_lessons))
    app.add_handler(CallbackQueryHandler(cb_lesson_start,  pattern=r"^lesson_start:"))
    app.add_handler(CallbackQueryHandler(cb_lesson_answer, pattern=r"^lesson_answer:"))
    app.add_handler(CallbackQueryHandler(cb_lesson_menu,   pattern=r"^lesson_menu"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_lessons_button), group=6)
