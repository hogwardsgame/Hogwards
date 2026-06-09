"""
Quest definitions per TZ section 8.3.
Types: story (once), daily, weekly.
Each quest is a multi-step branching narrative.
"""

QUESTS: dict[str, dict] = {

    # ── STORY QUESTS (10) ─────────────────────────────────────────────────────
    "sq_01_arrival": {
        "id": "sq_01_arrival", "type": "story", "repeatable": False,
        "name": {"ru": "Прибытие в Хогвартс", "en": "Arrival at Hogwarts"},
        "steps": [
            {
                "text": {"ru": "Ты прибыл в Хогвартс. Паровоз остановился у платформы. Что делаешь?",
                          "en": "You arrive at Hogwarts. The train stops at the platform. What do you do?"},
                "choices": [
                    {"text": {"ru": "Осмотреться", "en": "Look around"}, "next": 1, "bonus": None},
                    {"text": {"ru": "Поговорить с новыми учениками", "en": "Talk to new students"}, "next": 2, "bonus": "xp_10"},
                ],
            },
            {
                "text": {"ru": "Ты замечаешь странный свиток на скамейке. Что делаешь?",
                          "en": "You notice a strange scroll on a bench. What do you do?"},
                "choices": [
                    {"text": {"ru": "Открыть", "en": "Open it"}, "next": "end", "bonus": "spell_random"},
                    {"text": {"ru": "Отдать Дамблдору", "en": "Give to Dumbledore"}, "next": "end", "bonus": "xp_50"},
                    {"text": {"ru": "Уничтожить", "en": "Destroy it"}, "next": "end", "bonus": "gold_30"},
                ],
            },
            {
                "text": {"ru": "Новые друзья рассказывают о Запретном лесе. Поход туда?",
                          "en": "New friends talk about the Forbidden Forest. Go there?"},
                "choices": [
                    {"text": {"ru": "Да!", "en": "Yes!"}, "next": "end", "bonus": "xp_80"},
                    {"text": {"ru": "Нет, слишком опасно", "en": "No, too dangerous"}, "next": "end", "bonus": "gold_50"},
                ],
            },
        ],
        "final_reward": {"xp": 150, "gold": 50},
    },
    "sq_02_library": {
        "id": "sq_02_library", "type": "story", "repeatable": False,
        "name": {"ru": "Тайна библиотеки", "en": "Library Secret"},
        "steps": [
            {
                "text": {"ru": "Мадам Пинс просит найти пропавшую книгу. Куда идёшь?",
                          "en": "Madam Pince asks you to find a missing book. Where do you go?"},
                "choices": [
                    {"text": {"ru": "Запретный раздел", "en": "Restricted section"}, "next": 1, "bonus": None},
                    {"text": {"ru": "Комната с зеркалами", "en": "Mirror room"}, "next": 2, "bonus": "xp_20"},
                ],
            },
            {
                "text": {"ru": "Книга охраняется заклинанием. Взломать или отступить?",
                          "en": "The book is protected by a spell. Break in or retreat?"},
                "choices": [
                    {"text": {"ru": "Взломать", "en": "Break in"}, "next": "end", "bonus": "spell_random"},
                    {"text": {"ru": "Отступить", "en": "Retreat"}, "next": "end", "bonus": "gold_40"},
                ],
            },
            {
                "text": {"ru": "Ты нашёл книгу! Там секрет. Сохранить или рассказать Думbledore?",
                          "en": "You found the book! There's a secret inside. Keep it or tell Dumbledore?"},
                "choices": [
                    {"text": {"ru": "Сохранить", "en": "Keep"}, "next": "end", "bonus": "xp_60"},
                    {"text": {"ru": "Рассказать", "en": "Tell"}, "next": "end", "bonus": "xp_100"},
                ],
            },
        ],
        "final_reward": {"xp": 200, "gold": 60},
    },
    "sq_03_quidditch": {
        "id": "sq_03_quidditch", "type": "story", "repeatable": False,
        "name": {"ru": "Матч по квиддичу", "en": "Quidditch Match"},
        "steps": [
            {
                "text": {"ru": "Матч по квиддичу! Играть или наблюдать?",
                          "en": "Quidditch match! Play or watch?"},
                "choices": [
                    {"text": {"ru": "Играть", "en": "Play"}, "next": 1, "bonus": None},
                    {"text": {"ru": "Наблюдать", "en": "Watch"}, "next": "end", "bonus": "xp_30"},
                ],
            },
            {
                "text": {"ru": "Ты ловишь снитч! Какой приём?",
                          "en": "You chase the snitch! Which move?"},
                "choices": [
                    {"text": {"ru": "Пике вниз", "en": "Dive"}, "next": "end", "bonus": "xp_120"},
                    {"text": {"ru": "Обманный манёвр", "en": "Feint"}, "next": "end", "bonus": "gold_80"},
                ],
            },
        ],
        "final_reward": {"xp": 180, "gold": 70},
    },
    "sq_04_potions": {
        "id": "sq_04_potions", "type": "story", "repeatable": False,
        "name": {"ru": "Эксперимент Снейпа", "en": "Snape's Experiment"},
        "steps": [
            {
                "text": {"ru": "Снейп просит помочь с опасным зельем. Согласиться?",
                          "en": "Snape asks for help with a dangerous potion. Agree?"},
                "choices": [
                    {"text": {"ru": "Да", "en": "Yes"}, "next": 1, "bonus": None},
                    {"text": {"ru": "Нет", "en": "No"}, "next": "end", "bonus": "xp_20"},
                ],
            },
            {
                "text": {"ru": "Зелье взрывается! Использовать щит?",
                          "en": "The potion explodes! Use a shield?"},
                "choices": [
                    {"text": {"ru": "Протего!", "en": "Protego!"}, "next": "end", "bonus": "item_potion"},
                    {"text": {"ru": "Убежать", "en": "Run"}, "next": "end", "bonus": "xp_40"},
                ],
            },
        ],
        "final_reward": {"xp": 160, "gold": 55},
    },
    "sq_05_mirror": {
        "id": "sq_05_mirror", "type": "story", "repeatable": False,
        "name": {"ru": "Зеркало Еиналеж", "en": "Mirror of Erised"},
        "steps": [
            {
                "text": {"ru": "Ты нашёл Зеркало Еиналеж. Смотреть?",
                          "en": "You found the Mirror of Erised. Look into it?"},
                "choices": [
                    {"text": {"ru": "Смотреть", "en": "Look"}, "next": 1, "bonus": None},
                    {"text": {"ru": "Уйти", "en": "Leave"}, "next": "end", "bonus": "xp_30"},
                ],
            },
            {
                "text": {"ru": "Ты видишь победу в турнире. Рассказать Дамблдору?",
                          "en": "You see victory in a tournament. Tell Dumbledore?"},
                "choices": [
                    {"text": {"ru": "Рассказать", "en": "Tell"}, "next": "end", "bonus": "xp_100"},
                    {"text": {"ru": "Скрыть", "en": "Keep secret"}, "next": "end", "bonus": "spell_random"},
                ],
            },
        ],
        "final_reward": {"xp": 200, "gold": 80},
    },
    # Additional story quests 6-10 (shorter format)
    "sq_06_troll":     {"id": "sq_06_troll",     "type": "story", "repeatable": False, "name": {"ru": "Тролль в подземелье!", "en": "Troll in the Dungeon!"}, "steps": [], "final_reward": {"xp": 220, "gold": 90}},
    "sq_07_patronus":  {"id": "sq_07_patronus",  "type": "story", "repeatable": False, "name": {"ru": "Патронус",             "en": "Patronus"},             "steps": [], "final_reward": {"xp": 300, "gold": 100}},
    "sq_08_horcrux":   {"id": "sq_08_horcrux",   "type": "story", "repeatable": False, "name": {"ru": "Крестраж",             "en": "Horcrux"},              "steps": [], "final_reward": {"xp": 350, "gold": 120}},
    "sq_09_deathly":   {"id": "sq_09_deathly",   "type": "story", "repeatable": False, "name": {"ru": "Дары Смерти",          "en": "Deathly Hallows"},      "steps": [], "final_reward": {"xp": 400, "gold": 150}},
    "sq_10_final":     {"id": "sq_10_final",     "type": "story", "repeatable": False, "name": {"ru": "Финальная битва",      "en": "Final Battle"},         "steps": [], "final_reward": {"xp": 500, "gold": 200}},

    # ── DAILY QUEST POOL (30) ─────────────────────────────────────────────────
    "dq_01": {"id": "dq_01", "type": "daily", "repeatable": True,
              "name": {"ru": "Охота на акромантул",    "en": "Acromantula Hunt"},
              "objective": {"type": "kill_monster", "monster": "acromantula", "count": 3},
              "reward": {"xp": 80, "gold": 40}},
    "dq_02": {"id": "dq_02", "type": "daily", "repeatable": True,
              "name": {"ru": "Урок зельеварения",      "en": "Potions Class"},
              "objective": {"type": "attend_lesson", "subject": "potions", "count": 1},
              "reward": {"xp": 60, "gold": 30}},
    "dq_03": {"id": "dq_03", "type": "daily", "repeatable": True,
              "name": {"ru": "Дуэль новичков",          "en": "Beginner's Duel"},
              "objective": {"type": "pvp_win", "count": 1},
              "reward": {"xp": 100, "gold": 50}},
    "dq_04": {"id": "dq_04", "type": "daily", "repeatable": True,
              "name": {"ru": "Исследование леса",       "en": "Forest Exploration"},
              "objective": {"type": "pve_dungeon", "zone": "forbidden_forest", "count": 2},
              "reward": {"xp": 90, "gold": 45}},
    "dq_05": {"id": "dq_05", "type": "daily", "repeatable": True,
              "name": {"ru": "Три победы",              "en": "Three Victories"},
              "objective": {"type": "pvp_win", "count": 3},
              "reward": {"xp": 150, "gold": 70}},
    "dq_06": {"id": "dq_06", "type": "daily", "repeatable": True,
              "name": {"ru": "Сбор ингредиентов",       "en": "Collect Ingredients"},
              "objective": {"type": "kill_monster", "monster": "any", "count": 5},
              "reward": {"xp": 110, "gold": 55}},
    "dq_07": {"id": "dq_07", "type": "daily", "repeatable": True,
              "name": {"ru": "Защита Хогвартса",        "en": "Defend Hogwarts"},
              "objective": {"type": "pvp_win", "count": 2},
              "reward": {"xp": 120, "gold": 60}},
    "dq_08": {"id": "dq_08", "type": "daily", "repeatable": True,
              "name": {"ru": "Уроки чар",               "en": "Charms Class"},
              "objective": {"type": "attend_lesson", "subject": "charms", "count": 1},
              "reward": {"xp": 70, "gold": 35}},
    "dq_09": {"id": "dq_09", "type": "daily", "repeatable": True,
              "name": {"ru": "В пещерах гоблинов",      "en": "In Goblin Caves"},
              "objective": {"type": "kill_monster", "monster": "goblin", "count": 3},
              "reward": {"xp": 100, "gold": 60}},
    "dq_10": {"id": "dq_10", "type": "daily", "repeatable": True,
              "name": {"ru": "Первые шаги",             "en": "First Steps"},
              "objective": {"type": "pve_dungeon", "zone": "any", "count": 1},
              "reward": {"xp": 50, "gold": 25}},
    # dq_11 – dq_30 (compact)
    **{f"dq_{i:02d}": {"id": f"dq_{i:02d}", "type": "daily", "repeatable": True,
                        "name": {"ru": f"Ежедневное задание {i}", "en": f"Daily Quest {i}"},
                        "objective": {"type": "kill_monster", "monster": "any", "count": i % 5 + 1},
                        "reward": {"xp": 60 + i * 5, "gold": 30 + i * 3}}
       for i in range(11, 31)},

    # ── WEEKLY QUEST ──────────────────────────────────────────────────────────
    "wq_01": {
        "id": "wq_01", "type": "weekly", "repeatable": True,
        "name": {"ru": "Великий турнир",     "en": "Grand Tournament"},
        "objective": {"type": "pvp_win", "count": 10},
        "reward": {"xp": 500, "gold": 200, "item": "random_rare"},
    },
}



# Улучшенные сюжетные квесты 6-10: раньше они завершались без понятных шагов.
QUESTS["sq_06_troll"].update({
    "name": {"ru": "Тролль в подземелье", "en": "Troll in the Dungeon"},
    "description": {"ru": "Помоги ученикам выбраться из опасного коридора и останови тролля.", "en": "Help students escape a dangerous corridor and stop the troll."},
    "steps": [
        {"text": {"ru": "По коридору несётся крик: в подземелье тролль. Что делаешь?", "en": "A shout echoes: troll in the dungeon. What do you do?"}, "choices": [{"text": {"ru": "Предупредить учеников", "en": "Warn students"}, "next": 1, "bonus": "xp_40"}, {"text": {"ru": "Сразу бежать к шуму", "en": "Run to the noise"}, "next": 2, "bonus": None}]},
        {"text": {"ru": "Ученики спасены, но тролль ломает дверь. Нужен план.", "en": "The students are safe, but the troll breaks the door. Need a plan."}, "choices": [{"text": {"ru": "Отвлечь тролля чарами", "en": "Distract with charms"}, "next": "end", "bonus": "spell_random"}, {"text": {"ru": "Увести всех через боковой проход", "en": "Lead everyone through a side passage"}, "next": "end", "bonus": "gold_90"}]},
        {"text": {"ru": "Ты один у входа. Тролль поднимает дубину.", "en": "You stand at the entrance. The troll raises a club."}, "choices": [{"text": {"ru": "Вингардиум Левиоса на дубину", "en": "Wingardium Leviosa on the club"}, "next": "end", "bonus": "xp_140"}, {"text": {"ru": "Позвать профессора", "en": "Call a professor"}, "next": "end", "bonus": "xp_80"}]},
    ],
})
QUESTS["sq_07_patronus"].update({
    "name": {"ru": "Урок Патронуса", "en": "Patronus Lesson"},
    "description": {"ru": "Научи воспоминание светиться достаточно ярко, чтобы отогнать дементора.", "en": "Make a memory shine bright enough to repel a Dementor."},
    "steps": [
        {"text": {"ru": "Люпин просит выбрать воспоминание для тренировки Патронуса.", "en": "Lupin asks you to choose a memory for Patronus practice."}, "choices": [{"text": {"ru": "Самое счастливое", "en": "The happiest one"}, "next": 1, "bonus": "xp_60"}, {"text": {"ru": "Самое злое", "en": "The angriest one"}, "next": 2, "bonus": None}]},
        {"text": {"ru": "Свет появляется, но дрожит. Что усилит заклинание?", "en": "The light appears but trembles. What strengthens it?"}, "choices": [{"text": {"ru": "Сосредоточиться и повторить", "en": "Focus and repeat"}, "next": "end", "bonus": "spell_random"}, {"text": {"ru": "Опустить палочку", "en": "Lower the wand"}, "next": "end", "bonus": "xp_40"}]},
        {"text": {"ru": "Гнев не помогает: дементор давит сильнее.", "en": "Anger does not help; the Dementor presses harder."}, "choices": [{"text": {"ru": "Сменить воспоминание на радостное", "en": "Change to a happy memory"}, "next": "end", "bonus": "xp_100"}, {"text": {"ru": "Отступить", "en": "Retreat"}, "next": "end", "bonus": "gold_50"}]},
    ],
})
QUESTS["sq_08_horcrux"].update({
    "name": {"ru": "След крестража", "en": "Horcrux Trail"},
    "description": {"ru": "Найди тёмный артефакт и реши, кому доверить опасную находку.", "en": "Find a dark artefact and decide whom to trust."},
    "steps": [
        {"text": {"ru": "Амулет в старой шкатулке шепчет твоё имя.", "en": "An amulet in an old box whispers your name."}, "choices": [{"text": {"ru": "Не трогать руками", "en": "Do not touch it"}, "next": 1, "bonus": "xp_80"}, {"text": {"ru": "Надеть амулет", "en": "Wear it"}, "next": 2, "bonus": None}]},
        {"text": {"ru": "Защитный круг сдерживает тёмную магию.", "en": "A protective circle contains the dark magic."}, "choices": [{"text": {"ru": "Отнести профессору", "en": "Bring it to a professor"}, "next": "end", "bonus": "xp_160"}, {"text": {"ru": "Спрятать в библиотеке", "en": "Hide it in the library"}, "next": "end", "bonus": "gold_120"}]},
        {"text": {"ru": "Тьма усиливает урон, но давит на разум.", "en": "Darkness increases power but pressures the mind."}, "choices": [{"text": {"ru": "Снять амулет", "en": "Take it off"}, "next": "end", "bonus": "xp_120"}, {"text": {"ru": "Использовать силу", "en": "Use the power"}, "next": "end", "bonus": "spell_random"}]},
    ],
})
QUESTS["sq_09_deathly"].update({
    "name": {"ru": "Дары Смерти", "en": "Deathly Hallows"},
    "description": {"ru": "Собери подсказки о трёх дарах и выбери, что для тебя важнее: сила, защита или память.", "en": "Gather clues about the three Hallows and choose what matters most."},
    "steps": [
        {"text": {"ru": "На пергаменте нарисован знак: круг, линия и треугольник.", "en": "A parchment shows a circle, line and triangle."}, "choices": [{"text": {"ru": "Искать Бузинную палочку", "en": "Seek the Elder Wand"}, "next": 1, "bonus": None}, {"text": {"ru": "Изучить легенду полностью", "en": "Study the full legend"}, "next": 2, "bonus": "xp_100"}]},
        {"text": {"ru": "Сила палочки опасна: за ней охотятся все.", "en": "The wand's power is dangerous: everyone hunts it."}, "choices": [{"text": {"ru": "Отказаться от власти", "en": "Refuse power"}, "next": "end", "bonus": "xp_180"}, {"text": {"ru": "Продолжить поиски", "en": "Continue searching"}, "next": "end", "bonus": "spell_random"}]},
        {"text": {"ru": "Ты понимаешь: мантия защищает, камень хранит память, палочка даёт силу.", "en": "You understand: cloak protects, stone remembers, wand gives power."}, "choices": [{"text": {"ru": "Выбрать защиту", "en": "Choose protection"}, "next": "end", "bonus": "xp_160"}, {"text": {"ru": "Выбрать мудрость", "en": "Choose wisdom"}, "next": "end", "bonus": "gold_150"}]},
    ],
})
QUESTS["sq_10_final"].update({
    "name": {"ru": "Финальная битва за Хогвартс", "en": "Final Battle for Hogwarts"},
    "description": {"ru": "Последний выбор: защитить учеников, встретить врага лицом к лицу или поддержать союзников.", "en": "The final choice: protect students, face the enemy, or support allies."},
    "steps": [
        {"text": {"ru": "Замок дрожит от взрывов. Где ты нужен больше всего?", "en": "The castle shakes from explosions. Where are you needed most?"}, "choices": [{"text": {"ru": "В Большом зале", "en": "Great Hall"}, "next": 1, "bonus": "xp_120"}, {"text": {"ru": "У моста", "en": "The bridge"}, "next": 2, "bonus": "gold_120"}]},
        {"text": {"ru": "Ученики ранены, враг приближается.", "en": "Students are wounded, the enemy approaches."}, "choices": [{"text": {"ru": "Поставить щит", "en": "Raise a shield"}, "next": "end", "bonus": "xp_220"}, {"text": {"ru": "Контратаковать", "en": "Counterattack"}, "next": "end", "bonus": "spell_random"}]},
        {"text": {"ru": "Мост держится на последней опоре.", "en": "The bridge holds on one last support."}, "choices": [{"text": {"ru": "Укрепить чарами", "en": "Reinforce it with magic"}, "next": "end", "bonus": "xp_200"}, {"text": {"ru": "Эвакуировать всех", "en": "Evacuate everyone"}, "next": "end", "bonus": "gold_180"}]},
    ],
})

# Нормальные названия ежедневных квестов вместо «Ежедневное задание 11».
_DAILY_NAMES = {
    11: ("Патруль коридоров", "Выиграй стычки с мелкими монстрами и наведи порядок."),
    12: ("Дежурство в совятне", "Разберись с нарушителями и собери потерянные письма."),
    13: ("Опасные теплицы", "Победи существ, распугавших учеников у теплиц."),
    14: ("Следы в снегу", "Найди источник странных следов возле замка."),
    15: ("Проверка палочки", "Испытай боевые заклинания на тренировочных целях."),
    16: ("Ночной шум", "Успокой коридоры после отбоя."),
    17: ("Побег пикси", "Верни пикси в клетку, пока они не устроили хаос."),
    18: ("Забытый сундук", "Разберись с проклятым сундуком у лестницы."),
    19: ("Дым из подземелий", "Проверь, что пошло не так на зельеварении."),
    20: ("Тренировка реакции", "Проведи несколько быстрых боёв."),
    21: ("Запретный шёпот", "Проверь подозрительные звуки у Запретного леса."),
    22: ("Помощь первокурсникам", "Очисти путь для младших учеников."),
    23: ("Пыльные доспехи", "Останови ожившие доспехи в галерее."),
    24: ("Испытание смелости", "Пройди опасный маршрут и вернись с отчётом."),
    25: ("Сбор редкостей", "Победи существ и найди полезные материалы."),
    26: ("Сломанная лестница", "Разберись с магической поломкой лестниц."),
    27: ("Крик мандрагоры", "Помоги профессорам успокоить теплицу."),
    28: ("Дуэльный клуб", "Докажи, что готов к настоящей дуэли."),
    29: ("Тени у озера", "Проверь берег Чёрного озера."),
    30: ("За честь факультета", "Заработай награды и поддержи свой факультет."),
}
for _i, (_name, _desc) in _DAILY_NAMES.items():
    _qid = f"dq_{_i:02d}"
    if _qid in QUESTS:
        QUESTS[_qid]["name"] = {"ru": _name, "en": f"Daily Challenge {_i}"}
        QUESTS[_qid]["description"] = {"ru": _desc, "en": "Complete the objective and claim the reward."}

QUESTS["wq_01"]["description"] = {"ru": "Большая недельная цель: побеждай в PvP, получай золото, опыт и шанс на редкий предмет.", "en": "Weekly goal: win PvP battles for gold, XP and a rare item chance."}

def get_quest(quest_id: str) -> dict | None:
    return QUESTS.get(quest_id)


def daily_quest_pool() -> list[str]:
    """Return all quest IDs in the daily pool."""
    return [q["id"] for q in QUESTS.values() if q["type"] == "daily"]


def story_quest_ids() -> list[str]:
    return [q["id"] for q in QUESTS.values() if q["type"] == "story"]


def get_weekly_quest() -> dict:
    return QUESTS["wq_01"]
