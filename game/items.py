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
    bonus = random.randint(item["stat_min"], item["stat_max"])
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


def item_display_name(item: dict, lang: str = "ru") -> str:
    name = item.get("name", {})
    if isinstance(name, dict):
        return name.get(lang, name.get("en", item["id"]))
    return str(name)
