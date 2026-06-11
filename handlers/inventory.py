"""
Inventory handler — инвентарь игрока.
Показывает предметы с полными названиями, редкостью, бонусами.
Позволяет надевать снаряжение и использовать расходники.
"""
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler
from database import get_user, user_exists, get_conn, execute, fetchrow, fetchall
from utils.i18n import t
from game.items import (
    ITEMS, item_display_name, item_description,
    item_bonus_text, item_stat_value, stat_label,
    RARITY_NAMES, RARITY_NAMES_RU, SLOT_EMOJI,
)

logger = logging.getLogger(__name__)

PER_PAGE = 6   # предметов на страницу

TYPE_LABEL = {
    "equipment":  "⚙️ Снаряжение",
    "consumable": "🧪 Расходник",
    "ingredient": "🌿 Ингредиент",
    "key":        "🗝️ Ключевой",
    "misc":       "📦 Прочее",
}


# ── Вспомогательные функции ───────────────────────────────────────────────────

def _get_inventory(user_id: int) -> list:
    with get_conn() as conn:
        return fetchall(
            conn,
            "SELECT * FROM inventory WHERE user_id = %s ORDER BY acquired_at DESC",
            user_id,
        )


def _get_equipped(user_id: int) -> dict:
    """Возвращает {slot: {item_id, bonus}}."""
    with get_conn() as conn:
        rows = fetchall(
            conn,
            "SELECT slot, item_id, bonus FROM equipped_items WHERE user_id = %s",
            user_id,
        )
    return {r["slot"]: {"item_id": r["item_id"], "bonus": r.get("bonus") or 0} for r in rows}


def _safe_item(item_id: str) -> dict:
    """Возвращает данные предмета или заглушку если не найден."""
    item = ITEMS.get(item_id)
    if item:
        return item
    # Заглушка — предмет из нового контента (чёрный рынок, крестражи и т.д.)
    return {
        "id":     item_id,
        "name":   item_id.replace("_", " ").title(),
        "rarity": "rare",
        "type":   "misc",
        "desc":   "Особый предмет.",
    }


def _item_button_label(row: dict) -> str:
    """Красивый текст кнопки в списке инвентаря."""
    item   = _safe_item(row["item_id"])
    rarity = item.get("rarity", "common")
    re     = RARITY_NAMES.get(rarity, "⬜")
    name   = item_display_name(item, "ru")
    itype  = item.get("type", "misc")
    type_e = {"equipment": "⚙️", "consumable": "🧪", "ingredient": "🌿", "key": "🗝️"}.get(itype, "📦")
    qty    = row.get("quantity", 1)
    qty_s  = f" ×{qty}" if qty > 1 else ""
    return f"{re} {type_e} {name}{qty_s}"


def _equipped_section(equipped: dict) -> str:
    """Секция «Надето» для главного экрана инвентаря."""
    if not equipped:
        return "—"
    lines = []
    for slot, eq_data in equipped.items():
        item   = _safe_item(eq_data["item_id"])
        name   = item_display_name(item, "ru")
        bonus  = eq_data.get("bonus", 0)
        stat   = item.get("stat", "")
        slot_e = SLOT_EMOJI.get(slot, "🔲")
        bonus_s = f" (+{bonus} {stat_label(stat, 'ru')})" if stat and bonus else ""
        lines.append(f"{slot_e} {name}{bonus_s}")
    return "\n".join(lines)


def _inventory_keyboard(inv_rows: list, page: int = 0) -> InlineKeyboardMarkup:
    start  = page * PER_PAGE
    chunk  = inv_rows[start : start + PER_PAGE]
    buttons = []
    for row in chunk:
        buttons.append([InlineKeyboardButton(
            _item_button_label(row),
            callback_data=f"inv_item:{row['id']}",
        )])
    # Пагинация
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("⬅️ Назад", callback_data=f"inv_page:{page-1}"))
    if start + PER_PAGE < len(inv_rows):
        nav.append(InlineKeyboardButton("Вперёд ➡️", callback_data=f"inv_page:{page+1}"))
    if nav:
        buttons.append(nav)
    return InlineKeyboardMarkup(buttons)


def _item_action_keyboard(inv_id: int, item: dict, is_equipped: bool) -> InlineKeyboardMarkup:
    buttons = []
    itype   = item.get("type")
    if itype == "equipment":
        label  = "🔓 Снять" if is_equipped else "⚙️ Надеть"
        action = "inv_unequip" if is_equipped else "inv_equip"
        buttons.append([InlineKeyboardButton(label, callback_data=f"{action}:{inv_id}")])
    elif itype == "consumable":
        buttons.append([InlineKeyboardButton("🧪 Использовать", callback_data=f"inv_use:{inv_id}")])
    buttons.append([InlineKeyboardButton("◀️ К инвентарю", callback_data="inv_back")])
    return InlineKeyboardMarkup(buttons)


# ── Главный экран инвентаря ───────────────────────────────────────────────────

async def cmd_inventory(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not user_exists(user_id):
        await update.message.reply_text(t(user_id, "not_registered"))
        return

    inv      = _get_inventory(user_id)
    equipped = _get_equipped(user_id)
    ctx.user_data["inv"]      = inv
    ctx.user_data["equipped"] = equipped

    if not inv:
        await update.message.reply_text(
            "🎒 *Инвентарь пуст*\n\n"
            "Предметы можно купить в 🏪 Магазине или найти в приключениях.",
            parse_mode="Markdown",
        )
        return

    eq_text = _equipped_section(equipped)
    user    = get_user(user_id)

    # Считаем предметы по типу
    counts = {}
    for row in inv:
        itype = _safe_item(row["item_id"]).get("type", "misc")
        counts[itype] = counts.get(itype, 0) + 1
    counts_str = "  ".join(
        f"{TYPE_LABEL.get(k, k)}: {v}" for k, v in counts.items()
    )

    text = (
        f"🎒 *Инвентарь*\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"⚔️ *Надето:*\n{eq_text}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"📦 Всего предметов: {len(inv)}\n"
        f"{counts_str}\n\n"
        f"Нажми на предмет для деталей:"
    )
    await update.message.reply_text(
        text, parse_mode="Markdown",
        reply_markup=_inventory_keyboard(inv),
    )


# ── Пагинация ────────────────────────────────────────────────────────────────

async def cb_inv_page(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query   = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    page    = int(query.data.split(":")[1])
    inv     = ctx.user_data.get("inv") or _get_inventory(user_id)
    ctx.user_data["inv"] = inv
    await query.edit_message_reply_markup(reply_markup=_inventory_keyboard(inv, page))


# ── Карточка предмета ────────────────────────────────────────────────────────

async def cb_inv_item(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query   = update.callback_query
    user_id = query.from_user.id
    inv_id  = int(query.data.split(":")[1])

    with get_conn() as conn:
        row = fetchrow(conn, "SELECT * FROM inventory WHERE id=%s AND user_id=%s", inv_id, user_id)
    if not row:
        await query.answer("❌ Предмет не найден.", show_alert=True)
        return

    item   = _safe_item(row["item_id"])
    rarity = item.get("rarity", "common")
    re     = RARITY_NAMES.get(rarity, "⬜")
    rru    = RARITY_NAMES_RU.get(rarity, rarity)
    name   = item_display_name(item, "ru")
    desc   = item_description(item, "ru") if callable(item_description) else item.get("desc", "")
    bonus  = item_bonus_text(item, "ru")
    itype  = TYPE_LABEL.get(item.get("type", "misc"), "📦 Прочее")
    slot   = item.get("slot", "")
    slot_s = f"\n🔲 Слот: {SLOT_EMOJI.get(slot,'')} {slot}" if slot else ""
    qty    = row.get("quantity", 1)
    qty_s  = f"\n📦 Количество: {qty}" if qty > 1 else ""

    # Проверяем надет ли
    equipped  = _get_equipped(user_id)
    eq_data   = equipped.get(slot) if slot else None
    is_equipped = bool(eq_data and eq_data.get("item_id") == row["item_id"])
    eq_badge  = "\n✅ *Сейчас надето*" if is_equipped else ""

    bonus_block = f"\n\n📈 *Бонус:* {bonus}" if bonus else ""

    text = (
        f"{re} *{name}*\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"⭐ Редкость: {rru}\n"
        f"🏷️ Тип: {itype}"
        f"{slot_s}{qty_s}{eq_badge}\n\n"
        f"📜 {desc}"
        f"{bonus_block}"
    )
    await query.edit_message_text(
        text, parse_mode="Markdown",
        reply_markup=_item_action_keyboard(inv_id, item, is_equipped),
    )


# ── Надеть снаряжение ────────────────────────────────────────────────────────

async def cb_inv_equip(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query   = update.callback_query
    user_id = query.from_user.id
    inv_id  = int(query.data.split(":")[1])

    with get_conn() as conn:
        row = fetchrow(conn, "SELECT * FROM inventory WHERE id=%s AND user_id=%s", inv_id, user_id)
    if not row:
        await query.answer("❌", show_alert=True)
        return

    item = _safe_item(row["item_id"])
    if item.get("type") != "equipment":
        await query.answer("❌ Нельзя надеть.", show_alert=True)
        return

    slot  = item["slot"]
    stat  = item.get("stat", "")
    bonus = item_stat_value(item)

    with get_conn() as conn:
        # Снять старый предмет в этом слоте
        old = fetchrow(conn, "SELECT item_id, bonus FROM equipped_items WHERE user_id=%s AND slot=%s", user_id, slot)
        if old:
            old_item  = _safe_item(old["item_id"])
            old_stat  = old_item.get("stat", "")
            old_bonus = old.get("bonus") or 0
            if old_stat and old_bonus:
                execute(conn, f"UPDATE users SET {old_stat} = {old_stat} - %s WHERE user_id=%s", old_bonus, user_id)

        execute(conn, """
            INSERT INTO equipped_items (user_id, slot, item_id, bonus)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (user_id, slot) DO UPDATE
                SET item_id = EXCLUDED.item_id, bonus = EXCLUDED.bonus
        """, user_id, slot, row["item_id"], bonus)

        if stat and bonus:
            execute(conn, f"UPDATE users SET {stat} = {stat} + %s WHERE user_id=%s", bonus, user_id)

    name = item_display_name(item, "ru")
    bonus_s = f"+{bonus} к {stat_label(stat, 'ru')}" if stat and bonus else ""
    await query.edit_message_text(
        f"✅ *Надето:* {name}\n"
        f"{SLOT_EMOJI.get(slot,'')} Слот: {slot}\n"
        f"📈 {bonus_s}\n\n"
        f"Характеристики обновлены!",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("◀️ К инвентарю", callback_data="inv_back")
        ]])
    )


# ── Снять снаряжение ─────────────────────────────────────────────────────────

async def cb_inv_unequip(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query   = update.callback_query
    user_id = query.from_user.id
    inv_id  = int(query.data.split(":")[1])

    with get_conn() as conn:
        row = fetchrow(conn, "SELECT * FROM inventory WHERE id=%s AND user_id=%s", inv_id, user_id)
    if not row:
        await query.answer("❌", show_alert=True)
        return

    item = _safe_item(row["item_id"])
    slot = item.get("slot", "")

    with get_conn() as conn:
        equipped_row = fetchrow(conn, "SELECT item_id, bonus FROM equipped_items WHERE user_id=%s AND slot=%s", user_id, slot)
        if equipped_row:
            eq_item  = _safe_item(equipped_row["item_id"])
            eq_stat  = eq_item.get("stat", "")
            eq_bonus = equipped_row.get("bonus") or 0
            if eq_stat and eq_bonus:
                execute(conn, f"UPDATE users SET {eq_stat} = {eq_stat} - %s WHERE user_id=%s", eq_bonus, user_id)
        execute(conn, "DELETE FROM equipped_items WHERE user_id=%s AND slot=%s", user_id, slot)

    name = item_display_name(item, "ru")
    await query.edit_message_text(
        f"🔓 *Снято:* {name}\n\nХарактеристики обновлены.",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("◀️ К инвентарю", callback_data="inv_back")
        ]])
    )


# ── Использовать расходник ────────────────────────────────────────────────────

async def cb_inv_use(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query   = update.callback_query
    user_id = query.from_user.id
    inv_id  = int(query.data.split(":")[1])

    with get_conn() as conn:
        row = fetchrow(conn, "SELECT * FROM inventory WHERE id=%s AND user_id=%s", inv_id, user_id)
    if not row:
        await query.answer("❌", show_alert=True)
        return

    item = _safe_item(row["item_id"])
    if item.get("type") != "consumable":
        await query.answer("❌ Нельзя использовать.", show_alert=True)
        return

    effect = item.get("effect")
    value  = item.get("value", 0)

    if effect == "hp":
        with get_conn() as conn:
            execute(conn, "UPDATE users SET hp = LEAST(hp + %s, max_hp) WHERE user_id=%s", int(value), user_id)
        msg = f"💚 +{int(value)} ХП восстановлено"
    elif effect == "hp_full":
        with get_conn() as conn:
            execute(conn, "UPDATE users SET hp = max_hp WHERE user_id=%s", user_id)
        msg = "💚 Здоровье полностью восстановлено!"
    elif effect == "mana":
        with get_conn() as conn:
            execute(conn, "UPDATE users SET mana = LEAST(mana + %s, max_mana) WHERE user_id=%s", int(value), user_id)
        msg = f"💧 +{int(value)} маны восстановлено"
    elif effect == "mana_full":
        with get_conn() as conn:
            execute(conn, "UPDATE users SET mana = max_mana WHERE user_id=%s", user_id)
        msg = "💧 Мана полностью восстановлена!"
    elif effect == "xp":
        from database import add_xp
        add_xp(user_id, int(value))
        msg = f"✨ +{int(value)} опыта получено"
    elif effect == "gold":
        from database import add_gold
        add_gold(user_id, int(value))
        msg = f"💰 +{int(value)} золота получено"
    else:
        msg = f"✨ Эффект применён: {effect or 'особый'}"

    # Списать предмет
    with get_conn() as conn:
        qty = row.get("quantity", 1)
        if qty <= 1:
            execute(conn, "DELETE FROM inventory WHERE id=%s", inv_id)
        else:
            execute(conn, "UPDATE inventory SET quantity = quantity - 1 WHERE id=%s", inv_id)

    name = item_display_name(item, "ru")
    await query.edit_message_text(
        f"✅ *{name}* использован\n\n{msg}",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("◀️ К инвентарю", callback_data="inv_back")
        ]])
    )


# ── Назад к списку ────────────────────────────────────────────────────────────

async def cb_inv_back(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query   = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    inv     = ctx.user_data.get("inv") or _get_inventory(user_id)
    ctx.user_data["inv"] = inv
    equipped = _get_equipped(user_id)
    eq_text  = _equipped_section(equipped)
    user     = get_user(user_id)

    counts = {}
    for row in inv:
        itype = _safe_item(row["item_id"]).get("type", "misc")
        counts[itype] = counts.get(itype, 0) + 1
    counts_str = "  ".join(f"{TYPE_LABEL.get(k,k)}: {v}" for k, v in counts.items())

    text = (
        f"🎒 *Инвентарь*\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"⚔️ *Надето:*\n{eq_text}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"📦 Всего предметов: {len(inv)}\n"
        f"{counts_str}\n\n"
        f"Нажми на предмет для деталей:"
    )
    await query.edit_message_text(
        text, parse_mode="Markdown",
        reply_markup=_inventory_keyboard(inv),
    )


def register_inventory_handlers(app):
    app.add_handler(CommandHandler("inventory", cmd_inventory))
    app.add_handler(CallbackQueryHandler(cb_inv_page,    pattern=r"^inv_page:"))
    app.add_handler(CallbackQueryHandler(cb_inv_item,    pattern=r"^inv_item:"))
    app.add_handler(CallbackQueryHandler(cb_inv_equip,   pattern=r"^inv_equip:"))
    app.add_handler(CallbackQueryHandler(cb_inv_unequip, pattern=r"^inv_unequip:"))
    app.add_handler(CallbackQueryHandler(cb_inv_use,     pattern=r"^inv_use:"))
    app.add_handler(CallbackQueryHandler(cb_inv_back,    pattern=r"^inv_back"))
