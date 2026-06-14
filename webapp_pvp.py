"""
Асинхронный PvP для Mini App.

Игрок выбирает соперника → сервер симулирует пошаговый бой по статам и
заклинаниям обоих → возвращает полную "запись" боя (replay), которую
Mini App проигрывает с анимацией. Обновляет статистику и ELO.
"""
import logging
import random

logger = logging.getLogger(__name__)


def list_opponents(user_id: int) -> dict:
    """Список возможных соперников (другие игроки близкого уровня)."""
    from database import get_user, get_conn, fetchall
    me = get_user(user_id)
    if not me:
        return {"opponents": []}
    lvl = me.get("level", 1)
    try:
        with get_conn() as conn:
            rows = fetchall(conn, """
                SELECT user_id, wizard_name, house, level
                FROM users
                WHERE user_id != %s AND COALESCE(is_banned, FALSE) = FALSE
                ORDER BY ABS(level - %s) ASC, RANDOM()
                LIMIT 12
            """, user_id, lvl)
    except Exception as e:
        logger.warning("pvp opponents: %s", e)
        rows = []
    house_emojis = {"gryffindor": "🦁", "slytherin": "🐍", "ravenclaw": "🦅", "hufflepuff": "🦡"}
    out = []
    for r in rows:
        out.append({
            "id": r["user_id"],
            "name": r["wizard_name"],
            "house": house_emojis.get(r["house"], "🏰"),
            "level": r["level"],
        })
    return {"opponents": out}


def _combat_dict(user: dict) -> dict:
    return {
        "user_id": user["user_id"],
        "wizard_name": user["wizard_name"],
        "house": user.get("house", ""),
        "max_hp": user["max_hp"], "max_mana": user["max_mana"],
        "attack": user["attack"], "defense": user["defense"],
        "speed": user["speed"], "luck": user.get("luck", 5),
        "level": user.get("level", 1),
    }


def simulate(user_id: int, opponent_id: int) -> dict:
    """Симулировать бой и вернуть запись для анимации."""
    from database import get_user, get_user_spells, get_conn, execute
    from game.battle_engine import resolve_turn, fresh_status, element_badge
    from game.spells import SPELLS, spell_display_name

    me = get_user(user_id)
    opp = get_user(opponent_id)
    if not me or not opp:
        return {"ok": False, "error": "not_found"}

    p1 = _combat_dict(me)
    p2 = _combat_dict(opp)
    s1 = [r["spell_id"] for r in (get_user_spells(user_id) or [])] or ["expelliarmus"]
    s2 = [r["spell_id"] for r in (get_user_spells(opponent_id) or [])] or ["expelliarmus"]

    hp1, hp2 = p1["max_hp"], p2["max_hp"]
    mana1, mana2 = p1["max_mana"], p2["max_mana"]
    st1, st2 = fresh_status(), fresh_status()
    prev1 = prev2 = None

    house_emojis = {"gryffindor": "🦁", "slytherin": "🐍", "ravenclaw": "🦅", "hufflepuff": "🏰"}
    replay = []
    # Кто ходит первым — по скорости
    turn = 1 if p1["speed"] >= p2["speed"] else 2
    max_turns = 40

    def pick_spell(spell_ids, cur_mana):
        # Предпочитаем атакующее, по карману
        affordable = [s for s in spell_ids if SPELLS.get(s, {}).get("mana", 0) <= cur_mana]
        if not affordable:
            return spell_ids[0]
        attackers = [s for s in affordable if SPELLS.get(s, {}).get("damage", 0) > 0]
        return random.choice(attackers) if attackers else random.choice(affordable)

    for _ in range(max_turns):
        if hp1 <= 0 or hp2 <= 0:
            break
        if turn == 1:
            sid = pick_spell(s1, mana1)
            res = resolve_turn(sid, p1, p2, st1, st2, hp1, hp2, mana1, prev_spell_id=prev1)
            dmg = max(0, hp2 - res["defender_hp"])
            hp1, hp2 = res["attacker_hp"], res["defender_hp"]
            mana1 = max(0, mana1 - res["mana_cost"])
            st1, st2 = res["new_atk_status"], res["new_def_status"]
            prev1 = sid
            replay.append({
                "by": 1, "spell": spell_display_name(sid, "ru"),
                "element": element_badge(SPELLS.get(sid, {})),
                "dmg": dmg, "heal": res.get("heal", 0) or 0, "crit": bool(res.get("crit")),
                "hp1": max(0, hp1), "hp2": max(0, hp2), "mana1": mana1, "mana2": mana2,
            })
            mana1 = min(p1["max_mana"], mana1 + 10)
            turn = 2
        else:
            sid = pick_spell(s2, mana2)
            res = resolve_turn(sid, p2, p1, st2, st1, hp2, hp1, mana2, prev_spell_id=prev2)
            dmg = max(0, hp1 - res["defender_hp"])
            hp2, hp1 = res["attacker_hp"], res["defender_hp"]
            mana2 = max(0, mana2 - res["mana_cost"])
            st2, st1 = res["new_atk_status"], res["new_def_status"]
            prev2 = sid
            replay.append({
                "by": 2, "spell": spell_display_name(sid, "ru"),
                "element": element_badge(SPELLS.get(sid, {})),
                "dmg": dmg, "heal": res.get("heal", 0) or 0, "crit": bool(res.get("crit")),
                "hp1": max(0, hp1), "hp2": max(0, hp2), "mana1": mana1, "mana2": mana2,
            })
            mana2 = min(p2["max_mana"], mana2 + 10)
            turn = 1

    # Определяем победителя
    if hp1 > hp2:
        winner = 1
    elif hp2 > hp1:
        winner = 2
    else:
        winner = 1 if p1["attack"] >= p2["attack"] else 2

    won = (winner == 1)
    winner_id = user_id if won else opponent_id
    loser_id = opponent_id if won else user_id

    # Обновляем статистику и ELO
    elo_change = 0
    try:
        with get_conn() as conn:
            execute(conn, "INSERT INTO user_stats (user_id) VALUES (%s) ON CONFLICT DO NOTHING", winner_id)
            execute(conn, "INSERT INTO user_stats (user_id) VALUES (%s) ON CONFLICT DO NOTHING", loser_id)
            execute(conn, "UPDATE user_stats SET pvp_wins=pvp_wins+1, pvp_total=pvp_total+1 WHERE user_id=%s", winner_id)
            execute(conn, "UPDATE user_stats SET pvp_losses=pvp_losses+1, pvp_total=pvp_total+1 WHERE user_id=%s", loser_id)
        from handlers.duel_league import update_elo, _get_rating
        before = _get_rating(user_id)["elo"]
        update_elo(winner_id, loser_id)
        after = _get_rating(user_id)["elo"]
        elo_change = after - before
        # Награда победителю
        if won:
            from database import add_gold, add_xp
            add_gold(user_id, 40)
            add_xp(user_id, 60)
    except Exception as e:
        logger.warning("pvp stats: %s", e)

    return {
        "ok": True,
        "you": {"name": p1["wizard_name"], "house": house_emojis.get(p1["house"], "🏰"), "maxHp": p1["max_hp"], "maxMana": p1["max_mana"]},
        "foe": {"name": p2["wizard_name"], "house": house_emojis.get(p2["house"], "🏰"), "maxHp": p2["max_hp"], "maxMana": p2["max_mana"]},
        "replay": replay,
        "youWon": won,
        "eloChange": elo_change,
        "reward": {"gold": 40, "xp": 60} if won else None,
    }
