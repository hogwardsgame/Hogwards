"""
Inventory handler — TZ section 10.
Shows items, allows equipping equipment and using consumables.
"""
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler, MessageHandler, filters
from database import get_user, user_exists, get_conn, execute, fetchrow, fetchall
from utils.i18n import t
from game.items import ITEMS, item_display_name, RARITY_NAMES, RARITY_NAMES_RU, EQUIPMENT_SLOTS, SLOT_EMOJI

logger = logging.getLogger(__name__)


def _get_inventory(user_id: int) -> list:
    with get_conn() as conn:
        return fetchall(conn, "SELECT * FROM inventory WHERE user_id = %s ORDER BY acquired_at DESC", user_id)


def _get_equipped(user_id: int) -> dict:
    with get_conn() as conn:
        rows = fetchall(conn, "SELECT slot, item_id FROM equipped_items WHERE user_id = %s", user_id)
        return {r["slot"]: r["item_id"] for r in rows}


def _inventory_keyboard(inv_rows: list, page: int = 0) -> InlineKeyboardMarkup:
    per_page = 8
    start    = page * per_page
    chunk    = inv_rows[start:start + per_page]
    buttons  = []
    for row in chunk:
        item = ITEMS.get(row["item_id"])
        if not item:
            continue
        rarity_emoji = RARITY_NAMES.get(item.get("rarity", "common"), "⬜")
        name = item_display_name(item, "ru")
        qty_tag = f" ×{row['quantity']}" if row.get("quantity", 1) > 1 else ""
        buttons.append([InlineKeyboardButton(
            f"{rarity_emoji} {name}{qty_tag}",
            callback_data=f"inv_item:{row['id']}"
        )])
    # Pagination
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("⬅️", callback_data=f"inv_page:{page-1}"))
    if start + per_page < len(inv_rows):
        nav.append(InlineKeyboardButton("➡️", callback_data=f"inv_page:{page+1}"))
    if nav:
        buttons.append(nav)
    return InlineKeyboardMarkup(buttons)


def _item_action_keyboard(inv_id: int, item: dict, is_equipped: bool) -> InlineKeyboardMarkup:
    buttons = []
    itype = item.get("type")
    if itype == "equipment":
        label = "🔓 Снять" if is_equipped else "⚙️ Надеть"
        action = "inv_unequip" if is_equipped else "inv_equip"
        buttons.append([InlineKeyboardButton(label, callback_data=f"{action}:{inv_id}")])
    elif itype == "consumable":
        buttons.append([InlineKeyboardButton("🧪 Использовать", callback_data=f"inv_use:{inv_id}")])
    buttons.append([InlineKeyboardButton("◀️ Назад", callback_data="inv_back")])
    return InlineKeyboardMarkup(buttons)


async def cmd_inventory(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not user_exists(user_id):
        await update.message.reply_text(t(user_id, "not_registered"))
        return

    inv  = _get_inventory(user_id)
    equipped = _get_equipped(user_id)
    ctx.user_data["inv"] = inv
    ctx.user_data["equipped"] = equipped

    if not inv:
        await update.message.reply_text(t(user_id, "inventory_empty"))
        return

    equipped_text = "\n".join(
        f"{SLOT_EMOJI.get(slot,'🔲')} {item_display_name(ITEMS.get(iid, {'id': iid, 'name': iid}), 'ru')}"
        for slot, iid in equipped.items()
    ) or "—"

    text = (
        f"🎒 *Инвентарь*\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"*Надето:*\n{equipped_text}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"*Предметы ({len(inv)}):*"
    )
    markup = _inventory_keyboard(inv)
    await update.message.reply_text(text, parse_mode="Markdown", reply_markup=markup)


async def cb_inv_page(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query   = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    page    = int(query.data.split(":")[1])
    inv     = ctx.user_data.get("inv") or _get_inventory(user_id)
    ctx.user_data["inv"] = inv
    markup = _inventory_keyboard(inv, page)
    await query.edit_message_reply_markup(reply_markup=markup)


async def cb_inv_item(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query    = update.callback_query
    await query.answer()
    user_id  = query.from_user.id
    inv_id   = int(query.data.split(":")[1])

    with get_conn() as conn:
        row = fetchrow(conn, "SELECT * FROM inventory WHERE id=%s AND user_id=%s", inv_id, user_id)
    if not row:
        await query.answer("❌ Предмет не найден.", show_alert=True)
        return

    item = ITEMS.get(row["item_id"])
    if not item:
        await query.answer("❌ Данные предмета отсутствуют.", show_alert=True)
        return

    equipped = _get_equipped(user_id)
    slot     = item.get("slot")
    is_equipped = slot and equipped.get(slot) == row["item_id"]

    rarity_emoji = RARITY_NAMES.get(item.get("rarity", "common"), "⬜")
    name = item_display_name(item, "ru")
    bonus_text = ""
    if item.get("type") == "equipment":
        stat  = item.get("stat", "")
        bonus = row.get("quantity", 1)  # reuse quantity field for bonus? stored separately
        # Try reading bonus from item definition
        b_min = item.get("stat_min", 0)
        b_max = item.get("stat_max", 0)
        bonus_text = f"\n+{b_min}–{b_max} к `{stat}`"

    desc = item.get("desc_ru") or "Описание пока не добавлено."
    rarity_text = RARITY_NAMES_RU.get(item.get("rarity", "common"), item.get("rarity", "?"))
    qty_text = f"\nКоличество: {row.get('quantity', 1)}" if row.get("quantity", 1) > 1 else ""
    text = f"{rarity_emoji} *{name}*\nРедкость: {rarity_text}{qty_text}\n\n📜 {desc}{bonus_text}"
    markup = _item_action_keyboard(inv_id, item, is_equipped)
    await query.edit_message_text(text, parse_mode="Markdown", reply_markup=markup)


async def cb_inv_equip(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query   = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    inv_id  = int(query.data.split(":")[1])

    with get_conn() as conn:
        row = fetchrow(conn, "SELECT * FROM inventory WHERE id=%s AND user_id=%s", inv_id, user_id)
    if not row:
        await query.answer("❌", show_alert=True)
        return

    item = ITEMS.get(row["item_id"])
    if not item or item.get("type") != "equipment":
        await query.answer("❌ Нельзя надеть.", show_alert=True)
        return

    slot = item["slot"]
    stat = item.get("stat", "")
    import random
    bonus = random.randint(item.get("stat_min", 1), item.get("stat_max", 3))

    with get_conn() as conn:
        # Unequip previous in slot
        old = fetchrow(conn, "SELECT item_id FROM equipped_items WHERE user_id=%s AND slot=%s", user_id, slot)
        if old:
            old_item = ITEMS.get(old["item_id"], {})
            old_stat = old_item.get("stat", "")
            old_bonus = random.randint(old_item.get("stat_min",0), old_item.get("stat_max",0))
            if old_stat:
                execute(conn, f"UPDATE users SET {old_stat} = {old_stat} - %s WHERE user_id=%s", old_bonus, user_id)
        execute(conn, """
            INSERT INTO equipped_items (user_id, slot, item_id)
            VALUES (%s, %s, %s)
            ON CONFLICT (user_id, slot) DO UPDATE SET item_id = EXCLUDED.item_id
        """, user_id, slot, row["item_id"])
        if stat:
            execute(conn, f"UPDATE users SET {stat} = {stat} + %s WHERE user_id=%s", bonus, user_id)

    name = item_display_name(item, "ru")
    await query.edit_message_text(f"✅ Надето: *{name}* (+{bonus} к {stat})", parse_mode="Markdown")


async def cb_inv_unequip(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query   = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    inv_id  = int(query.data.split(":")[1])

    with get_conn() as conn:
        row = fetchrow(conn, "SELECT * FROM inventory WHERE id=%s AND user_id=%s", inv_id, user_id)
    if not row:
        await query.answer("❌", show_alert=True)
        return
    item = ITEMS.get(row["item_id"])
    if not item:
        await query.answer("❌", show_alert=True)
        return
    slot = item.get("slot")
    with get_conn() as conn:
        execute(conn, "DELETE FROM equipped_items WHERE user_id=%s AND slot=%s", user_id, slot)

    await query.edit_message_text(f"🔓 Снято: *{item_display_name(item,'ru')}*", parse_mode="Markdown")


async def cb_inv_use(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query   = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    inv_id  = int(query.data.split(":")[1])

    with get_conn() as conn:
        row = fetchrow(conn, "SELECT * FROM inventory WHERE id=%s AND user_id=%s", inv_id, user_id)
    if not row:
        await query.answer("❌", show_alert=True)
        return

    item = ITEMS.get(row["item_id"])
    if not item or item.get("type") != "consumable":
        await query.answer("❌ Нельзя использовать.", show_alert=True)
        return

    effect = item.get("effect")
    value  = item.get("value", 0)

    if effect == "hp":
        with get_conn() as conn:
            execute(conn, "UPDATE users SET hp = LEAST(hp + %s, max_hp) WHERE user_id=%s", int(value), user_id)
        msg = f"💚 +{int(value)} ХП"
    elif effect == "hp_full":
        with get_conn() as conn:
            execute(conn, "UPDATE users SET hp = max_hp WHERE user_id=%s", user_id)
        msg = "💚 здоровье полностью восстановлено"
    elif effect == "mana":
        with get_conn() as conn:
            execute(conn, "UPDATE users SET mana = LEAST(mana + %s, max_mana) WHERE user_id=%s", int(value), user_id)
        msg = f"💧 +{int(value)} маны"
    elif effect == "mana_full":
        with get_conn() as conn:
            execute(conn, "UPDATE users SET mana = max_mana WHERE user_id=%s", user_id)
        msg = "💧 мана полностью восстановлена"
    else:
        msg = f"✨ Эффект применён: {effect}"

    # Consume item
    with get_conn() as conn:
        qty = row.get("quantity", 1)
        if qty <= 1:
            execute(conn, "DELETE FROM inventory WHERE id=%s", inv_id)
        else:
            execute(conn, "UPDATE inventory SET quantity = quantity - 1 WHERE id=%s", inv_id)

    await query.edit_message_text(f"✅ {item_display_name(item,'ru')}: {msg}", parse_mode="Markdown")


async def cb_inv_back(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query   = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    inv     = ctx.user_data.get("inv") or _get_inventory(user_id)
    markup  = _inventory_keyboard(inv)
    await query.edit_message_reply_markup(reply_markup=markup)


async def handle_inventory_button(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if update.message.text == t(user_id, "btn_inventory"):
        await cmd_inventory(update, ctx)


def register_inventory_handlers(app):
    app.add_handler(CommandHandler("inventory", cmd_inventory))
    app.add_handler(CallbackQueryHandler(cb_inv_page,    pattern=r"^inv_page:"))
    app.add_handler(CallbackQueryHandler(cb_inv_item,    pattern=r"^inv_item:"))
    app.add_handler(CallbackQueryHandler(cb_inv_equip,   pattern=r"^inv_equip:"))
    app.add_handler(CallbackQueryHandler(cb_inv_unequip, pattern=r"^inv_unequip:"))
    app.add_handler(CallbackQueryHandler(cb_inv_use,     pattern=r"^inv_use:"))
    app.add_handler(CallbackQueryHandler(cb_inv_back,    pattern=r"^inv_back"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_inventory_button), group=8)
