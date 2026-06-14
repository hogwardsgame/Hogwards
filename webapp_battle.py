"""
PvE-бой для Mini App — серверная логика.

Состояние боя хранится в памяти, ключ — user_id. Ход считается через
проверенный battle_engine.resolve_turn. Mini App только показывает и анимирует.
"""
import logging
import random
import time

logger = logging.getLogger(__name__)

# Активные бои: user_id -> state
_battles: dict[int, dict] = {}
_win_streaks: dict[int, int] = {}
# Чистим старые бои (если игрок ушёл): храним не дольше 30 минут
_BATTLE_TTL = 1800


def _cleanup():
    now = time.time()
    dead = [uid for uid, st in _battles.items() if now - st.get("ts", now) > _BATTLE_TTL]
    for uid in dead:
        _battles.pop(uid, None)


def _spell_brief(spell_id: str, lang="ru"):
    from game.spells import SPELLS, spell_display_name
    from game.battle_engine import element_badge
    s = SPELLS.get(spell_id, {})
    return {
        "id":     spell_id,
        "name":   spell_display_name(spell_id, lang),
        "emoji":  s.get("emoji", "✨"),
        "mana":   s.get("mana", 0),
        "damage": s.get("damage", 0),
        "heal":   s.get("heal", 0),
        "element": element_badge(s),
    }


def _public_state(uid: int) -> dict:
    """Состояние боя для отправки в Mini App."""
    st = _battles.get(uid)
    if not st:
        return {"active": False}
    p = st["player"]
    m = st["monster"]
    return {
        "active":    True,
        "player": {
            "name":  p["wizard_name"],
            "hp":    st["player_hp"], "maxHp": p["max_hp"],
            "mana":  st["player_mana"], "maxMana": p["max_mana"],
        },
        "monster": {
            "name":  m["name"].get("ru", "Монстр") if isinstance(m.get("name"), dict) else m.get("name", "Монстр"),
            "emoji": m.get("emoji", "👹"),
            "hp":    st["monster_hp"], "maxHp": m["hp"],
        },
        "spells":  [_spell_brief(sid) for sid in st["spell_ids"]],
        "log":     st["log"][-4:],
        "turn":    st["turn"],
        "over":    st["over"],
        "result":  st.get("result"),
        "reward":  st.get("reward"),
        "lastTurn": st.get("last_turn"),
    }


def list_zones(user_id: int) -> dict:
    """Список зон с учётом уровня игрока (для выбора в бою)."""
    from database import get_user
    from game.monsters import ZONES, MONSTERS
    user = get_user(user_id)
    lvl = user.get("level", 1) if user else 1
    out = []
    for zid, z in ZONES.items():
        min_lvl = z.get("min_level", 1)
        mons = [MONSTERS[mid] for mid in z.get("monsters", []) if mid in MONSTERS]
        out.append({
            "id": zid,
            "name": z["name"].get("ru") if isinstance(z.get("name"), dict) else z.get("name", zid),
            "emoji": z.get("emoji", "🌲"),
            "minLevel": min_lvl,
            "locked": lvl < min_lvl,
            "monsters": len(mons),
        })
    return {"zones": out, "playerLevel": lvl}


def start_battle(user_id: int, zone_id: str = None) -> dict:
    """Начать PvE-бой. Если указана зона — монстр из неё, иначе случайный."""
    _cleanup()
    from database import get_user, get_user_spells
    from game.monsters import MONSTERS, ZONES
    from game.battle_engine import fresh_status

    user = get_user(user_id)
    if not user:
        return {"active": False, "error": "not_registered"}

    spell_rows = get_user_spells(user_id)
    spell_ids = [r["spell_id"] for r in spell_rows] if spell_rows else ["expelliarmus"]

    lvl = user.get("level", 1)
    monster = None
    if zone_id and zone_id in ZONES:
        z = ZONES[zone_id]
        if lvl < z.get("min_level", 1):
            return {"active": False, "error": "zone_locked",
                    "msg": f"Зона доступна с {z.get('min_level',1)} уровня"}
        zone_monsters = [MONSTERS[mid] for mid in z.get("monsters", []) if mid in MONSTERS and not MONSTERS[mid].get("is_boss")]
        if zone_monsters:
            monster = dict(random.choice(zone_monsters))
    if monster is None:
        candidates = [m for m in MONSTERS.values() if not m.get("is_boss")]
        monster = dict(random.choice(candidates))

    st = {
        "player":       dict(user),
        "monster":      monster,
        "player_hp":    user["max_hp"],
        "player_mana":  user["max_mana"],
        "monster_hp":   monster["hp"],
        "player_status":  fresh_status(),
        "monster_status": fresh_status(),
        "spell_ids":    spell_ids,
        "log":          [f"⚔️ Бой против {monster.get('emoji','')} {monster['name'].get('ru') if isinstance(monster.get('name'),dict) else monster.get('name')}!"],
        "turn":         "player",
        "over":         False,
        "prev_spell":   None,
        "ts":           time.time(),
    }
    _battles[user_id] = st
    return _public_state(user_id)


def cast(user_id: int, spell_id: str) -> dict:
    """Игрок применяет заклинание. Сервер считает ход игрока и ответ монстра."""
    from game.battle_engine import resolve_turn
    from game.spells import SPELLS

    st = _battles.get(user_id)
    if not st or st["over"]:
        return {"active": False, "error": "no_battle"}
    if st["turn"] != "player":
        return _public_state(user_id)
    if spell_id not in st["spell_ids"]:
        return _public_state(user_id)

    st["ts"] = time.time()
    player  = st["player"]
    monster = st["monster"]
    # Монстру нужны поля как у игрока
    mon_combat = {
        "wizard_name": monster["name"].get("ru") if isinstance(monster.get("name"), dict) else monster.get("name", "Монстр"),
        "max_hp": monster["hp"], "max_mana": 100,
        "attack": monster["attack"], "defense": monster["defense"],
        "speed": monster["speed"], "luck": 0, "house": "",
    }

    # ── Ход игрока ────────────────────────────────────────────────────────
    spell = SPELLS.get(spell_id, {})
    mana_cost = spell.get("mana", 0)
    if st["player_mana"] < mana_cost:
        st["log"].append("💧 Недостаточно маны!")
        return _public_state(user_id)

    res = resolve_turn(
        spell_id, player, mon_combat,
        st["player_status"], st["monster_status"],
        st["player_hp"], st["monster_hp"], st["player_mana"],
        prev_spell_id=st.get("prev_spell"),
    )
    dmg_to_monster = max(0, st["monster_hp"] - res["defender_hp"])
    st["player_hp"]      = res["attacker_hp"]
    st["monster_hp"]     = res["defender_hp"]
    st["player_mana"]    = max(0, st["player_mana"] - res["mana_cost"])
    st["player_status"]  = res["new_atk_status"]
    st["monster_status"] = res["new_def_status"]
    st["prev_spell"]     = spell_id

    from game.spells import spell_display_name, SPELLS as _SP
    from game.battle_engine import element_badge
    st["last_turn"] = {
        "who": "player",
        "dmg": dmg_to_monster,
        "heal": res.get("heal", 0) or 0,
        "crit": bool(res.get("crit")),
        "element": element_badge(_SP.get(spell_id, {})),
        "elementAdv": res.get("element_label") == "💥 Преимущество стихии!",
    }
    sname = spell_display_name(spell_id, "ru")
    line = f"🧙 {sname}: {res['log']}"
    if res.get("crit"): line = "💥 КРИТ! " + line
    st["log"].append(line)

    # Монстр побеждён?
    if st["monster_hp"] <= 0:
        st["over"] = True
        st["turn"] = "over"
        st["result"] = "win"
        st["reward"] = _give_reward(user_id, monster)
        st["log"].append("🏆 Победа!")
        return _public_state(user_id)

    # ── Ход монстра ───────────────────────────────────────────────────────
    st["turn"] = "monster"
    mon_spells = monster.get("spells", ["bite"])
    mon_spell = random.choice(mon_spells)
    res2 = resolve_turn(
        mon_spell, mon_combat, player,
        st["monster_status"], st["player_status"],
        st["monster_hp"], st["player_hp"], 100,
    )
    dmg_to_player = max(0, st["player_hp"] - res2["defender_hp"])
    st["monster_hp"]     = res2["attacker_hp"]
    st["player_hp"]      = res2["defender_hp"]
    st["monster_status"] = res2["new_atk_status"]
    st["player_status"]  = res2["new_def_status"]
    st["last_turn"] = {
        "who": "monster",
        "dmg": dmg_to_player,
        "crit": bool(res2.get("crit")),
        "element": "", "elementAdv": False, "heal": 0,
    }
    mname = monster["name"].get("ru") if isinstance(monster.get("name"), dict) else monster.get("name", "Монстр")
    st["log"].append(f"{monster.get('emoji','👹')} {mname}: {res2['log']}")

    # Игрок побеждён?
    if st["player_hp"] <= 0:
        st["over"] = True
        st["turn"] = "over"
        st["result"] = "lose"
        _win_streaks[user_id] = 0
        st["log"].append("💀 Поражение...")
        return _public_state(user_id)

    # Регенерация маны игроку в начале его хода
    st["player_mana"] = min(player["max_mana"], st["player_mana"] + 10)
    st["turn"] = "player"
    return _public_state(user_id)


def _give_reward(user_id: int, monster: dict) -> dict:
    """Выдать награду за победу (xp/gold/предмет) и обновить серию побед."""
    from database import add_xp, add_gold
    xp_range = monster.get("xp_reward", (10, 20))
    gold_range = monster.get("gold_reward", (3, 10))
    xp = random.randint(xp_range[0], xp_range[1]) if isinstance(xp_range, (tuple, list)) else int(xp_range)
    gold = random.randint(gold_range[0], gold_range[1]) if isinstance(gold_range, (tuple, list)) else int(gold_range)
    item_info = None
    try:
        add_xp(user_id, xp)
        add_gold(user_id, gold)
        # Опыт питомцу
        try:
            from handlers.pets import add_pet_xp
            add_pet_xp(user_id, 10)
        except Exception:
            pass
        # Дроп предмета или заклинания (повышенный шанс для Mini App)
        try:
            from game.drop_system import monster_drop
            from database import add_item_to_inventory, get_conn, execute
            from game.items import item_display_name, ITEMS
            from game.spells import SPELLS, spell_display_name
            drop = monster_drop(monster, luck_modifier=1.8)
            # Предмет
            if drop.get("item"):
                it = drop["item"]
                iid = it.get("id") if isinstance(it, dict) else it
                if iid:
                    add_item_to_inventory(user_id, iid, 1)
                    idata = ITEMS.get(iid, {})
                    item_info = {
                        "name": item_display_name(idata, "ru") if idata else iid,
                        "emoji": idata.get("emoji", "📦"),
                    }
            # Заклинание (раньше терялось — теперь выдаём)
            if drop.get("spell"):
                sp = drop["spell"]
                sid = sp.get("id") if isinstance(sp, dict) else sp
                if sid:
                    try:
                        with get_conn() as conn:
                            execute(conn, """
                                INSERT INTO user_spells (user_id, spell_id) VALUES (%s, %s)
                                ON CONFLICT DO NOTHING
                            """, user_id, sid)
                    except Exception:
                        pass
                    sdata = SPELLS.get(sid, {})
                    if item_info is None:
                        item_info = {
                            "name": spell_display_name(sid, "ru") + " (заклинание)",
                            "emoji": sdata.get("emoji", "📜"),
                        }
        except Exception as e:
            logger.warning("pve drop: %s", e)
        # Серия побед (в памяти на сессию)
        _win_streaks[user_id] = _win_streaks.get(user_id, 0) + 1
    except Exception as e:
        logger.warning("pve reward: %s", e)
    return {"xp": xp, "gold": gold, "item": item_info, "streak": _win_streaks.get(user_id, 1)}


def get_state(user_id: int) -> dict:
    return _public_state(user_id)


def flee(user_id: int) -> dict:
    _battles.pop(user_id, None)
    return {"active": False}
