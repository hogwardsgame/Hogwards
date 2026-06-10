from telegram import Update
from telegram.ext import ContextTypes, CommandHandler, MessageHandler, filters
from database import get_user, get_user_stats, get_spells_count, user_exists, get_conn, fetchall
from utils.i18n import t
from utils.helpers import xp_needed_for_level, house_emoji
from game.items import ITEMS, item_display_name, stat_label, SLOT_EMOJI


BASE_STATS = {
    "max_hp": 100,
    "max_mana": 50,
    "attack": 10,
    "defense": 5,
    "speed": 10,
    "luck": 5,
}


def _equipment_summary(user_id: int) -> tuple[str, dict]:
    with get_conn() as conn:
        rows = fetchall(conn, "SELECT slot, item_id, bonus FROM equipped_items WHERE user_id=%s ORDER BY slot", user_id)
    if not rows:
        return "—", {k: 0 for k in BASE_STATS}

    bonuses = {k: 0 for k in BASE_STATS}
    lines = []
    for row in rows:
        item = ITEMS.get(row["item_id"], {})
        stat = item.get("stat")
        bonus = int(row.get("bonus") or 0)
        if stat in bonuses:
            bonuses[stat] += bonus
        stat_part = f"+{bonus} к {stat_label(stat, 'ru')}" if stat and bonus else "без бонуса"
        lines.append(f"{SLOT_EMOJI.get(row['slot'], '🔲')} {item_display_name(item, 'ru')} — {stat_part}")
    return "\n".join(lines), bonuses


def _combat_overview(user: dict, equipment_bonuses: dict) -> str:
    base_attack = user["attack"] - equipment_bonuses.get("attack", 0)
    base_defense = user["defense"] - equipment_bonuses.get("defense", 0)
    base_speed = user["speed"] - equipment_bonuses.get("speed", 0)
    base_luck = user["luck"] - equipment_bonuses.get("luck", 0)
    base_mana = user["max_mana"] - equipment_bonuses.get("max_mana", 0)
    return (
        f"\n━━━━━━━━━━━━━━━━━━━━\n"
        f"📊 *Характеристики персонажа*\n"
        f"⚔️ Урон: {user['attack']}  _(база {base_attack} + снаряжение {equipment_bonuses.get('attack', 0)})_\n"
        f"🛡️ Защита: {user['defense']}  _(база {base_defense} + снаряжение {equipment_bonuses.get('defense', 0)})_\n"
        f"⚡ Скорость: {user['speed']}  _(база {base_speed} + снаряжение {equipment_bonuses.get('speed', 0)})_\n"
        f"🍀 Удача: {user['luck']}  _(база {base_luck} + снаряжение {equipment_bonuses.get('luck', 0)})_\n"
        f"💧 Максимальная мана: {user['max_mana']}  _(база {base_mana} + снаряжение {equipment_bonuses.get('max_mana', 0)})_"
    )


async def show_profile(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not user_exists(user_id):
        await update.message.reply_text(t(user_id, "not_registered"))
        return

    user = get_user(user_id)
    stats = get_user_stats(user_id)
    spells_count = get_spells_count(user_id)
    xp_needed = xp_needed_for_level(user["level"])
    house = user["house"]
    equipment_text, equipment_bonuses = _equipment_summary(user_id)

    header = t(user_id, "profile_header", wizard_name=user["wizard_name"])
    body = t(
        user_id, "profile_body",
        house_emoji=house_emoji(house),
        house=t(user_id, f"house_{house}"),
        level=user["level"],
        hp=user["hp"], max_hp=user["max_hp"],
        mana=user["mana"], max_mana=user["max_mana"],
        attack=user["attack"], defense=user["defense"],
        speed=user["speed"], luck=user["luck"],
        xp=user["xp"], xp_needed=xp_needed,
        gold=user["gold"],
        spells_count=spells_count,
        pvp_total=stats["pvp_total"] if stats else 0,
        pvp_wins=stats["pvp_wins"] if stats else 0,
    )
    combat = _combat_overview(user, equipment_bonuses)
    equipment = f"\n━━━━━━━━━━━━━━━━━━━━\n🎒 *Надетое снаряжение*\n{equipment_text}"
    await update.message.reply_text(f"{header}\n{body}{combat}{equipment}", parse_mode="Markdown")



def register_profile_handlers(app):
    app.add_handler(CommandHandler("profile", show_profile))
    