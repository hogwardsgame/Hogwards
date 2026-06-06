# game/battle_engine.py

import random
from typing import Optional
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

        # ⚡ инициатива
        self.turn_order = sorted(
            [p1["user_id"], p2["user_id"]],
            key=lambda uid: self.get_speed(uid),
            reverse=True
        )

        self.current_turn_index = 0
        self.turn = 1

        self.finished = False
        self.winner_id = None

    # ─────────────────────────────
    def get_speed(self, uid):
        if uid == self.p1["user_id"]:
            return self.p1["speed"]
        return self.p2["speed"]


# ─────────────────────────────────────────────
# 🧠 СТАТУСЫ
# ─────────────────────────────────────────────

def has_status(state, uid, name):
    return any(name in s for s in state.status[uid])


def apply_dot(state, uid):
    """урон по времени (burn)"""
    total = 0
    for s in state.status[uid]:
        if s.startswith("burn:"):
            dmg = int(s.split(":")[1])
            state.hp[uid] -= dmg
            total += dmg
    return total


def cleanup_status(state, uid):
    # stun снимается после хода
    state.status[uid] = [s for s in state.status[uid] if s != "stun"]


# ─────────────────────────────────────────────
# ⚔️ ХОД
# ─────────────────────────────────────────────

def apply_spell(state: BattleState, attacker_id: int, defender_id: int, spell_id: str):

    if state.finished:
        return {"error": "Battle finished"}

    spell = get_spell(spell_id)
    if not spell:
        return {"error": "Unknown spell"}

    # ───── проверка маны ─────
    if state.mana[attacker_id] < spell.mana_cost:
        return {"error": "Not enough mana"}

    # ───── stun / freeze ─────
    if has_status(state, attacker_id, "stun"):
        cleanup_status(state, attacker_id)
        return {"error": "You are stunned"}

    if has_status(state, attacker_id, "freeze"):
        return {"error": "You are frozen"}

    state.mana[attacker_id] -= spell.mana_cost

    log = {
        "attacker": attacker_id,
        "defender": defender_id,
        "spell": spell_id,
        "events": []
    }

    # ───── DOT (burn) ─────
    dmg_self = apply_dot(state, attacker_id)
    dmg_enemy = apply_dot(state, defender_id)

    if dmg_self:
        log["events"].append(f"burn_self:{dmg_self}")
    if dmg_enemy:
        log["events"].append(f"burn_enemy:{dmg_enemy}")

    # ───── HEAL ─────
    if spell.heal:
        state.hp[attacker_id] += spell.heal
        log["events"].append(f"heal:{spell.heal}")
        return log

    # ───── DAMAGE ─────
    attacker = state.p1 if attacker_id == state.p1["user_id"] else state.p2
    defender = state.p1 if defender_id == state.p1["user_id"] else state.p2

    damage = calculate_damage(
        spell_id,
        attacker["attack"],
        defender["defense"]
    )

    # 🛡 protego effect
    if has_status(state, defender_id, "shield"):
        damage = int(damage * 0.6)

    state.hp[defender_id] -= damage
    log["events"].append(f"damage:{damage}")

    # ───── EFFECTS ─────
    if spell.stun_chance and random.random() < spell.stun_chance:
        state.status[defender_id].append("stun")

    if spell.burn:
        state.status[defender_id].append(f"burn:{spell.burn}")

    if spell.freeze:
        state.status[defender_id].append("freeze")

    if spell.confusion:
        state.status[defender_id].append("confusion")

    # ───── WIN CHECK ─────
    if state.hp[defender_id] <= 0:
        state.finished = True
        state.winner_id = attacker_id
        log["events"].append("victory")

    return log


# ─────────────────────────────────────────────
# 🔁 СЛЕДУЮЩИЙ ХОД
# ─────────────────────────────────────────────

def next_turn(state: BattleState):

    state.current_turn_index += 1

    if state.current_turn_index >= len(state.turn_order):
        state.current_turn_index = 0
        state.turn += 1


# ─────────────────────────────────────────────
# 🏁 ФИНАЛ
# ─────────────────────────────────────────────

def is_finished(state):
    return state.finished


def get_winner(state):
    return state.winner_id


def get_current_player(state):
    return state.turn_order[state.current_turn_index]
