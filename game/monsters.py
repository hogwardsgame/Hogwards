"""
Monsters and PvE zones.
Добавлены новые боссы с фазами боя, уникальные способности, собственный дроп.
"""
import random

class AIPattern:
    AGGRESSIVE = "aggressive"
    DEFENSIVE  = "defensive"
    CUNNING    = "cunning"
    RANDOM     = "random"
    PHASED     = "phased"   # Босс с фазами


ZONES = {
    "forbidden_forest": {
        "id": "forbidden_forest", "min_level": 1,
        "name": {"ru": "Запретный лес"},
        "emoji": "🌲",
        "desc_ru": "Тёмный и загадочный лес рядом с Хогвартсом. Опасен для непосвящённых.",
        "monsters": ["acromantula", "centaur", "hippogriff", "bowtruckle", "niffler", "forest_werewolf", "pixie_swarm"],
        "boss": "aragog",
        "boss_every": 5,
        "main_boss_kills": 25,
        "drop_table": ["lacewing_flies", "flobberworm_mucus"],
    },
    "azkaban": {
        "id": "azkaban", "min_level": 5,
        "name": {"ru": "Азкабан"},
        "emoji": "🏚️",
        "desc_ru": "Страшная тюрьма, охраняемая дементорами.",
        "monsters": ["dementor", "troll", "dark_spirit", "azkaban_wraith"],
        "boss": "senior_dementor",
        "boss_every": 5,
        "main_boss_kills": 25,
        "drop_table": ["bezoar", "gillyweed"],
    },
    "chamber_of_secrets": {
        "id": "chamber_of_secrets", "min_level": 10,
        "name": {"ru": "Тайная комната"},
        "emoji": "🐍",
        "desc_ru": "Секретная камера под Хогвартсом. Обитель Василиска.",
        "monsters": ["basilisk_child", "serpent", "slytherin_ghost", "cave_basilisk"],
        "boss": "basilisk",
        "boss_every": 5,
        "main_boss_kills": 25,
        "drop_table": ["boomslang_skin", "bicorn_horn"],
    },
    "gringotts_caves": {
        "id": "gringotts_caves", "min_level": 15,
        "name": {"ru": "Пещеры Гринготтса"},
        "emoji": "💰",
        "desc_ru": "Подземные хранилища волшебного банка. Охраняются драконами.",
        "monsters": ["guardian_dragon", "goblin", "cursed_relic", "goblin_warrior"],
        "boss": "gringotts_dragon",
        "boss_every": 5,
        "main_boss_kills": 25,
        "drop_table": ["dragon_blood", "mandrake_root"],
    },
    "voldemort_castle": {
        "id": "voldemort_castle", "min_level": 20,
        "name": {"ru": "Замок Волдеморта"},
        "emoji": "💀",
        "desc_ru": "Цитадель тёмного лорда. Крайне опасна.",
        "monsters": ["death_eater", "nagini", "dark_wizard", "dark_knight"],
        "boss": "voldemort",
        "boss_every": 5,
        "main_boss_kills": 25,
        "drop_table": ["phoenix_feather", "dragon_blood"],
    },
    "hogwarts_dungeons": {
        "id": "hogwarts_dungeons", "min_level": 3,
        "name": {"ru": "Подземелья Хогвартса"},
        "emoji": "🕯️",
        "desc_ru": "Тёмные катакомбы под замком. Здесь бродят полтергейсты.",
        "monsters": ["peeves", "dungeon_ghost", "animated_suit", "poltergeist"],
        "boss": "bloody_baron",
        "boss_every": 5,
        "main_boss_kills": 20,
        "drop_table": ["flobberworm_mucus", "lacewing_flies"],
    },
    "black_lake": {
        "id": "black_lake", "min_level": 8,
        "name": {"ru": "Чёрное озеро"},
        "emoji": "🌊",
        "desc_ru": "Тёмные воды, населённые магическими существами.",
        "monsters": ["grindylow", "merrow", "giant_squid_tentacle", "inferius"],
        "boss": "lake_guardian",
        "boss_every": 5,
        "main_boss_kills": 20,
        "drop_table": ["gillyweed", "flobberworm_mucus"],
    },
}

MONSTERS: dict[str, dict] = {
    # ─── Запретный лес ──────────────────────────────────────────────────────────
    "acromantula": {
        "id": "acromantula", "is_boss": False,
        "name": {"ru": "Акромантула"}, "emoji": "🕷️",
        "hp": 80, "attack": 18, "defense": 8, "speed": 12,
        "xp_reward": (12, 35), "gold_reward": (3, 12),
        "ai": AIPattern.AGGRESSIVE,
        "spells": ["bite", "web_shot"],
        "drop_chance": 0.15,
        "desc_ru": "Гигантский говорящий паук. Смертельно ядовит.",
    },
    "centaur": {
        "id": "centaur", "is_boss": False,
        "name": {"ru": "Кентавр"}, "emoji": "🏹",
        "hp": 90, "attack": 15, "defense": 12, "speed": 14,
        "xp_reward": (14, 38), "gold_reward": (4, 14),
        "ai": AIPattern.CUNNING,
        "spells": ["arrow_shot", "prophecy_curse"],
        "drop_chance": 0.15,
        "desc_ru": "Мудрый, но опасный — особенно когда задет его гордость.",
    },
    "hippogriff": {
        "id": "hippogriff", "is_boss": False,
        "name": {"ru": "Гиппогриф"}, "emoji": "🦅",
        "hp": 75, "attack": 20, "defense": 6, "speed": 18,
        "xp_reward": (12, 32), "gold_reward": (3, 12),
        "ai": AIPattern.AGGRESSIVE,
        "spells": ["talon_strike", "dive"],
        "drop_chance": 0.20,
        "desc_ru": "Требует поклона — иначе атакует без предупреждения.",
    },
    "bowtruckle": {
        "id": "bowtruckle", "is_boss": False,
        "name": {"ru": "Боурты"}, "emoji": "🌿",
        "hp": 45, "attack": 10, "defense": 4, "speed": 20,
        "xp_reward": (8, 20), "gold_reward": (2, 8),
        "ai": AIPattern.CUNNING,
        "spells": ["scratch", "hide"],
        "drop_chance": 0.10,
        "desc_ru": "Маленький хранитель деревьев. Быстрый и хитрый.",
    },
    "niffler": {
        "id": "niffler", "is_boss": False,
        "name": {"ru": "Нюхлер"}, "emoji": "🦡",
        "hp": 40, "attack": 8, "defense": 3, "speed": 22,
        "xp_reward": (8, 18), "gold_reward": (8, 25),  # больше золота — любит блестящее
        "ai": AIPattern.CUNNING,
        "spells": ["steal", "scratch"],
        "drop_chance": 0.30,
        "desc_ru": "Обожает золото. Особенно твоё.",
    },
    "aragog": {
        "id": "aragog", "is_boss": True,
        "name": {"ru": "Арагог"}, "emoji": "🕷️👑",
        "hp": 350, "attack": 35, "defense": 20, "speed": 10,
        "xp_reward": (150, 350), "gold_reward": (50, 150),
        "ai": AIPattern.PHASED,
        "phases": [
            {"hp_threshold": 1.0, "spells": ["venom_bite", "web_shot"], "name": "Арагог здоров"},
            {"hp_threshold": 0.5, "spells": ["venom_bite", "web_cocoon", "spider_swarm"], "name": "Арагог разъярён"},
            {"hp_threshold": 0.25, "spells": ["venom_bite", "web_cocoon", "spider_swarm", "call_brood"], "name": "Арагог в ярости"},
        ],
        "spells": ["venom_bite", "web_cocoon", "spider_swarm"],
        "drop_chance": 1.0, "drop_min_rarity": "rare",
        "unique_drop": "gloves_basilisk",
        "desc_ru": "Гигантский акромантул, основатель колонии пауков в Запретном лесу.",
        "strategy_ru": "Используйте огонь — пауки боятся огня! Инцендио и Конфринго особенно эффективны.",
    },

    # ─── Азкабан ────────────────────────────────────────────────────────────────
    "dementor": {
        "id": "dementor", "is_boss": False,
        "name": {"ru": "Дементор"}, "emoji": "👻",
        "hp": 100, "attack": 22, "defense": 10, "speed": 8,
        "xp_reward": (16, 42), "gold_reward": (4, 16),
        "ai": AIPattern.CUNNING,
        "spells": ["soul_drain", "despair"],
        "drop_chance": 0.12,
        "desc_ru": "Высасывает счастье и воспоминания. Патронус — единственная защита.",
        "weakness": "patronus",
    },
    "troll": {
        "id": "troll", "is_boss": False,
        "name": {"ru": "Тролль"}, "emoji": "👹",
        "hp": 150, "attack": 28, "defense": 18, "speed": 5,
        "xp_reward": (18, 45), "gold_reward": (5, 18),
        "ai": AIPattern.AGGRESSIVE,
        "spells": ["club_smash", "roar"],
        "drop_chance": 0.15,
        "desc_ru": "Тупой, но невероятно сильный. Главный совет: беги.",
    },
    "dark_spirit": {
        "id": "dark_spirit", "is_boss": False,
        "name": {"ru": "Тёмный дух"}, "emoji": "🌑",
        "hp": 80, "attack": 20, "defense": 5, "speed": 16,
        "xp_reward": (14, 35), "gold_reward": (4, 14),
        "ai": AIPattern.CUNNING,
        "spells": ["darkness", "soul_drain"],
        "drop_chance": 0.12,
        "desc_ru": "Дух заключённого, поглощённый тьмой Азкабана.",
    },
    "senior_dementor": {
        "id": "senior_dementor", "is_boss": True,
        "name": {"ru": "Старший дементор"}, "emoji": "👻👑",
        "hp": 500, "attack": 40, "defense": 15, "speed": 12,
        "xp_reward": (200, 500), "gold_reward": (80, 200),
        "ai": AIPattern.PHASED,
        "phases": [
            {"hp_threshold": 1.0, "spells": ["dementor_kiss", "soul_drain"], "name": "Охотится"},
            {"hp_threshold": 0.6, "spells": ["dementor_kiss", "soul_drain", "despair"], "name": "Жаждет душу"},
            {"hp_threshold": 0.3, "spells": ["dementor_kiss", "darkness", "soul_drain", "despair"], "name": "Отчаяние"},
        ],
        "spells": ["dementor_kiss", "soul_drain", "despair", "darkness"],
        "drop_chance": 1.0, "drop_min_rarity": "rare",
        "unique_drop": "amulet_horcrux",
        "desc_ru": "Вожак стаи дементоров. Высасывает душу одним поцелуем.",
        "strategy_ru": "Экспекто Патронум значительно снижает его урон. Держите HP выше 50%.",
    },

    # ─── Тайная комната ─────────────────────────────────────────────────────────
    "basilisk_child": {
        "id": "basilisk_child", "is_boss": False,
        "name": {"ru": "Детёныш Василиска"}, "emoji": "🐍",
        "hp": 120, "attack": 30, "defense": 15, "speed": 8,
        "xp_reward": (20, 52), "gold_reward": (6, 20),
        "ai": AIPattern.AGGRESSIVE,
        "spells": ["petrify_gaze", "venom_bite"],
        "drop_chance": 0.18,
        "desc_ru": "Молодой Василиск. Взгляд уже смертелен.",
        "weakness": "rooster_cry",
    },
    "serpent": {
        "id": "serpent", "is_boss": False,
        "name": {"ru": "Змей Слизерина"}, "emoji": "🐍",
        "hp": 100, "attack": 25, "defense": 10, "speed": 15,
        "xp_reward": (18, 45), "gold_reward": (5, 18),
        "ai": AIPattern.CUNNING,
        "spells": ["poison_bite", "constrict"],
        "drop_chance": 0.18,
        "desc_ru": "Слуга Слизерина. Умный и коварный.",
    },
    "slytherin_ghost": {
        "id": "slytherin_ghost", "is_boss": False,
        "name": {"ru": "Призрак Слизерина"}, "emoji": "👤",
        "hp": 70, "attack": 18, "defense": 0, "speed": 20,
        "xp_reward": (14, 35), "gold_reward": (4, 12),
        "ai": AIPattern.CUNNING,
        "spells": ["soul_drain", "darkness"],
        "drop_chance": 0.10,
        "desc_ru": "Призрак давно умершего слизеринца.",
    },
    "basilisk": {
        "id": "basilisk", "is_boss": True,
        "name": {"ru": "Василиск"}, "emoji": "🐍👑",
        "hp": 800, "attack": 55, "defense": 30, "speed": 6,
        "xp_reward": (300, 700), "gold_reward": (120, 300),
        "ai": AIPattern.PHASED,
        "phases": [
            {"hp_threshold": 1.0, "spells": ["killing_gaze", "venom_bite"], "name": "Смотрит"},
            {"hp_threshold": 0.6, "spells": ["killing_gaze", "venom_flood", "tail_sweep"], "name": "Разъярён"},
            {"hp_threshold": 0.3, "spells": ["killing_gaze", "venom_flood", "tail_sweep", "constrict"], "name": "Агония"},
        ],
        "spells": ["killing_gaze", "venom_flood", "tail_sweep"],
        "drop_chance": 1.0, "drop_min_rarity": "very_rare",
        "unique_drop": "gloves_basilisk",
        "desc_ru": "Король змей. Взгляд убивает мгновенно. Только отражение безопасно.",
        "strategy_ru": "Используйте зеркало или закройте глаза! Приор Инкантато отражает его взгляд.",
    },

    # ─── Пещеры Гринготтса ──────────────────────────────────────────────────────
    "guardian_dragon": {
        "id": "guardian_dragon", "is_boss": False,
        "name": {"ru": "Дракон-охранник"}, "emoji": "🐉",
        "hp": 140, "attack": 35, "defense": 20, "speed": 10,
        "xp_reward": (22, 55), "gold_reward": (8, 25),
        "ai": AIPattern.AGGRESSIVE,
        "spells": ["fire_breath", "tail_smash"],
        "drop_chance": 0.20,
        "desc_ru": "Ослеплённый дракон, охраняющий хранилища Гринготтса.",
        "weakness": "loud_noise",
    },
    "goblin": {
        "id": "goblin", "is_boss": False,
        "name": {"ru": "Гоблин-охранник"}, "emoji": "👺",
        "hp": 90, "attack": 20, "defense": 14, "speed": 16,
        "xp_reward": (16, 40), "gold_reward": (10, 35),
        "ai": AIPattern.CUNNING,
        "spells": ["blade_throw", "steal"],
        "drop_chance": 0.25,
        "desc_ru": "Умный и жадный. Особенно злится, когда трогают его золото.",
    },
    "cursed_relic": {
        "id": "cursed_relic", "is_boss": False,
        "name": {"ru": "Проклятая реликвия"}, "emoji": "⚗️",
        "hp": 110, "attack": 25, "defense": 25, "speed": 5,
        "xp_reward": (18, 45), "gold_reward": (6, 20),
        "ai": AIPattern.DEFENSIVE,
        "spells": ["curse_aura", "multiply"],
        "drop_chance": 0.20,
        "desc_ru": "Магический предмет, получивший жизнь от проклятия Гринготтса.",
    },
    "gringotts_dragon": {
        "id": "gringotts_dragon", "is_boss": True,
        "name": {"ru": "Дракон Гринготтса"}, "emoji": "🐉👑",
        "hp": 1000, "attack": 70, "defense": 40, "speed": 8,
        "xp_reward": (400, 900), "gold_reward": (200, 500),
        "ai": AIPattern.PHASED,
        "phases": [
            {"hp_threshold": 1.0, "spells": ["fire_breath", "tail_smash"], "name": "Спокоен"},
            {"hp_threshold": 0.6, "spells": ["inferno", "wing_gust", "tail_smash"], "name": "Разбужен"},
            {"hp_threshold": 0.25, "spells": ["inferno", "wing_gust", "tail_smash", "flame_vortex"], "name": "Бешенство дракона"},
        ],
        "spells": ["inferno", "wing_gust", "treasure_hoard"],
        "drop_chance": 1.0, "drop_min_rarity": "very_rare",
        "unique_drop": "robe_auror",
        "desc_ru": "Венгерская хвосторога. Слепая, но слышит каждый шорох.",
        "strategy_ru": "Будьте тихи! Шумные заклинания увеличивают его ярость. Ледяные заклинания наиболее эффективны.",
    },

    # ─── Замок Волдеморта ───────────────────────────────────────────────────────
    "death_eater": {
        "id": "death_eater", "is_boss": False,
        "name": {"ru": "Пожиратель Смерти"}, "emoji": "🖤",
        "hp": 160, "attack": 40, "defense": 22, "speed": 14,
        "xp_reward": (25, 65), "gold_reward": (8, 28),
        "ai": AIPattern.AGGRESSIVE,
        "spells": ["crucio", "avada_kedavra_weak", "morsmordre"],
        "drop_chance": 0.22,
        "desc_ru": "Фанатичный последователь Тёмного Лорда.",
    },
    "nagini": {
        "id": "nagini", "is_boss": False,
        "name": {"ru": "Нагини"}, "emoji": "🐍🖤",
        "hp": 180, "attack": 45, "defense": 18, "speed": 18,
        "xp_reward": (28, 70), "gold_reward": (10, 32),
        "ai": AIPattern.CUNNING,
        "spells": ["soul_curse", "venom_flood"],
        "drop_chance": 0.20,
        "desc_ru": "Змея Волдеморта. Его крестраж.",
    },
    "dark_wizard": {
        "id": "dark_wizard", "is_boss": False,
        "name": {"ru": "Тёмный волшебник"}, "emoji": "🧙",
        "hp": 170, "attack": 42, "defense": 20, "speed": 16,
        "xp_reward": (26, 65), "gold_reward": (8, 30),
        "ai": AIPattern.CUNNING,
        "spells": ["crucio", "morsmordre", "soul_curse"],
        "drop_chance": 0.20,
        "desc_ru": "Опытный маг тёмных искусств.",
    },
    "voldemort": {
        "id": "voldemort", "is_boss": True,
        "name": {"ru": "Волдеморт"}, "emoji": "💀👑",
        "hp": 2000, "attack": 100, "defense": 60, "speed": 20,
        "xp_reward": (800, 2000), "gold_reward": (400, 1000),
        "ai": AIPattern.PHASED,
        "phases": [
            {"hp_threshold": 1.0, "spells": ["crucio", "avada_kedavra"], "name": "Тёмный лорд"},
            {"hp_threshold": 0.7, "spells": ["avada_kedavra", "crucio", "fiendfyre"], "name": "Гнев Волдеморта"},
            {"hp_threshold": 0.4, "spells": ["avada_kedavra", "fiendfyre", "horcrux_shield"], "name": "Защита крестража"},
            {"hp_threshold": 0.15, "spells": ["avada_kedavra", "fiendfyre", "nagini_call", "soul_rend"], "name": "Агония смерти"},
        ],
        "spells": ["avada_kedavra", "crucio", "fiendfyre", "horcrux_shield"],
        "drop_chance": 1.0, "drop_min_rarity": "epic",
        "unique_drop": "wand_yew_dragon",
        "desc_ru": "Тёмный Лорд. Величайший враг магического мира.",
        "strategy_ru": "Его крестражи восстанавливают HP! Используйте Авада Кедавра или очень редкие заклинания. В финальной фазе — только легендарные заклинания эффективны.",
    },

    # ─── Подземелья Хогвартса ───────────────────────────────────────────────────
    "peeves": {
        "id": "peeves", "is_boss": False,
        "name": {"ru": "Пивз"}, "emoji": "😈",
        "hp": 60, "attack": 12, "defense": 0, "speed": 25,
        "xp_reward": (8, 20), "gold_reward": (2, 8),
        "ai": AIPattern.RANDOM,
        "spells": ["prank", "roar"],
        "drop_chance": 0.08,
        "desc_ru": "Неугомонный полтергейст. Бросается предметами.",
    },
    "dungeon_ghost": {
        "id": "dungeon_ghost", "is_boss": False,
        "name": {"ru": "Призрак подземелья"}, "emoji": "👻",
        "hp": 70, "attack": 15, "defense": 5, "speed": 18,
        "xp_reward": (10, 25), "gold_reward": (2, 8),
        "ai": AIPattern.CUNNING,
        "spells": ["darkness", "soul_drain"],
        "drop_chance": 0.10,
        "desc_ru": "Блуждает в подземельях уже сотни лет.",
    },
    "animated_suit": {
        "id": "animated_suit", "is_boss": False,
        "name": {"ru": "Ожившие доспехи"}, "emoji": "🛡️",
        "hp": 120, "attack": 20, "defense": 30, "speed": 6,
        "xp_reward": (14, 35), "gold_reward": (4, 14),
        "ai": AIPattern.DEFENSIVE,
        "spells": ["club_smash", "defend"],
        "drop_chance": 0.12,
        "desc_ru": "Пустые доспехи, оживлённые тёмной магией.",
    },
    "bloody_baron": {
        "id": "bloody_baron", "is_boss": True,
        "name": {"ru": "Кровавый Барон"}, "emoji": "👻👑",
        "hp": 400, "attack": 38, "defense": 12, "speed": 15,
        "xp_reward": (180, 400), "gold_reward": (80, 200),
        "ai": AIPattern.PHASED,
        "phases": [
            {"hp_threshold": 1.0, "spells": ["soul_drain", "darkness"], "name": "Призрак Слизерина"},
            {"hp_threshold": 0.5, "spells": ["soul_drain", "darkness", "blood_curse"], "name": "Кровавая ярость"},
        ],
        "spells": ["soul_drain", "darkness", "blood_curse"],
        "drop_chance": 1.0, "drop_min_rarity": "rare",
        "unique_drop": "amulet_merlins_seal",
        "desc_ru": "Призрак Слизерина. Единственный, кого боится Пивз.",
        "strategy_ru": "Призраки уязвимы к заклинаниям света — Люмос и Экспекто Патронум наносят +50% урона.",
    },

    # ─── Чёрное озеро ────────────────────────────────────────────────────────────
    "grindylow": {
        "id": "grindylow", "is_boss": False,
        "name": {"ru": "Гриндилоу"}, "emoji": "🌊",
        "hp": 65, "attack": 14, "defense": 6, "speed": 16,
        "xp_reward": (10, 25), "gold_reward": (3, 10),
        "ai": AIPattern.AGGRESSIVE,
        "spells": ["constrict", "bite"],
        "drop_chance": 0.12,
        "desc_ru": "Водяной демон с длинными пальцами. Хватает за лодыжки.",
    },
    "merrow": {
        "id": "merrow", "is_boss": False,
        "name": {"ru": "Мерроу"}, "emoji": "🧜",
        "hp": 85, "attack": 18, "defense": 8, "speed": 14,
        "xp_reward": (12, 30), "gold_reward": (4, 14),
        "ai": AIPattern.CUNNING,
        "spells": ["water_jet", "song_lure"],
        "drop_chance": 0.15,
        "desc_ru": "Русалочий народ озера. Не дружелюбны к чужакам.",
    },
    "giant_squid_tentacle": {
        "id": "giant_squid_tentacle", "is_boss": False,
        "name": {"ru": "Щупальце гигантского кальмара"}, "emoji": "🦑",
        "hp": 100, "attack": 22, "defense": 15, "speed": 8,
        "xp_reward": (14, 35), "gold_reward": (4, 14),
        "ai": AIPattern.AGGRESSIVE,
        "spells": ["constrict", "slam"],
        "drop_chance": 0.12,
        "desc_ru": "Часть огромного кальмара, дремлющего на дне озера.",
    },
    "lake_guardian": {
        "id": "lake_guardian", "is_boss": True,
        "name": {"ru": "Страж Чёрного озера"}, "emoji": "🌊👑",
        "hp": 600, "attack": 48, "defense": 25, "speed": 10,
        "xp_reward": (250, 600), "gold_reward": (100, 250),
        "ai": AIPattern.PHASED,
        "phases": [
            {"hp_threshold": 1.0, "spells": ["water_jet", "constrict"], "name": "Глубинный страж"},
            {"hp_threshold": 0.5, "spells": ["water_jet", "constrict", "tidal_wave"], "name": "Пробудившийся"},
        ],
        "spells": ["water_jet", "constrict", "tidal_wave"],
        "drop_chance": 1.0, "drop_min_rarity": "rare",
        "unique_drop": "amulet_time_turner",
        "desc_ru": "Древнее существо, обитающее в глубинах Чёрного озера.",
        "strategy_ru": "Молниеносные заклинания наносят двойной урон водным существам.",
    },

    # ─── Новые монстры (дополнение) ─────────────────────────────────────────────
    "forest_werewolf": {
        "id": "forest_werewolf", "is_boss": False,
        "name": {"ru": "Оборотень"}, "emoji": "🐺",
        "hp": 95, "attack": 22, "defense": 9, "speed": 16,
        "xp_reward": (16, 40), "gold_reward": (5, 16),
        "ai": AIPattern.AGGRESSIVE,
        "spells": ["bite", "scratch"],
        "drop_chance": 0.18,
        "desc_ru": "Свирепый зверь, рыщущий по лесу в полнолуние.",
    },
    "pixie_swarm": {
        "id": "pixie_swarm", "is_boss": False,
        "name": {"ru": "Рой пикси"}, "emoji": "🧚",
        "hp": 60, "attack": 14, "defense": 6, "speed": 20,
        "xp_reward": (10, 28), "gold_reward": (3, 10),
        "ai": AIPattern.CUNNING,
        "spells": ["scratch", "steal"],
        "drop_chance": 0.2,
        "desc_ru": "Назойливые синие проказники, нападающие стаей.",
    },
    "azkaban_wraith": {
        "id": "azkaban_wraith", "is_boss": False,
        "name": {"ru": "Призрак Азкабана"}, "emoji": "👻",
        "hp": 110, "attack": 24, "defense": 10, "speed": 13,
        "xp_reward": (20, 48), "gold_reward": (6, 20),
        "ai": AIPattern.CUNNING,
        "spells": ["soul_drain", "despair"],
        "drop_chance": 0.18,
        "desc_ru": "Истерзанная душа, навеки запертая в стенах тюрьмы.",
    },
    "cave_basilisk": {
        "id": "cave_basilisk", "is_boss": False,
        "name": {"ru": "Пещерный василиск"}, "emoji": "🐉",
        "hp": 130, "attack": 28, "defense": 14, "speed": 11,
        "xp_reward": (24, 55), "gold_reward": (8, 25),
        "ai": AIPattern.AGGRESSIVE,
        "spells": ["venom_bite", "petrify_gaze"],
        "drop_chance": 0.2,
        "desc_ru": "Молодой василиск, скрывающийся в тёмных пещерах.",
    },
    "goblin_warrior": {
        "id": "goblin_warrior", "is_boss": False,
        "name": {"ru": "Гоблин-воин"}, "emoji": "👺",
        "hp": 105, "attack": 25, "defense": 16, "speed": 12,
        "xp_reward": (22, 50), "gold_reward": (12, 35),
        "ai": AIPattern.AGGRESSIVE,
        "spells": ["blade_throw", "slam"],
        "drop_chance": 0.22,
        "desc_ru": "Свирепый страж сокровищниц Гринготтса.",
    },
    "dark_knight": {
        "id": "dark_knight", "is_boss": False,
        "name": {"ru": "Тёмный рыцарь"}, "emoji": "🗡️",
        "hp": 140, "attack": 30, "defense": 18, "speed": 13,
        "xp_reward": (28, 60), "gold_reward": (10, 30),
        "ai": AIPattern.CUNNING,
        "spells": ["blade_throw", "curse_aura"],
        "drop_chance": 0.2,
        "desc_ru": "Зачарованные доспехи, служащие Тёмному Лорду.",
    },
    "inferius": {
        "id": "inferius", "is_boss": False,
        "name": {"ru": "Инферий"}, "emoji": "🧟",
        "hp": 120, "attack": 26, "defense": 12, "speed": 9,
        "xp_reward": (24, 54), "gold_reward": (7, 22),
        "ai": AIPattern.AGGRESSIVE,
        "spells": ["constrict", "darkness"],
        "drop_chance": 0.18,
        "desc_ru": "Восставший мертвец, поднятый тёмной магией из глубин озера.",
    },
    "poltergeist": {
        "id": "poltergeist", "is_boss": False,
        "name": {"ru": "Полтергейст"}, "emoji": "💀",
        "hp": 85, "attack": 19, "defense": 8, "speed": 17,
        "xp_reward": (15, 38), "gold_reward": (5, 15),
        "ai": AIPattern.CUNNING,
        "spells": ["prank", "multiply"],
        "drop_chance": 0.18,
        "desc_ru": "Озорной дух, обожающий устраивать хаос в подземельях.",
    },
}

# ── Библиотека заклинаний монстров ─────────────────────────────────────────────
MONSTER_SPELLS = {
    "bite":              {"damage": 20, "effect": None},
    "web_shot":          {"damage": 15, "effect": "slow"},
    "arrow_shot":        {"damage": 22, "effect": None},
    "prophecy_curse":    {"damage": 0,  "effect": "curse"},
    "talon_strike":      {"damage": 25, "effect": None},
    "dive":              {"damage": 30, "effect": "stun"},
    "scratch":           {"damage": 12, "effect": None},
    "hide":              {"damage": 0,  "effect": "block"},
    "steal":             {"damage": 10, "effect": "disarm"},
    "venom_bite":        {"damage": 20, "effect": "poison"},
    "web_cocoon":        {"damage": 10, "effect": "freeze"},
    "spider_swarm":      {"damage": 40, "effect": "blind"},
    "call_brood":        {"damage": 25, "effect": "poison"},
    "soul_drain":        {"damage": 25, "effect": "curse"},
    "despair":           {"damage": 15, "effect": "confuse"},
    "club_smash":        {"damage": 35, "effect": "stun"},
    "roar":              {"damage": 0,  "effect": "blind"},
    "dementor_kiss":     {"damage": 60, "effect": "curse"},
    "darkness":          {"damage": 0,  "effect": "blind"},
    "petrify_gaze":      {"damage": 0,  "effect": "stun"},
    "poison_bite":       {"damage": 18, "effect": "poison"},
    "constrict":         {"damage": 20, "effect": "freeze"},
    "killing_gaze":      {"damage": 80, "effect": "stun"},
    "venom_flood":       {"damage": 35, "effect": "poison"},
    "tail_sweep":        {"damage": 45, "effect": "stun"},
    "fire_breath":       {"damage": 40, "effect": "burn"},
    "tail_smash":        {"damage": 35, "effect": "stun"},
    "blade_throw":       {"damage": 25, "effect": None},
    "inferno":           {"damage": 70, "effect": "burn"},
    "wing_gust":         {"damage": 30, "effect": "blind"},
    "treasure_hoard":    {"damage": 50, "effect": None},
    "flame_vortex":      {"damage": 80, "effect": "burn"},
    "crucio":            {"damage": 40, "effect": "curse"},
    "avada_kedavra_weak": {"damage": 60, "effect": None},
    "morsmordre":        {"damage": 35, "effect": "burn"},
    "soul_curse":        {"damage": 30, "effect": "curse"},
    "avada_kedavra":     {"damage": 0,  "effect": "instant_kill", "chance": 0.3},
    "fiendfyre":         {"damage": 80, "effect": "burn"},
    "horcrux_shield":    {"damage": 0,  "effect": "shield"},
    "nagini_call":       {"damage": 45, "effect": "poison"},
    "soul_rend":         {"damage": 90, "effect": "curse"},
    "blood_curse":       {"damage": 30, "effect": "burn"},
    "prank":             {"damage": 10, "effect": "confuse"},
    "defend":            {"damage": 0,  "effect": "block"},
    "curse_aura":        {"damage": 20, "effect": "curse"},
    "multiply":          {"damage": 25, "effect": None},
    "water_jet":         {"damage": 28, "effect": "slow"},
    "song_lure":         {"damage": 0,  "effect": "confuse"},
    "slam":              {"damage": 32, "effect": "stun"},
    "tidal_wave":        {"damage": 55, "effect": "stun"},
}


def get_monster(monster_id: str) -> dict | None:
    return MONSTERS.get(monster_id)


def get_zone(zone_id: str) -> dict | None:
    return ZONES.get(zone_id)


def available_zones(player_level: int) -> list[dict]:
    return [z for z in ZONES.values() if z["min_level"] <= player_level]


def pick_monster(zone_id: str, is_boss: bool = False) -> dict | None:
    zone = ZONES.get(zone_id)
    if not zone:
        return None
    if is_boss:
        boss_id = zone["boss"]
        return MONSTERS.get(boss_id)
    candidates = [MONSTERS[m] for m in zone["monsters"] if m in MONSTERS]
    return random.choice(candidates) if candidates else None


def get_monster_phase(monster: dict, current_hp: int) -> dict | None:
    """Определить текущую фазу боя босса."""
    if monster.get("ai") != AIPattern.PHASED:
        return None
    max_hp = monster["hp"]
    hp_ratio = current_hp / max_hp
    phases = monster.get("phases", [])
    active_phase = None
    for phase in phases:
        if hp_ratio <= phase["hp_threshold"]:
            active_phase = phase
    return active_phase or (phases[0] if phases else None)


def monster_ai_action(monster: dict, current_hp: int, player_hp: int, turn: int) -> dict:
    """Выбрать действие монстра с учётом фаз."""
    pattern = monster.get("ai", AIPattern.AGGRESSIVE)
    max_hp  = monster["hp"]
    hp_ratio = current_hp / max_hp

    # Фазовый AI для боссов
    if pattern == AIPattern.PHASED:
        phase = get_monster_phase(monster, current_hp)
        spells = phase["spells"] if phase else monster.get("spells", [])
        # В низкой фазе HP — с шансом 20% использовать самое мощное
        if hp_ratio < 0.3:
            spell_id = spells[-1]  # последнее заклинание в фазе самое мощное
        else:
            spell_id = random.choice(spells)
        return {
            "action": "attack",
            "spell": MONSTER_SPELLS.get(spell_id, {"damage": monster["attack"], "effect": None}),
            "spell_id": spell_id,
            "phase_name": phase["name"] if phase else "",
        }

    spells = monster.get("spells", [])

    if pattern == AIPattern.AGGRESSIVE:
        spell_id = random.choice(spells)
        return {"action": "attack", "spell": MONSTER_SPELLS.get(spell_id, {"damage": monster["attack"], "effect": None}), "spell_id": spell_id}

    elif pattern == AIPattern.DEFENSIVE:
        if turn % 2 == 0 or hp_ratio < 0.4:
            return {"action": "defend", "spell": None, "spell_id": "defend"}
        spell_id = random.choice(spells)
        return {"action": "attack", "spell": MONSTER_SPELLS.get(spell_id, {"damage": monster["attack"], "effect": None}), "spell_id": spell_id}

    elif pattern == AIPattern.CUNNING:
        debuff_spells = [s for s in spells if MONSTER_SPELLS.get(s, {}).get("effect")]
        if player_hp > 60 and debuff_spells:
            spell_id = random.choice(debuff_spells)
        else:
            spell_id = random.choice(spells)
        return {"action": "attack", "spell": MONSTER_SPELLS.get(spell_id, {"damage": monster["attack"], "effect": None}), "spell_id": spell_id}

    else:  # RANDOM
        if random.random() < 0.15 and hp_ratio < 0.5:
            return {"action": "defend", "spell": None, "spell_id": "defend"}
        spell_id = random.choice(spells)
        return {"action": "attack", "spell": MONSTER_SPELLS.get(spell_id, {"damage": monster["attack"], "effect": None}), "spell_id": spell_id}
