# game/spells.py

from dataclasses import dataclass
from typing import Dict, Optional
import random


# ─────────────────────────────────────────────
# 🎯 МОДЕЛЬ ЗАКЛИНАНИЯ
# ─────────────────────────────────────────────

@dataclass
class Spell:
    id: str
    name: str
    type: str  # attack / defense / debuff / heal
    mana_cost: int
    power: int = 0  # базовый урон или сила эффекта

    # эффекты
    stun_chance: float = 0.0
    burn: int = 0
    freeze: bool = False
    confusion: bool = False
    silence: bool = False
    shield: float = 0.0
    reflect: float = 0.0
    heal: int = 0
    dispel: bool = False


# ─────────────────────────────────────────────
# 🔮 БАЗОВЫЕ ЗАКЛИНАНИЯ
# ─────────────────────────────────────────────

SPELLS: Dict[str, Spell] = {

    # ─── АТАКА ───────────────────────────────
    "expelliarmus": Spell(
        id="expelliarmus",
        name="Экспеллиармус",
        type="attack",
        mana_cost=15,
        power=25,
        silence=True  # разоружение (условно: запрет 1 случайного заклинания)
    ),

    "stupify": Spell(
        id="stupify",
        name="Ступефай",
        type="attack",
        mana_cost=25,
        power=35,
        stun_chance=0.4
    ),

    "confundus": Spell(
        id="confundus",
        name="Конфундус",
        type="attack",
        mana_cost=20,
        power=20,
        confusion=True
    ),

    "flipendo": Spell(
        id="flipendo",
        name="Флипендо",
        type="attack",
        mana_cost=20,
        power=30
    ),

    # ─── ЗАЩИТА ─────────────────────────────
    "protego": Spell(
        id="protego",
        name="Протего",
        type="defense",
        mana_cost=20,
        shield=0.4
    ),

    "escudo": Spell(
        id="escudo",
        name="Эскудо",
        type="defense",
        mana_cost=25,
        heal=20
    ),

    "ricochet": Spell(
        id="ricochet",
        name="Рикошет",
        type="defense",
        mana_cost=30,
        reflect=0.25
    ),

    # ─── ДЕБАФФ ────────────────────────────
    "inflammare": Spell(
        id="inflammare",
        name="Инфламмаре",
        type="debuff",
        mana_cost=25,
        burn=10
    ),

    "ice_chain": Spell(
        id="ice_chain",
        name="Ледяная цепь",
        type="debuff",
        mana_cost=30,
        freeze=True
    ),

    "tenebrus": Spell(
        id="tenebrus",
        name="Тенебрус",
        type="debuff",
        mana_cost=20,
        silence=True
    ),

    # ─── ЛЕЧЕНИЕ ────────────────────────────
    "vulnero": Spell(
        id="vulnero",
        name="Вулнеро",
        type="heal",
        mana_cost=30,
        heal=30
    ),

    "sanacus": Spell(
        id="sanacus",
        name="Санакус",
        type="heal",
        mana_cost=25,
        heal=15,
        dispel=True
    ),
}


# ─────────────────────────────────────────────
# ⚙️ ФУНКЦИИ
# ─────────────────────────────────────────────

def get_spell(spell_id: str) -> Optional[Spell]:
    return SPELLS.get(spell_id)


def get_all_spells():
    return list(SPELLS.values())


def is_attack(spell_id: str) -> bool:
    spell = get_spell(spell_id)
    return spell and spell.type == "attack"


def is_defense(spell_id: str) -> bool:
    spell = get_spell(spell_id)
    return spell and spell.type == "defense"


def calculate_damage(spell_id: str, attacker_attack: int, target_defense: int) -> int:
    """
    Базовая формула урона
    """
    spell = get_spell(spell_id)
    if not spell:
        return 0

    base = spell.power + attacker_attack - target_defense
    return max(1, base)


def roll_stun(spell_id: str) -> bool:
    spell = get_spell(spell_id)
    if not spell:
        return False
    return random.random() < spell.stun_chance


def apply_shield(damage: int, shield: float) -> int:
    return int(damage * (1 - shield))


def apply_reflect(damage: int, reflect: float) -> int:
    return int(damage * reflect)
