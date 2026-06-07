"""
Battle Engine — handles both PvP and PvE combat logic.
Stateless: callers maintain state between turns.
"""
import random
import math
from game.spells import SPELLS, get_spell

# ── House advantage matrix (TZ 8.1) ───────────────────────────────────────────
HOUSE_ADVANTAGE: dict[str, str] = {
    "gryffindor": "slytherin",
    "slytherin":  "ravenclaw",
    "ravenclaw":  "hufflepuff",
    "hufflepuff": "gryffindor",
}
HOUSE_ADVANTAGE_BONUS = 0.15  # +15% damage


def _house_damage_mult(attacker_house: str | None, defender_house: str | None) -> float:
    if attacker_house and HOUSE_ADVANTAGE.get(attacker_house) == defender_house:
        return 1 + HOUSE_ADVANTAGE_BONUS
    return 1.0


# ── Status effect helpers ──────────────────────────────────────────────────────
def fresh_status() -> dict:
    return {
        "burn":      0,   # turns remaining
        "freeze":    0,
        "stun":      0,
        "blind":     0,
        "curse":     0,
        "poison":    0,
        "confuse":   0,
        "disarmed":  0,
        "shield":    0,   # HP remaining in shield
        "block":     False,
        "reflect":   False,
        "silence":   0,   # turns can't use spells
    }


def tick_status(status: dict) -> tuple[dict, int]:
    """
    Advance one turn: decrement timers, return (new_status, dot_damage).
    """
    dmg = 0
    s = status.copy()

    if s["burn"] > 0:
        dmg += 10
        s["burn"] -= 1
    if s["poison"] > 0:
        dmg += 8
        s["poison"] -= 1
    if s["curse"] > 0:
        dmg += 10
        s["curse"] -= 1
    for key in ("freeze", "stun", "blind", "confuse", "disarmed", "silence"):
        if s[key] > 0:
            s[key] -= 1
    # block and reflect reset each turn
    s["block"]   = False
    s["reflect"] = False
    return s, dmg


def apply_effect(effect: str, status: dict, value: int = 1) -> dict:
    s = status.copy()
    if effect == "burn":    s["burn"]    = max(s["burn"],    3)
    elif effect == "freeze": s["freeze"]  = max(s["freeze"],  2)
    elif effect == "stun":   s["stun"]    = max(s["stun"],    1)
    elif effect == "blind":  s["blind"]   = max(s["blind"],   2)
    elif effect == "curse":  s["curse"]   = max(s["curse"],   3)
    elif effect == "poison": s["poison"]  = max(s["poison"],  4)
    elif effect == "confuse":s["confuse"] = max(s["confuse"], 1)
    elif effect == "disarm": s["disarmed"]= max(s["disarmed"],1)
    elif effect == "block":  s["block"]   = True
    elif effect == "reflect":s["reflect"] = True
    elif effect == "shield": s["shield"]  += 60   # basic shield HP
    elif effect == "cleanse":
        for key in ("burn", "freeze", "blind", "curse", "poison", "confuse"):
            s[key] = 0
    elif effect == "silence":s["silence"] = max(s["silence"], 2)
    elif effect == "slow":   s["stun"]    = max(s["stun"], 1)
    return s


# ── Core combat calculator ─────────────────────────────────────────────────────
def calculate_damage(
    spell: dict,
    attacker: dict,       # {attack, luck, house}
    defender: dict,       # {defense, house}
    attacker_status: dict,
    defender_status: dict,
) -> tuple[int, bool, bool]:
    """
    Compute damage dealt.
    Returns (final_damage, is_crit, missed).
    """
    base = spell.get("damage", 0)
    if base == 0:
        return 0, False, False

    # Miss chance from blind
    if attacker_status["blind"] > 0:
        miss_chance = 0.50
        if random.random() < miss_chance:
            return 0, False, True

    # Confuse: attacker hits themselves
    if attacker_status["confuse"] > 0:
        # caller handles this separately
        pass

    # Crit based on luck (base 5% + 0.5% per luck point)
    luck       = attacker.get("luck", 5)
    crit_chance = 0.05 + luck * 0.005
    is_crit     = random.random() < crit_chance
    if is_crit:
        base = int(base * 1.5)

    # Attack modifier
    base = int(base * (attacker.get("attack", 10) / 20))

    # House advantage
    mult = _house_damage_mult(attacker.get("house"), defender.get("house"))
    base = int(base * mult)

    # Defender's defense reduction
    defense = defender.get("defense", 5)
    reduction = defense / (defense + 30)  # soft-cap formula
    damage = int(base * (1 - reduction))

    # Shield absorption
    if defender_status["shield"] > 0:
        absorbed = min(defender_status["shield"], damage)
        damage  -= absorbed
        defender_status["shield"] -= absorbed

    # Block: reduce 40%
    if defender_status["block"]:
        damage = int(damage * 0.6)

    # Reflect: send 25% back (caller handles reflected hp)
    reflect_dmg = 0
    if defender_status["reflect"]:
        reflect_dmg = int(damage * 0.25)

    return max(damage, 0), is_crit, False


def apply_spell_effect(
    spell: dict,
    attacker_status: dict,
    defender_status: dict,
    attacker_luck: int = 5,
) -> tuple[dict, dict, bool]:
    """
    Roll and apply spell's status effect.
    Returns (new_attacker_status, new_defender_status, effect_triggered).
    """
    effect = spell.get("effect")
    chance = spell.get("effect_chance", 0.0)

    if not effect or random.random() > chance:
        return attacker_status, defender_status, False

    if effect == "instant_kill":
        return attacker_status, defender_status, True  # caller handles

    # Cleanse / block / reflect go on attacker
    if effect in ("cleanse", "block", "reflect", "shield"):
        new_atk = apply_effect(effect, attacker_status)
        return new_atk, defender_status, True

    # All others go on defender
    new_def = apply_effect(effect, defender_status)
    return attacker_status, new_def, True


def resolve_turn(
    spell_id: str,
    attacker: dict,         # full user/monster dict
    defender: dict,
    attacker_status: dict,
    defender_status: dict,
    attacker_current_hp: int,
    defender_current_hp: int,
    attacker_current_mana: int,
) -> dict:
    """
    Resolve a single combat turn.
    Returns full result dict.
    """
    spell = get_spell(spell_id)
    result = {
        "spell_id":      spell_id,
        "damage":        0,
        "heal":          0,
        "mana_cost":     0,
        "effect":        None,
        "effect_hit":    False,
        "crit":          False,
        "missed":        False,
        "skipped":       False,
        "instant_kill":  False,
        "confuse_self":  False,
        "reflect_damage":0,
        "attacker_hp":   attacker_current_hp,
        "defender_hp":   defender_current_hp,
        "log":           "",
    }

    if spell is None:
        result["log"] = "❌ Неизвестное заклинание"
        return result

    # Mana cost
    mana_cost = spell.get("mana", 0)
    if attacker_current_mana < mana_cost:
        result["log"] = "💧 Недостаточно маны!"
        return result
    result["mana_cost"] = mana_cost

    # Stun: skip turn
    if attacker_status.get("stun", 0) > 0:
        result["skipped"] = True
        result["log"] = "😵 Оглушён — ход пропущен!"
        return result

    # Silence: can't use spells
    if attacker_status.get("silence", 0) > 0 and spell.get("mana", 0) > 0:
        result["log"] = "🤐 Молчание — нельзя использовать заклинания!"
        result["skipped"] = True
        return result

    # Confuse: might attack self
    if attacker_status.get("confuse", 0) > 0 and random.random() < 0.5:
        result["confuse_self"] = True
        result["log"] = "🔄 Замешательство — атака по себе!"
        # minimal self-damage
        result["damage"] = max(int(spell.get("damage", 10) * 0.5), 5)
        result["attacker_hp"] = max(0, attacker_current_hp - result["damage"])
        return result

    stype = spell.get("type", "attack")

    # ── Healing spell ─────────────────────────────────────────────────────────
    if stype == "heal":
        heal = spell.get("heal", 0)
        if attacker_status.get("curse", 0) > 0:
            result["log"] = "☠️ Проклятие — лечение невозможно!"
            result["skipped"] = True
            return result
        # Cleanse effect
        new_atk, _, hit = apply_spell_effect(spell, attacker_status, defender_status, attacker.get("luck", 5))
        result["heal"] = heal
        result["attacker_hp"] = min(attacker.get("max_hp", 100), attacker_current_hp + heal)
        result["effect"] = spell.get("effect")
        result["effect_hit"] = hit
        result["log"] = f"💚 +{heal} ХП"
        return result

    # ── Defense / buff spell ──────────────────────────────────────────────────
    if stype == "defense":
        new_atk, new_def, hit = apply_spell_effect(spell, attacker_status, defender_status, attacker.get("luck", 5))
        result["effect"] = spell.get("effect")
        result["effect_hit"] = hit
        result["log"] = f"🛡️ {spell['id']}"
        return result

    # ── Attack / debuff spell ─────────────────────────────────────────────────
    dmg, is_crit, missed = calculate_damage(spell, attacker, defender, attacker_status, defender_status)

    result["crit"]   = is_crit
    result["missed"] = missed
    result["damage"] = dmg

    if missed:
        result["log"] = "💨 Промах!"
        return result

    # Instant kill (Avada Kedavra)
    if spell.get("effect") == "instant_kill":
        chance = spell.get("effect_chance", 0.5)
        if random.random() < chance:
            result["instant_kill"] = True
            result["defender_hp"]  = 0
            result["log"] = "☠️ Авада Кедавра! Мгновенная победа!"
            return result

    # Reflect damage
    reflect_dmg = 0
    if defender_status.get("reflect"):
        reflect_dmg = int(dmg * 0.25)
        result["reflect_damage"] = reflect_dmg

    result["defender_hp"] = max(0, defender_current_hp - dmg)
    result["attacker_hp"] = max(0, attacker_current_hp - reflect_dmg)

    # Status effect
    _, new_def, hit = apply_spell_effect(spell, attacker_status, defender_status, attacker.get("luck", 5))
    result["effect"]     = spell.get("effect")
    result["effect_hit"] = hit

    crit_tag = " 💥КРИТ!" if is_crit else ""
    result["log"] = f"⚡ {dmg} урона{crit_tag}"
    return result


def determine_turn_order(player_speed: int, opponent_speed: int) -> str:
    """Returns 'player' or 'opponent'."""
    if player_speed == opponent_speed:
        return random.choice(["player", "opponent"])
    return "player" if player_speed >= opponent_speed else "opponent"


def format_battle_status(status: dict) -> str:
    """Format status effects for display."""
    icons = []
    if status.get("burn",    0) > 0: icons.append("🔥")
    if status.get("freeze",  0) > 0: icons.append("❄️")
    if status.get("stun",    0) > 0: icons.append("😵")
    if status.get("blind",   0) > 0: icons.append("🌑")
    if status.get("disarmed",0) > 0: icons.append("🔄")
    if status.get("curse",   0) > 0: icons.append("☠️")
    if status.get("poison",  0) > 0: icons.append("🟢")
    if status.get("confuse", 0) > 0: icons.append("💫")
    return " ".join(icons)
