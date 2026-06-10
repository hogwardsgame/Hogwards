"""
World Bosses — мировые боссы.
Появляются по расписанию (12:00 и 20:00 UTC).
Общий запас HP — все игроки бьют вместе.
Награды зависят от вклада игрока.
"""
import logging
import random
from datetime import datetime, timezone
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler
from database import (
    get_user, user_exists, add_xp, add_gold, add_house_points,
    get_active_world_boss, record_world_boss_damage, get_world_boss_top,
    get_daily_limit, increment_daily, get_conn, execute, fetchrow, fetchall,
)
from game.battle_engine import fresh_status, resolve_turn, format_hp_bar
from game.spells import get_spell, SPELLS
from utils.i18n import t
from config import (
    DAILY_LIMITS, WORLD_BOSS_DURATION_MINUTES,
    XP_REWARDS, GOLD_REWARDS, HOUSE_POINTS_REWARDS,
)

logger = logging.getLogger(__name__)

# ── Каталог мировых боссов ─────────────────────────────────────────────────────
WORLD_BOSSES: dict[str, dict] = {
    "basilisk_ancient": {
        "name":    "Древний Василиск",
        "emoji":   "🐍💀",
        "hp":      50_000,
        "attack":  80,
        "defense": 40,
        "desc":    "Первый Василиск, созданный самим Слизерином. Его взгляд обращает в камень целые армии.",
        "weakness":"fire",
        "phases": [
            {"threshold": 1.00, "name": "Дремлющий",  "dmg_mult": 1.0},
            {"threshold": 0.70, "name": "Пробудившийся","dmg_mult": 1.3},
            {"threshold": 0.40, "name": "Разъярённый", "dmg_mult": 1.6},
            {"threshold": 0.15, "name": "Агония",      "dmg_mult": 2.0},
        ],
        "passive_dmg":      [8, 15],
        "special_cooldown": 5,
        "special_spell":    "killing_gaze",
        "special_desc":     "Смертоносный взгляд — 50 урона всем атакующим!",
        "drop_table": {
            "top1":   {"xp": 2000, "gold": 1000, "title": "Гроза Василисков"},
            "top3":   {"xp": 1500, "gold": 700},
            "top10":  {"xp": 1000, "gold": 400},
            "others": {"xp": 400,  "gold": 150},
        },
        "unique_drop_chance": 0.05,
        "unique_drop": "gloves_basilisk",
    },
    "ancient_dementor": {
        "name":    "Древний Дементор",
        "emoji":   "👻💀",
        "hp":      40_000,
        "attack":  70,
        "defense": 20,
        "desc":    "Первый дементор — источник всей тьмы Азкабана. Высасывает надежду из мира.",
        "weakness":"patronus",
        "phases": [
            {"threshold": 1.00, "name": "Тень",         "dmg_mult": 1.0},
            {"threshold": 0.60, "name": "Голод",        "dmg_mult": 1.4},
            {"threshold": 0.25, "name": "Поглощение",   "dmg_mult": 1.8},
        ],
        "passive_dmg":      [10, 20],
        "special_cooldown": 4,
        "special_spell":    "dementor_kiss",
        "special_desc":     "Массовый поцелуй — все атакующие теряют 30 маны!",
        "drop_table": {
            "top1":   {"xp": 1800, "gold": 900, "title": "Защитник от тьмы"},
            "top3":   {"xp": 1200, "gold": 600},
            "top10":  {"xp": 800,  "gold": 350},
            "others": {"xp": 300,  "gold": 120},
        },
        "unique_drop_chance": 0.05,
        "unique_drop": "amulet_horcrux",
    },
    "hungarian_horntail": {
        "name":    "Венгерская хвосторога",
        "emoji":   "🐉🔥",
        "hp":      60_000,
        "attack":  100,
        "defense": 50,
        "desc":    "Самый опасный дракон в мире. Огонь плавит сталь, хвост крушит стены.",
        "weakness":"ice",
        "phases": [
            {"threshold": 1.00, "name": "Спящая",      "dmg_mult": 1.0},
            {"threshold": 0.65, "name": "Разбуженная", "dmg_mult": 1.4},
            {"threshold": 0.30, "name": "Ярость",      "dmg_mult": 1.8},
            {"threshold": 0.10, "name": "Бешенство",   "dmg_mult": 2.2},
        ],
        "passive_dmg":      [12, 22],
        "special_cooldown": 6,
        "special_spell":    "inferno",
        "special_desc":     "Инфернальный огонь — 80 урона всем, кто атакует!",
        "drop_table": {
            "top1":   {"xp": 2500, "gold": 1200, "title": "Победитель Хвосторогой"},
            "top3":   {"xp": 1800, "gold": 800},
            "top10":  {"xp": 1200, "gold": 500},
            "others": {"xp": 500,  "gold": 200},
        },
        "unique_drop_chance": 0.04,
        "unique_drop": "robe_auror",
    },
    "giant_troll": {
        "name":    "Гигантский тролль",
        "emoji":   "👹⚡",
        "hp":      35_000,
        "attack":  90,
        "defense": 60,
        "desc":    "Тролль размером с башню. Его дубина крушит всё вокруг.",
        "weakness":"magic",
        "phases": [
            {"threshold": 1.00, "name": "Злобный",   "dmg_mult": 1.0},
            {"threshold": 0.50, "name": "Бешеный",   "dmg_mult": 1.5},
            {"threshold": 0.20, "name": "Агония",    "dmg_mult": 2.0},
        ],
        "passive_dmg":      [6, 12],
        "special_cooldown": 3,
        "special_spell":    "club_smash",
        "special_desc":     "Удар дубиной — все игроки оглушены на 1 ход!",
        "drop_table": {
            "top1":   {"xp": 1500, "gold": 700},
            "top3":   {"xp": 1000, "gold": 450},
            "top10":  {"xp": 700,  "gold": 300},
            "others": {"xp": 250,  "gold": 100},
        },
        "unique_drop_chance": 0.06,
        "unique_drop": "wand_oak_dragon",
    },
    "dark_lord": {
        "name":    "Тёмный Лорд",
        "emoji":   "💀👑",
        "hp":      100_000,
        "attack":  120,
        "defense": 70,
        "desc":    "Сам Волдеморт во плоти. Тот-Кого-Нельзя-Называть. Величайший тёмный маг всех времён.",
        "weakness":"love",
        "phases": [
            {"threshold": 1.00, "name": "Тёмный лорд",    "dmg_mult": 1.0},
            {"threshold": 0.70, "name": "Гнев",           "dmg_mult": 1.3},
            {"threshold": 0.40, "name": "Крестраж",       "dmg_mult": 1.7},
            {"threshold": 0.15, "name": "Последний вздох","dmg_mult": 2.5},
        ],
        "passive_dmg":      [15, 30],
        "special_cooldown": 5,
        "special_spell":    "avada_kedavra",
        "special_desc":     "Авада Кедавра — случайный игрок получает 200 урона!",
        "drop_table": {
            "top1":   {"xp": 5000, "gold": 2500, "title": "Победитель Тёмного Лорда"},
            "top3":   {"xp": 3000, "gold": 1500, "title": "Герой магического мира"},
            "top10":  {"xp": 2000, "gold": 1000},
            "others": {"xp": 800,  "gold": 300},
        },
        "unique_drop_chance": 0.03,
        "unique_drop": "wand_elder",
    },
}

_active_sessions: dict[int, dict] = {}   # world_boss_db_id → session


def _get_phase(boss_data: dict, hp_ratio: float) -> dict:
    phases = boss_data.get("phases", [])
    active = phases[0]
    for phase in phases:
        if hp_ratio <= phase["threshold"]:
            active = phase
    return active


def _format_wb_panel(boss_data: dict, wb_row: dict, top: list, user_dmg: int = 0) -> str:
    hp     = wb_row["current_hp"]
    max_hp = wb_row["max_hp"]
    ratio  = hp / max_hp if max_hp else 0
    phase  = _get_phase(boss_data, ratio)
    bar    = format_hp_bar(hp, max_hp, 14)

    top_lines = []
    for i, row in enumerate(top[:5], 1):
        medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣"]
        top_lines.append(f"{medals[i-1]} {row['wizard_name']}: {row['damage']:,} урона")

    return (
        f"{boss_data['emoji']} *{boss_data['name']}*\n"
        f"⚠️ {phase['name']} (×{phase['dmg_mult']} урон)\n"
        f"❤️ `[{bar}]` {hp:,}/{max_hp:,}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        + ("\n".join(top_lines) if top_lines else "Нет атак пока")
        + (f"\n\n⚔️ Твой урон: {user_dmg:,}" if user_dmg else "")
    )


async def cmd_worldboss(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """/worldboss — атаковать активного мирового босса."""
    user_id = update.effective_user.id
    if not user_exists(user_id):
        await update.message.reply_text(t(user_id, "not_registered"))
        return

    wb = get_active_world_boss()
    if not wb:
        await update.message.reply_text(
            "🌍 *Мировых боссов сейчас нет*\n\n"
            "Они появляются в 12:00 и 20:00 UTC.\n"
            "Следи за объявлениями!",
            parse_mode="Markdown"
        )
        return

    if wb["current_hp"] <= 0:
        await update.message.reply_text("💀 Мировой босс уже повержен!")
        return

    used = get_daily_limit(user_id, "world_boss")
    if used >= DAILY_LIMITS["world_boss"]:
        await update.message.reply_text("⚔️ Ты уже атаковал мирового босса сегодня!")
        return

    boss_data = WORLD_BOSSES.get(wb["boss_id"])
    if not boss_data:
        await update.message.reply_text("❌ Данные босса не найдены.")
        return

    top      = get_world_boss_top(wb["id"])
    user_row = next((r for r in top if r.get("user_id") == user_id), None)
    user_dmg = user_row["damage"] if user_row else 0

    from database import get_user_spells
    spells = [r["spell_id"] for r in get_user_spells(user_id)][:6]
    from game.spells import spell_display_name, RARITY_EMOJI
    buttons = []
    for sid in spells:
        spell = SPELLS.get(sid)
        if not spell:
            continue
        rarity_e = RARITY_EMOJI.get(spell.get("rarity", "common"), "⚪")
        name     = spell_display_name(sid, "ru")
        dmg      = spell.get("damage", 0)
        buttons.append([InlineKeyboardButton(
            f"{rarity_e}{name} ⚔️{dmg}",
            callback_data=f"wb_attack:{wb['id']}:{sid}"
        )])

    markup = InlineKeyboardMarkup(buttons)
    panel  = _format_wb_panel(boss_data, wb, top, user_dmg)
    await update.message.reply_text(panel, parse_mode="Markdown", reply_markup=markup)


async def cb_wb_attack(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query    = update.callback_query
    user_id  = query.from_user.id
    parts    = query.data.split(":")
    wb_id    = int(parts[1])
    spell_id = parts[2]

    wb = get_active_world_boss()
    if not wb or wb["id"] != wb_id or wb["current_hp"] <= 0:
        await query.edit_message_text("💀 Мировой босс уже повержен!")
        return

    used = get_daily_limit(user_id, "world_boss")
    if used >= DAILY_LIMITS["world_boss"]:
        await query.answer("⚔️ Ты уже атаковал сегодня!", show_alert=True)
        return

    user      = get_user(user_id)
    boss_data = WORLD_BOSSES.get(wb["boss_id"])
    spell     = SPELLS.get(spell_id)
    if not spell or not boss_data:
        await query.edit_message_text("❌ Ошибка.")
        return

    # Рассчитываем урон
    hp_ratio  = wb["current_hp"] / wb["max_hp"]
    phase     = _get_phase(boss_data, hp_ratio)
    base_dmg  = spell.get("damage", 10)
    atk_mult  = 1 + (user["attack"] - 10) * 0.02
    luck_crit = 0.05 + user.get("luck", 5) * 0.005
    is_crit   = random.random() < luck_crit
    crit_mult = 1.5 if is_crit else 1.0
    dmg       = max(1, int(base_dmg * atk_mult * crit_mult))

    # Урон боссу
    record_world_boss_damage(wb_id, user_id, dmg)
    increment_daily(user_id, "world_boss")

    # Обновляем данные
    wb_updated = get_active_world_boss()
    top        = get_world_boss_top(wb_id)

    user_row   = next((r for r in top if r.get("wizard_name") == user["wizard_name"]), None)
    total_dmg  = user_row["damage"] if user_row else dmg

    # Пассивный урон босса игроку (в лог)
    passive    = random.randint(*boss_data["passive_dmg"])
    log_line   = (
        f"⚔️ {dmg} урона" + (" 💥КРИТ!" if is_crit else "")
        + f"\n🐉 Босс наносит {passive} урона в ответ"
    )

    crit_text = " 💥 КРИТ!" if is_crit else ""

    if wb_updated and wb_updated["current_hp"] <= 0:
        # Босс убит
        await query.edit_message_text(
            f"💀 *{boss_data['name']} повержен!*\n\n"
            f"Твой удар: {dmg}{crit_text}\n"
            f"Твой общий урон: {total_dmg:,}\n\n"
            f"🏆 Награды рассчитываются...",
            parse_mode="Markdown"
        )
        await _distribute_wb_rewards(wb_id, boss_data, ctx)
        return

    panel = _format_wb_panel(boss_data, wb_updated, top, total_dmg)
    panel += f"\n\n{log_line}"

    # Снова показываем кнопки для повторной атаки (если осталось)
    await query.edit_message_text(
        panel,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("🔄 Обновить", callback_data=f"wb_refresh:{wb_id}"),
        ]])
    )


async def cb_wb_refresh(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query   = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    wb_id   = int(query.data.split(":")[1])

    wb = get_active_world_boss()
    if not wb or wb["id"] != wb_id:
        await query.edit_message_text("💀 Мировой босс уже завершён.")
        return

    boss_data = WORLD_BOSSES.get(wb["boss_id"])
    top       = get_world_boss_top(wb_id)
    user      = get_user(user_id)
    user_row  = next((r for r in top if r.get("wizard_name") == user["wizard_name"]), None)
    user_dmg  = user_row["damage"] if user_row else 0

    panel = _format_wb_panel(boss_data, wb, top, user_dmg)
    await query.edit_message_text(
        panel,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("🔄 Обновить", callback_data=f"wb_refresh:{wb_id}"),
        ]])
    )


async def _distribute_wb_rewards(wb_id: int, boss_data: dict, ctx):
    """Раздать награды после победы над мировым боссом."""
    top     = get_world_boss_top(wb_id, limit=100)
    drop    = boss_data.get("drop_table", {})
    total   = len(top)

    with get_conn() as conn:
        execute(conn, "UPDATE world_bosses SET status = 'defeated', ended_at = NOW() WHERE id = %s", wb_id)
        execute(conn, "UPDATE user_stats SET world_boss_kills = world_boss_kills + 1 WHERE user_id IN (SELECT user_id FROM world_boss_damage WHERE world_boss_id = %s)", wb_id)

    for i, row in enumerate(top):
        uid = None
        with get_conn() as conn:
            u = fetchrow(conn, "SELECT user_id, house FROM users WHERE wizard_name = %s", row["wizard_name"])
        if not u:
            continue
        uid = u["user_id"]

        if i == 0:
            reward = drop.get("top1", {})
        elif i < 3:
            reward = drop.get("top3", {})
        elif i < 10:
            reward = drop.get("top10", {})
        else:
            reward = drop.get("others", {})

        xp   = reward.get("xp", 200)
        gold = reward.get("gold", 80)
        title = reward.get("title")

        add_xp(uid, xp)
        add_gold(uid, gold)
        add_house_points(uid, u["house"], HOUSE_POINTS_REWARDS["world_boss"], "world_boss")

        if title:
            with get_conn() as conn:
                execute(conn, "INSERT INTO user_titles (user_id, title_id) VALUES (%s, %s) ON CONFLICT DO NOTHING", uid, title)

        # Уникальный дроп для топ-1
        unique_text = ""
        if i == 0 and random.random() < boss_data.get("unique_drop_chance", 0.05):
            udrop = boss_data.get("unique_drop")
            if udrop:
                with get_conn() as conn:
                    execute(conn, "INSERT INTO inventory (user_id, item_id, quantity) VALUES (%s, %s, 1) ON CONFLICT (user_id, item_id) DO UPDATE SET quantity = inventory.quantity + 1", uid, udrop)
                unique_text = f"\n🌟 *Уникальный дроп:* `{udrop}`!"

        place_text = f"#{i+1}" if i >= 3 else ["🥇", "🥈", "🥉"][i]
        try:
            await ctx.bot.send_message(
                uid,
                f"🌍 *{boss_data['name']} повержен!*\n\n"
                f"Твоё место: {place_text} ({row['damage']:,} урона)\n"
                f"+{xp} XP | +{gold} 💰"
                + (f"\n🎭 Титул: *{title}*" if title else "")
                + unique_text,
                parse_mode="Markdown"
            )
        except Exception:
            pass


async def spawn_world_boss(boss_id: str, ctx) -> bool:
    """Заспawnить мирового босса. Вызывается планировщиком или /admin_wb."""
    boss_data = WORLD_BOSSES.get(boss_id)
    if not boss_data:
        return False

    # Проверить — нет ли уже активного
    wb = get_active_world_boss()
    if wb:
        return False

    with get_conn() as conn:
        execute(conn, """
            INSERT INTO world_bosses (boss_id, max_hp, current_hp, status)
            VALUES (%s, %s, %s, 'active')
        """, boss_id, boss_data["hp"], boss_data["hp"])
        wb_row = fetchrow(conn, "SELECT id FROM world_bosses ORDER BY id DESC LIMIT 1")
    wb_id = wb_row["id"]

    # Уведомить всех игроков
    with get_conn() as conn:
        users = fetchall(conn, "SELECT user_id FROM users WHERE is_banned = FALSE")

    text = (
        f"⚠️ *МИРОВОЙ БОСС ПОЯВИЛСЯ!*\n\n"
        f"{boss_data['emoji']} *{boss_data['name']}*\n"
        f"❤️ {boss_data['hp']:,} HP\n\n"
        f"_{boss_data['desc']}_\n\n"
        f"Слабость: {boss_data.get('weakness', 'нет')}\n\n"
        f"Используй /worldboss чтобы атаковать!\n"
        f"Босс исчезнет через {WORLD_BOSS_DURATION_MINUTES} минут."
    )
    for row in users[:200]:
        try:
            await ctx.bot.send_message(row["user_id"], text, parse_mode="Markdown")
        except Exception:
            pass

    # Авто-закрытие через N минут
    import asyncio
    async def _auto_expire():
        await asyncio.sleep(WORLD_BOSS_DURATION_MINUTES * 60)
        wb_check = get_active_world_boss()
        if wb_check and wb_check["id"] == wb_id and wb_check["current_hp"] > 0:
            with get_conn() as conn:
                execute(conn, "UPDATE world_bosses SET status = 'expired', ended_at = NOW() WHERE id = %s", wb_id)
            for row in users[:100]:
                try:
                    await ctx.bot.send_message(
                        row["user_id"],
                        f"⏰ *{boss_data['name']} скрылся!*\n\nВремя вышло. Следи за появлением нового!",
                        parse_mode="Markdown"
                    )
                except Exception:
                    pass
    asyncio.get_event_loop().create_task(_auto_expire())
    return True


def register_world_boss_handlers(app):
    app.add_handler(CommandHandler("worldboss", cmd_worldboss))
    app.add_handler(CallbackQueryHandler(cb_wb_attack,  pattern=r"^wb_attack:"))
    app.add_handler(CallbackQueryHandler(cb_wb_refresh, pattern=r"^wb_refresh:"))

