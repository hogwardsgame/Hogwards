"""
Items system: equipment, consumables, cosmetics, ingredients.
50+ именных предметов с описаниями, редкостями и характеристиками.
"""
import random

# ── Редкости ───────────────────────────────────────────────────────────────────
RARITIES = [
    ("common",     "⬜", (1,  3),   0.40),
    ("uncommon",   "🟢", (4,  7),   0.25),
    ("rare",       "🔵", (8,  14),  0.15),
    ("very_rare",  "🟣", (15, 24),  0.10),
    ("epic",       "🟠", (25, 39),  0.06),
    ("legendary",  "🔴", (40, 60),  0.03),
    ("mythical",   "⭐", (61, 100), 0.005),
    ("abyssal",    "💀", (101,150), 0.001),
]

RARITY_NAMES    = {r[0]: r[1] for r in RARITIES}
RARITY_STAT_RANGE = {r[0]: r[2] for r in RARITIES}
RARITY_SHOP_CHANCE = {r[0]: r[3] for r in RARITIES}

RARITY_NAMES_RU = {
    "common":    "Обычный",
    "uncommon":  "Необычный",
    "rare":      "Редкий",
    "very_rare": "Очень редкий",
    "epic":      "Эпический",
    "legendary": "Легендарный",
    "mythical":  "Мифический",
    "abyssal":   "Бездонный",
}

# ── Слоты снаряжения ───────────────────────────────────────────────────────────
EQUIPMENT_SLOTS = {
    "wand":   "attack",
    "robe":   "defense",
    "amulet": "max_mana",
    "ring":   "luck",
    "hat":    "speed",
    "boots":  "speed",
    "gloves": "attack",
}

SLOT_EMOJI = {
    "wand":   "🪄",
    "robe":   "🧥",
    "amulet": "📿",
    "ring":   "💍",
    "hat":    "🎩",
    "boots":  "👢",
    "gloves": "🧤",
}

# ── Каталог предметов ──────────────────────────────────────────────────────────
ITEMS: dict[str, dict] = {}

def _equip(item_id, name_ru, slot, rarity, desc_ru="", emoji=None):
    stat_range = RARITY_STAT_RANGE[rarity]
    return {
        "id": item_id, "type": "equipment", "slot": slot,
        "rarity": rarity, "emoji": emoji or RARITY_NAMES[rarity],
        "name": {"ru": name_ru},
        "desc_ru": desc_ru,
        "stat": EQUIPMENT_SLOTS[slot],
        "stat_min": stat_range[0], "stat_max": stat_range[1],
    }

# ─── ИМЕННЫЕ ПРЕДМЕТЫ (50+) ───────────────────────────────────────────────────

# Палочки
NAMED_WANDS = {
    "wand_holly_phoenix": _equip(
        "wand_holly_phoenix", "Палочка из падуба с пером феникса", "wand", "epic",
        "Легендарная палочка — принадлежала Гарри Поттеру. Идеальна для редких заклинаний.", "🪄"),
    "wand_elder": _equip(
        "wand_elder", "Бузинная палочка", "wand", "mythical",
        "Неодолимая из Даров Смерти. Усиливает все атаки на 25%.", "☠️"),
    "wand_yew_dragon": _equip(
        "wand_yew_dragon", "Палочка из тиса с сердцевиной дракона", "wand", "legendary",
        "Тёмная палочка — сила дракона во плоти. Принадлежала Волдеморту.", "🐉"),
    "wand_vine_unicorn": _equip(
        "wand_vine_unicorn", "Палочка из лозы с волосом единорога", "wand", "rare",
        "Мягкая и отзывчивая палочка Гермионы. Отлично подходит для защитных заклинаний.", "🦄"),
    "wand_oak_dragon": _equip(
        "wand_oak_dragon", "Дубовая палочка с сердцевиной дракона", "wand", "very_rare",
        "Мощная и капризная. Усиливает урон на 15%.", "🌳"),
    "wand_blackthorn": _equip(
        "wand_blackthorn", "Палочка из тёрна", "wand", "epic",
        "Грозная боевая палочка. Предпочитает сильных и смелых волшебников.", "⚡"),
    "wand_elder_thestral": _equip(
        "wand_elder_thestral", "Бузинная палочка с волосом фестрала", "wand", "legendary",
        "Легендарнейшая палочка, дарующая невероятную мощь своему истинному хозяину.", "🪄"),
    "wand_willow_unicorn": _equip(
        "wand_willow_unicorn", "Ивовая палочка с волосом единорога", "wand", "rare",
        "Гибкая и верная палочка, особенно хороша в исцеляющих чарах.", "🌿"),
}
ITEMS.update(NAMED_WANDS)

# Мантии
NAMED_ROBES = {
    "robe_invisibility_cloak": {
        "id": "robe_invisibility_cloak", "type": "equipment", "slot": "robe",
        "rarity": "mythical", "emoji": "🌫️",
        "name": {"ru": "Мантия-невидимка"},
        "desc_ru": "Один из Даров Смерти. Даёт уклонение 15% в бою.",
        "stat": "defense", "stat_min": 61, "stat_max": 80,
        "special": "evasion_15",
    },
    "robe_death_eater": {
        "id": "robe_death_eater", "type": "equipment", "slot": "robe",
        "rarity": "epic", "emoji": "🖤",
        "name": {"ru": "Мантия Пожирателя Смерти"},
        "desc_ru": "Внушает страх врагам. -10% к атаке противника.",
        "stat": "defense", "stat_min": 25, "stat_max": 39,
        "special": "intimidate_10",
    },
    "robe_auror": {
        "id": "robe_auror", "type": "equipment", "slot": "robe",
        "rarity": "legendary", "emoji": "🔵",
        "name": {"ru": "Мантия Авроры"},
        "desc_ru": "Официальное снаряжение охотника на тёмных магов.",
        "stat": "defense", "stat_min": 40, "stat_max": 55,
    },
    "robe_headmaster": {
        "id": "robe_headmaster", "type": "equipment", "slot": "robe",
        "rarity": "legendary", "emoji": "🏫",
        "name": {"ru": "Мантия Директора Хогвартса"},
        "desc_ru": "Символ мудрости и власти. +15 к мане.",
        "stat": "defense", "stat_min": 40, "stat_max": 60,
        "bonus_mana": 15,
    },
}
ITEMS.update(NAMED_ROBES)

# Амулеты
NAMED_AMULETS = {
    "amulet_philosopher_stone": {
        "id": "amulet_philosopher_stone", "type": "equipment", "slot": "amulet",
        "rarity": "mythical", "emoji": "🔮",
        "name": {"ru": "Осколок Философского камня"},
        "desc_ru": "Фрагмент легендарного камня. Восстанавливает 5 HP в ход пассивно.",
        "stat": "max_mana", "stat_min": 70, "stat_max": 100,
        "special": "regen_5",
    },
    "amulet_horcrux": {
        "id": "amulet_horcrux", "type": "equipment", "slot": "amulet",
        "rarity": "epic", "emoji": "💀",
        "name": {"ru": "Медальон Слизерина"},
        "desc_ru": "Один из крестражей Волдеморта. Тёмная магия — +20% к урону.",
        "stat": "max_mana", "stat_min": 30, "stat_max": 45,
        "special": "dark_boost_20",
    },
    "amulet_time_turner": {
        "id": "amulet_time_turner", "type": "equipment", "slot": "amulet",
        "rarity": "legendary", "emoji": "⏳",
        "name": {"ru": "Маховик времени"},
        "desc_ru": "Даёт шанс 10% повторить заклинание бесплатно.",
        "stat": "max_mana", "stat_min": 45, "stat_max": 60,
        "special": "double_cast_10",
    },
    "amulet_merlins_seal": {
        "id": "amulet_merlins_seal", "type": "equipment", "slot": "amulet",
        "rarity": "legendary", "emoji": "🌟",
        "name": {"ru": "Печать Мерлина"},
        "desc_ru": "Символ величайшего волшебника древности.",
        "stat": "max_mana", "stat_min": 50, "stat_max": 70,
    },
}
ITEMS.update(NAMED_AMULETS)

# Кольца
NAMED_RINGS = {
    "ring_resurrection_stone": {
        "id": "ring_resurrection_stone", "type": "equipment", "slot": "ring",
        "rarity": "mythical", "emoji": "💎",
        "name": {"ru": "Перстень с Воскрешающим камнем"},
        "desc_ru": "Второй Дар Смерти. При смерти в бою шанс 20% выжить с 1 HP.",
        "stat": "luck", "stat_min": 70, "stat_max": 100,
        "special": "cheat_death_20",
    },
    "ring_gaunt": {
        "id": "ring_gaunt", "type": "equipment", "slot": "ring",
        "rarity": "epic", "emoji": "💍",
        "name": {"ru": "Кольцо Гонтов"},
        "desc_ru": "Родовое кольцо дома Слизерина. +15 удачи.",
        "stat": "luck", "stat_min": 25, "stat_max": 40,
    },
    "ring_dumbledore": {
        "id": "ring_dumbledore", "type": "equipment", "slot": "ring",
        "rarity": "legendary", "emoji": "🔵",
        "name": {"ru": "Кольцо Дамблдора"},
        "desc_ru": "Передаёт мудрость великого директора. +10% к эффектам лечения.",
        "stat": "luck", "stat_min": 40, "stat_max": 60,
        "special": "heal_boost_10",
    },
}
ITEMS.update(NAMED_RINGS)

# Шляпы / головные уборы
NAMED_HATS = {
    "hat_sorting": {
        "id": "hat_sorting", "type": "equipment", "slot": "hat",
        "rarity": "legendary", "emoji": "🎩",
        "name": {"ru": "Распределяющая шляпа"},
        "desc_ru": "Сама выбирает лучшее заклинание для ситуации (пассивно).",
        "stat": "speed", "stat_min": 45, "stat_max": 60,
        "special": "auto_spell",
    },
    "hat_moody": {
        "id": "hat_moody", "type": "equipment", "slot": "hat",
        "rarity": "epic", "emoji": "👁️",
        "name": {"ru": "Шляпа с магическим глазом"},
        "desc_ru": "Магический глаз Грозного Глаза. +20% к уклонению.",
        "stat": "speed", "stat_min": 28, "stat_max": 40,
        "special": "evasion_20",
    },
}
ITEMS.update(NAMED_HATS)

# Сапоги и перчатки
NAMED_BOOTS_GLOVES = {
    "boots_seven_league": {
        "id": "boots_seven_league", "type": "equipment", "slot": "boots",
        "rarity": "very_rare", "emoji": "👢",
        "name": {"ru": "Семимильные сапоги"},
        "desc_ru": "Легендарная обувь. Увеличивает скорость на 30%.",
        "stat": "speed", "stat_min": 18, "stat_max": 26,
    },
    "gloves_basilisk": {
        "id": "gloves_basilisk", "type": "equipment", "slot": "gloves",
        "rarity": "epic", "emoji": "🧤",
        "name": {"ru": "Перчатки из кожи Василиска"},
        "desc_ru": "Пропитаны ядом Василиска. Атаки имеют шанс отравить.",
        "stat": "attack", "stat_min": 28, "stat_max": 42,
        "special": "poison_on_hit_15",
    },
    "gloves_dragon_hide": {
        "id": "gloves_dragon_hide", "type": "equipment", "slot": "gloves",
        "rarity": "rare", "emoji": "🐉",
        "name": {"ru": "Перчатки из драконьей кожи"},
        "desc_ru": "Стандартная защита волшебника. Огнестойкость.",
        "stat": "attack", "stat_min": 10, "stat_max": 16,
    },
}
ITEMS.update(NAMED_BOOTS_GLOVES)

# ─── РАСХОДНИКИ (зелья) ────────────────────────────────────────────────────────
CONSUMABLES = {
    "hp_potion_small": {
        "id": "hp_potion_small", "type": "consumable", "rarity": "common",
        "emoji": "🧪", "name": {"ru": "Малое зелье HP"},
        "desc_ru": "Восстанавливает 30 HP", "effect": "hp", "value": 30, "price": 40,
    },
    "hp_potion_medium": {
        "id": "hp_potion_medium", "type": "consumable", "rarity": "uncommon",
        "emoji": "🧪", "name": {"ru": "Среднее зелье HP"},
        "desc_ru": "Восстанавливает 70 HP", "effect": "hp", "value": 70, "price": 90,
    },
    "hp_potion_large": {
        "id": "hp_potion_large", "type": "consumable", "rarity": "rare",
        "emoji": "🧪", "name": {"ru": "Большое зелье HP"},
        "desc_ru": "Восстанавливает 150 HP", "effect": "hp", "value": 150, "price": 200,
    },
    "hp_potion_max": {
        "id": "hp_potion_max", "type": "consumable", "rarity": "epic",
        "emoji": "❤️", "name": {"ru": "Зелье полного исцеления"},
        "desc_ru": "Полностью восстанавливает HP", "effect": "hp_full", "value": 9999, "price": 800,
    },
    "mana_potion": {
        "id": "mana_potion", "type": "consumable", "rarity": "uncommon",
        "emoji": "💧", "name": {"ru": "Зелье маны"},
        "desc_ru": "Восстанавливает 60 маны", "effect": "mana", "value": 60, "price": 60,
    },
    "mana_potion_large": {
        "id": "mana_potion_large", "type": "consumable", "rarity": "rare",
        "emoji": "💙", "name": {"ru": "Большое зелье маны"},
        "desc_ru": "Восстанавливает 150 маны", "effect": "mana", "value": 150, "price": 150,
    },
    "strength_potion": {
        "id": "strength_potion", "type": "consumable", "rarity": "rare",
        "emoji": "⚡", "name": {"ru": "Зелье силы"},
        "desc_ru": "+20% к атаке на 3 хода", "effect": "attack_boost",
        "value": 0.20, "duration": 3, "price": 120,
    },
    "luck_potion": {
        "id": "luck_potion", "type": "consumable", "rarity": "rare",
        "emoji": "🍀", "name": {"ru": "Зелье удачи (Феликс Фелицис)"},
        "desc_ru": "+50% к удаче на 1 час", "effect": "luck_boost",
        "value": 0.50, "duration": 3600, "price": 300,
    },
    "shield_potion": {
        "id": "shield_potion", "type": "consumable", "rarity": "uncommon",
        "emoji": "🛡️", "name": {"ru": "Зелье щита"},
        "desc_ru": "+15% к защите на 3 хода", "effect": "defense_boost",
        "value": 0.15, "duration": 3, "price": 100,
    },
    "xp_potion": {
        "id": "xp_potion", "type": "consumable", "rarity": "epic",
        "emoji": "✨", "name": {"ru": "Зелье опыта"},
        "desc_ru": "+50% к получаемому опыту на 30 минут", "effect": "xp_boost",
        "value": 0.50, "duration": 1800, "price": 500,
    },
    "antidote": {
        "id": "antidote", "type": "consumable", "rarity": "uncommon",
        "emoji": "💚", "name": {"ru": "Противоядие"},
        "desc_ru": "Снимает отравление и горение", "effect": "cleanse",
        "value": 1, "price": 80,
    },
    "polyjuice_potion": {
        "id": "polyjuice_potion", "type": "consumable", "rarity": "legendary",
        "emoji": "🫗", "name": {"ru": "Оборотное зелье"},
        "desc_ru": "Копирует характеристики случайного игрока на 2 хода в бою",
        "effect": "copycat", "value": 1, "price": 1000,
    },
    "veritaserum": {
        "id": "veritaserum", "type": "consumable", "rarity": "epic",
        "emoji": "💎", "name": {"ru": "Правдосыворотка"},
        "desc_ru": "В PvP раскрывает все заклинания противника на следующий ход",
        "effect": "reveal", "value": 1, "price": 600,
    },
    "draught_living_death": {
        "id": "draught_living_death", "type": "consumable", "rarity": "legendary",
        "emoji": "🫀", "name": {"ru": "Зелье живой смерти"},
        "desc_ru": "В бою погружает врага в сон на 2 хода (стан)",
        "effect": "battle_stun", "value": 2, "price": 900,
    },
    "mandrake_potion": {
        "id": "mandrake_potion", "type": "consumable", "rarity": "rare",
        "emoji": "🌿", "name": {"ru": "Восстановительное зелье мандрагоры"},
        "desc_ru": "Снимает окаменение и петрификацию", "effect": "restore",
        "value": 1, "price": 250,
    },
}
ITEMS.update(CONSUMABLES)

# ─── ИНГРЕДИЕНТЫ для зельеварения ─────────────────────────────────────────────
INGREDIENTS = {
    "lacewing_flies": {
        "id": "lacewing_flies", "type": "ingredient", "rarity": "common",
        "emoji": "🦋", "name": {"ru": "Мухи-кружевницы"}, "price": 15,
    },
    "boomslang_skin": {
        "id": "boomslang_skin", "type": "ingredient", "rarity": "uncommon",
        "emoji": "🐍", "name": {"ru": "Кожа бумсланга"}, "price": 40,
    },
    "flobberworm_mucus": {
        "id": "flobberworm_mucus", "type": "ingredient", "rarity": "common",
        "emoji": "🐛", "name": {"ru": "Слизь флоббервурма"}, "price": 10,
    },
    "bicorn_horn": {
        "id": "bicorn_horn", "type": "ingredient", "rarity": "rare",
        "emoji": "🦄", "name": {"ru": "Рог бикорна"}, "price": 80,
    },
    "bezoar": {
        "id": "bezoar", "type": "ingredient", "rarity": "rare",
        "emoji": "💠", "name": {"ru": "Безоар"}, "price": 100,
    },
    "gillyweed": {
        "id": "gillyweed", "type": "ingredient", "rarity": "uncommon",
        "emoji": "🌿", "name": {"ru": "Жабрник"}, "price": 50,
    },
    "mandrake_root": {
        "id": "mandrake_root", "type": "ingredient", "rarity": "uncommon",
        "emoji": "🌱", "name": {"ru": "Корень мандрагоры"}, "price": 45,
    },
    "dragon_blood": {
        "id": "dragon_blood", "type": "ingredient", "rarity": "very_rare",
        "emoji": "🐉", "name": {"ru": "Кровь дракона"}, "price": 200,
    },
    "phoenix_feather": {
        "id": "phoenix_feather", "type": "ingredient", "rarity": "epic",
        "emoji": "🔥", "name": {"ru": "Перо феникса"}, "price": 500,
    },
    "dittany": {
        "id": "dittany", "type": "ingredient", "rarity": "rare",
        "emoji": "🌼", "name": {"ru": "Диттани"}, "price": 90,
    },
}
ITEMS.update(INGREDIENTS)

# ─── ОСОБЫЕ / ЛЕГЕНДАРНЫЕ ПРЕДМЕТЫ (лес, чёрный рынок, крестражи) ──────────────
# Названия на 5 языках — чтобы игроки видели читаемое имя, а не item_id.
SPECIAL_ITEMS = {
    "basilisk_fang": {
        "id": "basilisk_fang", "type": "key", "rarity": "epic", "emoji": "🦷",
        "name": {"ru": "Клык василиска", "en": "Basilisk Fang", "es": "Colmillo de basilisco",
                 "de": "Basilisken-Reißzahn", "pt": "Presa de basilisco"},
        "desc_ru": "Единственное, что уничтожает крестражи. Ищи в Запретном лесу или у боссов.",
        "desc_en": "The only thing that destroys Horcruxes. Found in the Forbidden Forest or from bosses.",
        "desc_es": "Lo único que destruye Horrocruxes. Búscalo en el Bosque Prohibido o en jefes.",
        "desc_de": "Das Einzige, was Horkruxe zerstört. Im Verbotenen Wald oder bei Bossen zu finden.",
        "desc_pt": "A única coisa que destrói Horcruxes. Procure na Floresta Proibida ou em chefes.",
    },
    "cloak_invisibility": {
        "id": "cloak_invisibility", "type": "equipment", "slot": "robe", "rarity": "legendary", "emoji": "🧥",
        "name": {"ru": "Мантия-невидимка", "en": "Cloak of Invisibility", "es": "Capa de invisibilidad",
                 "de": "Tarnumhang", "pt": "Capa da invisibilidade"},
        "stat": "defense", "stat_value": 45,
        "desc_ru": "Один из Даров Смерти. Скрывает от любых глаз. +45 к защите.",
        "desc_en": "One of the Deathly Hallows. Hides you from all eyes. +45 defense.",
        "desc_es": "Una de las Reliquias de la Muerte. Te oculta de toda mirada. +45 defensa.",
        "desc_de": "Eines der Heiligtümer des Todes. Verbirgt dich vor allen Augen. +45 Verteidigung.",
        "desc_pt": "Uma das Relíquias da Morte. Esconde de todos os olhos. +45 defesa.",
    },
    "marauders_map": {
        "id": "marauders_map", "type": "key", "rarity": "rare", "emoji": "🗺️",
        "name": {"ru": "Карта Мародёров", "en": "Marauder's Map", "es": "Mapa del Merodeador",
                 "de": "Karte des Rumtreibers", "pt": "Mapa do Maroto"},
        "desc_ru": "Показывает всех в Хогвартсе. «Торжественно клянусь, что замышляю шалость».",
        "desc_en": "Shows everyone in Hogwarts. 'I solemnly swear that I am up to no good.'",
        "desc_es": "Muestra a todos en Hogwarts. 'Juro solemnemente que mis intenciones no son buenas.'",
        "desc_de": "Zeigt jeden in Hogwarts. 'Ich schwöre feierlich, ich bin ein Tunichtgut.'",
        "desc_pt": "Mostra todos em Hogwarts. 'Juro solenemente não fazer nada de bom.'",
    },
    "time_turner": {
        "id": "time_turner", "type": "key", "rarity": "mythical", "emoji": "⏳",
        "name": {"ru": "Маховик времени", "en": "Time-Turner", "es": "Giratiempo",
                 "de": "Zeitumkehrer", "pt": "Vira-Tempo"},
        "desc_ru": "Позволяет вернуться в прошлое. Чрезвычайно редкий артефакт Министерства.",
        "desc_en": "Lets you travel back in time. An extremely rare Ministry artefact.",
        "desc_es": "Permite viajar al pasado. Un artefacto del Ministerio extremadamente raro.",
        "desc_de": "Ermöglicht Zeitreisen in die Vergangenheit. Ein extrem seltenes Ministeriums-Artefakt.",
        "desc_pt": "Permite voltar no tempo. Um artefato raríssimo do Ministério.",
    },
    "felix_felicis": {
        "id": "felix_felicis", "type": "consumable", "rarity": "legendary", "emoji": "🍀",
        "name": {"ru": "Феликс Фелицис", "en": "Felix Felicis", "es": "Felix Felicis",
                 "de": "Felix Felicis", "pt": "Felix Felicis"},
        "effect": "luck_mult", "value": 0.5, "duration": 3600,
        "desc_ru": "Жидкая удача. +50% к удаче на 1 час. Очень редкое зелье.",
        "desc_en": "Liquid luck. +50% luck for 1 hour. A very rare potion.",
        "desc_es": "Suerte líquida. +50% de suerte durante 1 hora. Una poción muy rara.",
        "desc_de": "Flüssiges Glück. +50% Glück für 1 Stunde. Ein sehr seltener Trank.",
        "desc_pt": "Sorte líquida. +50% de sorte por 1 hora. Uma poção muito rara.",
    },
    "polyjuice_ready": {
        "id": "polyjuice_ready", "type": "consumable", "rarity": "rare", "emoji": "🧪",
        "name": {"ru": "Оборотное зелье (готовое)", "en": "Polyjuice Potion (ready)",
                 "es": "Poción multijugos (lista)", "de": "Vielsafttrank (fertig)",
                 "pt": "Poção polissuco (pronta)"},
        "effect": "xp", "value": 100,
        "desc_ru": "Готовое оборотное зелье. Даёт +100 опыта при использовании.",
        "desc_en": "Ready-made Polyjuice Potion. Grants +100 XP when used.",
        "desc_es": "Poción multijugos lista. Otorga +100 de experiencia al usarla.",
        "desc_de": "Fertiger Vielsafttrank. Gibt +100 EP bei Benutzung.",
        "desc_pt": "Poção polissuco pronta. Concede +100 de XP ao usar.",
    },
    "dragon_heartstring": {
        "id": "dragon_heartstring", "type": "ingredient", "rarity": "very_rare", "emoji": "🐉",
        "name": {"ru": "Струна сердца дракона", "en": "Dragon Heartstring",
                 "es": "Fibra de corazón de dragón", "de": "Drachenherzfaser",
                 "pt": "Corda de coração de dragão"},
        "desc_ru": "Мощный компонент для палочек и зелий. Ищи в Запретном лесу.",
        "desc_en": "A powerful component for wands and potions. Found in the Forbidden Forest.",
        "desc_es": "Un componente poderoso para varitas y pociones. En el Bosque Prohibido.",
        "desc_de": "Eine mächtige Komponente für Zauberstäbe und Tränke. Im Verbotenen Wald.",
        "desc_pt": "Um componente poderoso para varinhas e poções. Na Floresta Proibida.",
    },
    "dark_arts_tome": {
        "id": "dark_arts_tome", "type": "key", "rarity": "epic", "emoji": "📕",
        "name": {"ru": "Том тёмных искусств", "en": "Dark Arts Tome",
                 "es": "Tomo de artes oscuras", "de": "Foliant der dunklen Künste",
                 "pt": "Tomo das artes das trevas"},
        "desc_ru": "Запрещённая книга тёмной магии. Хранится под стеклом в Чёрном рынке.",
        "desc_en": "A forbidden book of dark magic. Kept under glass at the Black Market.",
        "desc_es": "Un libro prohibido de magia oscura. Guardado bajo vidrio en el Mercado Negro.",
        "desc_de": "Ein verbotenes Buch dunkler Magie. Unter Glas im Schwarzmarkt aufbewahrt.",
        "desc_pt": "Um livro proibido de magia das trevas. Guardado sob vidro no Mercado Negro.",
    },
}
ITEMS.update(SPECIAL_ITEMS)

# ─── КОСМЕТИКА ─────────────────────────────────────────────────────────────────
COSMETICS = {
    "frame_gryffindor": {
        "id": "frame_gryffindor", "type": "cosmetic", "sub": "frame",
        "rarity": "uncommon", "emoji": "🦁",
        "name": {"ru": "Рамка Гриффиндора"}, "house": "gryffindor",
    },
    "frame_slytherin": {
        "id": "frame_slytherin", "type": "cosmetic", "sub": "frame",
        "rarity": "uncommon", "emoji": "🐍",
        "name": {"ru": "Рамка Слизерина"}, "house": "slytherin",
    },
    "frame_ravenclaw": {
        "id": "frame_ravenclaw", "type": "cosmetic", "sub": "frame",
        "rarity": "uncommon", "emoji": "🦅",
        "name": {"ru": "Рамка Когтеврана"}, "house": "ravenclaw",
    },
    "frame_hufflepuff": {
        "id": "frame_hufflepuff", "type": "cosmetic", "sub": "frame",
        "rarity": "uncommon", "emoji": "🦡",
        "name": {"ru": "Рамка Пуффендуя"}, "house": "hufflepuff",
    },
    "title_champion": {
        "id": "title_champion", "type": "cosmetic", "sub": "title",
        "rarity": "legendary", "emoji": "🏆",
        "name": {"ru": "Чемпион Хогвартса"},
    },
    "title_dark_lord": {
        "id": "title_dark_lord", "type": "cosmetic", "sub": "title",
        "rarity": "epic", "emoji": "💀",
        "name": {"ru": "Тёмный лорд"},
    },
}
ITEMS.update(COSMETICS)

# ─── Генерируем базовые слоты по редкостям ────────────────────────────────────
for _rarity in [r[0] for r in RARITIES]:
    for _slot in ["wand", "robe", "amulet", "ring", "hat", "boots", "gloves"]:
        _id = f"{_slot}_{_rarity}"
        if _id not in ITEMS:
            stat_range = RARITY_STAT_RANGE[_rarity]
            ITEMS[_id] = {
                "id": _id, "type": "equipment", "slot": _slot,
                "rarity": _rarity, "emoji": RARITY_NAMES[_rarity],
                "name": {"ru": f"{SLOT_EMOJI.get(_slot, '')} ({RARITY_NAMES_RU.get(_rarity, _rarity)})"},
                "stat": EQUIPMENT_SLOTS[_slot],
                "stat_min": stat_range[0], "stat_max": stat_range[1],
            }


def get_item(item_id: str) -> dict | None:
    return ITEMS.get(item_id)


def roll_item_rarity(luck_modifier: float = 1.0) -> str:
    pool = [
        (r, w * luck_modifier if r not in ("mythical", "abyssal") else w)
        for r, _, _, w in RARITIES if r in ("common", "uncommon", "rare", "very_rare", "epic", "legendary")
    ]
    rarities = [p[0] for p in pool]
    weights  = [p[1] for p in pool]
    return random.choices(rarities, weights=weights, k=1)[0]


def roll_equipment(rarity: str | None = None) -> dict:
    if rarity is None:
        rarity = roll_item_rarity()
    slots = list(EQUIPMENT_SLOTS.keys())
    slot  = random.choice(slots)
    item  = ITEMS.get(f"{slot}_{rarity}", ITEMS[f"wand_{rarity}"]).copy()
    bonus = item_stat_value(item)
    item["bonus"] = bonus
    return item


def generate_shop_inventory(size: int = 8) -> list[dict]:
    """Ежедневный ассортимент магазина."""
    allowed = ["common", "uncommon", "rare"]
    result  = []
    cons_pool = list(CONSUMABLES.values())
    result.extend(random.sample(cons_pool, min(3, len(cons_pool))))
    for _ in range(5):
        rarity = random.choices(allowed, weights=[0.55, 0.30, 0.15], k=1)[0]
        item   = roll_equipment(rarity)
        result.append(item)
    return result



SUPPORTED_LANGS = ("ru", "en", "es", "de", "pt")

STAT_LABELS = {
    "ru": {"attack": "урону", "defense": "защите", "max_mana": "максимальной мане", "speed": "скорости", "luck": "удаче", "max_hp": "максимальному здоровью"},
    "en": {"attack": "damage", "defense": "defense", "max_mana": "max mana", "speed": "speed", "luck": "luck", "max_hp": "max health"},
    "es": {"attack": "daño", "defense": "defensa", "max_mana": "maná máximo", "speed": "velocidad", "luck": "suerte", "max_hp": "salud máxima"},
    "de": {"attack": "Schaden", "defense": "Verteidigung", "max_mana": "max. Mana", "speed": "Tempo", "luck": "Glück", "max_hp": "max. Leben"},
    "pt": {"attack": "dano", "defense": "defesa", "max_mana": "mana máxima", "speed": "velocidade", "luck": "sorte", "max_hp": "vida máxima"},
}

SLOT_LABELS = {
    "ru": {"wand": "палочка", "robe": "мантия", "amulet": "амулет", "ring": "кольцо", "hat": "головной убор", "boots": "обувь", "gloves": "перчатки"},
    "en": {"wand": "wand", "robe": "robe", "amulet": "amulet", "ring": "ring", "hat": "hat", "boots": "boots", "gloves": "gloves"},
    "es": {"wand": "varita", "robe": "túnica", "amulet": "amuleto", "ring": "anillo", "hat": "sombrero", "boots": "botas", "gloves": "guantes"},
    "de": {"wand": "Zauberstab", "robe": "Robe", "amulet": "Amulett", "ring": "Ring", "hat": "Hut", "boots": "Stiefel", "gloves": "Handschuhe"},
    "pt": {"wand": "varinha", "robe": "manto", "amulet": "amuleto", "ring": "anel", "hat": "chapéu", "boots": "botas", "gloves": "luvas"},
}

RARITY_NAMES_LOCALIZED = {
    "ru": RARITY_NAMES_RU,
    "en": {"common": "Common", "uncommon": "Uncommon", "rare": "Rare", "very_rare": "Very rare", "epic": "Epic", "legendary": "Legendary", "mythical": "Mythical", "abyssal": "Abyssal"},
    "es": {"common": "Común", "uncommon": "Poco común", "rare": "Raro", "very_rare": "Muy raro", "epic": "Épico", "legendary": "Legendario", "mythical": "Mítico", "abyssal": "Abisal"},
    "de": {"common": "Gewöhnlich", "uncommon": "Ungewöhnlich", "rare": "Selten", "very_rare": "Sehr selten", "epic": "Episch", "legendary": "Legendär", "mythical": "Mythisch", "abyssal": "Abgründig"},
    "pt": {"common": "Comum", "uncommon": "Incomum", "rare": "Raro", "very_rare": "Muito raro", "epic": "Épico", "legendary": "Lendário", "mythical": "Mítico", "abyssal": "Abissal"},
}

TYPE_LABELS = {
    "ru": {"equipment": "Снаряжение", "consumable": "Расходник", "ingredient": "Ингредиент", "cosmetic": "Косметика"},
    "en": {"equipment": "Equipment", "consumable": "Consumable", "ingredient": "Ingredient", "cosmetic": "Cosmetic"},
    "es": {"equipment": "Equipo", "consumable": "Consumible", "ingredient": "Ingrediente", "cosmetic": "Cosmético"},
    "de": {"equipment": "Ausrüstung", "consumable": "Verbrauchsgegenstand", "ingredient": "Zutat", "cosmetic": "Kosmetik"},
    "pt": {"equipment": "Equipamento", "consumable": "Consumível", "ingredient": "Ingrediente", "cosmetic": "Cosmético"},
}

_EFFECT_LABELS = {
    "ru": {"hp": "восстанавливает здоровье", "hp_full": "полностью лечит", "mana": "восстанавливает ману", "mana_full": "полностью восстанавливает ману", "attack_boost": "усиливает урон", "defense_boost": "усиливает защиту", "luck_boost": "повышает удачу", "xp_boost": "повышает опыт", "cleanse": "снимает негативные эффекты", "copycat": "копирует характеристики", "reveal": "раскрывает заклинания врага", "battle_stun": "оглушает врага", "restore": "снимает окаменение"},
    "en": {"hp": "restores health", "hp_full": "fully heals", "mana": "restores mana", "mana_full": "fully restores mana", "attack_boost": "increases damage", "defense_boost": "increases defense", "luck_boost": "increases luck", "xp_boost": "increases experience", "cleanse": "removes negative effects", "copycat": "copies stats", "reveal": "reveals enemy spells", "battle_stun": "stuns the enemy", "restore": "removes petrification"},
    "es": {"hp": "restaura salud", "hp_full": "cura por completo", "mana": "restaura maná", "mana_full": "restaura todo el maná", "attack_boost": "aumenta el daño", "defense_boost": "aumenta la defensa", "luck_boost": "aumenta la suerte", "xp_boost": "aumenta la experiencia", "cleanse": "elimina efectos negativos", "copycat": "copia estadísticas", "reveal": "revela hechizos enemigos", "battle_stun": "aturde al enemigo", "restore": "elimina petrificación"},
    "de": {"hp": "stellt Leben wieder her", "hp_full": "heilt vollständig", "mana": "stellt Mana wieder her", "mana_full": "stellt Mana vollständig wieder her", "attack_boost": "erhöht Schaden", "defense_boost": "erhöht Verteidigung", "luck_boost": "erhöht Glück", "xp_boost": "erhöht Erfahrung", "cleanse": "entfernt negative Effekte", "copycat": "kopiert Werte", "reveal": "deckt gegnerische Zauber auf", "battle_stun": "betäubt den Gegner", "restore": "hebt Versteinerung auf"},
    "pt": {"hp": "restaura vida", "hp_full": "cura completamente", "mana": "restaura mana", "mana_full": "restaura toda a mana", "attack_boost": "aumenta dano", "defense_boost": "aumenta defesa", "luck_boost": "aumenta sorte", "xp_boost": "aumenta experiência", "cleanse": "remove efeitos negativos", "copycat": "copia atributos", "reveal": "revela feitiços inimigos", "battle_stun": "atordoa o inimigo", "restore": "remove petrificação"},
}

# Итоговый баланс: теперь у предмета всегда одна понятная цифра, а не разброс.
RARITY_FIXED_BONUS = {
    "common": 2,
    "uncommon": 5,
    "rare": 10,
    "very_rare": 18,
    "epic": 30,
    "legendary": 48,
    "mythical": 72,
    "abyssal": 110,
}

SPECIAL_TEXT = {
    "ru": {"evasion_15": "15% шанс уклониться от атаки", "intimidate_10": "снижает атаку врага на 10%", "regen_5": "восстанавливает 5 HP каждый ход", "dark_boost_20": "+20% к тёмной магии", "double_cast_10": "10% шанс повторить заклинание бесплатно", "cheat_death_20": "20% шанс выжить с 1 HP", "heal_boost_10": "+10% к лечению", "auto_spell": "помогает выбрать лучшее заклинание", "evasion_20": "20% шанс уклониться", "poison_on_hit_15": "15% шанс отравить врага"},
    "en": {"evasion_15": "15% chance to dodge an attack", "intimidate_10": "reduces enemy attack by 10%", "regen_5": "restores 5 HP each turn", "dark_boost_20": "+20% dark magic damage", "double_cast_10": "10% chance to recast for free", "cheat_death_20": "20% chance to survive at 1 HP", "heal_boost_10": "+10% healing", "auto_spell": "helps choose the best spell", "evasion_20": "20% dodge chance", "poison_on_hit_15": "15% chance to poison the enemy"},
    "es": {}, "de": {}, "pt": {},
}


def _lang(lang: str) -> str:
    return lang if lang in SUPPORTED_LANGS else "ru"


def stat_label(stat: str, lang: str = "ru") -> str:
    lang = _lang(lang)
    return STAT_LABELS.get(lang, STAT_LABELS["ru"]).get(stat, stat)


def slot_label(slot: str, lang: str = "ru") -> str:
    lang = _lang(lang)
    return SLOT_LABELS.get(lang, SLOT_LABELS["ru"]).get(slot, slot)


def rarity_label(rarity: str, lang: str = "ru") -> str:
    lang = _lang(lang)
    return RARITY_NAMES_LOCALIZED.get(lang, RARITY_NAMES_LOCALIZED["ru"]).get(rarity, rarity)


def type_label(item_type: str, lang: str = "ru") -> str:
    lang = _lang(lang)
    return TYPE_LABELS.get(lang, TYPE_LABELS["ru"]).get(item_type, item_type)


def item_stat_value(item: dict) -> int:
    if "bonus" in item and item.get("bonus") is not None:
        return int(item["bonus"])
    if "stat_value" in item and item.get("stat_value") is not None:
        return int(item["stat_value"])
    rarity = item.get("rarity", "common")
    fixed = RARITY_FIXED_BONUS.get(rarity)
    if fixed is not None:
        return int(fixed)
    return int(round((item.get("stat_min", 0) + item.get("stat_max", 0)) / 2))


def _default_desc(item: dict, lang: str = "ru") -> str:
    lang = _lang(lang)
    item_type = item.get("type")
    if item_type == "equipment":
        if lang == "ru":
            return f"Надёжное снаряжение: {slot_label(item.get('slot', ''), lang)}. Усиливает персонажа без случайного разброса характеристик."
        if lang == "en":
            return f"Reliable {slot_label(item.get('slot', ''), lang)} equipment. Gives a fixed stat bonus with no random spread."
        if lang == "es":
            return f"Equipo fiable: {slot_label(item.get('slot', ''), lang)}. Da una bonificación fija sin valores aleatorios."
        if lang == "de":
            return f"Zuverlässige Ausrüstung: {slot_label(item.get('slot', ''), lang)}. Gibt einen festen Bonus ohne Zufallsbereich."
        return f"Equipamento confiável: {slot_label(item.get('slot', ''), lang)}. Dá um bônus fixo sem variação aleatória."
    if item_type == "consumable":
        effect = _EFFECT_LABELS.get(lang, _EFFECT_LABELS["ru"]).get(item.get("effect"), item.get("effect", "effect"))
        return {"ru": f"Расходный предмет: {effect}.", "en": f"Consumable item: {effect}.", "es": f"Objeto consumible: {effect}.", "de": f"Verbrauchsgegenstand: {effect}.", "pt": f"Item consumível: {effect}."}.get(lang)
    if item_type == "ingredient":
        return {"ru": "Ингредиент для зелий и игровых активностей.", "en": "Ingredient for potions and game activities.", "es": "Ingrediente para pociones y actividades.", "de": "Zutat für Tränke und Spielaktivitäten.", "pt": "Ingrediente para poções e atividades."}.get(lang)
    if item_type == "cosmetic":
        return {"ru": "Косметический предмет для оформления персонажа.", "en": "Cosmetic item for character customization.", "es": "Objeto cosmético para personalizar al personaje.", "de": "Kosmetikgegenstand zur Charakteranpassung.", "pt": "Item cosmético para personalizar o personagem."}.get(lang)
    return item.get("desc_ru") or item.get("description") or "Описание пока не добавлено."


def item_display_name(item: dict, lang: str = "ru") -> str:
    lang = _lang(lang)
    name = item.get("name", {})
    if isinstance(name, dict):
        return name.get(lang) or name.get("ru") or name.get("en") or item.get("id", "item")
    return str(name)


def item_description(item: dict, lang: str = "ru") -> str:
    lang = _lang(lang)
    return item.get(f"desc_{lang}") or item.get("desc_ru") or item.get("description") or _default_desc(item, lang)


def item_bonus_text(item: dict, lang: str = "ru") -> str:
    lang = _lang(lang)
    if item.get("type") == "equipment":
        stat = item.get("stat", "")
        bonus = item_stat_value(item)
        if lang == "ru":
            text = f"📈 Характеристика: +{bonus} к {stat_label(stat, lang)}"
        elif lang == "en":
            text = f"📈 Stat: +{bonus} {stat_label(stat, lang)}"
        elif lang == "es":
            text = f"📈 Atributo: +{bonus} {stat_label(stat, lang)}"
        elif lang == "de":
            text = f"📈 Wert: +{bonus} {stat_label(stat, lang)}"
        else:
            text = f"📈 Atributo: +{bonus} {stat_label(stat, lang)}"
        special = item.get("special")
        special_text = SPECIAL_TEXT.get(lang, {}).get(special) or SPECIAL_TEXT["ru"].get(special)
        if special_text:
            text += f"\n✨ Особенность: {special_text}" if lang == "ru" else f"\n✨ Special: {special_text}"
        return text
    if item.get("type") == "consumable":
        effect = _EFFECT_LABELS.get(lang, _EFFECT_LABELS["ru"]).get(item.get("effect"), item.get("effect", "effect"))
        value = item.get("value")
        duration = item.get("duration")
        value_text = ""
        if isinstance(value, float):
            value_text = f" {int(value * 100)}%"
        elif isinstance(value, int) and value not in (0, 1, 9999):
            value_text = f" {value}"
        duration_text = f", {duration // 60} мин." if isinstance(duration, int) and duration >= 60 and lang == "ru" else ""
        return f"✨ Эффект: {effect}{value_text}{duration_text}" if lang == "ru" else f"✨ Effect: {effect}{value_text}"
    return ""


def item_card_text(item: dict, lang: str = "ru", include_id: bool = False) -> str:
    rarity = item.get("rarity", "common")
    lines = [
        f"{RARITY_NAMES.get(rarity, '⬜')} *{item_display_name(item, lang)}*",
        f"⭐ {rarity_label(rarity, lang)} · {type_label(item.get('type', 'item'), lang)}",
        f"📜 {item_description(item, lang)}",
    ]
    bonus = item_bonus_text(item, lang)
    if bonus:
        lines.append(bonus)
    if include_id:
        lines.append(f"ID: `{item.get('id')}`")
    return "\n".join(lines)


# Заполняем отсутствующие описания и фиксированные бонусы сразу при импорте.
for _item in ITEMS.values():
    if _item.get("type") == "equipment":
        _item.setdefault("stat_value", item_stat_value(_item))
    for _lang_code in SUPPORTED_LANGS:
        _item.setdefault(f"desc_{_lang_code}", _item.get(f"desc_{_lang_code}") or (_item.get("desc_ru") if _lang_code == "ru" else _default_desc(_item, _lang_code)))
