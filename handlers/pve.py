"""
PvE Dungeons handler — TZ section 8.2.
Player fights monsters zone by zone; every 5 kills = mini-boss.

ИСПРАВЛЕНИЯ:
  1. Читаем new_atk_status / new_def_status из resolve_turn (раньше статусы не сохранялись)
  2. Урон монстра теперь честно считается через resolve_turn (не самодельная формула)
  3. Эффекты монстра (яд, ожог, оглушение) теперь реально применяются к игроку
  4. Флейвор-реплики из battle_engine отображаются в логе боя
  5. Добавлено отображение иконки щита 🔵 и тишины 🤐 в статусе
"""
import logging
import random
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler, MessageHandler, filters
from database import (
    get_user, user_exists, get_user_spells, get_daily_limit, increment_daily,
    add_xp, add_gold, get_conn, execute, fetchval,
)
from utils.i18n import t
from utils.helpers import house_emoji
from game.battle_engine import fresh_status, tick_status, resolve_turn, format_battle_status, battle_summary, can_cast_any, MANA_REGEN_PER_TURN
from game.spells import spell_display_name, SPELLS
from game.monsters import ZONES, get_zone, available_zones, pick_monster, monster_ai_action, MONSTER_SPELLS
from game.drop_system import monster_drop, apply_antifarm_xp
from config import DAILY_LIMITS

logger = logging.getLogger(__name__)

# In-memory PvE sessions: user_id → session
_pve_sessions: dict[int, dict] = {}


def _zones_keyboard(player_level: int, user_id: int) -> InlineKeyboardMarkup:
    zones = available_zones(player_level)
    buttons = []
    for z in zones:
        name = z["name"].get(t(user_id, "_lang_code") or "ru", z["name"]["en"])
        buttons.append([InlineKeyboardButton(
            f"{z['emoji']} {name}",
            callback_data=f"pve_enter:{z['id']}"
        )])
    return InlineKeyboardMarkup(buttons)


def _spells_keyboard(spell_ids: list[str], lang: str, current_mana: int = 9999) -> InlineKeyboardMarkup:
    buttons = []
    for sid in spell_ids[:8]:
        spell = SPELLS.get(sid)
        if not spell:
            continue
        name  = spell_display_name(sid, lang)
        mana  = spell.get("mana", 0)
        dmg   = spell.get("damage", 0)
        heal  = spell.get("heal", 0)
        # Показываем серым (крестиком) если не хватает маны
        if mana > current_mana:
            label = f"🚫 {name} | 💧{mana}"
        else:
            label = f"{name} | 💧{mana}"
            if dmg:  label += f" ⚔️{dmg}"
            if heal: label += f" 💚{heal}"
        buttons.append([InlineKeyboardButton(label, callback_data=f"pve_cast:{sid}")])
    buttons.append([InlineKeyboardButton("🏃 Сбежать", callback_data="pve_flee")])
    return InlineKeyboardMarkup(buttons)


def _format_pve_text(session: dict) -> str:
    monster = session["monster"]
    user    = session["user"]
    ps = format_battle_status(session["player_status"])
    ms = format_battle_status(session["monster_status"])
    log_tail = "\n".join(session["log"][-5:])
    mname = monster["name"].get("ru", monster["id"])
    # Полоска HP монстра
    max_hp = monster["hp"]
    cur_hp = session["monster_hp"]
    bar_len = 10
    filled = int(bar_len * cur_hp / max_hp) if max_hp > 0 else 0
    hp_bar = "█" * filled + "░" * (bar_len - filled)
    return (
        f"{monster.get('emoji','🐉')} *{mname}*\n"
        f"❤️ `[{hp_bar}]` {cur_hp}/{max_hp} {ms}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🧙 {user['wizard_name']} {house_emoji(user['house'])} {ps}\n"
        f"❤️ {session['player_hp']}/{user['max_hp']} | 💧{session['player_mana']}/{user['max_mana']}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"{log_tail}"
    )


async def cmd_dungeon(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not user_exists(user_id):
        await update.message.reply_text(t(user_id, "not_registered"))
        return

    used = get_daily_limit(user_id, "pve_dungeons")
    if used >= DAILY_LIMITS["pve_dungeons"]:
        await update.message.reply_text(t(user_id, "daily_limit_reached"))
        return

    user = get_user(user_id)
    zones = available_zones(user["level"])
    if not zones:
        await update.message.reply_text(t(user_id, "pve_no_zones"))
        return

    # Сбрасываем зависшую сессию при входе в меню зон
    _pve_sessions.pop(user_id, None)

    buttons = []
    for z in zones:
        name = z["name"].get("ru", z["name"]["en"])
        buttons.append([InlineKeyboardButton(
            f"{z['emoji']} {name} (мин. {z['min_level']} ур.)",
            callback_data=f"pve_enter:{z['id']}"
        )])
    markup = InlineKeyboardMarkup(buttons)
    await update.message.reply_text(t(user_id, "pve_choose_zone"), reply_markup=markup)


async def cb_pve_enter(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query   = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    zone_id = query.data.split(":")[1]

    # Если сессия зависла — тихо сбрасываем
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

    session = {
        "zone_id":         zone_id,
        "user":            dict(user),
        "monster":         dict(monster),
        "player_hp":       user["hp"],
        "player_mana":     user["mana"],
        "monster_hp":      monster["hp"],
        "player_status":   fresh_status(),
        "monster_status":  fresh_status(),
        "turn":            1,
        "log":             [f"🏴 Ты встретил {monster['name'].get('ru','?')}!"],
        # Статистика боя (новое)
        "total_dmg_dealt": 0,
        "total_dmg_taken": 0,
    }
    _pve_sessions[user_id] = session

    spells = [row["spell_id"] for row in get_user_spells(user_id)]
    lang   = user.get("lang", "ru")
    markup = _spells_keyboard(spells, lang, session["player_mana"])
    await query.edit_message_text(_format_pve_text(session), parse_mode="Markdown", reply_markup=markup)


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
        session["player_hp"], session["monster_hp"], session["player_mana"],
    )

    session["player_hp"]      = result["attacker_hp"]
    session["monster_hp"]     = result["defender_hp"]
    session["player_mana"]    = max(0, session["player_mana"] - result["mana_cost"])

    # ИСПРАВЛЕНИЕ: берём обновлённые статусы из результата
    session["player_status"]  = result["new_atk_status"]
    session["monster_status"] = result["new_def_status"]

    session["total_dmg_dealt"] += result["damage"]

    sname = spell_display_name(spell_id, lang)
    log_entry = f"🧙 {sname}: {result['log']}"
    if result.get("flavour"):
        log_entry += f"\n_{result['flavour']}_"
    session["log"].append(log_entry)

    # Проверка гибели монстра
    if result.get("instant_kill") or session["monster_hp"] <= 0:
        await _pve_win(query, user_id, session, ctx)
        return

    # ── Ход монстра ───────────────────────────────────────────────────────────
    m_action = monster_ai_action(monster, session["monster_hp"], session["player_hp"], session["turn"])

    if m_action["action"] == "defend":
        # ИСПРАВЛЕНИЕ: применяем эффект защиты через apply_effect
        from game.battle_engine import apply_effect
        session["monster_status"] = apply_effect("block", session["monster_status"])
        session["log"].append(f"{monster.get('emoji','🐉')} Защищается!")
    else:
        # ИСПРАВЛЕНИЕ: урон монстра считаем через resolve_turn,
        # чтобы корректно работали блок, щит, яд и всё остальное.
        m_spell_data = m_action.get("spell") or {}
        m_spell_id   = m_action.get("spell_id", "bite")

        # Строим псевдо-спелл из данных монстра если это не настоящий спелл
        pseudo_spell = {
            "id":            m_spell_id,
            "type":          "attack",
            "mana":          0,
            "damage":        m_spell_data.get("damage", monster["attack"]),
            "effect":        m_spell_data.get("effect"),
            "effect_chance": m_spell_data.get("effect_chance", 0.3),
        }

        # Монстр атакует игрока
        m_result = resolve_turn(
            m_spell_id,
            monster,        # атакующий монстр
            user,           # защищающийся игрок
            session["monster_status"],
            session["player_status"],
            session["monster_hp"],
            session["player_hp"],
            9999,            # у монстра бесконечная мана
        )

        # Но resolve_turn ищет спелл в SPELLS словаре — если не найден,
        # делаем fallback на ручной расчёт с корректным учётом защиты
        if m_result["damage"] == 0 and not m_result["skipped"] and not m_result["missed"]:
            # Спелл монстра не найден в SPELLS — считаем вручную, но честно
            from game.battle_engine import calculate_damage
            m_dmg, _, _, _, updated_player_status = calculate_damage(
                pseudo_spell, monster, user,
                session["monster_status"], session["player_status"]
            )
            session["player_hp"]     = max(0, session["player_hp"] - m_dmg)
            session["player_status"] = updated_player_status
            session["total_dmg_taken"] += m_dmg
            effect = m_spell_data.get("effect")
            eff_tag = f" ({effect})" if effect else ""
            session["log"].append(f"{monster.get('emoji','🐉')} -{m_dmg} ХП{eff_tag}")
        else:
            # resolve_turn сработал корректно — применяем его результаты
            # (для монстра: attacker=монстр, defender=игрок)
            m_dmg = m_result["damage"]
            session["player_hp"]      = m_result["defender_hp"]
            session["monster_hp"]     = m_result["attacker_hp"]   # отражение
            session["monster_status"] = m_result["new_atk_status"]
            session["player_status"]  = m_result["new_def_status"]
            session["total_dmg_taken"] += m_dmg
            m_log = f"{monster.get('emoji','🐉')} {m_result['log']}"
            if m_result.get("flavour"):
                m_log += f"\n_{m_result['flavour']}_"
            session["log"].append(m_log)

    # Тик статусов (DoT-эффекты)
    ps, dot_p = tick_status(session["player_status"])
    ms, dot_m = tick_status(session["monster_status"])
    session["player_status"]  = ps
    session["monster_status"] = ms
    if dot_p > 0:
        session["player_hp"]  = max(0, session["player_hp"] - dot_p)
        session["log"].append(f"🔥 Урон от эффекта: -{dot_p} ХП")
    if dot_m > 0:
        session["monster_hp"] = max(0, session["monster_hp"] - dot_m)
        session["log"].append(f"🔥 Монстр получает урон от эффекта: -{dot_m} ХП")

    session["turn"] += 1

    if session["player_hp"] <= 0:
        await _pve_lose(query, user_id, session)
        return
    if session["monster_hp"] <= 0:
        await _pve_win(query, user_id, session, ctx)
        return

    # Продолжаем бой
    spells = [row["spell_id"] for row in get_user_spells(user_id)]

    # ── НОВОЕ: проверка пата по мане ─────────────────────────────────────────
    if not can_cast_any(spells, session["player_mana"]):
        # Регенерируем ману пассивно (5 в ход) пока не хватит хоть на что-то
        session["player_mana"] = min(
            session["user"]["max_mana"],
            session["player_mana"] + MANA_REGEN_PER_TURN
        )
        session["log"].append(f"✨ Мана восстанавливается... +{MANA_REGEN_PER_TURN} 💧")
        # Если после регена всё равно ничего нельзя скастовать — завершаем бой
        if not can_cast_any(spells, session["player_mana"]):
            session["log"].append("💀 Мана на нуле — силы покинули тебя...")
            await _pve_lose(query, user_id, session)
            return

    markup = _spells_keyboard(spells, lang, session["player_mana"])
    await query.edit_message_text(_format_pve_text(session), parse_mode="Markdown", reply_markup=markup)


async def _pve_win(query, user_id: int, session: dict, ctx: ContextTypes.DEFAULT_TYPE):
    _pve_sessions.pop(user_id, None)
    user    = session["user"]
    monster = session["monster"]

    luck_mod = 1.0 + (user.get("luck", 5) - 5) * 0.01
    drop     = monster_drop(monster, luck_modifier=luck_mod)

    # Anti-farm XP
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

    with get_conn() as conn:
        execute(conn, """
            INSERT INTO pve_sessions (user_id, zone, monster, result, xp_gained, gold_gained)
            VALUES (%s, %s, %s, 'win', %s, %s)
        """, user_id, session["zone_id"], monster["id"], xp_actual, drop["gold"])

    with get_conn() as conn:
        execute(conn,
            "UPDATE house_points SET points = points + 5 WHERE house = (SELECT house FROM users WHERE user_id=%s)",
            user_id)

    mname   = monster["name"].get("ru", monster["id"])
    summary = battle_summary(session["turn"], session["total_dmg_dealt"], session["total_dmg_taken"])

    text = (
        f"🏆 *{mname} повержен!*\n"
        f"+{xp_actual} XP | +{drop['gold']} 💰\n"
        f"\n{summary}\n"
    )
    if drop["spell"]:
        text += f"\n✨ Получено заклинание: `{drop['spell']}`!"
    if drop["item"]:
        text += f"\n🎁 Получен предмет: `{drop['item']['id']}`!"
    if leveled_up:
        text += f"\n\n🎉 Уровень повышен до {new_level}!"

    await query.edit_message_text(text, parse_mode="Markdown")


async def _pve_lose(query, user_id: int, session: dict):
    _pve_sessions.pop(user_id, None)
    mname = session["monster"]["name"].get("ru", session["monster"]["id"])
    xp_consolation = 10
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
    await query.edit_message_text(t(user_id, "pve_fled"))


async def handle_dungeon_button(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if update.message.text == t(user_id, "btn_dungeon"):
        await cmd_dungeon(update, ctx)


def register_pve_handlers(app):
    app.add_handler(CommandHandler("dungeon", cmd_dungeon))
    app.add_handler(CallbackQueryHandler(cb_pve_enter, pattern=r"^pve_enter:"))
    app.add_handler(CallbackQueryHandler(cb_pve_cast,  pattern=r"^pve_cast:"))
    app.add_handler(CallbackQueryHandler(cb_pve_flee,  pattern=r"^pve_flee"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_dungeon_button), group=5)
