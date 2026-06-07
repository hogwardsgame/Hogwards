"""
Monsters and PvE zones per TZ section 8.2.
Each monster has an AI pattern that controls combat decisions.
"""
import random

# ── AI Patterns ────────────────────────────────────────────────────────────────
class AIPattern:
    AGGRESSIVE = "aggressive"   # always attacks max damage
    DEFENSIVE  = "defensive"    # alternates attack / defense
    CUNNING    = "cunning"      # focuses on debuffs
    RANDOM     = "random"       # unpredictable (bosses)


# ── Zone definitions ──────────────────────────────────────────────────────────
ZONES = {
    "forbidden_forest": {
        "id": "forbidden_forest", "min_level": 1,
        "name": {"ru": "Запретный лес", "en": "Forbidden Forest"},
        "emoji": "🌲",
        "monsters": ["acromantula", "centaur", "hippogriff"],
        "boss": "aragog",
        "boss_every": 5,       # mini-boss every 5 kills
        "main_boss_kills": 25,
    },
    "azkaban": {
        "id": "azkaban", "min_level": 5,
        "name": {"ru": "Азкабан", "en": "Azkaban"},
        "emoji": "🏚️",
        "monsters": ["dementor", "troll"],
        "boss": "senior_dementor",
        "boss_every": 5,
        "main_boss_kills": 25,
    },
    "chamber_of_secrets": {
        "id": "chamber_of_secrets", "min_level": 10,
        "name": {"ru": "Камера тайн", "en": "Chamber of Secrets"},
        "emoji": "🐍",
        "monsters": ["basilisk_child", "serpent"],
        "boss": "basilisk",
        "boss_every": 5,
        "main_boss_kills": 25,
    },
    "gringotts_caves": {
        "id": "gringotts_caves", "min_level": 15,
        "name": {"ru": "Пещеры Гринготтса", "en": "Gringotts Caves"},
        "emoji": "💰",
        "monsters": ["guardian_dragon", "goblin"],
        "boss": "gringotts_dragon",
        "boss_every": 5,
        "main_boss_kills": 25,
    },
    "voldemort_castle": {
        "id": "voldemort_castle", "min_level": 20,
        "name": {"ru": "Замок Волдеморта", "en": "Voldemort's Castle"},
        "emoji": "💀",
        "monsters": ["death_eater", "nagini"],
        "boss": "voldemort",
        "boss_every": 5,
        "main_boss_kills": 25,
    },
}

# ── Monster definitions ────────────────────────────────────────────────────────
MONSTERS: dict[str, dict] = {
    # Forbidden Forest
    "acromantula": {
        "id": "acromantula", "is_boss": False,
        "name": {"ru": "Акромантула", "en": "Acromantula"}, "emoji": "🕷️",
        "hp": 80, "attack": 18, "defense": 8, "speed": 12,
        "xp_reward": (30, 60), "gold_reward": (10, 30),
        "ai": AIPattern.AGGRESSIVE,
        "spells": ["bite", "web_shot"],
        "drop_chance": 0.15,
    },
    "centaur": {
        "id": "centaur", "is_boss": False,
        "name": {"ru": "Кентавр", "en": "Centaur"}, "emoji": "🏹",
        "hp": 90, "attack": 15, "defense": 12, "speed": 14,
        "xp_reward": (35, 65), "gold_reward": (12, 35),
        "ai": AIPattern.CUNNING,
        "spells": ["arrow_shot", "prophecy_curse"],
        "drop_chance": 0.15,
    },
    "hippogriff": {
        "id": "hippogriff", "is_boss": False,
        "name": {"ru": "Гиппогриф", "en": "Hippogriff"}, "emoji": "🦅",
        "hp": 75, "attack": 20, "defense": 6, "speed": 18,
        "xp_reward": (28, 55), "gold_reward": (10, 28),
        "ai": AIPattern.AGGRESSIVE,
        "spells": ["talon_strike", "dive"],
        "drop_chance": 0.20,
    },
    "aragog": {
        "id": "aragog", "is_boss": True,
        "name": {"ru": "Арагог", "en": "Aragog"}, "emoji": "🕷️👑",
        "hp": 300, "attack": 35, "defense": 20, "speed": 10,
        "xp_reward": (300, 500), "gold_reward": (100, 250),
        "ai": AIPattern.RANDOM,
        "spells": ["venom_bite", "web_cocoon", "spider_swarm"],
        "drop_chance": 1.0, "drop_min_rarity": "rare",
    },
    # Azkaban
    "dementor": {
        "id": "dementor", "is_boss": False,
        "name": {"ru": "Дементор", "en": "Dementor"}, "emoji": "👻",
        "hp": 100, "attack": 22, "defense": 5, "speed": 10,
        "xp_reward": (40, 75), "gold_reward": (15, 40),
        "ai": AIPattern.CUNNING,
        "spells": ["soul_drain", "despair"],
        "drop_chance": 0.15,
    },
    "troll": {
        "id": "troll", "is_boss": False,
        "name": {"ru": "Тролль", "en": "Troll"}, "emoji": "👹",
        "hp": 150, "attack": 28, "defense": 18, "speed": 5,
        "xp_reward": (45, 80), "gold_reward": (18, 45),
        "ai": AIPattern.AGGRESSIVE,
        "spells": ["club_smash", "roar"],
        "drop_chance": 0.15,
    },
    "senior_dementor": {
        "id": "senior_dementor", "is_boss": True,
        "name": {"ru": "Старший дементор", "en": "Senior Dementor"}, "emoji": "👻👑",
        "hp": 400, "attack": 40, "defense": 15, "speed": 12,
        "xp_reward": (400, 700), "gold_reward": (150, 350),
        "ai": AIPattern.RANDOM,
        "spells": ["dementor_kiss", "soul_drain", "despair", "darkness"],
        "drop_chance": 1.0, "drop_min_rarity": "rare",
    },
    # Chamber of Secrets
    "basilisk_child": {
        "id": "basilisk_child", "is_boss": False,
        "name": {"ru": "Василиск-детёныш", "en": "Baby Basilisk"}, "emoji": "🐍",
        "hp": 120, "attack": 30, "defense": 15, "speed": 8,
        "xp_reward": (55, 90), "gold_reward": (20, 55),
        "ai": AIPattern.AGGRESSIVE,
        "spells": ["petrify_gaze", "venom_bite"],
        "drop_chance": 0.18,
    },
    "serpent": {
        "id": "serpent", "is_boss": False,
        "name": {"ru": "Змей", "en": "Serpent"}, "emoji": "🐍",
        "hp": 100, "attack": 25, "defense": 10, "speed": 15,
        "xp_reward": (50, 85), "gold_reward": (18, 50),
        "ai": AIPattern.CUNNING,
        "spells": ["poison_bite", "constrict"],
        "drop_chance": 0.18,
    },
    "basilisk": {
        "id": "basilisk", "is_boss": True,
        "name": {"ru": "Василиск", "en": "Basilisk"}, "emoji": "🐍👑",
        "hp": 600, "attack": 55, "defense": 30, "speed": 6,
        "xp_reward": (500, 800), "gold_reward": (200, 450),
        "ai": AIPattern.RANDOM,
        "spells": ["killing_gaze", "venom_flood", "tail_sweep"],
        "drop_chance": 1.0, "drop_min_rarity": "very_rare",
    },
    # Gringotts Caves
    "guardian_dragon": {
        "id": "guardian_dragon", "is_boss": False,
        "name": {"ru": "Дракон-охранник", "en": "Guardian Dragon"}, "emoji": "🐉",
        "hp": 140, "attack": 35, "defense": 20, "speed": 10,
        "xp_reward": (60, 100), "gold_reward": (25, 60),
        "ai": AIPattern.AGGRESSIVE,
        "spells": ["fire_breath", "tail_smash"],
        "drop_chance": 0.20,
    },
    "goblin": {
        "id": "goblin", "is_boss": False,
        "name": {"ru": "Гоблин", "en": "Goblin"}, "emoji": "👺",
        "hp": 90, "attack": 20, "defense": 14, "speed": 16,
        "xp_reward": (45, 80), "gold_reward": (30, 70),
        "ai": AIPattern.CUNNING,
        "spells": ["blade_throw", "steal"],
        "drop_chance": 0.25,
    },
    "gringotts_dragon": {
        "id": "gringotts_dragon", "is_boss": True,
        "name": {"ru": "Дракон Гринготтса", "en": "Gringotts Dragon"}, "emoji": "🐉👑",
        "hp": 800, "attack": 70, "defense": 40, "speed": 8,
        "xp_reward": (700, 1000), "gold_reward": (300, 500),
        "ai": AIPattern.RANDOM,
        "spells": ["inferno", "wing_gust", "treasure_hoard"],
        "drop_chance": 1.0, "drop_min_rarity": "very_rare",
    },
    # Voldemort's Castle
    "death_eater": {
        "id": "death_eater", "is_boss": False,
        "name": {"ru": "Пожиратель Смерти", "en": "Death Eater"}, "emoji": "🖤",
        "hp": 160, "attack": 40, "defense": 22, "speed": 14,
        "xp_reward": (70, 120), "gold_reward": (30, 80),
        "ai": AIPattern.AGGRESSIVE,
        "spells": ["crucio", "avada_kedavra_weak", "morsmordre"],
        "drop_chance": 0.22,
    },
    "nagini": {
        "id": "nagini", "is_boss": False,
        "name": {"ru": "Нагини", "en": "Nagini"}, "emoji": "🐍🖤",
        "hp": 180, "attack": 45, "defense": 18, "speed": 18,
        "xp_reward": (80, 130), "gold_reward": (35, 85),
        "ai": AIPattern.CUNNING,
        "spells": ["soul_curse", "venom_flood"],
        "drop_chance": 0.20,
    },
    "voldemort": {
        "id": "voldemort", "is_boss": True,
        "name": {"ru": "Волдеморт", "en": "Voldemort"}, "emoji": "💀👑",
        "hp": 1500, "attack": 100, "defense": 60, "speed": 20,
        "xp_reward": (1000, 2000), "gold_reward": (500, 1000),
        "ai": AIPattern.RANDOM,
        "spells": ["avada_kedavra", "crucio", "fiendfyre", "horcrux_shield"],
        "drop_chance": 1.0, "drop_min_rarity": "epic",
    },
}

# ── Monster spell library (simplified for AI) ─────────────────────────────────
MONSTER_SPELLS = {
    "bite":            {"damage": 20, "effect": None},
    "web_shot":        {"damage": 15, "effect": "slow"},
    "arrow_shot":      {"damage": 22, "effect": None},
    "prophecy_curse":  {"damage": 0,  "effect": "curse"},
    "talon_strike":    {"damage": 25, "effect": None},
    "dive":            {"damage": 30, "effect": "stun"},
    "venom_bite":      {"damage": 20, "effect": "poison"},
    "web_cocoon":      {"damage": 10, "effect": "freeze"},
    "spider_swarm":    {"damage": 40, "effect": "blind"},
    "soul_drain":      {"damage": 25, "effect": "curse"},
    "despair":         {"damage": 15, "effect": "confuse"},
    "club_smash":      {"damage": 35, "effect": "stun"},
    "roar":            {"damage": 0,  "effect": "blind"},
    "dementor_kiss":   {"damage": 60, "effect": "curse"},
    "darkness":        {"damage": 0,  "effect": "blind"},
    "petrify_gaze":    {"damage": 0,  "effect": "stun"},
    "poison_bite":     {"damage": 18, "effect": "poison"},
    "constrict":       {"damage": 20, "effect": "freeze"},
    "killing_gaze":    {"damage": 80, "effect": "stun"},
    "venom_flood":     {"damage": 35, "effect": "poison"},
    "tail_sweep":      {"damage": 45, "effect": "stun"},
    "fire_breath":     {"damage": 40, "effect": "burn"},
    "tail_smash":      {"damage": 35, "effect": "stun"},
    "blade_throw":     {"damage": 25, "effect": None},
    "steal":           {"damage": 10, "effect": "disarm"},
    "inferno":         {"damage": 70, "effect": "burn"},
    "wing_gust":       {"damage": 30, "effect": "blind"},
    "treasure_hoard":  {"damage": 50, "effect": None},
    "crucio":          {"damage": 40, "effect": "curse"},
    "avada_kedavra_weak": {"damage": 60, "effect": None},
    "morsmordre":      {"damage": 35, "effect": "burn"},
    "soul_curse":      {"damage": 30, "effect": "curse"},
    "avada_kedavra":   {"damage": 0,  "effect": "instant_kill", "chance": 0.3},
    "fiendfyre":       {"damage": 80, "effect": "burn"},
    "horcrux_shield":  {"damage": 0,  "effect": "shield"},
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


def monster_ai_action(monster: dict, current_hp: int, player_hp: int, turn: int) -> dict:
    """
    Decide monster's action for this turn.
    Returns: {"action": "attack"|"defend", "spell": spell_data}
    """
    pattern = monster.get("ai", AIPattern.AGGRESSIVE)
    spells  = monster.get("spells", [])
    hp_ratio = current_hp / monster["hp"]

    if pattern == AIPattern.AGGRESSIVE:
        spell_id = random.choice(spells)
        return {"action": "attack", "spell": MONSTER_SPELLS.get(spell_id, {"damage": monster["attack"], "effect": None}), "spell_id": spell_id}

    elif pattern == AIPattern.DEFENSIVE:
        if turn % 2 == 0 or hp_ratio < 0.4:
            return {"action": "defend", "spell": None, "spell_id": "defend"}
        spell_id = random.choice(spells)
        return {"action": "attack", "spell": MONSTER_SPELLS.get(spell_id, {"damage": monster["attack"], "effect": None}), "spell_id": spell_id}

    elif pattern == AIPattern.CUNNING:
        # Prefer debuff spells when player hp is high
        debuff_spells = [s for s in spells if MONSTER_SPELLS.get(s, {}).get("effect")]
        if player_hp > 60 and debuff_spells:
            spell_id = random.choice(debuff_spells)
        else:
            spell_id = random.choice(spells)
        return {"action": "attack", "spell": MONSTER_SPELLS.get(spell_id, {"damage": monster["attack"], "effect": None}), "spell_id": spell_id}

    else:  # RANDOM (bosses)
        if random.random() < 0.15 and hp_ratio < 0.5:
            return {"action": "defend", "spell": None, "spell_id": "defend"}
        spell_id = random.choice(spells)
        return {"action": "attack", "spell": MONSTER_SPELLS.get(spell_id, {"damage": monster["attack"], "effect": None}), "spell_id": spell_id}
