"""
Drop system — determines what items/spells drop after fights.
Implements anti-farm XP reduction per TZ section 5.
"""
import random
from game.spells import SPELLS, RARITY_DROP_CHANCE as SPELL_DROP_CHANCE, spells_by_rarity
from game.items  import roll_equipment, RARITIES

# Rarity order for comparison
_RARITY_ORDER = ["common", "uncommon", "rare", "very_rare", "epic", "legendary", "mythical", "abyssal"]


def _rarity_index(rarity: str) -> int:
    try:
        return _RARITY_ORDER.index(rarity)
    except ValueError:
        return 0


def roll_spell_drop(
    luck_modifier: float = 1.0,
    min_rarity: str = "uncommon",
    allowed_rarities: list[str] | None = None,
) -> str | None:
    """
    Roll a random spell drop.
    Returns spell_id or None if no drop this time.
    """
    if allowed_rarities is None:
        allowed_rarities = ["uncommon", "rare", "very_rare", "epic", "legendary"]

    min_idx = _rarity_index(min_rarity)
    eligible = [r for r in allowed_rarities if _rarity_index(r) >= min_idx]

    # Base chance to get ANY spell drop
    base_chance = 0.12 * luck_modifier
    if random.random() > base_chance:
        return None

    # Pick rarity weighted by drop chances
    rarities = [r for r in eligible if spells_by_rarity(r)]
    if not rarities:
        return None

    weights = [SPELL_DROP_CHANCE.get(r, 0.01) for r in rarities]
    chosen_rarity = random.choices(rarities, weights=weights, k=1)[0]

    candidates = spells_by_rarity(chosen_rarity)
    if not candidates:
        return None
    return random.choice(candidates)["id"]


def roll_item_drop(
    luck_modifier: float = 1.0,
    min_rarity: str = "common",
    guaranteed: bool = False,
) -> dict | None:
    """
    Roll a random equipment drop.
    Returns item dict or None.
    """
    base_chance = 0.20 * luck_modifier
    if not guaranteed and random.random() > base_chance:
        return None

    min_idx = _rarity_index(min_rarity)
    eligible = [r[0] for r in RARITIES if _rarity_index(r[0]) >= min_idx]
    if not eligible:
        eligible = ["common"]

    weights = [1.0 / (i + 1) for i in range(len(eligible))]
    chosen_rarity = random.choices(eligible, weights=weights, k=1)[0]
    item = roll_equipment(chosen_rarity)
    item["bonus"] = random.randint(item["stat_min"], item["stat_max"])
    return item


def monster_drop(monster: dict, luck_modifier: float = 1.0) -> dict:
    """
    Generate full drop from a monster kill.
    Returns {"xp": int, "gold": int, "spell": str|None, "item": dict|None}
    """
    xp_range   = monster.get("xp_reward",   (30, 80))
    gold_range = monster.get("gold_reward",  (10, 40))
    drop_chance = monster.get("drop_chance", 0.15)
    min_rarity  = monster.get("drop_min_rarity", "common")
    guaranteed  = monster.get("is_boss", False)

    xp   = random.randint(*xp_range)
    gold = random.randint(*gold_range)

    spell = None
    item  = None

    if random.random() <= drop_chance * luck_modifier:
        # 50/50 between spell and item drop
        if random.random() < 0.5:
            spell = roll_spell_drop(luck_modifier=luck_modifier, min_rarity=min_rarity)
        else:
            item = roll_item_drop(luck_modifier=luck_modifier, min_rarity=min_rarity, guaranteed=guaranteed)

    if guaranteed and item is None and spell is None:
        item = roll_item_drop(luck_modifier=luck_modifier, min_rarity=min_rarity, guaranteed=True)

    return {"xp": xp, "gold": gold, "spell": spell, "item": item}


def apply_antifarm_xp(
    base_xp: int,
    repeat_count: int,      # how many times this monster type fought today
    consecutive_wins: int,  # consecutive wins over SAME player (PvP)
    player_level: int,
    daily_xp_earned: int,
) -> int:
    """
    Apply anti-farm penalties per TZ section 5.
    - PvE: -10% XP for each repeat fight vs same monster type (daily)
    - PvP: -50% if >5 consecutive wins vs same player
    - Daily XP cap: level * 300
    """
    xp = base_xp

    # PvE repeated monster penalty
    if repeat_count > 0:
        penalty = min(0.10 * repeat_count, 0.80)
        xp = int(xp * (1 - penalty))

    # PvP consecutive wins penalty
    if consecutive_wins >= 5:
        xp = xp // 2

    # Daily cap
    daily_cap = player_level * 300
    remaining = daily_cap - daily_xp_earned
    if remaining <= 0:
        return 0
    return min(xp, remaining)


def lesson_drop(luck_modifier: float = 1.0) -> str | None:
    """15% chance to drop a spell from lessons per TZ."""
    if random.random() > 0.15 * luck_modifier:
        return None
    return roll_spell_drop(luck_modifier=luck_modifier, min_rarity="uncommon",
                            allowed_rarities=["uncommon"])
