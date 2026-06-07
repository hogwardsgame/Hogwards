"""
Battle Engine — handles both PvP and PvE combat logic.
Stateless: callers maintain state between turns.

ИСПРАВЛЕНИЯ:
  1. resolve_turn теперь возвращает new_atk_status и new_def_status
  2. calculate_damage больше не мутирует defender_status напрямую —
     возвращает updated_defender_status отдельно
  3. Щит (shield) корректно сохраняется после поглощения урона
  4. reflect_damage корректно возвращается из calculate_damage

НОВОЕ:
  - Таблица атмосферных фраз для критов, промахов, эффектов (Хогвартс-флейвор)
  - Функция flavour_line() для генерации случайных реплик
  - Функция battle_summary() — итоговая статистика боя
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

# ── Атмосферные реплики (новое) ────────────────────────────────────────────────
_FLAVOUR: dict[str, list[str]] = {
    "crit": [
        "💥 Блестящее попадание — профессор Флитвик был бы доволен!",
        "💥 Невероятный крит! Дамблдор кивнул бы с одобрением.",
        "💥 Критический удар! Стены Хогвартса задрожали.",
        "💥 Безупречное исполнение! Даже портреты на стенах зааплодировали.",
    ],
    "miss": [
        "💨 Заклинание ушло в никуда... Нужно больше практики!",
        "💨 Промах! Мадам Хуч недовольно покачала головой.",
        "💨 Заклинание рассеялось в воздухе.",
        "💨 Мисс! Полтергейст Пивз захихикал.",
    ],
    "stun": [
        "😵 Оглушён! Звёзды перед глазами...",
        "😵 Stupefied! Ход пропущен.",
    ],
    "burn": [
        "🔥 Пламя пожирает! Огонь Горного тролля ничто по сравнению с этим.",
        "🔥 Горит! Феникс Дамблдора сочувственно пискнул.",
    ],
    "freeze": [
        "❄️ Заморожен! Холоднее подвалов Азкабана.",
        "❄️ Лёд сковал движения!",
    ],
    "poison": [
        "🟢 Яд течёт по жилам... Беззар бы сейчас не помешал.",
        "🟢 Отравлен! Профессор Снейп знал бы противоядие.",
    ],
    "instant_kill": [
        "☠️ АВАДА КЕДАВРА! Зелёная вспышка — и всё кончено.",
        "☠️ Непростительное заклинание! Мгновенная победа.",
    ],
    "confuse": [
        "💫 Замешательство! Где свои, где чужие?",
        "💫 Голова идёт кругом от Конфундуса...",
    ],
    "reflect": [
        "🪞 Заклинание отражено обратно! Протего работает!",
        "🪞 Зеркальный щит отбил удар!",
    ],
    "shield_break": [
        "💢 Щит разрушен! Магическая защита рассеялась.",
        "💢 Протего пробит — теперь ты уязвим!",
    ],
    "level_up_hint": [
        "✨ Ещё немного — и новый уровень!",
    ],
    "low_hp": [
        "😰 Совсем плохо... ещё удар и конец.",
        "😰 Держись! Очень мало ХП осталось.",
    ],
    "mana_low": [
        "💧 Мана на исходе! Скоро нечем будет колдовать.",
        "💧 Силы иссякают...",
    ],
}


def flavour_line(event: str) -> str:
    """Возвращает случайную атмосферную реплику для события."""
    lines = _FLAVOUR.get(event, [])
    return random.choice(lines) if lines else ""


def battle_summary(turns: int, total_dmg_dealt: int, total_dmg_taken: int) -> str:
    """Итоговая статистика боя."""
    rating = "⭐⭐⭐" if total_dmg_taken == 0 else ("⭐⭐" if total_dmg_taken < total_dmg_dealt // 2 else "⭐")
    return (
        f"📊 *Итог боя:*\n"
        f"Ходов: {turns} | "
        f"Нанесено: {total_dmg_dealt} | "
        f"Получено: {total_dmg_taken}\n"
        f"Оценка: {rating}"
    )


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


def _house_damage_mult(attacker_house: str | None, defender_house: str | None) -> float:
    if attacker_house and HOUSE_ADVANTAGE.get(attacker_house) == defender_house:
        return 1 + HOUSE_ADVANTAGE_BONUS
    return 1.0


# ── Core combat calculator ─────────────────────────────────────────────────────
def calculate_damage(
    spell: dict,
    attacker: dict,        # {attack, luck, house}
    defender: dict,        # {defense, house}
    attacker_status: dict,
    defender_status: dict,
) -> tuple[int, bool, bool, int, dict]:
    """
    Compute damage dealt.
    Returns (final_damage, is_crit, missed, reflect_damage, updated_defender_status).

    ИСПРАВЛЕНИЕ: больше не мутируем defender_status напрямую —
    возвращаем обновлённую копию (чтобы щит сохранялся).
    """
    def_status = defender_status.copy()  # работаем с копией

    base = spell.get("damage", 0)
    if base == 0:
        return 0, False, False, 0, def_status

    # Miss chance from blind
    if attacker_status.get("blind", 0) > 0:
        if random.random() < 0.50:
            return 0, False, True, 0, def_status

    # Crit based on luck (base 5% + 0.5% per luck point)
    luck        = attacker.get("luck", 5)
    crit_chance = 0.05 + luck * 0.005
    is_crit     = random.random() < crit_chance
    if is_crit:
        base = int(base * 1.5)

    # Attack modifier
    base = int(base * (attacker.get("attack", 10) / 20))

    # House advantage
    mult = _house_damage_mult(attacker.get("house"), defender.get("house"))
    base = int(base * mult)

    # Defender's defense reduction (soft-cap formula)
    defense = defender.get("defense", 5)
    reduction = defense / (defense + 30)
    damage = int(base * (1 - reduction))

    # Shield absorption — ИСПРАВЛЕНИЕ: обновляем копию, не оригинал
    if def_status.get("shield", 0) > 0:
        absorbed = min(def_status["shield"], damage)
        damage  -= absorbed
        def_status["shield"] -= absorbed

    # Block: reduce 40%
    if def_status.get("block"):
        damage = int(damage * 0.6)

    # Reflect: send 25% back
    reflect_dmg = 0
    if def_status.get("reflect"):
        reflect_dmg = int(damage * 0.25)

    return max(damage, 0), is_crit, False, reflect_dmg, def_status


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

    # Cleanse / block / reflect / shield go on attacker
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

    ИСПРАВЛЕНИЕ: теперь возвращает new_atk_status и new_def_status —
    без этого статусы (щит, яд, оглушение) не сохранялись между ходами!
    """
    spell = get_spell(spell_id)
    result = {
        "spell_id":       spell_id,
        "damage":         0,
        "heal":           0,
        "mana_cost":      0,
        "effect":         None,
        "effect_hit":     False,
        "crit":           False,
        "missed":         False,
        "skipped":        False,
        "instant_kill":   False,
        "confuse_self":   False,
        "reflect_damage": 0,
        "attacker_hp":    attacker_current_hp,
        "defender_hp":    defender_current_hp,
        "log":            "",
        "flavour":        "",
        # ИСПРАВЛЕНИЕ: возвращаем обновлённые статусы
        "new_atk_status": attacker_status.copy(),
        "new_def_status": defender_status.copy(),
    }

    if spell is None:
        result["log"] = "❌ Неизвестное заклинание"
        return result

    # Mana cost
    mana_cost = spell.get("mana", 0)
    if attacker_current_mana < mana_cost:
        result["log"] = "💧 Недостаточно маны!"
        if attacker_current_mana < 20:
            result["flavour"] = flavour_line("mana_low")
        return result
    result["mana_cost"] = mana_cost

    # Stun: skip turn
    if attacker_status.get("stun", 0) > 0:
        result["skipped"] = True
        result["log"] = "😵 Оглушён — ход пропущен!"
        result["flavour"] = flavour_line("stun")
        return result

    # Silence: can't use spells
    if attacker_status.get("silence", 0) > 0 and spell.get("mana", 0) > 0:
        result["log"] = "🤐 Молчание — нельзя использовать заклинания!"
        result["skipped"] = True
        return result

    # Confuse: might attack self
    if attacker_status.get("confuse", 0) > 0 and random.random() < 0.5:
        result["confuse_self"] = True
        result["flavour"] = flavour_line("confuse")
        result["log"] = "🔄 Замешательство — атака по себе!"
        self_dmg = max(int(spell.get("damage", 10) * 0.5), 5)
        result["damage"] = self_dmg
        result["attacker_hp"] = max(0, attacker_current_hp - self_dmg)
        return result

    stype = spell.get("type", "attack")

    # ── Healing spell ──────────────────────────────────────────────────────────
    if stype == "heal":
        heal = spell.get("heal", 0)
        if attacker_status.get("curse", 0) > 0:
            result["log"] = "☠️ Проклятие — лечение невозможно!"
            result["skipped"] = True
            return result
        new_atk, new_def, hit = apply_spell_effect(
            spell, attacker_status, defender_status, attacker.get("luck", 5)
        )
        result["heal"] = heal
        result["attacker_hp"] = min(attacker.get("max_hp", 100), attacker_current_hp + heal)
        result["effect"] = spell.get("effect")
        result["effect_hit"] = hit
        result["log"] = f"💚 +{heal} ХП"
        result["new_atk_status"] = new_atk
        result["new_def_status"] = new_def
        return result

    # ── Defense / buff spell ───────────────────────────────────────────────────
    if stype == "defense":
        new_atk, new_def, hit = apply_spell_effect(
            spell, attacker_status, defender_status, attacker.get("luck", 5)
        )
        result["effect"] = spell.get("effect")
        result["effect_hit"] = hit
        result["log"] = f"🛡️ {spell['id']}"
        result["new_atk_status"] = new_atk
        result["new_def_status"] = new_def
        return result

    # ── Attack / debuff spell ──────────────────────────────────────────────────
    dmg, is_crit, missed, reflect_dmg, updated_def_status = calculate_damage(
        spell, attacker, defender, attacker_status, defender_status
    )

    result["crit"]    = is_crit
    result["missed"]  = missed
    result["damage"]  = dmg

    if missed:
        result["log"]     = "💨 Промах!"
        result["flavour"] = flavour_line("miss")
        return result

    # Instant kill (Avada Kedavra)
    if spell.get("effect") == "instant_kill":
        chance = spell.get("effect_chance", 0.5)
        if random.random() < chance:
            result["instant_kill"] = True
            result["defender_hp"]  = 0
            result["log"]          = "☠️ Авада Кедавра! Мгновенная победа!"
            result["flavour"]      = flavour_line("instant_kill")
            result["new_def_status"] = updated_def_status
            return result

    # ИСПРАВЛЕНИЕ: сохраняем обновлённый статус защитника (со щитом после поглощения)
    result["new_def_status"] = updated_def_status

    # Reflect damage
    if reflect_dmg > 0:
        result["reflect_damage"] = reflect_dmg
        result["flavour"] = flavour_line("reflect")

    result["defender_hp"] = max(0, defender_current_hp - dmg)
    result["attacker_hp"] = max(0, attacker_current_hp - reflect_dmg)

    # Status effect
    new_atk, new_def, hit = apply_spell_effect(
        spell, attacker_status, updated_def_status, attacker.get("luck", 5)
    )
    result["effect"]      = spell.get("effect")
    result["effect_hit"]  = hit
    result["new_atk_status"] = new_atk
    result["new_def_status"] = new_def

    # Флейвор для крита и эффектов
    if is_crit:
        result["flavour"] = flavour_line("crit")
    elif hit and spell.get("effect") in _FLAVOUR:
        result["flavour"] = flavour_line(spell["effect"])

    # Предупреждение о низком ХП
    if result["defender_hp"] > 0 and result["defender_hp"] < defender.get("max_hp", 100) * 0.2:
        if not result["flavour"]:
            result["flavour"] = flavour_line("low_hp")

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
    if status.get("shield",  0) > 0: icons.append("🔵")   # новое: показываем активный щит
    if status.get("silence", 0) > 0: icons.append("🤐")   # новое: показываем молчание
    return " ".join(icons)
