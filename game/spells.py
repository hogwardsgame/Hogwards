"""
All spells data for Hogwarts Legacy Bot.
Rarities: common, uncommon, rare, very_rare, epic, legendary
"""

SPELLS = {
    # ── BASIC SPELLS (common) ─────────────────────────────────────────────────
    "expelliarmus": {
        "id": "expelliarmus", "rarity": "common", "type": "attack",
        "mana": 15, "damage": 25,
        "effect": "disarm",       # target loses 1 random spell for 1 turn
        "effect_chance": 1.0,
    },
    "stupefy": {
        "id": "stupefy", "rarity": "common", "type": "attack",
        "mana": 25, "damage": 35,
        "effect": "stun",         # target skips next turn
        "effect_chance": 0.4,
    },
    "confundus": {
        "id": "confundus", "rarity": "common", "type": "attack",
        "mana": 20, "damage": 20,
        "effect": "confuse",      # target attacks itself
        "effect_chance": 0.3,
    },
    "flipendo": {
        "id": "flipendo", "rarity": "common", "type": "attack",
        "mana": 20, "damage": 30,
        "effect": None,
        "effect_chance": 0,
    },
    "protego": {
        "id": "protego", "rarity": "common", "type": "defense",
        "mana": 20, "damage": 0,
        "effect": "block",        # blocks 40% incoming damage for 1 turn
        "effect_chance": 1.0,
    },
    "escudo": {
        "id": "escudo", "rarity": "common", "type": "heal",
        "mana": 25, "damage": 0,
        "heal": 20,
        "effect": None,
        "effect_chance": 0,
    },
    "ricochet": {
        "id": "ricochet", "rarity": "common", "type": "defense",
        "mana": 30, "damage": 0,
        "effect": "reflect",      # reflects 25% damage back
        "effect_chance": 1.0,
    },
    "inflammare": {
        "id": "inflammare", "rarity": "common", "type": "debuff",
        "mana": 25, "damage": 15,
        "effect": "burn",         # 10 dmg/turn for 3 turns
        "effect_chance": 1.0,
    },
    "ice_chain": {
        "id": "ice_chain", "rarity": "common", "type": "debuff",
        "mana": 30, "damage": 10,
        "effect": "freeze",       # can't defend for 2 turns
        "effect_chance": 1.0,
    },
    "tenebrus": {
        "id": "tenebrus", "rarity": "common", "type": "debuff",
        "mana": 20, "damage": 10,
        "effect": "blind",        # -50% accuracy for 2 turns
        "effect_chance": 1.0,
    },
    "vulnero": {
        "id": "vulnero", "rarity": "common", "type": "heal",
        "mana": 30, "damage": 0,
        "heal": 30,
        "effect": None,
        "effect_chance": 0,
    },
    "sanacus": {
        "id": "sanacus", "rarity": "common", "type": "heal",
        "mana": 25, "damage": 0,
        "heal": 15,
        "effect": "cleanse",      # removes 1 debuff
        "effect_chance": 1.0,
    },
    # ── NPC-only basic (used by Hufflepuff) ───────────────────────────────────
    "reparo": {
        "id": "reparo", "rarity": "common", "type": "heal",
        "mana": 20, "damage": 0,
        "heal": 5,                # +5 HP in combat per TZ
        "effect": None,
        "effect_chance": 0,
    },
    "levicorpus": {
        "id": "levicorpus", "rarity": "common", "type": "attack",
        "mana": 20, "damage": 22,
        "effect": "stun",
        "effect_chance": 0.25,
    },

    # ── UNCOMMON (🔵) ─────────────────────────────────────────────────────────
    "aqua_eructo": {
        "id": "aqua_eructo", "rarity": "uncommon", "type": "attack",
        "mana": 30, "damage": 40,
        "effect": "slow",
        "effect_chance": 0.5,
    },
    "wingardium_leviosa": {
        "id": "wingardium_leviosa", "rarity": "uncommon", "type": "debuff",
        "mana": 25, "damage": 5,
        "effect": "stun",
        "effect_chance": 0.35,
    },
    "alohomora": {
        "id": "alohomora", "rarity": "uncommon", "type": "attack",
        "mana": 28, "damage": 38,
        "effect": None,
        "effect_chance": 0,
    },
    "accio": {
        "id": "accio", "rarity": "uncommon", "type": "attack",
        "mana": 22, "damage": 28,
        "effect": "disarm",
        "effect_chance": 0.4,
    },
    "lumos_maxima": {
        "id": "lumos_maxima", "rarity": "uncommon", "type": "debuff",
        "mana": 30, "damage": 0,
        "effect": "blind",
        "effect_chance": 1.0,
    },
    "petrificus_totalus": {
        "id": "petrificus_totalus", "rarity": "uncommon", "type": "debuff",
        "mana": 35, "damage": 15,
        "effect": "stun",
        "effect_chance": 0.6,
    },
    "diffindo": {
        "id": "diffindo", "rarity": "uncommon", "type": "attack",
        "mana": 32, "damage": 45,
        "effect": "burn",
        "effect_chance": 0.3,
    },
    "locomotor_mortis": {
        "id": "locomotor_mortis", "rarity": "uncommon", "type": "debuff",
        "mana": 28, "damage": 10,
        "effect": "freeze",
        "effect_chance": 0.7,
    },
    "silencio": {
        "id": "silencio", "rarity": "uncommon", "type": "debuff",
        "mana": 30, "damage": 5,
        "effect": "silence",      # target can only use physical attacks 2 turns
        "effect_chance": 0.8,
    },
    "episkey": {
        "id": "episkey", "rarity": "uncommon", "type": "heal",
        "mana": 35, "damage": 0,
        "heal": 40,
        "effect": "cleanse",
        "effect_chance": 1.0,
    },

    # ── RARE (🟣) ─────────────────────────────────────────────────────────────
    "sectumsempra": {
        "id": "sectumsempra", "rarity": "rare", "type": "attack",
        "mana": 45, "damage": 60,
        "effect": "burn",         # heavy bleed
        "effect_chance": 0.7,
    },
    "bombarda": {
        "id": "bombarda", "rarity": "rare", "type": "attack",
        "mana": 50, "damage": 70,
        "effect": "stun",
        "effect_chance": 0.45,
    },
    "glacius": {
        "id": "glacius", "rarity": "rare", "type": "debuff",
        "mana": 40, "damage": 20,
        "effect": "freeze",
        "effect_chance": 1.0,
    },
    "reducto": {
        "id": "reducto", "rarity": "rare", "type": "attack",
        "mana": 45, "damage": 65,
        "effect": None,
        "effect_chance": 0,
    },
    "crucio": {
        "id": "crucio", "rarity": "rare", "type": "debuff",
        "mana": 50, "damage": 30,
        "effect": "curse",        # -10 HP/turn, immune to healing
        "effect_chance": 0.6,
    },
    "imperio": {
        "id": "imperio", "rarity": "rare", "type": "debuff",
        "mana": 55, "damage": 0,
        "effect": "confuse",
        "effect_chance": 0.7,
    },
    "serpensortia": {
        "id": "serpensortia", "rarity": "rare", "type": "attack",
        "mana": 48, "damage": 55,
        "effect": "poison",       # like burn but 8 dmg/turn 4 turns
        "effect_chance": 0.65,
    },
    "morsmordre": {
        "id": "morsmordre", "rarity": "rare", "type": "attack",
        "mana": 60, "damage": 75,
        "effect": "curse",
        "effect_chance": 0.5,
    },

    # ── VERY RARE (🟠) ────────────────────────────────────────────────────────
    "fiendfyre": {
        "id": "fiendfyre", "rarity": "very_rare", "type": "attack",
        "mana": 70, "damage": 120,
        "effect": "burn",         # burn 5 turns (per TZ)
        "effect_chance": 1.0,
    },
    "obliviate": {
        "id": "obliviate", "rarity": "very_rare", "type": "debuff",
        "mana": 60, "damage": 0,
        "effect": "disarm",       # target loses ALL spells for 1 turn
        "effect_chance": 0.8,
    },
    "prior_incantato": {
        "id": "prior_incantato", "rarity": "very_rare", "type": "attack",
        "mana": 65, "damage": 90,
        "effect": "reflect",
        "effect_chance": 0.5,
    },
    "oppugno": {
        "id": "oppugno", "rarity": "very_rare", "type": "attack",
        "mana": 65, "damage": 85,
        "effect": "blind",
        "effect_chance": 0.9,
    },
    "duro": {
        "id": "duro", "rarity": "very_rare", "type": "defense",
        "mana": 55, "damage": 0,
        "effect": "shield",       # absorbs next 60 damage
        "effect_chance": 1.0,
    },
    "confringo": {
        "id": "confringo", "rarity": "very_rare", "type": "attack",
        "mana": 70, "damage": 100,
        "effect": "burn",
        "effect_chance": 0.8,
    },

    # ── EPIC (🔴) ─────────────────────────────────────────────────────────────
    "avada_kedavra": {
        "id": "avada_kedavra", "rarity": "epic", "type": "attack",
        "mana": 80, "damage": 0,
        "effect": "instant_kill",
        "effect_chance": 0.5,
        "min_level": 20,          # blocked for beginners per TZ
    },
    "legilimens": {
        "id": "legilimens", "rarity": "epic", "type": "debuff",
        "mana": 75, "damage": 40,
        "effect": "confuse",      # reveals enemy hand, confuse 2 turns
        "effect_chance": 1.0,
    },
    "protego_totalum": {
        "id": "protego_totalum", "rarity": "epic", "type": "defense",
        "mana": 70, "damage": 0,
        "effect": "shield",       # absorbs 120 damage
        "effect_chance": 1.0,
    },
    "exarmo_maxima": {
        "id": "exarmo_maxima", "rarity": "epic", "type": "attack",
        "mana": 85, "damage": 110,
        "effect": "disarm",
        "effect_chance": 1.0,
    },

    # ── LEGENDARY (⭐) ────────────────────────────────────────────────────────
    "tempus_maxima": {
        "id": "tempus_maxima", "rarity": "legendary", "type": "debuff",
        "mana": 100, "damage": 0,
        "effect": "stun",         # target skips 3 turns per TZ
        "effect_chance": 1.0,
        "stun_turns": 3,
    },
    "animus_supremus": {
        "id": "animus_supremus", "rarity": "legendary", "type": "attack",
        "mana": 120, "damage": 200,
        "effect": "burn",
        "effect_chance": 1.0,
    },
}

RARITY_DROP_CHANCE = {
    "uncommon":  0.15,
    "rare":      0.08,
    "very_rare": 0.03,
    "epic":      0.01,
    "legendary": 0.002,
}

RARITY_EMOJI = {
    "common":    "⚪",
    "uncommon":  "🔵",
    "rare":      "🟣",
    "very_rare": "🟠",
    "epic":      "🔴",
    "legendary": "⭐",
}

RARITY_SOURCES = {
    "uncommon":  ["lessons", "quests"],
    "rare":      ["dungeons", "shop"],
    "very_rare": ["deep_dungeons", "events"],
    "epic":      ["bosses", "weekly_event"],
    "legendary": ["final_bosses"],
}


def get_spell(spell_id: str) -> dict | None:
    return SPELLS.get(spell_id)


def spells_by_rarity(rarity: str) -> list[dict]:
    return [s for s in SPELLS.values() if s["rarity"] == rarity]


def basic_spells() -> list[dict]:
    return [s for s in SPELLS.values() if s["rarity"] == "common"]


def spell_display_name(spell_id: str, lang: str = "ru") -> str:
    names = {
        "expelliarmus": {"ru": "Экспеллиармус", "en": "Expelliarmus", "es": "Expelliarmus", "de": "Expelliarmus", "pt": "Expelliarmus"},
        "stupefy":      {"ru": "Ступефай",       "en": "Stupefy",       "es": "Stupefy",      "de": "Stupefy",     "pt": "Stupefy"},
        "confundus":    {"ru": "Конфундус",       "en": "Confundus",     "es": "Confundus",    "de": "Confundus",   "pt": "Confundus"},
        "flipendo":     {"ru": "Флипендо",        "en": "Flipendo",      "es": "Flipendo",     "de": "Flipendo",    "pt": "Flipendo"},
        "protego":      {"ru": "Протего",         "en": "Protego",       "es": "Protego",      "de": "Protego",     "pt": "Protego"},
        "escudo":       {"ru": "Эскудо",          "en": "Escudo",        "es": "Escudo",       "de": "Escudo",      "pt": "Escudo"},
        "ricochet":     {"ru": "Рикошет",         "en": "Ricochet",      "es": "Rebote",       "de": "Ricochet",    "pt": "Ricochete"},
        "inflammare":   {"ru": "Инфламмаре",      "en": "Inflammare",    "es": "Inflammare",   "de": "Inflammare",  "pt": "Inflammare"},
        "ice_chain":    {"ru": "Ледяная цепь",    "en": "Ice Chain",     "es": "Cadena de Hielo", "de": "Eiskette", "pt": "Corrente de Gelo"},
        "tenebrus":     {"ru": "Тенебрус",        "en": "Tenebrus",      "es": "Tenebrus",     "de": "Tenebrus",   "pt": "Tenebrus"},
        "vulnero":      {"ru": "Вулнеро",         "en": "Vulnero",       "es": "Vulnero",      "de": "Vulnero",    "pt": "Vulnero"},
        "sanacus":      {"ru": "Санакус",         "en": "Sanacus",       "es": "Sanacus",      "de": "Sanacus",    "pt": "Sanacus"},
        "reparo":       {"ru": "Репаро",          "en": "Reparo",        "es": "Reparo",       "de": "Reparo",     "pt": "Reparo"},
        "levicorpus":   {"ru": "Левикорпус",      "en": "Levicorpus",    "es": "Levicorpus",   "de": "Levicorpus", "pt": "Levicorpus"},
        "fiendfyre":    {"ru": "Фиендфайр",       "en": "Fiendfyre",     "es": "Fiendfyre",    "de": "Fiendfyre",  "pt": "Fiendfyre"},
        "avada_kedavra": {"ru": "Авада Кедавра",  "en": "Avada Kedavra", "es": "Avada Kedavra","de": "Avada Kedavra","pt": "Avada Kedavra"},
        "tempus_maxima": {"ru": "Темпус Максима", "en": "Tempus Maxima", "es": "Tempus Maxima","de": "Tempus Maxima","pt": "Tempus Maxima"},
        "sectumsempra": {"ru": "Сектумсемпра",    "en": "Sectumsempra",  "es": "Sectumsempra", "de": "Sectumsempra","pt": "Sectumsempra"},
        "bombarda":     {"ru": "Бомбарда",        "en": "Bombarda",      "es": "Bombarda",     "de": "Bombarda",   "pt": "Bombarda"},
    }
    entry = names.get(spell_id, {})
    return entry.get(lang, spell_id.replace("_", " ").title())
