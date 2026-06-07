"""
Items system: equipment, cosmetics, consumables.
Rarity tiers match TZ section 10.
"""
import random

# ── Rarity config ──────────────────────────────────────────────────────────────
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

RARITY_NAMES = {r[0]: r[1] for r in RARITIES}
RARITY_STAT_RANGE = {r[0]: r[2] for r in RARITIES}
RARITY_SHOP_CHANCE = {r[0]: r[3] for r in RARITIES}

# ── Equipment slots ────────────────────────────────────────────────────────────
EQUIPMENT_SLOTS = {
    "wand":    "attack",
    "robe":    "defense",
    "amulet":  "max_mana",
    "ring":    "luck",
    "hat":     "speed",
}

SLOT_EMOJI = {
    "wand":   "🪄",
    "robe":   "🧥",
    "amulet": "📿",
    "ring":   "💍",
    "hat":    "🎩",
}

# ── Item catalogue ─────────────────────────────────────────────────────────────
ITEMS: dict[str, dict] = {}

def _make_equipment(item_id: str, name_ru: str, name_en: str, slot: str, rarity: str) -> dict:
    stat_range = RARITY_STAT_RANGE[rarity]
    return {
        "id": item_id, "type": "equipment", "slot": slot,
        "rarity": rarity, "emoji": RARITY_NAMES[rarity],
        "name": {"ru": name_ru, "en": name_en},
        "stat": EQUIPMENT_SLOTS[slot],
        "stat_min": stat_range[0], "stat_max": stat_range[1],
    }

# Wands
for _rarity in [r[0] for r in RARITIES]:
    _id = f"wand_{_rarity}"
    ITEMS[_id] = _make_equipment(_id, f"Палочка ({RARITY_NAMES[_rarity]})", f"Wand ({RARITY_NAMES[_rarity]})", "wand", _rarity)

# Robes
for _rarity in [r[0] for r in RARITIES]:
    _id = f"robe_{_rarity}"
    ITEMS[_id] = _make_equipment(_id, f"Мантия ({RARITY_NAMES[_rarity]})", f"Robe ({RARITY_NAMES[_rarity]})", "robe", _rarity)

# Amulets
for _rarity in [r[0] for r in RARITIES]:
    _id = f"amulet_{_rarity}"
    ITEMS[_id] = _make_equipment(_id, f"Амулет ({RARITY_NAMES[_rarity]})", f"Amulet ({RARITY_NAMES[_rarity]})", "amulet", _rarity)

# Rings
for _rarity in [r[0] for r in RARITIES]:
    _id = f"ring_{_rarity}"
    ITEMS[_id] = _make_equipment(_id, f"Кольцо ({RARITY_NAMES[_rarity]})", f"Ring ({RARITY_NAMES[_rarity]})", "ring", _rarity)

# Hats
for _rarity in [r[0] for r in RARITIES]:
    _id = f"hat_{_rarity}"
    ITEMS[_id] = _make_equipment(_id, f"Шляпа ({RARITY_NAMES[_rarity]})", f"Hat ({RARITY_NAMES[_rarity]})", "hat", _rarity)

# ── Consumables ────────────────────────────────────────────────────────────────
CONSUMABLES = {
    "hp_potion_small":  {"id": "hp_potion_small",  "type": "consumable", "rarity": "common",   "emoji": "🧪", "name": {"ru": "Малое зелье ХП",   "en": "Small HP Potion"},   "effect": "hp", "value": 30,  "price": 50},
    "hp_potion_medium": {"id": "hp_potion_medium", "type": "consumable", "rarity": "uncommon", "emoji": "🧪", "name": {"ru": "Среднее зелье ХП", "en": "Medium HP Potion"},  "effect": "hp", "value": 60,  "price": 100},
    "hp_potion_large":  {"id": "hp_potion_large",  "type": "consumable", "rarity": "rare",     "emoji": "🧪", "name": {"ru": "Большое зелье ХП", "en": "Large HP Potion"},   "effect": "hp", "value": 120, "price": 200},
    "mana_potion":      {"id": "mana_potion",      "type": "consumable", "rarity": "uncommon", "emoji": "💧", "name": {"ru": "Зелье маны",        "en": "Mana Potion"},       "effect": "mana", "value": 50, "price": 80},
    "strength_potion":  {"id": "strength_potion",  "type": "consumable", "rarity": "rare",     "emoji": "⚡", "name": {"ru": "Зелье силы",        "en": "Strength Potion"},   "effect": "attack_boost", "value": 0.20, "duration": 1, "price": 150},
    "luck_potion":      {"id": "luck_potion",      "type": "consumable", "rarity": "rare",     "emoji": "🍀", "name": {"ru": "Зелье удачи",       "en": "Luck Potion"},       "effect": "luck_boost",   "value": 0.50, "duration": 3600, "price": 200},
}
ITEMS.update(CONSUMABLES)

# ── Cosmetics ──────────────────────────────────────────────────────────────────
COSMETICS = {
    "frame_gryffindor": {"id": "frame_gryffindor", "type": "cosmetic", "sub": "frame",  "rarity": "uncommon", "emoji": "⚡", "name": {"ru": "Рамка Гриффиндора", "en": "Gryffindor Frame"}, "house": "gryffindor"},
    "frame_slytherin":  {"id": "frame_slytherin",  "type": "cosmetic", "sub": "frame",  "rarity": "uncommon", "emoji": "🐍", "name": {"ru": "Рамка Слизерина",   "en": "Slytherin Frame"},  "house": "slytherin"},
    "frame_ravenclaw":  {"id": "frame_ravenclaw",  "type": "cosmetic", "sub": "frame",  "rarity": "uncommon", "emoji": "🦅", "name": {"ru": "Рамка Когтеврана",  "en": "Ravenclaw Frame"},  "house": "ravenclaw"},
    "frame_hufflepuff": {"id": "frame_hufflepuff", "type": "cosmetic", "sub": "frame",  "rarity": "uncommon", "emoji": "🦡", "name": {"ru": "Рамка Пуффендуя",   "en": "Hufflepuff Frame"}, "house": "hufflepuff"},
    "title_champion":   {"id": "title_champion",   "type": "cosmetic", "sub": "title",  "rarity": "legendary","emoji": "🏆", "name": {"ru": "Чемпион Хогвартса", "en": "Hogwarts Champion"}},
    "title_dark_lord":  {"id": "title_dark_lord",  "type": "cosmetic", "sub": "title",  "rarity": "epic",     "emoji": "💀", "name": {"ru": "Тёмный лорд",       "en": "Dark Lord"}},
}
ITEMS.update(COSMETICS)


def get_item(item_id: str) -> dict | None:
    return ITEMS.get(item_id)


def roll_item_rarity(luck_modifier: float = 1.0) -> str:
    """Roll a rarity based on shop weights, modified by luck."""
    pool = [(r, w * luck_modifier if r not in ("mythical", "abyssal") else w)
            for r, _, _, w in RARITIES if r in ("common", "uncommon", "rare", "very_rare", "epic", "legendary")]
    rarities = [p[0] for p in pool]
    weights  = [p[1] for p in pool]
    return random.choices(rarities, weights=weights, k=1)[0]


def roll_equipment(rarity: str | None = None) -> dict:
    """Return a random equipment item, optionally of a specific rarity."""
    if rarity is None:
        rarity = roll_item_rarity()
    slots = list(EQUIPMENT_SLOTS.keys())
    slot  = random.choice(slots)
    item  = ITEMS[f"{slot}_{rarity}"].copy()
    bonus = random.randint(item["stat_min"], item["stat_max"])
    item["bonus"] = bonus
    return item


def generate_shop_inventory(size: int = 8) -> list[dict]:
    """Generate a daily shop stock (common to rare only per TZ)."""
    allowed = ["common", "uncommon", "rare"]
    result  = []
    # 3 consumables
    cons_pool = list(CONSUMABLES.values())
    result.extend(random.sample(cons_pool, min(3, len(cons_pool))))
    # 5 equipment pieces
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
