# game/battle_engine.py

import random
from typing import Optional, List
from game.spells import get_spell, calculate_damage


# ─────────────────────────────────────────────
# 🧠 БОЙ
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
        self.history = []
        self.finished = False
        self.winner_id = None


# ─────────────────────────────────────────────
# ⚙️ УТИЛИТЫ СТАТУСОВ
# ─────────────────────────────────────────────

def has_status(state: BattleState, user_id: int, status: str) -> bool:
    return any(status in s for s in state.status[user_id])


def apply_burn(state: BattleState, user_id: int):
    for s in state.status[user_id]:
        if s.startswith("burn:"):
            dmg = int(s.split(":")[1])
            state.hp[user_id] -= dmg
            return dmg
    return 0


def clear_one_time_statuses(state: BattleState, user_id: int):
    state.status[user_id] = [
        s for s in state.status[user_id]
        if s != "stun"
    ]


# ─────────────────────────────────────────────
# ⚔️ ХОД БОЯ
# ─────────────────────────────────────────────

def apply_spell(state: BattleState, attacker_id: int, defender_id: int, spell_id: str):
    spell = get_spell(spell_id)

    if not spell:
        return {"error": "Unknown spell"}

    # ───────────── МАНА ─────────────
    if state.mana[attacker_id] < spell.mana_cost:
        return {"error": "Not enough mana"}

    # ───────────── СТАН ─────────────
    if has_status(state, attacker_id, "stun"):
        state.status[attacker_id].remove("stun")
        return {"error": "You are stunned"}

    # ───────────── МАНА СПИСАНИЕ ─────────────
    state.mana[attacker_id] -= spell.mana_cost

    log = {
        "turn": state.turn,
        "attacker": attacker_id,
        "defender": defender_id,
        "spell": spell_id,
        "events": []
    }

    # ───────────── БЕРН УРОН ─────────────
    burn_damage = apply_burn(state, attacker_id)
    if burn_damage:
        log["events"].append(f"burn_self:{burn_damage}")

    burn_def = apply_burn(state, defender_id)
    if burn_def:
        log["events"].append(f"burn_enemy:{burn_def}")

    # ───────────── ЛЕЧЕНИЕ ─────────────
    if spell.heal > 0:
        state.hp[attacker_id] += spell.heal
        log["events"].append(f"heal +{spell.heal}")
        state.history.append(log)
        return log

    # ───────────── УРОН ─────────────
    attacker_stats = state.p1 if attacker_id == state.p1["user_id"] else state.p2
    defender_stats = state.p1 if defender_id == state.p1["user_id"] else state.p2

    base_damage = calculate_damage(
        spell_id,
        attacker_stats["attack"],
        defender_stats["defense"]
    )

    # защита (Protego)
    if has_status(state, defender_id, "shield"):
        base_damage = int(base_damage * 0.6)

    state.hp[defender_id] -= base_damage
    log["events"].append(f"damage:{base_damage}")

    # ───────────── ЭФФЕКТЫ ─────────────

    if spell.stun_chance and random.random() < spell.stun_chance:
        state.status[defender_id].append("stun")
        log["events"].append("stun")

    if spell.burn:
        state.status[defender_id].append(f"burn:{spell.burn}")
        log["events"].append("burn")

    if spell.freeze:
        state.status[defender_id].append("freeze")
        log["events"].append("freeze")

    if spell.confusion:
        state.status[defender_id].append("confusion")
        log["events"].append("confusion")

    # ───────────── ПРОВЕРКА ПОБЕДЫ ─────────────
    if state.hp[defender_id] <= 0:
        state.finished = True
        state.winner_id = attacker_id
        log["events"].append("victory")

    state.history.append(log)

    clear_one_time_statuses(state, attacker_id)

    return log


# ─────────────────────────────────────────────
# 🔁 ХОД
# ─────────────────────────────────────────────

def next_turn(state: BattleState):
    state.turn += 1


def is_finished(state: BattleState) -> bool:
    return state.finished


def get_winner(state: BattleState):
    return state.winner_id


def get_history(state: BattleState):
    return state.history
