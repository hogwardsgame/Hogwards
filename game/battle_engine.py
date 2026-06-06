# game/battle_engine.py

import random
from typing import Dict, Any, Tuple, List, Optional

from game.spells import get_spell, calculate_damage


# ─────────────────────────────────────────────
# 🧠 СОСТОЯНИЕ БОЯ
# ─────────────────────────────────────────────

class BattleState:
    def __init__(self, p1: dict, p2: dict):
        self.p1 = p1
        self.p2 = p2

        self.hp = {
            p1["user_id"]: p1["hp"],
            p2["user_id"]: p2["hp"]
        }

        self.mana = {
            p1["user_id"]: p1["mana"],
            p2["user_id"]: p2["mana"]
        }

        self.status = {
            p1["user_id"]: [],
            p2["user_id"]: []
        }

        self.turn = 1
        self.history: List[dict] = []
        self.finished = False
        self.winner_id: Optional[int] = None


# ─────────────────────────────────────────────
# ⚔️ ОСНОВНОЙ ДВИЖОК БОЯ
# ─────────────────────────────────────────────

def apply_spell(state: BattleState, attacker_id: int, defender_id: int, spell_id: str):
    spell = get_spell(spell_id)

    if not spell:
        return {"error": "Unknown spell"}

    # ─────────────────────────────
    # Проверка маны
    # ─────────────────────────────
    if state.mana[attacker_id] < spell.mana_cost:
        return {"error": "Not enough mana"}

    state.mana[attacker_id] -= spell.mana_cost

    log = {
        "turn": state.turn,
        "attacker": attacker_id,
        "defender": defender_id,
        "spell": spell_id,
        "events": []
    }

    # ─────────────────────────────
    # ХИЛ
    # ─────────────────────────────
    if spell.heal > 0:
        heal = spell.heal
        state.hp[attacker_id] += heal
        log["events"].append(f"heal +{heal}")
        state.history.append(log)
        return log

    # ─────────────────────────────
    # УРОН
    # ─────────────────────────────
    damage = calculate_damage(
        spell_id,
        attacker_attack=10,   # позже заменим на статы игрока
        target_defense=5
    )

    state.hp[defender_id] -= damage
    log["events"].append(f"damage {damage}")

    # ─────────────────────────────
    # СТАТУСЫ
    # ─────────────────────────────

    # оглушение
    if spell.stun_chance and random.random() < spell.stun_chance:
        state.status[defender_id].append("stun")
        log["events"].append("stun applied")

    # горение
    if spell.burn:
        state.status[defender_id].append(f"burn:{spell.burn}")
        log["events"].append(f"burn {spell.burn}")

    # заморозка
    if spell.freeze:
        state.status[defender_id].append("freeze")
        log["events"].append("freeze applied")

    # путаница
    if spell.confusion:
        state.status[defender_id].append("confusion")
        log["events"].append("confusion applied")

    # ─────────────────────────────
    # ПРОВЕРКА ПОБЕДЫ
    # ─────────────────────────────
    if state.hp[defender_id] <= 0:
        state.finished = True
        state.winner_id = attacker_id
        log["events"].append("victory")

    state.history.append(log)
    return log


# ─────────────────────────────────────────────
# 🔁 СЛЕДУЮЩИЙ ХОД
# ─────────────────────────────────────────────

def next_turn(state: BattleState):
    state.turn += 1


# ─────────────────────────────────────────────
# 🏁 ПРОВЕРКА ОКОНЧАНИЯ БОЯ
# ─────────────────────────────────────────────

def is_finished(state: BattleState) -> bool:
    return state.finished


def get_winner(state: BattleState):
    return state.winner_id


# ─────────────────────────────────────────────
# 📜 ИСТОРИЯ БОЯ
# ─────────────────────────────────────────────

def get_history(state: BattleState):
    return state.history
