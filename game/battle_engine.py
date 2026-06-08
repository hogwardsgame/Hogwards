"""
Battle Engine — PvP и PvE боевая логика.

Новое в этой версии:
  - Система комбо-заклинаний (30+ комбинаций)
  - Система контрзаклинаний с временным окном
  - Полностью переработанные визуальные панели боя
  - Эффекты: weaken, expose, lifesteal, dispel, slow
  - Журнал боя с иконками и флейвором
  - Многофазные боссы
"""
import random
import math
from game.spells import SPELLS, get_spell

# ── Преимущество факультетов ───────────────────────────────────────────────────
HOUSE_ADVANTAGE: dict[str, str] = {
    "gryffindor": "slytherin",
    "slytherin":  "ravenclaw",
    "ravenclaw":  "hufflepuff",
    "hufflepuff": "gryffindor",
}
HOUSE_ADVANTAGE_BONUS = 0.15

HOUSE_EMOJI = {
    "gryffindor": "🦁", "slytherin": "🐍",
    "ravenclaw": "🦅",  "hufflepuff": "🦡",
}

# ══════════════════════════════════════════════════════════════════════════════
# СИСТЕМА КОМБО-ЗАКЛИНАНИЙ
# ══════════════════════════════════════════════════════════════════════════════
# Структура: (заклинание_1, заклинание_2) → {name, bonus_damage, effect, desc}
COMBO_SPELLS: dict[tuple, dict] = {
    # ── Огненные комбо ────────────────────────────────────────────────────────
    ("lumos", "expelliarmus"): {
        "name": "Слепящее разоружение",
        "emoji": "✨",
        "bonus_damage": 20,
        "effect": "blind",
        "effect_chance": 1.0,
        "desc": "Вспышка ослепляет и выбивает оружие",
    },
    ("incendio", "confringo"): {
        "name": "Огненная буря",
        "emoji": "🔥",
        "bonus_damage": 50,
        "effect": "burn",
        "effect_chance": 1.0,
        "burn_turns": 5,
        "desc": "Двойной огонь — смертоносное горение",
    },
    ("inflammare", "fiendfyre"): {
        "name": "Адская вспышка",
        "emoji": "🌋",
        "bonus_damage": 70,
        "effect": "burn",
        "effect_chance": 1.0,
        "burn_turns": 6,
        "desc": "Инфламмаре поджигает, Фиендфайр раздувает пламя",
    },
    # ── Ледяные комбо ─────────────────────────────────────────────────────────
    ("glacius", "petrificus_totalus"): {
        "name": "Ледяная петрификация",
        "emoji": "❄️",
        "bonus_damage": 40,
        "effect": "freeze",
        "effect_chance": 1.0,
        "stun_turns": 3,
        "desc": "Заморозка и окаменение — враг не может двигаться 3 хода",
    },
    ("ice_chain", "locomotor_mortis"): {
        "name": "Ледяные оковы",
        "emoji": "⛓️",
        "bonus_damage": 30,
        "effect": "freeze",
        "effect_chance": 1.0,
        "desc": "Лёд сковывает каждый сустав",
    },
    # ── Контроль разума ───────────────────────────────────────────────────────
    ("confundus", "imperio"): {
        "name": "Полное подчинение",
        "emoji": "🌀",
        "bonus_damage": 15,
        "effect": "confuse",
        "effect_chance": 1.0,
        "confuse_turns": 3,
        "desc": "Разум врага полностью сломлен на 3 хода",
    },
    ("legilimens", "obliviate"): {
        "name": "Разрушение памяти",
        "emoji": "🧠",
        "bonus_damage": 60,
        "effect": "silence",
        "effect_chance": 1.0,
        "desc": "Стирает разум и лишает дара речи",
    },
    # ── Яд и проклятия ────────────────────────────────────────────────────────
    ("serpensortia", "crucio"): {
        "name": "Яд и пытка",
        "emoji": "☠️",
        "bonus_damage": 55,
        "effect": "curse",
        "effect_chance": 1.0,
        "desc": "Змея кусает, затем Крусиатус добивает",
    },
    ("morsmordre", "sectumsempra"): {
        "name": "Печать Тёмного лорда",
        "emoji": "💀",
        "bonus_damage": 80,
        "effect": "curse",
        "effect_chance": 0.9,
        "desc": "Тёмная метка и кровотечение",
    },
    # ── Защитные комбо ────────────────────────────────────────────────────────
    ("protego", "episkey"): {
        "name": "Щит и исцеление",
        "emoji": "💚",
        "bonus_damage": 0,
        "bonus_heal": 40,
        "effect": "shield",
        "effect_chance": 1.0,
        "shield_value": 50,
        "desc": "Щит восстанавливает здоровье и поглощает урон",
    },
    ("ricochet", "expecto_patronum"): {
        "name": "Патронус-рикошет",
        "emoji": "🦌",
        "bonus_damage": 30,
        "effect": "reflect",
        "effect_chance": 1.0,
        "desc": "Патронус отражает заклинания на 2 хода",
    },
    # ── Разоружение ────────────────────────────────────────────────────────────
    ("expelliarmus", "accio"): {
        "name": "Двойное разоружение",
        "emoji": "🔄",
        "bonus_damage": 25,
        "effect": "disarm",
        "effect_chance": 1.0,
        "disarm_turns": 2,
        "desc": "Оружие выбито и притянуто к тебе",
    },
    ("petrificus_totalus", "stupefy"): {
        "name": "Окаменение и оглушение",
        "emoji": "😵",
        "bonus_damage": 45,
        "effect": "stun",
        "effect_chance": 1.0,
        "stun_turns": 2,
        "desc": "Петрификация + Ступефай = 2 хода без сознания",
    },
    # ── Вода и свет ────────────────────────────────────────────────────────────
    ("aguamenti", "lumos_maxima"): {
        "name": "Световой поток",
        "emoji": "💧",
        "bonus_damage": 35,
        "effect": "blind",
        "effect_chance": 1.0,
        "desc": "Вода преломляет свет — ослепление гарантировано",
    },
    ("aqua_eructo", "glacius"): {
        "name": "Ледяной поток",
        "emoji": "🌊❄️",
        "bonus_damage": 55,
        "effect": "freeze",
        "effect_chance": 1.0,
        "desc": "Вода мгновенно замерзает вместе с врагом",
    },
    # ── Тёмные ────────────────────────────────────────────────────────────────
    ("fiendfyre", "avada_kedavra"): {
        "name": "Адское убийство",
        "emoji": "🔥💀",
        "bonus_damage": 0,
        "effect": "instant_kill",
        "effect_chance": 0.75,
        "desc": "Адское пламя + Авада — 75% шанс мгновенной победы",
    },
    ("horcrux_drain", "legilimens"): {
        "name": "Кража жизни",
        "emoji": "🩸",
        "bonus_damage": 70,
        "effect": "lifesteal",
        "effect_chance": 1.0,
        "desc": "Высасывает половину урона как HP атакующего",
    },
    # ── Взрывы ────────────────────────────────────────────────────────────────
    ("bombarda", "confringo"): {
        "name": "Двойной взрыв",
        "emoji": "💥",
        "bonus_damage": 90,
        "effect": "stun",
        "effect_chance": 0.8,
        "desc": "Два взрыва подряд — оглушает почти гарантированно",
    },
    ("reducto", "bombarda"): {
        "name": "Разрушительная волна",
        "emoji": "⚡",
        "bonus_damage": 75,
        "effect": "stun",
        "effect_chance": 0.7,
        "desc": "Сносящий удар двух разрушительных заклинаний",
    },
    # ── Тьма и свет ────────────────────────────────────────────────────────────
    ("tenebrus", "lumos"): {
        "name": "Контраст тьмы",
        "emoji": "☯️",
        "bonus_damage": 40,
        "effect": "confuse",
        "effect_chance": 0.9,
        "desc": "Переход от тьмы к свету дезориентирует врага",
    },
    ("nox", "oppugno"): {
        "name": "Атака из темноты",
        "emoji": "🌑",
        "bonus_damage": 65,
        "effect": "blind",
        "effect_chance": 1.0,
        "desc": "Тьма скрывает атаку — ослепление и урон",
    },
    # ── Молчание и удар ────────────────────────────────────────────────────────
    ("silencio", "expelliarmus"): {
        "name": "Немое разоружение",
        "emoji": "🤐",
        "bonus_damage": 30,
        "effect": "disarm",
        "effect_chance": 1.0,
        "desc": "Заставляет молчать и выбивает палочку",
    },
    ("silencio", "diffindo"): {
        "name": "Тихий удар",
        "emoji": "🔕",
        "bonus_damage": 55,
        "effect": "burn",
        "effect_chance": 0.8,
        "desc": "Молчание снижает защиту — Диффиндо режет глубже",
    },
    # ── Скорость ──────────────────────────────────────────────────────────────
    ("wingardium_leviosa", "stupefy"): {
        "name": "Падение с оглушением",
        "emoji": "💫",
        "bonus_damage": 40,
        "effect": "stun",
        "effect_chance": 0.9,
        "desc": "Поднять врага и оглушить в воздухе",
    },
    ("flipendo", "accio"): {
        "name": "Удар и притяжение",
        "emoji": "🔀",
        "bonus_damage": 35,
        "effect": "disarm",
        "effect_chance": 0.8,
        "desc": "Флипендо бьёт, Акцио притягивает ошеломлённого врага",
    },
    # ── Яд + лечение = дренаж ─────────────────────────────────────────────────
    ("serpensortia", "vulnero"): {
        "name": "Вампирский укус",
        "emoji": "🩸",
        "bonus_damage": 30,
        "bonus_heal": 30,
        "effect": "poison",
        "effect_chance": 1.0,
        "desc": "Отравляет врага и возвращает тебе HP",
    },
    # ── Легендарные комбо ─────────────────────────────────────────────────────
    ("death_hallow", "avada_kedavra"): {
        "name": "Дар Смерти: Конец",
        "emoji": "💀⭐",
        "bonus_damage": 0,
        "effect": "instant_kill",
        "effect_chance": 0.90,
        "desc": "90% шанс мгновенной победы — только для сильнейших",
    },
    ("elder_wand_surge", "animus_supremus"): {
        "name": "Высший приговор",
        "emoji": "⭐⭐",
        "bonus_damage": 250,
        "effect": "stun",
        "effect_chance": 1.0,
        "stun_turns": 3,
        "desc": "Мощь Бузинной палочки + Анимус — чудовищный урон",
    },
    ("tempus_maxima", "glacius_maxima"): {
        "name": "Вечная мерзлота",
        "emoji": "⏳❄️",
        "bonus_damage": 80,
        "effect": "freeze",
        "effect_chance": 1.0,
        "stun_turns": 4,
        "desc": "Остановка времени в ледяном аду",
    },
}

# ── Контрзаклинания ────────────────────────────────────────────────────────────
# триггер → {counter_spell, reduce_pct, cancel_effect, reflect_pct, desc}
COUNTER_SPELLS: dict[str, dict] = {
    "burn":         {"counter": "aguamenti",    "reduce_pct": 0.80, "cancel_effect": True,  "desc": "Вода гасит огонь"},
    "freeze":       {"counter": "incendio",     "reduce_pct": 0.75, "cancel_effect": True,  "desc": "Огонь топит лёд"},
    "stun":         {"counter": "ennervate",    "reduce_pct": 0.00, "cancel_effect": True,  "desc": "Восстанавливает после оглушения"},
    "poison":       {"counter": "vipera_evanesca", "reduce_pct": 0.70, "cancel_effect": True, "desc": "Нейтрализует яд"},
    "curse":        {"counter": "finite_incantatem", "reduce_pct": 0.60, "cancel_effect": True, "desc": "Снимает проклятие"},
    "blind":        {"counter": "nox",          "reduce_pct": 0.50, "cancel_effect": True,  "desc": "Тьма скрывает от слепящего света"},
    "confuse":      {"counter": "sanacus",      "reduce_pct": 0.60, "cancel_effect": True,  "desc": "Очищает разум"},
    "disarmed":     {"counter": "accio",        "reduce_pct": 0.00, "cancel_effect": True,  "desc": "Возвращает палочку"},
    "silence":      {"counter": "episkey",      "reduce_pct": 0.50, "cancel_effect": True,  "desc": "Восстанавливает голос"},
    "instant_kill": {"counter": "protego_totalum", "reduce_pct": 0.0, "cancel_effect": True, "reflect_pct": 0.0, "desc": "Абсолютный щит отменяет Авада"},
    "attack":       {"counter": "ricochet",     "reduce_pct": 0.40, "cancel_effect": False, "reflect_pct": 0.25, "desc": "Рикошет отражает 25% урона"},
    "heavy_attack": {"counter": "protego",      "reduce_pct": 0.40, "cancel_effect": False, "desc": "Протего снижает урон на 40%"},
}

# ── Атмосферные реплики ────────────────────────────────────────────────────────
_FLAVOUR: dict[str, list[str]] = {
    "crit": [
        "💥 Блестящее попадание — профессор Флитвик был бы доволен!",
        "💥 Невероятный крит! Дамблдор кивнул бы с одобрением.",
        "💥 Критический удар! Стены Хогвартса задрожали.",
        "💥 Безупречное исполнение! Портреты на стенах зааплодировали.",
    ],
    "miss": [
        "💨 Заклинание ушло в никуда... Нужно больше практики!",
        "💨 Промах! Мадам Хуч недовольно покачала головой.",
        "💨 Заклинание рассеялось в воздухе.",
        "💨 Мисс! Пивз захихикал.",
    ],
    "combo": [
        "✨ КОМБО! Магия усилилась вдвое!",
        "🌟 Потрясающая комбинация заклинаний!",
        "⚡ Комбо-удар — враги в панике!",
    ],
    "counter": [
        "🛡️ Контрзаклинание! Атака отражена!",
        "⚡ Молниеносная контратака!",
        "🪞 Вовремя! Заклинание нейтрализовано.",
    ],
    "stun": ["😵 Оглушён! Звёзды перед глазами...", "😵 Stupefied! Ход пропущен."],
    "burn":  ["🔥 Пламя пожирает!", "🔥 Горит! Феникс сочувственно пискнул."],
    "freeze": ["❄️ Заморожен! Холоднее подвалов Азкабана.", "❄️ Лёд сковал движения!"],
    "poison": ["🟢 Яд течёт по жилам... Беззар бы не помешал.", "🟢 Отравлен!"],
    "instant_kill": ["☠️ АВАДА КЕДАВРА! Зелёная вспышка — всё кончено.", "☠️ Непростительное заклинание! Мгновенная победа."],
    "confuse": ["💫 Замешательство! Где свои, где чужие?", "💫 Голова кружится..."],
    "reflect": ["🪞 Заклинание отражено! Протего работает!", "🪞 Зеркальный щит отбил удар!"],
    "lifesteal": ["🩸 Жизненная сила перетекает к победителю!", "🩸 Кража HP!"],
    "expose": ["🔍 Слабость обнаружена! +30% урон следующей атакой!", "🔍 Броня пробита!"],
    "shield_break": ["💢 Щит разрушен!", "💢 Протего пробит — теперь уязвим!"],
    "low_hp": ["😰 Совсем плохо... ещё удар и конец.", "😰 Держись! Почти ничего не осталось."],
    "mana_low": ["💧 Мана на исходе!", "💧 Силы иссякают..."],
    "phase_change": ["⚠️ Противник меняет тактику!", "⚠️ Новая фаза — будь осторожен!"],
}


def flavour_line(event: str) -> str:
    lines = _FLAVOUR.get(event, [])
    return random.choice(lines) if lines else ""


def battle_summary(turns: int, total_dmg_dealt: int, total_dmg_taken: int) -> str:
    if total_dmg_taken == 0:
        rating = "⭐⭐⭐ Безупречно!"
    elif total_dmg_taken < total_dmg_dealt // 2:
        rating = "⭐⭐ Хорошо"
    else:
        rating = "⭐ Выжил"
    return (
        f"📊 *Итог боя:*\n"
        f"Ходов: {turns} | Нанесено: {total_dmg_dealt} | Получено: {total_dmg_taken}\n"
        f"Оценка: {rating}"
    )


# ── Статусы ────────────────────────────────────────────────────────────────────
def fresh_status() -> dict:
    return {
        "burn":      0,
        "freeze":    0,
        "stun":      0,
        "blind":     0,
        "curse":     0,
        "poison":    0,
        "confuse":   0,
        "disarmed":  0,
        "shield":    0,
        "block":     False,
        "reflect":   False,
        "silence":   0,
        "weaken":    0,   # -20% атаки
        "expose":    0,   # +30% урон по ослабленному
        "slow":      0,   # аналог stun
        "lifesteal": 0,   # процент кражи HP (временный)
    }


def tick_status(status: dict) -> tuple[dict, int]:
    dmg = 0
    s = status.copy()
    if s["burn"] > 0:
        dmg += 10; s["burn"] -= 1
    if s["poison"] > 0:
        dmg += 8;  s["poison"] -= 1
    if s["curse"] > 0:
        dmg += 12; s["curse"] -= 1
    for key in ("freeze", "stun", "blind", "confuse", "disarmed", "silence", "weaken", "expose", "slow", "lifesteal"):
        if s[key] > 0:
            s[key] -= 1
    s["block"]   = False
    s["reflect"] = False
    return s, dmg


def apply_effect(effect: str, status: dict, value: int = 1, shield_val: int = 0) -> dict:
    s = status.copy()
    if effect == "burn":     s["burn"]    = max(s["burn"],    3)
    elif effect == "freeze": s["freeze"]  = max(s["freeze"],  2)
    elif effect == "stun":   s["stun"]    = max(s["stun"],    value)
    elif effect == "blind":  s["blind"]   = max(s["blind"],   2)
    elif effect == "curse":  s["curse"]   = max(s["curse"],   3)
    elif effect == "poison": s["poison"]  = max(s["poison"],  4)
    elif effect == "confuse":s["confuse"] = max(s["confuse"], value)
    elif effect == "disarm": s["disarmed"]= max(s["disarmed"],1)
    elif effect == "block":  s["block"]   = True
    elif effect == "reflect":s["reflect"] = True
    elif effect == "shield": s["shield"]  += (shield_val or 60)
    elif effect == "cleanse" or effect == "dispel":
        for key in ("burn", "freeze", "blind", "curse", "poison", "confuse", "weaken", "expose", "slow"):
            s[key] = 0
    elif effect == "silence":s["silence"] = max(s["silence"], 2)
    elif effect == "slow":   s["stun"]    = max(s["stun"],    1)
    elif effect == "weaken": s["weaken"]  = max(s["weaken"],  3)
    elif effect == "expose": s["expose"]  = max(s["expose"],  1)
    elif effect == "lifesteal": s["lifesteal"] = max(s["lifesteal"], 2)
    return s


# ── Проверка комбо ─────────────────────────────────────────────────────────────
def check_combo(prev_spell_id: str | None, curr_spell_id: str) -> dict | None:
    """Проверить, образуют ли два заклинания комбо."""
    if not prev_spell_id:
        return None
    return COMBO_SPELLS.get((prev_spell_id, curr_spell_id)) or COMBO_SPELLS.get((curr_spell_id, prev_spell_id))


def check_counter(trigger_effect: str, defender_spell_ids: list[str]) -> dict | None:
    """Проверить, есть ли у защитника контрзаклинание против данного эффекта."""
    counter_info = COUNTER_SPELLS.get(trigger_effect)
    if not counter_info:
        return None
    if counter_info["counter"] in defender_spell_ids:
        return counter_info
    return None


# ── Расчёт урона ──────────────────────────────────────────────────────────────
def _house_damage_mult(atk_house: str | None, def_house: str | None) -> float:
    if atk_house and HOUSE_ADVANTAGE.get(atk_house) == def_house:
        return 1 + HOUSE_ADVANTAGE_BONUS
    return 1.0


def calculate_damage(
    spell: dict,
    attacker: dict,
    defender: dict,
    attacker_status: dict,
    defender_status: dict,
    combo_bonus: int = 0,
) -> tuple[int, bool, bool, int, dict]:
    """
    Вычислить урон заклинания.
    Возвращает (final_damage, is_crit, missed, reflect_damage, updated_defender_status).
    """
    def_status = defender_status.copy()
    base = spell.get("damage", 0) + combo_bonus
    if base == 0:
        return 0, False, False, 0, def_status

    # Промах от ослепления
    if attacker_status.get("blind", 0) > 0:
        if random.random() < 0.50:
            return 0, False, True, 0, def_status

    # Крит
    luck = attacker.get("luck", 5)
    crit_chance = 0.05 + luck * 0.005
    is_crit = random.random() < crit_chance
    if is_crit:
        base = int(base * 1.5)

    # Ослабление атакующего
    atk_mult = 0.8 if attacker_status.get("weaken", 0) > 0 else 1.0
    base = int(base * (attacker.get("attack", 10) / 20) * atk_mult)

    # Преимущество факультета
    base = int(base * _house_damage_mult(attacker.get("house"), defender.get("house")))

    # Ослабленная цель — +30% урон
    if def_status.get("expose", 0) > 0:
        base = int(base * 1.3)

    # Снижение защитой
    defense = defender.get("defense", 5)
    reduction = defense / (defense + 30)
    damage = int(base * (1 - reduction))

    # Щит
    if def_status.get("shield", 0) > 0:
        absorbed = min(def_status["shield"], damage)
        damage  -= absorbed
        def_status["shield"] -= absorbed

    # Блок (-40%)
    if def_status.get("block"):
        damage = int(damage * 0.6)

    # Отражение
    reflect_dmg = 0
    if def_status.get("reflect"):
        reflect_dmg = int(damage * 0.25)

    return max(damage, 0), is_crit, False, reflect_dmg, def_status


def apply_spell_effect(
    spell: dict,
    attacker_status: dict,
    defender_status: dict,
    attacker_luck: int = 5,
    combo: dict | None = None,
) -> tuple[dict, dict, bool]:
    """Применить эффект заклинания. Возвращает (new_atk_status, new_def_status, triggered)."""
    # Сначала применяем эффект комбо (если есть)
    if combo:
        c_effect = combo.get("effect")
        c_chance = combo.get("effect_chance", 1.0)
        if c_effect and random.random() <= c_chance:
            stun_val = combo.get("stun_turns", 1)
            conf_val = combo.get("confuse_turns", 1)
            shield_v = combo.get("shield_value", 0)
            if c_effect in ("cleanse", "block", "reflect", "shield"):
                attacker_status = apply_effect(c_effect, attacker_status, shield_val=shield_v)
            else:
                defender_status = apply_effect(c_effect, defender_status, value=max(stun_val, conf_val), shield_val=shield_v)

    # Основной эффект заклинания
    effect = spell.get("effect")
    chance = spell.get("effect_chance", 0.0)
    if not effect or random.random() > chance:
        return attacker_status, defender_status, bool(combo)

    if effect == "instant_kill":
        return attacker_status, defender_status, True

    shield_val = spell.get("shield_value", 0)
    if effect in ("cleanse", "dispel", "block", "reflect", "shield"):
        attacker_status = apply_effect(effect, attacker_status, shield_val=shield_val)
        return attacker_status, defender_status, True

    defender_status = apply_effect(effect, defender_status)
    return attacker_status, defender_status, True


def resolve_turn(
    spell_id: str,
    attacker: dict,
    defender: dict,
    attacker_status: dict,
    defender_status: dict,
    attacker_current_hp: int,
    defender_current_hp: int,
    attacker_current_mana: int,
    prev_spell_id: str | None = None,    # для системы комбо
    defender_spell_ids: list | None = None,  # для контрзаклинаний
) -> dict:
    """
    Разрешить один боевой ход.
    Возвращает полный словарь с результатом.
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
        "mana_empty":     False,
        "combo":          None,
        "counter":        None,
        "new_atk_status": attacker_status.copy(),
        "new_def_status": defender_status.copy(),
    }

    if spell is None:
        result["log"] = "❌ Неизвестное заклинание"
        return result

    mana_cost = spell.get("mana", 0)
    if attacker_current_mana < mana_cost:
        result["log"] = "💧 Недостаточно маны!"
        result["mana_empty"] = True
        if attacker_current_mana < 20:
            result["flavour"] = flavour_line("mana_low")
        return result

    result["mana_cost"] = mana_cost

    # Стан — пропуск хода
    if attacker_status.get("stun", 0) > 0 or attacker_status.get("slow", 0) > 0:
        result["skipped"] = True
        result["log"] = "😵 Оглушён — ход пропущен!"
        result["flavour"] = flavour_line("stun")
        return result

    # Молчание — нельзя заклинания
    if attacker_status.get("silence", 0) > 0 and mana_cost > 0:
        result["log"] = "🤐 Молчание — нельзя использовать заклинания!"
        result["skipped"] = True
        return result

    # Замешательство — атака по себе
    if attacker_status.get("confuse", 0) > 0 and random.random() < 0.5:
        result["confuse_self"] = True
        result["flavour"] = flavour_line("confuse")
        result["log"] = "🔄 Замешательство — атака по себе!"
        self_dmg = max(int(spell.get("damage", 10) * 0.5), 5)
        result["damage"] = self_dmg
        result["attacker_hp"] = max(0, attacker_current_hp - self_dmg)
        return result

    # ── Проверка КОМБО ────────────────────────────────────────────────────────
    combo = check_combo(prev_spell_id, spell_id)
    if combo:
        result["combo"] = combo
        result["flavour"] = flavour_line("combo")

    # ── Проверка КОНТРЗАКЛИНАНИЯ (у защитника) ────────────────────────────────
    counter = None
    if defender_spell_ids:
        trigger = spell.get("effect")
        if trigger:
            counter = check_counter(trigger, defender_spell_ids)
            # Также проверяем по силе атаки
            if not counter and spell.get("damage", 0) > 60:
                counter = check_counter("heavy_attack", defender_spell_ids)
            elif not counter and spell.get("damage", 0) > 20:
                counter = check_counter("attack", defender_spell_ids)
        if counter:
            result["counter"] = counter

    stype = spell.get("type", "attack")

    # ── Лечение ───────────────────────────────────────────────────────────────
    if stype == "heal":
        heal = spell.get("heal", 0)
        if heal == 9999:  # tempus_regressus
            heal = attacker.get("max_hp", 100) - attacker_current_hp
        if attacker_status.get("curse", 0) > 0:
            result["log"] = "☠️ Проклятие — лечение невозможно!"
            result["skipped"] = True
            return result
        combo_heal = combo.get("bonus_heal", 0) if combo else 0
        total_heal = heal + combo_heal
        new_atk, new_def, hit = apply_spell_effect(spell, attacker_status, defender_status, attacker.get("luck", 5), combo)
        result["heal"] = total_heal
        result["attacker_hp"] = min(attacker.get("max_hp", 100), attacker_current_hp + total_heal)
        result["effect"] = spell.get("effect")
        result["effect_hit"] = hit
        result["log"] = f"💚 +{total_heal} ХП"
        if combo:
            result["log"] += f" ✨ КОМБО: {combo['name']}!"
        result["new_atk_status"] = new_atk
        result["new_def_status"] = new_def
        return result

    # ── Защита/баф ────────────────────────────────────────────────────────────
    if stype == "defense":
        new_atk, new_def, hit = apply_spell_effect(spell, attacker_status, defender_status, attacker.get("luck", 5), combo)
        result["effect"] = spell.get("effect")
        result["effect_hit"] = hit
        result["log"] = f"🛡️ {spell_id}"
        result["new_atk_status"] = new_atk
        result["new_def_status"] = new_def
        return result

    # ── Атака/дебаф ───────────────────────────────────────────────────────────
    combo_bonus = combo.get("bonus_damage", 0) if combo else 0

    # Применяем контрзаклинание защитника
    counter_reduce = 0.0
    cancel_effect = False
    if counter:
        counter_reduce = counter.get("reduce_pct", 0.0)
        cancel_effect  = counter.get("cancel_effect", False)

    dmg, is_crit, missed, reflect_dmg, updated_def_status = calculate_damage(
        spell, attacker, defender, attacker_status, defender_status, combo_bonus
    )

    # Снизить урон контрзаклинанием
    if counter_reduce > 0:
        dmg = int(dmg * (1 - counter_reduce))
        reflect_from_counter = counter.get("reflect_pct", 0)
        if reflect_from_counter > 0:
            reflect_dmg = max(reflect_dmg, int(dmg * reflect_from_counter))

    result["crit"]   = is_crit
    result["missed"] = missed
    result["damage"] = dmg

    if missed:
        result["log"]     = "💨 Промах!"
        result["flavour"] = flavour_line("miss")
        return result

    # Мгновенная смерть
    if spell.get("effect") == "instant_kill" and not cancel_effect:
        chance = spell.get("effect_chance", 0.5)
        if combo:
            chance = combo.get("effect_chance", chance)
        if random.random() < chance:
            result["instant_kill"] = True
            result["defender_hp"]  = 0
            result["log"]          = "☠️ Авада Кедавра! Мгновенная победа!"
            result["flavour"]      = flavour_line("instant_kill")
            result["new_def_status"] = updated_def_status
            return result

    result["new_def_status"] = updated_def_status

    if reflect_dmg > 0:
        result["reflect_damage"] = reflect_dmg
        if not result["flavour"]:
            result["flavour"] = flavour_line("reflect")

    result["defender_hp"] = max(0, defender_current_hp - dmg)
    result["attacker_hp"] = max(0, attacker_current_hp - reflect_dmg)

    # Лайфстил
    if spell.get("effect") == "lifesteal" or (combo and combo.get("effect") == "lifesteal"):
        lifesteal_hp = int(dmg * 0.4)
        result["attacker_hp"] = min(attacker.get("max_hp", 100), result["attacker_hp"] + lifesteal_hp)
        result["log_extra"] = f"🩸 +{lifesteal_hp} HP (лайфстил)"
        if not result["flavour"]:
            result["flavour"] = flavour_line("lifesteal")

    # Применяем эффекты (с учётом контрзаклинания)
    eff_spell = spell if not cancel_effect else {**spell, "effect": None, "effect_chance": 0}
    new_atk, new_def, hit = apply_spell_effect(
        eff_spell, attacker_status, updated_def_status, attacker.get("luck", 5), combo if not cancel_effect else None
    )
    result["effect"]      = spell.get("effect") if not cancel_effect else None
    result["effect_hit"]  = hit
    result["new_atk_status"] = new_atk
    result["new_def_status"] = new_def

    # Флейвор
    if not result["flavour"]:
        if is_crit:
            result["flavour"] = flavour_line("crit")
        elif hit and spell.get("effect") in _FLAVOUR:
            result["flavour"] = flavour_line(spell["effect"])
    if counter:
        result["flavour"] = (result["flavour"] + "\n" if result["flavour"] else "") + flavour_line("counter")

    # Предупреждение о низком HP
    hp_pct = result["defender_hp"] / defender.get("max_hp", 100)
    if 0 < hp_pct < 0.2 and not result["flavour"]:
        result["flavour"] = flavour_line("low_hp")

    crit_tag = " 💥КРИТ!" if is_crit else ""
    combo_tag = f" ✨{combo['name']}!" if combo else ""
    counter_tag = f" 🛡️ Контр (-{int(counter_reduce*100)}%)!" if counter else ""
    result["log"] = f"⚡ {dmg} урона{crit_tag}{combo_tag}{counter_tag}"
    return result


def determine_turn_order(player_speed: int, opponent_speed: int) -> str:
    if player_speed == opponent_speed:
        return random.choice(["player", "opponent"])
    return "player" if player_speed >= opponent_speed else "opponent"


def format_battle_status(status: dict) -> str:
    icons = []
    if status.get("burn",      0) > 0: icons.append("🔥")
    if status.get("freeze",    0) > 0: icons.append("❄️")
    if status.get("stun",      0) > 0: icons.append("😵")
    if status.get("blind",     0) > 0: icons.append("🌑")
    if status.get("disarmed",  0) > 0: icons.append("🔄")
    if status.get("curse",     0) > 0: icons.append("☠️")
    if status.get("poison",    0) > 0: icons.append("🟢")
    if status.get("confuse",   0) > 0: icons.append("💫")
    if status.get("shield",    0) > 0: icons.append(f"🔵{status['shield']}")
    if status.get("silence",   0) > 0: icons.append("🤐")
    if status.get("weaken",    0) > 0: icons.append("📉")
    if status.get("expose",    0) > 0: icons.append("🎯")
    if status.get("lifesteal", 0) > 0: icons.append("🩸")
    return " ".join(icons)


def format_hp_bar(current: int, maximum: int, length: int = 10) -> str:
    if maximum <= 0:
        return "░" * length
    filled = max(0, int(length * current / maximum))
    pct = current / maximum
    if pct > 0.6:
        char = "█"
    elif pct > 0.3:
        char = "▓"
    else:
        char = "▒"
    return char * filled + "░" * (length - filled)


def format_pvp_panel(state: dict) -> str:
    """Красивая панель PvP-боя."""
    p  = state["player"]
    o  = state["opponent"]
    ps = format_battle_status(state["player_status"])
    os = format_battle_status(state["opponent_status"])

    p_bar = format_hp_bar(state["player_hp"], p["max_hp"])
    o_bar = format_hp_bar(state["opponent_hp"], o["max_hp"])

    p_mana_bar = format_hp_bar(state["player_mana"], p["max_mana"], 6)
    o_mana_bar = format_hp_bar(state["opponent_mana"], o["max_mana"], 6)

    p_house = HOUSE_EMOJI.get(p.get("house", ""), "🏠")
    o_house = HOUSE_EMOJI.get(o.get("house", ""), "🏠")

    log_tail = "\n".join(state["log"][-5:])

    turn_marker = "⚡ *Твой ход*" if state.get("current_turn") == "player" else "⏳ Ход противника"

    return (
        f"⚔️ *Дуэль* | Ход {state.get('turn_number', 1)}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"{p_house} *{p['wizard_name']}* {ps}\n"
        f"❤️ `[{p_bar}]` {state['player_hp']}/{p['max_hp']}\n"
        f"💧 `[{p_mana_bar}]` {state['player_mana']}/{p['max_mana']}\n"
        f"\n"
        f"{o_house} *{o['wizard_name']}* {os}\n"
        f"❤️ `[{o_bar}]` {state['opponent_hp']}/{o['max_hp']}\n"
        f"💧 `[{o_mana_bar}]` {state['opponent_mana']}/{o['max_mana']}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"{log_tail}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"{turn_marker}"
    )


def format_pve_panel(session: dict) -> str:
    """Красивая панель PvE-боя."""
    monster = session["monster"]
    user    = session["user"]
    ps = format_battle_status(session["player_status"])
    ms = format_battle_status(session["monster_status"])

    m_bar = format_hp_bar(session["monster_hp"], monster["hp"])
    p_bar = format_hp_bar(session["player_hp"], user["max_hp"])
    p_mana_bar = format_hp_bar(session["player_mana"], user["max_mana"], 6)

    mname = monster["name"].get("ru", monster["id"])
    log_tail = "\n".join(session["log"][-4:])

    # Фаза босса
    phase_line = ""
    if monster.get("is_boss") and session.get("phase_name"):
        phase_line = f"⚠️ *{session['phase_name']}*\n"

    p_house = HOUSE_EMOJI.get(user.get("house", ""), "🏠")

    return (
        f"{monster.get('emoji', '🐉')} *{mname}* {ms}\n"
        f"❤️ `[{m_bar}]` {session['monster_hp']}/{monster['hp']}\n"
        f"{phase_line}"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"{p_house} *{user['wizard_name']}* {ps}\n"
        f"❤️ `[{p_bar}]` {session['player_hp']}/{user['max_hp']}\n"
        f"💧 `[{p_mana_bar}]` {session['player_mana']}/{user['max_mana']}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"{log_tail}"
    )


def can_cast_any(spell_ids: list[str], current_mana: int) -> bool:
    for sid in spell_ids:
        spell = get_spell(sid)
        if spell and spell.get("mana", 0) <= current_mana:
            return True
    return False


MANA_REGEN_PER_TURN = 5
