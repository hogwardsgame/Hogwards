"""
Кузница — улучшение предметов.
Объедини 3 предмета одной редкости → получи 1 предмет следующей редкости.
"""
import logging
import random
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler
from database import user_exists, get_conn, execute, fetchrow, fetchall
from game.items import ITEMS, item_display_name, RARITY_NAMES, RARITY_NAMES_RU
from utils.i18n import t

logger = logging.getLogger(__name__)

RARITY_ORDER = ["common","uncommon","rare","very_rare","epic","legendary","mythical"]
RARITY_NEXT  = {RARITY_ORDER[i]: RARITY_ORDER[i+1] for i in range(len(RARITY_ORDER)-1)}
FORGE_COST   = {"common":50,"uncommon":100,"rare":200,"very_rare":500,
                "epic":1000,"legendary":2500}
FORGE_COUNT  = 3   # Нужно N предметов одной редкости

def _get_forgeable(user_id: int) -> dict:
    """Группирует предметы инвентаря по редкости — только те где >= FORGE_COUNT."""
    try:
        with get_conn() as conn:
            rows = fetchall(conn,
                "SELECT item_id, SUM(quantity) as qty FROM inventory "
                "WHERE user_id=%s GROUP BY item_id", user_id)
    except Exception:
        return {}

    by_rarity: dict[str, list] = {}
    for row in rows:
        item   = ITEMS.get(row["item_id"])
        if not item or item.get("type") != "equipment":
            continue
        rarity = item.get("rarity", "common")
        if rarity not in RARITY_NEXT:
            continue  # mythical нельзя улучшить
        if rarity not in by_rarity:
            by_rarity[rarity] = []
        by_rarity[rarity].append({
            "item_id": row["item_id"],
            "qty":     int(row["qty"]),
            "item":    item,
        })

    # Оставляем только редкости с достаточным количеством
    result = {}
    for rarity, items in by_rarity.items():
        total_qty = sum(i["qty"] for i in items)
        if total_qty >= FORGE_COUNT:
            result[rarity] = items
    return result

def _forge_keyboard(forgeable: dict, user: dict) -> InlineKeyboardMarkup:
    buttons = []
    for rarity, items in sorted(forgeable.items(), key=lambda x: RARITY_ORDER.index(x[0])):
        rarity_next = RARITY_NEXT[rarity]
        re = RARITY_NAMES.get(rarity, "⬜")
        re_next = RARITY_NAMES.get(rarity_next, "⬜")
        rru = RARITY_NAMES_RU.get(rarity, rarity)
        cost = FORGE_COST.get(rarity, 100)
        total = sum(i["qty"] for i in items)
        can_afford = user["gold"] >= cost
        label = f"{re}→{re_next} {rru} ({total}/{FORGE_COUNT}) — {cost}💰"
        if not can_afford:
            label += " ❌"
        buttons.append([InlineKeyboardButton(label, callback_data=f"forge_do:{rarity}")])
    if not buttons:
        buttons.append([InlineKeyboardButton("Нет подходящих предметов", callback_data="forge_info")])
    return InlineKeyboardMarkup(buttons)

async def cmd_forge(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not user_exists(user_id):
        await update.message.reply_text(t(user_id, "not_registered"))
        return

    from database import get_user
    user       = get_user(user_id)
    forgeable  = _get_forgeable(user_id)

    text = (
        f"⚒️ *Кузница*\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"Объедини {FORGE_COUNT} предмета одной редкости → получи 1 предмет следующей!\n\n"
        f"💰 Твоё золото: {user['gold']:,}\n\n"
        f"**Доступные улучшения:**\n"
        f"(нужно {FORGE_COUNT} предмета + золото на плавку)"
    )
    await update.message.reply_text(text, parse_mode="Markdown",
                                    reply_markup=_forge_keyboard(forgeable, user))

async def cb_forge_do(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query   = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    rarity  = query.data.split(":")[1]

    from database import get_user
    user      = get_user(user_id)
    forgeable = _get_forgeable(user_id)

    if rarity not in forgeable:
        await query.edit_message_text("❌ Нет предметов этой редкости.")
        return

    cost = FORGE_COST.get(rarity, 100)
    if user["gold"] < cost:
        await query.answer(f"❌ Нужно {cost} 💰", show_alert=True)
        return

    items = forgeable[rarity]
    rarity_next = RARITY_NEXT[rarity]

    # Списываем 3 предмета (жадно берём по одному из каждого стака)
    consumed = 0
    with get_conn() as conn:
        for item_row in items:
            if consumed >= FORGE_COUNT:
                break
            take = min(item_row["qty"], FORGE_COUNT - consumed)
            if take <= 0:
                continue
            new_qty = item_row["qty"] - take
            if new_qty <= 0:
                execute(conn, "DELETE FROM inventory WHERE user_id=%s AND item_id=%s",
                        user_id, item_row["item_id"])
            else:
                execute(conn, "UPDATE inventory SET quantity=%s WHERE user_id=%s AND item_id=%s",
                        new_qty, user_id, item_row["item_id"])
            consumed += take

        # Списываем золото
        execute(conn, "UPDATE users SET gold=gold-%s WHERE user_id=%s", cost, user_id)

    # Выбираем случайный предмет следующей редкости
    candidates = [iid for iid, item in ITEMS.items()
                  if item.get("rarity") == rarity_next and item.get("type") == "equipment"]
    if not candidates:
        # Fallback — любой предмет следующей редкости
        candidates = [iid for iid, item in ITEMS.items() if item.get("rarity") == rarity_next]

    if not candidates:
        await query.edit_message_text(f"❌ Нет предметов редкости {rarity_next} в базе.")
        return

    result_id = random.choice(candidates)
    result_item = ITEMS[result_id]
    with get_conn() as conn:
        execute(conn, """
            INSERT INTO inventory (user_id, item_id, quantity)
            VALUES (%s, %s, 1)
            ON CONFLICT (user_id, item_id) DO UPDATE SET quantity=inventory.quantity+1
        """, user_id, result_id)

    re_old  = RARITY_NAMES.get(rarity, "⬜")
    re_new  = RARITY_NAMES.get(rarity_next, "⬜")
    rru_old = RARITY_NAMES_RU.get(rarity, rarity)
    rru_new = RARITY_NAMES_RU.get(rarity_next, rarity_next)
    name    = item_display_name(result_item, "ru")

    await query.edit_message_text(
        f"⚒️ *Плавка завершена!*\n\n"
        f"{re_old} 3× {rru_old} → {re_new} *{name}*\n\n"
        f"🎉 Предмет добавлен в инвентарь!\n"
        f"💰 Потрачено: {cost} золота",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("⚒️ Ещё раз", callback_data="forge_back")
        ]])
    )

async def cb_forge_back(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query   = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    from database import get_user
    user      = get_user(user_id)
    forgeable = _get_forgeable(user_id)
    text = (
        f"⚒️ *Кузница*\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"Объедини {FORGE_COUNT} предмета одной редкости → получи 1 следующей!\n\n"
        f"💰 Твоё золото: {user['gold']:,}"
    )
    await query.edit_message_text(text, parse_mode="Markdown",
                                  reply_markup=_forge_keyboard(forgeable, user))

async def cb_forge_info(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer(
        f"Нужно {FORGE_COUNT} предмета типа 'снаряжение' одной редкости.\n"
        f"Ищи предметы в подземельях и магазине!",
        show_alert=True
    )

def register_forge_handlers(app):
    app.add_handler(CommandHandler("forge", cmd_forge))
    app.add_handler(CallbackQueryHandler(cb_forge_do,   pattern=r"^forge_do:"))
    app.add_handler(CallbackQueryHandler(cb_forge_back, pattern=r"^forge_back$"))
    app.add_handler(CallbackQueryHandler(cb_forge_info, pattern=r"^forge_info$"))
