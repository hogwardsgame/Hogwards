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


def get_quest(quest_id: str) -> dict | None:
    return QUESTS.get(quest_id)


def daily_quest_pool() -> list[str]:
    """Return all quest IDs in the daily pool."""
    return [q["id"] for q in QUESTS.values() if q["type"] == "daily"]


def story_quest_ids() -> list[str]:
    return [q["id"] for q in QUESTS.values() if q["type"] == "story"]


def get_weekly_quest() -> dict:
    return QUESTS["wq_01"]
