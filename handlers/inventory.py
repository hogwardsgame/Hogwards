"""
Inventory — инвентарь с группировкой по типу и понятным отображением.
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

PER_PAGE = 5

SLOT_LABEL_RU = {
    "wand":   "🪄 Палочка",
    "robe":   "🧥 Мантия",
    "amulet": "📿 Амулет",
    "ring":   "💍 Кольцо",
    "hat":    "🎩 Шляпа",
    "boots":  "👢 Ботинки",
    "gloves": "🧤 Перчатки",
}

TYPE_HEADER = {
    "equipment":  "⚙️ Снаряжение",
    "consumable": "🧪 Расходники",
    "ingredient": "🌿 Ингредиенты",
    "key":        "🗝️ Ключевые",
    "misc":       "📦 Прочее",
}

TYPE_ORDER = ["equipment", "consumable", "ingredient", "key", "misc"]


def _safe_item(item_id: str) -> dict:
    item = ITEMS.get(item_id)
    if item:
        return item
    return {"id": item_id, "name": {"ru": item_id.replace("_", " ").title()},
            "rarity": "rare", "type": "misc", "desc_ru": "Особый предмет."}


def _get_inventory(user_id: int) -> list:
    with get_conn() as conn:
        return fetchall(conn,
            "SELECT * FROM inventory WHERE user_id=%s ORDER BY acquired_at DESC", user_id)


def _get_equipped(user_id: int) -> dict:
    with get_conn() as conn:
        rows = fetchall(conn,
            "SELECT slot, item_id, bonus FROM equipped_items WHERE user_id=%s", user_id)
    return {r["slot"]: {"item_id": r["item_id"], "bonus": r.get("bonus") or 0} for r in rows}


def _equipped_card(equipped: dict) -> str:
    """Карточка персонажа — что надето в каждый слот."""
    if not equipped:
        return "  Ничего не надето"
    lines = []
    for slot in ["wand", "robe", "hat", "amulet", "ring", "boots", "gloves"]:
        eq = equipped.get(slot)
        slot_label = SLOT_LABEL_RU.get(slot, slot)
        if eq:
            item  = _safe_item(eq["item_id"])
            name  = item_display_name(item, "ru")
            bonus = eq.get("bonus", 0)
            stat  = item.get("stat", "")
            rarity = item.get("rarity", "common")
            re = RARITY_NAMES.get(rarity, "⬜")
            bonus_s = f" +{bonus} {stat_label(stat,'ru')}" if stat and bonus else ""
            lines.append(f"  {slot_label}: {re} *{name}*{bonus_s}")
        else:
            lines.append(f"  {slot_label}: _пусто_")
    return "\n".join(lines)


def _group_inventory(inv: list) -> dict:
    """Группирует инвентарь по типу предмета."""
    groups: dict[str, list] = {}
    for row in inv:
        item  = _safe_item(row["item_id"])
        itype = item.get("type", "misc")
        groups.setdefault(itype, []).append(row)
    return groups


def _inv_main_text(inv: list, equipped: dict) -> str:
    eq_card = _equipped_card(equipped)
    groups  = _group_inventory(inv)
    total   = len(inv)

    summary_parts = []
    for itype in TYPE_ORDER:
        if itype in groups:
            summary_parts.append(f"{TYPE_HEADER[itype]}: {len(groups[itype])}")
    summary = "\n".join(summary_parts)

    return (
        f"🎒 *Инвентарь*\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"👤 *Надето:*\n{eq_card}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"📦 Предметов: {total}\n{summary}\n\n"
        f"Выбери раздел:"
    )


def _main_keyboard(groups: dict) -> InlineKeyboardMarkup:
    buttons = []
    for itype in TYPE_ORDER:
        if itype in groups:
            cnt   = len(groups[itype])
            label = f"{TYPE_HEADER[itype]} ({cnt})"
            buttons.append([InlineKeyboardButton(label, callback_data=f"inv_tab:{itype}:0")])
    # Кнопка авто-экипировки лучшего снаряжения
    if "equipment" in groups:
        buttons.append([InlineKeyboardButton("⚡ Надеть лучшее снаряжение", callback_data="inv_autoequip")])
    return InlineKeyboardMarkup(buttons)


def _tab_text(itype: str, rows: list, page: int) -> str:
    header = TYPE_HEADER.get(itype, itype)
    start  = page * PER_PAGE
    chunk  = rows[start:start + PER_PAGE]
    total  = len(rows)
    pages  = (total + PER_PAGE - 1) // PER_PAGE
    return (
        f"🎒 *Инвентарь — {header}*\n"
        f"Страница {page+1}/{pages}  •  Всего: {total}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"Нажми на предмет чтобы увидеть детали:"
    )


def _tab_keyboard(itype: str, rows: list, page: int) -> InlineKeyboardMarkup:
    start  = page * PER_PAGE
    chunk  = rows[start:start + PER_PAGE]
    buttons = []

    for row in chunk:
        item   = _safe_item(row["item_id"])
        name   = item_display_name(item, "ru")
        rarity = item.get("rarity", "common")
        re     = RARITY_NAMES.get(rarity, "⬜")
        rru    = RARITY_NAMES_RU.get(rarity, rarity)
        qty    = row.get("quantity", 1)
        qty_s  = f" ×{qty}" if qty > 1 else ""

        # Показываем слот для снаряжения
        slot   = item.get("slot", "")
        slot_s = f" [{SLOT_LABEL_RU.get(slot, slot).split(' ',1)[-1]}]" if slot else ""

        # Бонус для снаряжения
        stat   = item.get("stat", "")
        bonus  = item_stat_value(item)
        bonus_s = f" +{bonus}" if bonus and itype == "equipment" else ""

        label = f"{re} {name}{slot_s}{bonus_s}{qty_s}"
        buttons.append([InlineKeyboardButton(label, callback_data=f"inv_item:{row['id']}:{itype}:{page}")])

    # Навигация
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("⬅️", callback_data=f"inv_tab:{itype}:{page-1}"))
    if start + PER_PAGE < len(rows):
        nav.append(InlineKeyboardButton("➡️", callback_data=f"inv_tab:{itype}:{page+1}"))
    if nav:
        buttons.append(nav)

    buttons.append([InlineKeyboardButton("◀️ К разделам", callback_data="inv_main")])
    return InlineKeyboardMarkup(buttons)


def _item_card_text(row: dict, item: dict, equipped: dict) -> str:
    name   = item_display_name(item, "ru")
    rarity = item.get("rarity", "common")
    re     = RARITY_NAMES.get(rarity, "⬜")
    rru    = RARITY_NAMES_RU.get(rarity, rarity)
    itype  = item.get("type", "misc")
    slot   = item.get("slot", "")
    desc   = item.get("desc_ru") or item.get("description") or item_description(item, "ru")
    qty    = row.get("quantity", 1)

    # Надет ли?
    eq_data     = equipped.get(slot) if slot else None
    is_equipped = bool(eq_data and eq_data.get("item_id") == row["item_id"])

    # Бонус
    stat   = item.get("stat", "")
    bonus  = item_stat_value(item)
    bonus_line = f"\n📈 Бонус: *+{bonus} к {stat_label(stat,'ru')}*" if stat and bonus else ""

    slot_line   = f"\n🔲 Слот: {SLOT_LABEL_RU.get(slot, slot)}" if slot else ""
    qty_line    = f"\n📦 Количество: {qty}" if qty > 1 else ""
    eq_line     = "\n\n✅ *Сейчас надето*" if is_equipped else ""

    return (
        f"{re} *{name}*\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"⭐ Редкость: {rru}\n"
        f"🏷️ Тип: {TYPE_HEADER.get(itype, itype)}"
        f"{slot_line}{bonus_line}{qty_line}{eq_line}\n\n"
        f"📜 _{desc}_"
    )


def _item_action_keyboard(inv_id: int, item: dict, is_equipped: bool,
                          back_itype: str, back_page: int) -> InlineKeyboardMarkup:
    buttons = []
    itype   = item.get("type")
    if itype == "equipment":
        label  = "🔓 Снять" if is_equipped else "⚙️ Надеть"
        action = "inv_unequip" if is_equipped else "inv_equip"
        buttons.append([InlineKeyboardButton(label, callback_data=f"{action}:{inv_id}:{back_itype}:{back_page}")])
    elif itype == "consumable":
        buttons.append([InlineKeyboardButton(
            "🧪 Использовать",
            callback_data=f"inv_use:{inv_id}:{back_itype}:{back_page}"
        )])
    buttons.append([InlineKeyboardButton(
        "◀️ Назад",
        callback_data=f"inv_tab:{back_itype}:{back_page}"
    )])
    return InlineKeyboardMarkup(buttons)


# ── Handlers ──────────────────────────────────────────────────────────────────

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
            "Покупай предметы в 🏪 Магазине или находи в приключениях!",
            parse_mode="Markdown",
        )
        return

    groups = _group_inventory(inv)
    await update.message.reply_text(
        _inv_main_text(inv, equipped),
        parse_mode="Markdown",
        reply_markup=_main_keyboard(groups),
    )


async def cb_inv_main(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query   = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    inv      = _get_inventory(user_id)
    equipped = _get_equipped(user_id)
    ctx.user_data["inv"]      = inv
    ctx.user_data["equipped"] = equipped
    groups  = _group_inventory(inv)
    await query.edit_message_text(
        _inv_main_text(inv, equipped),
        parse_mode="Markdown",
        reply_markup=_main_keyboard(groups),
    )


async def cb_inv_tab(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query   = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    parts   = query.data.split(":")
    itype   = parts[1]
    page    = int(parts[2])

    inv    = ctx.user_data.get("inv") or _get_inventory(user_id)
    groups = _group_inventory(inv)
    rows   = groups.get(itype, [])

    await query.edit_message_text(
        _tab_text(itype, rows, page),
        parse_mode="Markdown",
        reply_markup=_tab_keyboard(itype, rows, page),
    )


async def cb_inv_item(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query   = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    parts   = query.data.split(":")
    inv_id  = int(parts[1])
    back_itype = parts[2] if len(parts) > 2 else "equipment"
    back_page  = int(parts[3]) if len(parts) > 3 else 0

    with get_conn() as conn:
        row = fetchrow(conn, "SELECT * FROM inventory WHERE id=%s AND user_id=%s", inv_id, user_id)
    if not row:
        await query.answer("❌ Предмет не найден.", show_alert=True)
        return

    item     = _safe_item(row["item_id"])
    equipped = _get_equipped(user_id)
    slot     = item.get("slot", "")
    eq_data  = equipped.get(slot) if slot else None
    is_eq    = bool(eq_data and eq_data.get("item_id") == row["item_id"])

    await query.edit_message_text(
        _item_card_text(row, item, equipped),
        parse_mode="Markdown",
        reply_markup=_item_action_keyboard(inv_id, item, is_eq, back_itype, back_page),
    )


async def cb_inv_equip(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query   = update.callback_query
    user_id = query.from_user.id
    parts   = query.data.split(":")
    inv_id  = int(parts[1])
    back_itype = parts[2] if len(parts) > 2 else "equipment"
    back_page  = int(parts[3]) if len(parts) > 3 else 0

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
        old = fetchrow(conn, "SELECT item_id, bonus FROM equipped_items WHERE user_id=%s AND slot=%s", user_id, slot)
        if old:
            old_item  = _safe_item(old["item_id"])
            old_stat  = old_item.get("stat", "")
            old_bonus = old.get("bonus") or 0
            if old_stat and old_bonus:
                execute(conn, f"UPDATE users SET {old_stat}={old_stat}-%s WHERE user_id=%s", old_bonus, user_id)
        execute(conn, """
            INSERT INTO equipped_items (user_id, slot, item_id, bonus)
            VALUES (%s,%s,%s,%s)
            ON CONFLICT (user_id, slot) DO UPDATE SET item_id=EXCLUDED.item_id, bonus=EXCLUDED.bonus
        """, user_id, slot, row["item_id"], bonus)
        if stat and bonus:
            execute(conn, f"UPDATE users SET {stat}={stat}+%s WHERE user_id=%s", bonus, user_id)

    name = item_display_name(item, "ru")
    await query.answer(f"✅ Надето: {name}", show_alert=True)

    # Refresh item card
    equipped_fresh = _get_equipped(user_id)
    is_eq = True
    await query.edit_message_text(
        _item_card_text(row, item, equipped_fresh),
        parse_mode="Markdown",
        reply_markup=_item_action_keyboard(inv_id, item, is_eq, back_itype, back_page),
    )


async def cb_inv_unequip(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query   = update.callback_query
    user_id = query.from_user.id
    parts   = query.data.split(":")
    inv_id  = int(parts[1])
    back_itype = parts[2] if len(parts) > 2 else "equipment"
    back_page  = int(parts[3]) if len(parts) > 3 else 0

    with get_conn() as conn:
        row = fetchrow(conn, "SELECT * FROM inventory WHERE id=%s AND user_id=%s", inv_id, user_id)
    if not row:
        await query.answer("❌", show_alert=True)
        return

    item = _safe_item(row["item_id"])
    slot = item.get("slot", "")

    with get_conn() as conn:
        eq_row = fetchrow(conn, "SELECT item_id, bonus FROM equipped_items WHERE user_id=%s AND slot=%s", user_id, slot)
        if eq_row:
            eq_item  = _safe_item(eq_row["item_id"])
            eq_stat  = eq_item.get("stat", "")
            eq_bonus = eq_row.get("bonus") or 0
            if eq_stat and eq_bonus:
                execute(conn, f"UPDATE users SET {eq_stat}={eq_stat}-%s WHERE user_id=%s", eq_bonus, user_id)
        execute(conn, "DELETE FROM equipped_items WHERE user_id=%s AND slot=%s", user_id, slot)

    name = item_display_name(item, "ru")
    await query.answer(f"🔓 Снято: {name}", show_alert=True)

    equipped_fresh = _get_equipped(user_id)
    is_eq = False
    await query.edit_message_text(
        _item_card_text(row, item, equipped_fresh),
        parse_mode="Markdown",
        reply_markup=_item_action_keyboard(inv_id, item, is_eq, back_itype, back_page),
    )


async def cb_inv_use(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query   = update.callback_query
    user_id = query.from_user.id
    parts   = query.data.split(":")
    inv_id  = int(parts[1])
    back_itype = parts[2] if len(parts) > 2 else "consumable"
    back_page  = int(parts[3]) if len(parts) > 3 else 0

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
            execute(conn, "UPDATE users SET hp=LEAST(hp+%s,max_hp) WHERE user_id=%s", int(value), user_id)
        msg = f"💚 +{int(value)} ХП"
    elif effect == "hp_full":
        with get_conn() as conn:
            execute(conn, "UPDATE users SET hp=max_hp WHERE user_id=%s", user_id)
        msg = "💚 Здоровье полностью восстановлено!"
    elif effect == "mana":
        with get_conn() as conn:
            execute(conn, "UPDATE users SET mana=LEAST(mana+%s,max_mana) WHERE user_id=%s", int(value), user_id)
        msg = f"💧 +{int(value)} маны"
    elif effect == "mana_full":
        with get_conn() as conn:
            execute(conn, "UPDATE users SET mana=max_mana WHERE user_id=%s", user_id)
        msg = "💧 Мана полностью восстановлена!"
    elif effect == "xp":
        from database import add_xp
        add_xp(user_id, int(value))
        msg = f"✨ +{int(value)} опыта"
    elif effect == "gold":
        from database import add_gold
        add_gold(user_id, int(value))
        msg = f"💰 +{int(value)} золота"
    elif effect in ("attack_mult", "defense_mult", "luck_mult", "speed_mult"):
        # Боевые зелья — активируются на 60 минут
        duration = item.get("duration", 3600) // 60
        try:
            from database import apply_potion
            apply_potion(user_id, item.get("id", effect), effect, float(value), duration)
        except Exception:
            pass
        effect_names = {
            "attack_mult":  f"⚔️ +{int(float(value)*100)}% к атаке",
            "defense_mult": f"🛡️ +{int(float(value)*100)}% к защите",
            "luck_mult":    f"🍀 +{int(float(value)*100)}% к удаче",
            "speed_mult":   f"⚡ +{int(float(value)*100)}% к скорости",
        }
        msg = f"{effect_names.get(effect, effect)} на {duration} мин"
    else:
        msg = f"✨ Эффект: {effect or 'применён'}"

    with get_conn() as conn:
        qty = row.get("quantity", 1)
        if qty <= 1:
            execute(conn, "DELETE FROM inventory WHERE id=%s", inv_id)
        else:
            execute(conn, "UPDATE inventory SET quantity=quantity-1 WHERE id=%s", inv_id)

    name = item_display_name(item, "ru")
    await query.edit_message_text(
        f"✅ *{name}* использован\n\n{msg}\n\n"
        f"_Характеристики обновлены._",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("◀️ К инвентарю", callback_data=f"inv_tab:{back_itype}:{back_page}")
        ]])
    )


async def cb_inv_autoequip(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Надеть лучшее снаряжение в каждый слот по величине бонуса."""
    query   = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    inv = _get_inventory(user_id)

    # Группируем снаряжение по слоту, выбираем лучшее по бонусу
    best_per_slot: dict[str, tuple] = {}  # slot -> (item_id, bonus)
    for row in inv:
        item = _safe_item(row["item_id"])
        if item.get("type") != "equipment":
            continue
        slot  = item.get("slot")
        if not slot:
            continue
        bonus = item_stat_value(item)
        if slot not in best_per_slot or bonus > best_per_slot[slot][1]:
            best_per_slot[slot] = (row["item_id"], bonus, item.get("stat", ""))

    if not best_per_slot:
        await query.answer("Нет снаряжения для экипировки.", show_alert=True)
        return

    equipped_now = _get_equipped(user_id)
    changes = []

    with get_conn() as conn:
        for slot, (item_id, bonus, stat) in best_per_slot.items():
            current = equipped_now.get(slot)
            # Уже надет этот предмет — пропускаем
            if current and current.get("item_id") == item_id:
                continue
            # Снимаем старый бонус
            if current:
                old_item  = _safe_item(current["item_id"])
                old_stat  = old_item.get("stat", "")
                old_bonus = current.get("bonus") or 0
                if old_stat and old_bonus:
                    execute(conn, f"UPDATE users SET {old_stat}={old_stat}-%s WHERE user_id=%s", old_bonus, user_id)
            # Надеваем новый
            execute(conn, """
                INSERT INTO equipped_items (user_id, slot, item_id, bonus)
                VALUES (%s,%s,%s,%s)
                ON CONFLICT (user_id, slot) DO UPDATE SET item_id=EXCLUDED.item_id, bonus=EXCLUDED.bonus
            """, user_id, slot, item_id, bonus)
            if stat and bonus:
                execute(conn, f"UPDATE users SET {stat}={stat}+%s WHERE user_id=%s", bonus, user_id)
            item = _safe_item(item_id)
            changes.append(f"{item.get('emoji','🔲')} {item_display_name(item,'ru')}")

    if not changes:
        await query.answer("Лучшее снаряжение уже надето!", show_alert=True)
        return

    inv_fresh      = _get_inventory(user_id)
    equipped_fresh = _get_equipped(user_id)
    groups         = _group_inventory(inv_fresh)

    changes_text = "\n".join(f"  ✅ {c}" for c in changes)
    await query.edit_message_text(
        f"⚡ *Снаряжение обновлено!*\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"Надето лучшее в {len(changes)} слот(ов):\n{changes_text}\n\n"
        f"_Характеристики пересчитаны._",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("◀️ К инвентарю", callback_data="inv_main")
        ]])
    )


def register_inventory_handlers(app):
    app.add_handler(CommandHandler("inventory", cmd_inventory))
    app.add_handler(CallbackQueryHandler(cb_inv_main,      pattern=r"^inv_main$"))
    app.add_handler(CallbackQueryHandler(cb_inv_autoequip, pattern=r"^inv_autoequip$"))
    app.add_handler(CallbackQueryHandler(cb_inv_tab,     pattern=r"^inv_tab:"))
    app.add_handler(CallbackQueryHandler(cb_inv_item,    pattern=r"^inv_item:"))
    app.add_handler(CallbackQueryHandler(cb_inv_equip,   pattern=r"^inv_equip:"))
    app.add_handler(CallbackQueryHandler(cb_inv_unequip, pattern=r"^inv_unequip:"))
    app.add_handler(CallbackQueryHandler(cb_inv_use,     pattern=r"^inv_use:"))
