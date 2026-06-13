"""
Профиль игрока — «паспорт волшебника».
Прогресс-бары, ранг по уровню, снаряжение, ID, быстрые действия.
"""
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler
from database import get_user, get_user_stats, get_spells_count, user_exists, get_conn, fetchall
from utils.i18n import t
from utils.helpers import (
    xp_needed_for_level, house_emoji, progress_bar, hp_bar,
    get_rank, next_rank,
)
from game.items import ITEMS, item_display_name, stat_label, SLOT_EMOJI

HOUSE_NAMES_RU = {
    "gryffindor": "Гриффиндор", "slytherin": "Слизерин",
    "ravenclaw": "Когтевран",  "hufflepuff": "Пуффендуй",
}

def _equipment_summary(user_id: int) -> tuple[str, dict]:
    with get_conn() as conn:
        rows = fetchall(conn, "SELECT slot, item_id, bonus FROM equipped_items WHERE user_id=%s ORDER BY slot", user_id)
    bonuses = {"max_hp":0,"max_mana":0,"attack":0,"defense":0,"speed":0,"luck":0}
    if not rows:
        return "  _Ничего не надето_", bonuses
    lines = []
    for row in rows:
        item = ITEMS.get(row["item_id"], {})
        stat = item.get("stat")
        bonus = int(row.get("bonus") or 0)
        if stat in bonuses:
            bonuses[stat] += bonus
        name = item_display_name(item, "ru") if item else row["item_id"]
        emoji = item.get("emoji", SLOT_EMOJI.get(row["slot"], "🔲"))
        stat_part = f"+{bonus} {stat_label(stat, 'ru')}" if stat and bonus else ""
        lines.append(f"  {emoji} {name}  {stat_part}".rstrip())
    return "\n".join(lines), bonuses

def _quick_actions() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("⚔️ В бой", callback_data="pf_quick:dungeon"),
         InlineKeyboardButton("🏪 Магазин", callback_data="pf_quick:shop")],
        [InlineKeyboardButton("🎒 Инвентарь", callback_data="pf_quick:inventory"),
         InlineKeyboardButton("🎁 Бонус дня", callback_data="pf_quick:daily")],
    ])

def _build_profile_text(user_id: int) -> str:
    user      = get_user(user_id)
    stats     = get_user_stats(user_id)
    spells_count = get_spells_count(user_id)
    xp_needed = xp_needed_for_level(user["level"])
    house     = user["house"]
    equipment_text, eq = _equipment_summary(user_id)

    rank   = get_rank(user["level"])
    nxt    = next_rank(user["level"])
    rank_line = f"🎖️ Ранг: *{rank}*"
    if nxt:
        rank_line += f"\n   До «{nxt[0]}»: ур. {nxt[1]}"

    # Бары
    hp_b   = hp_bar(user["hp"], user["max_hp"])
    mana_b = progress_bar(user["mana"], user["max_mana"])
    xp_b   = progress_bar(user["xp"], xp_needed)

    pvp_total = stats["pvp_total"] if stats else 0
    pvp_wins  = stats["pvp_wins"]  if stats else 0
    winrate   = f"{int(pvp_wins/pvp_total*100)}%" if pvp_total else "—"

    return (
        f"╔═══════════════════╗\n"
        f"  {house_emoji(house)} *{user['wizard_name']}*\n"
        f"  {HOUSE_NAMES_RU.get(house, house)}  •  Уровень {user['level']}\n"
        f"╚═══════════════════╝\n"
        f"{rank_line}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"❤️ HP    {hp_b}  {user['hp']}/{user['max_hp']}\n"
        f"💧 Мана  {mana_b}  {user['mana']}/{user['max_mana']}\n"
        f"✨ Опыт  {xp_b}  {user['xp']}/{xp_needed}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"⚔️ Урон: {user['attack']}   🛡️ Защита: {user['defense']}\n"
        f"⚡ Скорость: {user['speed']}   🍀 Удача: {user['luck']}\n"
        f"💰 Золото: {user['gold']:,}\n"
        f"📜 Заклинаний: {spells_count}\n"
        f"⚔️ Дуэли: {pvp_wins}/{pvp_total} побед ({winrate})\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🎽 *Снаряжение*\n{equipment_text}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🆔 Твой ID: `{user_id}`"
    )

async def show_profile(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not user_exists(user_id):
        await update.message.reply_text(t(user_id, "not_registered"))
        return
    text = _build_profile_text(user_id)
    # Показываем герб факультета игрока если загружен, иначе общий баннер профиля
    try:
        from handlers.images import send_with_image, HOUSE_IMAGE_MAP, get_image
        user = get_user(user_id)
        house_slot = HOUSE_IMAGE_MAP.get(user.get("house"))
        slot = house_slot if (house_slot and get_image(house_slot)) else "profile"
        await send_with_image(update.get_bot(), update.effective_chat.id, slot,
                              text, reply_markup=_quick_actions())
        return
    except Exception:
        pass
    await update.message.reply_text(text, parse_mode="Markdown", reply_markup=_quick_actions())

async def cb_pf_quick(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query  = update.callback_query
    await query.answer()
    action = query.data.split(":")[1]

    # Обёртка для вызова cmd_ функций из callback
    class _Wrap:
        def __init__(self, q): self._q = q
        @property
        def effective_user(self): return self._q.from_user
        @property
        def effective_chat(self): return self._q.message.chat
        @property
        def message(self): return self._q.message
        @property
        def callback_query(self): return None
        def get_bot(self): return self._q.message.get_bot()

    wrap = _Wrap(query)
    try:
        if action == "dungeon":
            from handlers.pve import cmd_dungeon
            await cmd_dungeon(wrap, ctx)
        elif action == "shop":
            from handlers.shop import cmd_shop
            await cmd_shop(wrap, ctx)
        elif action == "inventory":
            from handlers.inventory import cmd_inventory
            await cmd_inventory(wrap, ctx)
        elif action == "daily":
            from handlers.daily_bonus import cmd_daily
            await cmd_daily(wrap, ctx)
    except Exception as e:
        await query.message.reply_text(f"⚠️ Не удалось открыть. Попробуй из меню.")

def register_profile_handlers(app):
    app.add_handler(CommandHandler("profile", show_profile))
    app.add_handler(CallbackQueryHandler(cb_pf_quick, pattern=r"^pf_quick:"))
