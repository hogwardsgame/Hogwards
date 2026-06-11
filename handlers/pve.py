"""
PvE Dungeons handler.
Полностью переработанный визуал: панели монстров, шкалы HP,
описание действий врагов, эффекты и статусы, система фаз боссов,
комбо-заклинания, журнал боя.
"""
import logging
import random
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler, MessageHandler, filters
from database import (
    get_user, user_exists, get_user_spells, get_daily_limit, increment_daily,
    add_xp, add_gold, add_house_points, get_conn, execute, fetchval, add_item_to_inventory,
)
from utils.i18n import t
from utils.helpers import house_emoji
from game.battle_engine import (
    fresh_status, tick_status, resolve_turn, format_pve_panel,
    format_battle_status, battle_summary, can_cast_any, MANA_REGEN_PER_TURN,
    check_combo, flavour_line,
)
from game.spells import spell_display_name, SPELLS, RARITY_EMOJI
from game.monsters import (
    ZONES, get_zone, available_zones, pick_monster,
    monster_ai_action, MONSTER_SPELLS, get_monster_phase, AIPattern,
)
from game.drop_system import monster_drop, apply_antifarm_xp
from config import DAILY_LIMITS, XP_REWARDS, GOLD_REWARDS, HOUSE_POINTS_REWARDS

logger = logging.getLogger(__name__)

_pve_sessions: dict[int, dict] = {}


def _spells_keyboard(spell_ids: list[str], lang: str, current_mana: int = 9999, prev_spell: str = None) -> InlineKeyboardMarkup:
    """Клавиатура заклинаний с подсветкой комбо."""
    from game.battle_engine import COMBO_SPELLS
    buttons = []
    for sid in spell_ids[:8]:
        spell = SPELLS.get(sid)
        if not spell:
            continue
        name  = spell_display_name(sid, lang)
        mana  = spell.get("mana", 0)
        dmg   = spell.get("damage", 0)
        heal  = spell.get("heal", 0)
        rarity_e = RARITY_EMOJI.get(spell.get("rarity", "common"), "⚪")

        # Проверяем, образует ли комбо с предыдущим заклинанием
        is_combo = prev_spell and (
            (prev_spell, sid) in COMBO_SPELLS or (sid, prev_spell) in COMBO_SPELLS
        )
        combo_mark = "✨" if is_combo else ""

        if mana > current_mana:
            label = f"🚫 {rarity_e}{name} 💧{mana}"
        else:
            label = f"{combo_mark}{rarity_e}{name} 💧{mana}"
            if dmg:  label += f" ⚔️{dmg}"
            if heal: label += f" 💚{heal}"
        buttons.append([InlineKeyboardButton(label, callback_data=f"pve_cast:{sid}")])
    buttons.append([InlineKeyboardButton("🏃 Сбежать", callback_data="pve_flee")])
    return InlineKeyboardMarkup(buttons)


async def cmd_dungeon(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not user_exists(user_id):
        await update.message.reply_text(t(user_id, "not_registered"))
        return

    used = get_daily_limit(user_id, "pve_dungeons")
    if used >= DAILY_LIMITS["pve_dungeons"]:
        await update.message.reply_text(t(user_id, "daily_limit_reached"))
        return

    user  = get_user(user_id)
    zones = available_zones(user["level"])
    if not zones:
        await update.message.reply_text(t(user_id, "pve_no_zones"))
        return

    _pve_sessions.pop(user_id, None)

    buttons = []
    for z in zones:
        name = z["name"].get("ru", z["id"])
        desc = z.get("desc_ru", "")
        min_lvl = z["min_level"]
        buttons.append([InlineKeyboardButton(
            f"{z['emoji']} {name} (ур.{min_lvl}+)",
            callback_data=f"pve_enter:{z['id']}"
        )])

    markup = InlineKeyboardMarkup(buttons)
    await update.message.reply_text(
        f"🗺️ *Выбери локацию*\n\n"
        f"Твой уровень: {user['level']}\n"
        f"Доступно зон: {len(zones)}",
        parse_mode="Markdown",
        reply_markup=markup
    )


async def cb_pve_enter(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query   = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    zone_id = query.data.split(":")[1]

    _pve_sessions.pop(user_id, None)

    user  = get_user(user_id)
    zone  = get_zone(zone_id)
    if not zone:
        await query.edit_message_text("❌ Зона не найдена.")
        return

    with get_conn() as conn:
        kills_in_zone = fetchval(
            conn,
            "SELECT COUNT(*) FROM pve_sessions WHERE user_id=%s AND zone=%s AND result='win'",
            user_id, zone_id
        ) or 0

    is_boss = (kills_in_zone > 0) and (kills_in_zone % zone["boss_every"] == 0)
    monster = pick_monster(zone_id, is_boss=is_boss)
    if not monster:
        await query.edit_message_text("❌ Монстр не найден.")
        return

    # Масштабируем HP монстра под уровень игрока для интереса
    level_mult = 1 + (user["level"] - zone["min_level"]) * 0.05
    scaled_hp  = int(monster["hp"] * min(level_mult, 2.0))

    # Начальная фаза для боссов
    phase = get_monster_phase(monster, scaled_hp) if is_boss else None
    phase_name = phase["name"] if phase else ""

    session = {
        "zone_id":         zone_id,
        "user":            dict(user),
        "monster":         dict(monster),
        "monster_max_hp":  scaled_hp,
        "player_hp":       user["hp"],
        "player_mana":     user["mana"],
        "monster_hp":      scaled_hp,
        "player_status":   fresh_status(),
        "monster_status":  fresh_status(),
        "turn":            1,
        "log":             [],
        "total_dmg_dealt": 0,
        "total_dmg_taken": 0,
        "prev_spell":      None,
        "phase_name":      phase_name,
    }

    # Применяем бонусы активных зелий
    try:
        from database import get_potion_bonus
        atk_bonus = get_potion_bonus(user_id, "attack_mult")
        def_bonus = get_potion_bonus(user_id, "defense_mult")
        if atk_bonus:
            session["user"] = dict(user)
            session["user"]["attack"] = int(user["attack"] * (1 + atk_bonus))
            session["log"].append(f"⚡ Зелье силы активно: +{int(atk_bonus*100)}% к атаке!")
        if def_bonus:
            session["user"]["defense"] = int(user["defense"] * (1 + def_bonus))
            session["log"].append(f"🛡️ Зелье щита активно: +{int(def_bonus*100)}% к защите!")
        luck_bonus = get_potion_bonus(user_id, "luck_mult")
        if luck_bonus:
            session["user"]["luck"] = int(user["luck"] * (1 + luck_bonus))
            session["log"].append(f"🍀 Феликс Фелицис активен: удача усилена!")
    except Exception:
        pass

    mname = monster["name"].get("ru", monster["id"])
    if is_boss:
        session["log"].append(f"⚠️ БОСС: *{mname}* появился!")
        if monster.get("strategy_ru"):
            session["log"].append(f"💡 {monster['strategy_ru']}")
    else:
        session["log"].append(f"🏴 Ты встретил {mname}!")
        if monster.get("desc_ru"):
            session["log"].append(f"_{monster['desc_ru']}_")

    _pve_sessions[user_id] = session

    spells = [row["spell_id"] for row in get_user_spells(user_id)]
    lang   = user.get("lang", "ru")
    markup = _spells_keyboard(spells, lang, session["player_mana"], session["prev_spell"])
    await query.edit_message_text(
        format_pve_panel(session),
        parse_mode="Markdown",
        reply_markup=markup
    )


async def cb_pve_cast(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query    = update.callback_query
    await query.answer()
    user_id  = query.from_user.id
    spell_id = query.data.split(":")[1]

    session = _pve_sessions.get(user_id)
    if not session:
        await query.edit_message_text("❌ Бой завершён.")
        return

    user    = session["user"]
    monster = session["monster"]
    lang    = user.get("lang", "ru")

    # ── Ход игрока ────────────────────────────────────────────────────────────
    result = resolve_turn(
        spell_id, user, monster,
        session["player_status"], session["monster_status"],
        session["player_hp"], session["monster_hp"],
        session["player_mana"],
        prev_spell_id=session.get("prev_spell"),
    )

    session["player_hp"]      = result["attacker_hp"]
    session["monster_hp"]     = result["defender_hp"]
    session["player_mana"]    = max(0, session["player_mana"] - result["mana_cost"])
    session["player_status"]  = result["new_atk_status"]
    session["monster_status"] = result["new_def_status"]
    session["total_dmg_dealt"] += result["damage"]
    session["prev_spell"]     = spell_id   # запоминаем для следующего комбо

    sname = spell_display_name(spell_id, lang)
    log_entry = f"🧙 {sname}: {result['log']}"
    if result.get("combo"):
        log_entry = f"✨ КОМБО «{result['combo']['name']}»!\n" + log_entry
    if result.get("flavour"):
        log_entry += f"\n_{result['flavour']}_"
    session["log"].append(log_entry)

    # Победа
    if result.get("instant_kill") or session["monster_hp"] <= 0:
        await _pve_win(query, user_id, session, ctx)
        return

    # ── Ход монстра ───────────────────────────────────────────────────────────
    m_action = monster_ai_action(monster, session["monster_hp"], session["player_hp"], session["turn"])

    # Обновляем фазу босса
    if monster.get("is_boss"):
        phase = get_monster_phase(monster, session["monster_hp"])
        if phase and phase["name"] != session.get("phase_name"):
            session["phase_name"] = phase["name"]
            session["log"].append(f"⚠️ *{phase['name']}* — противник меняет тактику!")

    if m_action["action"] == "defend":
        from game.battle_engine import apply_effect
        session["monster_status"] = apply_effect("block", session["monster_status"])
        session["log"].append(f"{monster.get('emoji', '🐉')} Защищается!")
    else:
        m_spell_data = m_action.get("spell") or {}
        m_spell_id   = m_action.get("spell_id", "bite")

        pseudo_spell = {
            "id":            m_spell_id,
            "type":          "attack",
            "mana":          0,
            "damage":        m_spell_data.get("damage", monster["attack"]),
            "effect":        m_spell_data.get("effect"),
            "effect_chance": m_spell_data.get("effect_chance", 0.3),
        }

        # Монстр атакует через resolve_turn
        m_result = resolve_turn(
            m_spell_id, monster, user,
            session["monster_status"], session["player_status"],
            session["monster_hp"], session["player_hp"], 9999,
        )

        if m_result["damage"] == 0 and not m_result["skipped"] and not m_result["missed"]:
            from game.battle_engine import calculate_damage
            m_dmg, _, _, _, upd_ps = calculate_damage(
                pseudo_spell, monster, user,
                session["monster_status"], session["player_status"]
            )
            session["player_hp"]     = max(0, session["player_hp"] - m_dmg)
            session["player_status"] = upd_ps
            session["total_dmg_taken"] += m_dmg
            effect = m_spell_data.get("effect")
            eff_tag = f" ({effect})" if effect else ""
            m_name_ru = _monster_spell_name(m_spell_id)
            session["log"].append(f"{monster.get('emoji','🐉')} {m_name_ru}: -{m_dmg} ХП{eff_tag}")
        else:
            m_dmg = m_result["damage"]
            session["player_hp"]      = m_result["defender_hp"]
            session["monster_hp"]     = m_result["attacker_hp"]
            session["monster_status"] = m_result["new_atk_status"]
            session["player_status"]  = m_result["new_def_status"]
            session["total_dmg_taken"] += m_dmg
            m_name_ru = _monster_spell_name(m_spell_id)
            m_log = f"{monster.get('emoji','🐉')} {m_name_ru}: {m_result['log']}"
            if m_result.get("flavour"):
                m_log += f"\n_{m_result['flavour']}_"
            session["log"].append(m_log)

    # Тик DoT-эффектов
    ps, dot_p = tick_status(session["player_status"])
    ms, dot_m = tick_status(session["monster_status"])
    session["player_status"]  = ps
    session["monster_status"] = ms
    if dot_p > 0:
        session["player_hp"]  = max(0, session["player_hp"] - dot_p)
        session["log"].append(f"🔥 Эффект наносит тебе {dot_p} урона")
    if dot_m > 0:
        session["monster_hp"] = max(0, session["monster_hp"] - dot_m)
        session["log"].append(f"🔥 Эффект наносит монстру {dot_m} урона")

    session["turn"] += 1
    # Ограничиваем лог 6 строками
    session["log"] = session["log"][-6:]

    # Если оба умерли от эффектов, победу отдаём игроку: монстр тоже повержен.
    if session["monster_hp"] <= 0:
        await _pve_win(query, user_id, session, ctx)
        return
    if session["player_hp"] <= 0:
        await _pve_lose(query, user_id, session)
        return

    spells = [row["spell_id"] for row in get_user_spells(user_id)]

    if not can_cast_any(spells, session["player_mana"]):
        session["player_mana"] = min(
            session["user"]["max_mana"],
            session["player_mana"] + MANA_REGEN_PER_TURN
        )
        session["log"].append(f"✨ Мана восстанавливается +{MANA_REGEN_PER_TURN} 💧")
        if not can_cast_any(spells, session["player_mana"]):
            session["log"].append("💀 Мана иссякла — силы покинули тебя...")
            await _pve_lose(query, user_id, session)
            return

    markup = _spells_keyboard(spells, lang, session["player_mana"], session["prev_spell"])
    await query.edit_message_text(
        format_pve_panel(session),
        parse_mode="Markdown",
        reply_markup=markup
    )


def _monster_spell_name(spell_id: str) -> str:
    """Читаемое название атаки монстра."""
    names = {
        "bite": "Укус", "web_shot": "Паутина", "arrow_shot": "Стрела",
        "venom_bite": "Ядовитый укус", "web_cocoon": "Кокон",
        "spider_swarm": "Рой пауков", "soul_drain": "Высасывание души",
        "despair": "Отчаяние", "club_smash": "Удар дубиной",
        "roar": "Рёв", "dementor_kiss": "Поцелуй дементора",
        "darkness": "Тьма", "petrify_gaze": "Взгляд петрификации",
        "killing_gaze": "Смертоносный взгляд", "venom_flood": "Поток яда",
        "tail_sweep": "Удар хвостом", "fire_breath": "Огненное дыхание",
        "tail_smash": "Удар хвостом", "inferno": "Инфернальный огонь",
        "wing_gust": "Порыв крыльев", "crucio": "Крусиатус",
        "avada_kedavra": "Авада Кедавра", "fiendfyre": "Фиендфайр",
        "soul_curse": "Проклятие души", "morsmordre": "Морсмордре",
        "blood_curse": "Кровавое проклятие", "water_jet": "Струя воды",
        "tidal_wave": "Приливная волна", "constrict": "Удушение",
        "slam": "Удар щупальцем", "defend": "Защита",
    }
    return names.get(spell_id, spell_id.replace("_", " ").title())


async def _pve_win(query, user_id: int, session: dict, ctx: ContextTypes.DEFAULT_TYPE):
    _pve_sessions.pop(user_id, None)
    user    = session["user"]
    monster = session["monster"]

    luck_mod = 1.0 + (user.get("luck", 5) - 5) * 0.01
    drop     = monster_drop(monster, luck_modifier=luck_mod)

    with get_conn() as conn:
        repeat_count = fetchval(
            conn,
            "SELECT COUNT(*) FROM pve_sessions WHERE user_id=%s AND monster=%s AND created_at::date=CURRENT_DATE",
            user_id, monster["id"]
        ) or 0
    xp_actual = apply_antifarm_xp(drop["xp"], repeat_count, 0, user["level"], 0)

    new_level, leveled_up = add_xp(user_id, xp_actual)
    add_gold(user_id, drop["gold"])
    increment_daily(user_id, "pve_dungeons")

    # Очки факультета
    pts_reason = "pve_boss_kill" if monster.get("is_boss") else "pve_kill"
    pts = HOUSE_POINTS_REWARDS.get("pve_boss_kill" if monster.get("is_boss") else "pve_kill", 2)
    add_house_points(user_id, user["house"], pts, pts_reason)

    with get_conn() as conn:
        execute(conn, """
            INSERT INTO pve_sessions (user_id, zone, monster, result, xp_gained, gold_gained)
            VALUES (%s, %s, %s, 'win', %s, %s)
        """, user_id, session["zone_id"], monster["id"], xp_actual, drop["gold"])
        if monster.get("is_boss"):
            execute(conn, "UPDATE user_stats SET boss_kills = boss_kills + 1 WHERE user_id = %s", user_id)
        else:
            execute(conn, "UPDATE user_stats SET pve_kills = pve_kills + 1 WHERE user_id = %s", user_id)

    mname   = monster["name"].get("ru", monster["id"])
    summary = battle_summary(session["turn"], session["total_dmg_dealt"], session["total_dmg_taken"])

    drop_text = ""
    if drop.get("spell"):
        with get_conn() as conn:
            execute(conn, "INSERT INTO user_spells (user_id, spell_id) VALUES (%s, %s) ON CONFLICT DO NOTHING", user_id, drop["spell"])
        drop_text += f"\n✨ *Новое заклинание:* `{drop['spell']}`!"
    if drop.get("item"):
        add_item_to_inventory(user_id, drop["item"]["id"], 1)
        drop_text += f"\n🎁 *Найден предмет:* `{drop['item']['id']}`!"
    # Уникальный дроп босса
    if monster.get("is_boss") and monster.get("unique_drop"):
        if random.random() < 0.05:  # 5% шанс уникального дропа
            add_item_to_inventory(user_id, monster["unique_drop"], 1)
            drop_text += f"\n🌟 *РЕДКИЙ ДРОП:* `{monster['unique_drop']}`!"

    level_text = f"\n\n🎉 *Уровень повышен до {new_level}!*" if leveled_up else ""

    text = (
        f"🏆 *{mname} повержен!*\n"
        f"+{xp_actual} XP | +{drop['gold']} 💰 | +{pts} очков факультету\n"
        f"\n{summary}"
        f"{drop_text}"
        f"{level_text}"
    )
    await query.edit_message_text(text, parse_mode="Markdown")

    # Обновить достижения и задания дня
    try:
        from handlers.achievements import check_achievements
        await check_achievements(user_id, ctx)
    except Exception:
        pass
    try:
        from handlers.daily_bonus import update_task_progress
        update_task_progress(user_id, "pve_kills", 1)
        if monster.get("is_boss"):
            update_task_progress(user_id, "boss_kills", 1)
    except Exception:
        pass
    try:
        from database import add_weekly_xp, add_weekly_kill
        add_weekly_xp(user_id, xp_actual)
        add_weekly_kill(user_id)
    except Exception:
        pass


async def _pve_lose(query, user_id: int, session: dict):
    _pve_sessions.pop(user_id, None)
    mname = session["monster"]["name"].get("ru", session["monster"]["id"])
    xp_consolation = 5
    add_xp(user_id, xp_consolation)

    summary = battle_summary(session["turn"], session["total_dmg_dealt"], session["total_dmg_taken"])

    with get_conn() as conn:
        execute(conn, """
            INSERT INTO pve_sessions (user_id, zone, monster, result, xp_gained, gold_gained)
            VALUES (%s, %s, %s, 'loss', %s, 0)
        """, user_id, session["zone_id"], session["monster"]["id"], xp_consolation)

    await query.edit_message_text(
        f"💀 *{mname} победил тебя!*\n+{xp_consolation} XP за участие.\n\n{summary}",
        parse_mode="Markdown"
    )


async def cb_pve_flee(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query   = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    _pve_sessions.pop(user_id, None)
    await query.edit_message_text("🏃 Ты сбежал с поля боя!")



def register_pve_handlers(app):
    app.add_handler(CommandHandler("dungeon", cmd_dungeon))
    app.add_handler(CallbackQueryHandler(cb_pve_enter, pattern=r"^pve_enter:"))
    app.add_handler(CallbackQueryHandler(cb_pve_cast,  pattern=r"^pve_cast:"))
    app.add_handler(CallbackQueryHandler(cb_pve_flee,  pattern=r"^pve_flee"))
    