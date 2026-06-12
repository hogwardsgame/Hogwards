"""
Крафт палочек — собери компоненты и создай уникальную палочку.
Сердцевина (ядро) + древесина + редкий компонент = палочка с бонусом.
Чем редче компоненты — тем сильнее палочка.
"""
import logging
import random
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler
from database import user_exists, get_user, get_conn, execute, fetchrow, fetchall, add_item_to_inventory
from game.items import ITEMS, item_display_name
from utils.i18n import t

logger = logging.getLogger(__name__)

# ── Сердцевины (ядра) палочек ─────────────────────────────────────────────────
CORES = {
    "phoenix_feather":   {"name": "Перо феникса",        "attack": 25, "rarity": "epic"},
    "dragon_heartstring":{"name": "Струна сердца дракона","attack": 30, "rarity": "epic"},
    "dragon_blood":      {"name": "Кровь дракона",        "attack": 18, "rarity": "rare"},
}

# ── Рецепты палочек: ядро + сколько ингредиентов нужно ────────────────────────
# Игрок выбирает ядро, тратит его + 2 любых ингредиента + золото → палочка.
CRAFT_COST_GOLD = 500

# Префиксы названий по силе
WAND_WOODS = ["Дубовая", "Тисовая", "Падубовая", "Буковая", "Ясеневая", "Кедровая", "Виноградная"]

def _ensure_table():
    try:
        with get_conn() as conn:
            execute(conn, """
                CREATE TABLE IF NOT EXISTS crafted_wands (
                    id        SERIAL PRIMARY KEY,
                    user_id   BIGINT NOT NULL,
                    item_id   TEXT NOT NULL,
                    name      TEXT NOT NULL,
                    attack    INT NOT NULL,
                    created_at TIMESTAMPTZ DEFAULT NOW()
                )
            """)
    except Exception as e:
        logger.warning("crafted_wands table: %s", e)

def _get_inventory_ids(user_id: int) -> dict:
    """item_id -> quantity для всех предметов игрока."""
    try:
        with get_conn() as conn:
            rows = fetchall(conn, "SELECT item_id, quantity FROM inventory WHERE user_id=%s", user_id)
        return {r["item_id"]: r["quantity"] for r in rows}
    except Exception:
        return {}

def _available_cores(inv: dict) -> list:
    return [(cid, c) for cid, c in CORES.items() if inv.get(cid, 0) >= 1]

def _available_ingredients(inv: dict) -> list:
    """Ингредиенты, доступные для крафта (не ядра)."""
    result = []
    for iid, qty in inv.items():
        item = ITEMS.get(iid, {})
        if item.get("type") == "ingredient" and iid not in CORES and qty >= 1:
            result.append((iid, item, qty))
    return result

async def cmd_wandcraft(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not user_exists(user_id):
        await update.message.reply_text(t(user_id, "not_registered"))
        return
    _ensure_table()
    inv  = _get_inventory_ids(user_id)
    user = get_user(user_id)
    cores = _available_cores(inv)
    ings  = _available_ingredients(inv)

    text = (
        f"🪄 *Мастерская палочек*\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"Создай уникальную палочку!\n\n"
        f"*Нужно:*\n"
        f"• 1 сердцевина (перо феникса, струна дракона...)\n"
        f"• 2 любых ингредиента\n"
        f"• {CRAFT_COST_GOLD} 💰\n\n"
        f"💰 Твоё золото: {user['gold']:,}\n"
        f"🔮 Сердцевин доступно: {len(cores)}\n"
        f"🌿 Ингредиентов: {sum(q for _,_,q in ings)}\n"
    )
    buttons = []
    if cores and sum(q for _,_,q in ings) >= 2 and user["gold"] >= CRAFT_COST_GOLD:
        for cid, core in cores:
            buttons.append([InlineKeyboardButton(
                f"🔮 Создать на основе: {core['name']}",
                callback_data=f"wc_craft:{cid}"
            )])
    else:
        reasons = []
        if not cores: reasons.append("нет сердцевины (ищи перо феникса/струну дракона в лесу)")
        if sum(q for _,_,q in ings) < 2: reasons.append("нужно минимум 2 ингредиента")
        if user["gold"] < CRAFT_COST_GOLD: reasons.append(f"нужно {CRAFT_COST_GOLD} золота")
        text += f"\n⚠️ Не хватает: {', '.join(reasons)}"

    buttons.append([InlineKeyboardButton("🪄 Мои созданные палочки", callback_data="wc_mine")])
    await update.message.reply_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(buttons))

async def cb_wc_craft(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query   = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    core_id = query.data.split(":")[1]
    core    = CORES.get(core_id)
    if not core:
        await query.answer("Сердцевина не найдена.", show_alert=True)
        return

    _ensure_table()
    inv  = _get_inventory_ids(user_id)
    user = get_user(user_id)

    if inv.get(core_id, 0) < 1:
        await query.answer("У тебя нет этой сердцевины.", show_alert=True)
        return
    if user["gold"] < CRAFT_COST_GOLD:
        await query.answer(f"Нужно {CRAFT_COST_GOLD} золота.", show_alert=True)
        return

    ings = _available_ingredients(inv)
    if sum(q for _,_,q in ings) < 2:
        await query.answer("Нужно минимум 2 ингредиента.", show_alert=True)
        return

    # Берём 2 ингредиента (жадно)
    to_consume = []
    need = 2
    for iid, item, qty in ings:
        take = min(qty, need)
        to_consume.append((iid, take))
        need -= take
        if need <= 0:
            break

    # Считаем силу палочки: база ядра + бонус от редкости ингредиентов + рандом
    bonus_attack = core["attack"]
    for iid, take in to_consume:
        item = ITEMS.get(iid, {})
        rarity_bonus = {"common":2,"uncommon":4,"rare":7,"very_rare":10,"epic":15}.get(item.get("rarity","common"), 2)
        bonus_attack += rarity_bonus * take
    bonus_attack += random.randint(-3, 8)  # элемент удачи
    bonus_attack = max(10, bonus_attack)

    # Списываем компоненты и золото
    with get_conn() as conn:
        execute(conn, "UPDATE users SET gold=gold-%s WHERE user_id=%s", CRAFT_COST_GOLD, user_id)
        # Ядро
        if inv[core_id] <= 1:
            execute(conn, "DELETE FROM inventory WHERE user_id=%s AND item_id=%s", user_id, core_id)
        else:
            execute(conn, "UPDATE inventory SET quantity=quantity-1 WHERE user_id=%s AND item_id=%s", user_id, core_id)
        # Ингредиенты
        for iid, take in to_consume:
            if inv[iid] <= take:
                execute(conn, "DELETE FROM inventory WHERE user_id=%s AND item_id=%s", user_id, iid)
            else:
                execute(conn, "UPDATE inventory SET quantity=quantity-%s WHERE user_id=%s AND item_id=%s", take, user_id, iid)

    # Определяем редкость палочки по силе
    if bonus_attack >= 60: rarity, rstar = "legendary", "🔴"
    elif bonus_attack >= 45: rarity, rstar = "epic", "🟠"
    elif bonus_attack >= 30: rarity, rstar = "very_rare", "🟣"
    else: rarity, rstar = "rare", "🔵"

    wood = random.choice(WAND_WOODS)
    wand_name = f"{wood} палочка ({core['name']})"
    # Уникальный item_id для крафченой палочки
    wand_item_id = f"crafted_wand_{user_id}_{random.randint(1000,9999)}"

    # Регистрируем палочку в ITEMS на лету (в рамках сессии) + сохраняем в БД
    ITEMS[wand_item_id] = {
        "id": wand_item_id, "type": "equipment", "slot": "wand",
        "rarity": rarity, "emoji": "🪄",
        "name": {"ru": wand_name}, "stat": "attack", "stat_value": bonus_attack,
        "desc_ru": f"Уникальная палочка, созданная своими руками. +{bonus_attack} к атаке.",
    }
    add_item_to_inventory(user_id, wand_item_id, 1)
    with get_conn() as conn:
        execute(conn, "INSERT INTO crafted_wands (user_id, item_id, name, attack) VALUES (%s,%s,%s,%s)",
                user_id, wand_item_id, wand_name, bonus_attack)

    await query.edit_message_text(
        f"🪄✨ *Палочка создана!*\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"{rstar} *{wand_name}*\n"
        f"⚔️ Бонус атаки: +{bonus_attack}\n\n"
        f"Палочка добавлена в инвентарь — надень её через 🎒 Инвентарь!",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("🪄 Создать ещё", callback_data="wc_back")
        ]])
    )

async def cb_wc_mine(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query   = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    _ensure_table()
    try:
        with get_conn() as conn:
            rows = fetchall(conn, "SELECT name, attack, created_at FROM crafted_wands WHERE user_id=%s ORDER BY attack DESC LIMIT 15", user_id)
    except Exception:
        rows = []
    lines = ["🪄 *Мои созданные палочки*\n━━━━━━━━━━━━━━━━━━━━"]
    if not rows:
        lines.append("_Ты ещё не создал ни одной палочки._")
    for r in rows:
        lines.append(f"🪄 {r['name']} — ⚔️+{r['attack']}")
    await query.edit_message_text(
        "\n".join(lines), parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("◀️ Назад", callback_data="wc_back")
        ]])
    )

async def cb_wc_back(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    class _W:
        def __init__(self,q): self._q=q
        @property
        def effective_user(self): return self._q.from_user
        @property
        def message(self): return self._q.message
    await cmd_wandcraft(_W(query), ctx)

def register_wandcraft_handlers(app):
    app.add_handler(CommandHandler("wandcraft", cmd_wandcraft))
    app.add_handler(CommandHandler("craftwand", cmd_wandcraft))
    app.add_handler(CallbackQueryHandler(cb_wc_craft, pattern=r"^wc_craft:"))
    app.add_handler(CallbackQueryHandler(cb_wc_mine,  pattern=r"^wc_mine$"))
    app.add_handler(CallbackQueryHandler(cb_wc_back,  pattern=r"^wc_back$"))


def load_crafted_wands_into_items():
    """Подгрузить созданные палочки в ITEMS при старте бота.
    Иначе после перезапуска инвентарь не сможет показать крафченую палочку."""
    _ensure_table()
    try:
        with get_conn() as conn:
            rows = fetchall(conn, "SELECT item_id, name, attack FROM crafted_wands")
        for r in rows:
            ITEMS[r["item_id"]] = {
                "id": r["item_id"], "type": "equipment", "slot": "wand",
                "rarity": "epic", "emoji": "🪄",
                "name": {"ru": r["name"]}, "stat": "attack", "stat_value": r["attack"],
                "desc_ru": f"Уникальная созданная палочка. +{r['attack']} к атаке.",
            }
        logger.info("Загружено крафченых палочек: %d", len(rows))
    except Exception as e:
        logger.warning("load_crafted_wands: %s", e)
