"""
Potion System — зельеварение.
Сбор ингредиентов, изучение рецептов, варка зелий с таймером.
Команда: /potions
"""
import logging
from datetime import datetime, timedelta, timezone
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler
from database import (
    get_user, user_exists, get_user_recipes, get_brewing_queue,
    add_gold, get_conn, execute, fetchrow, fetchall, fetchval,
)
from game.items import ITEMS, item_display_name, RARITY_NAMES_RU
from utils.i18n import t
from config import POTION_BREW_TIME_MINUTES

logger = logging.getLogger(__name__)

# ── Каталог рецептов ───────────────────────────────────────────────────────────
RECIPES: dict[str, dict] = {
    "healing_small": {
        "name":        "Малое зелье исцеления",
        "emoji":       "🧪",
        "rarity":      "common",
        "ingredients": {"lacewing_flies": 2, "flobberworm_mucus": 1},
        "result_item": "hp_potion_small",
        "desc":        "Базовое зелье для восстановления HP.",
        "unlock":      "start",   # доступно с начала
    },
    "healing_medium": {
        "name":        "Среднее зелье исцеления",
        "emoji":       "🧪",
        "rarity":      "uncommon",
        "ingredients": {"lacewing_flies": 3, "flobberworm_mucus": 2, "dittany": 1},
        "result_item": "hp_potion_medium",
        "desc":        "Восстанавливает 70 HP.",
        "unlock":      "level_5",
    },
    "healing_large": {
        "name":        "Большое зелье исцеления",
        "emoji":       "❤️",
        "rarity":      "rare",
        "ingredients": {"mandrake_root": 2, "dittany": 2, "bezoar": 1},
        "result_item": "hp_potion_large",
        "desc":        "Восстанавливает 150 HP.",
        "unlock":      "level_10",
    },
    "strength_brew": {
        "name":        "Зелье силы",
        "emoji":       "⚡",
        "rarity":      "rare",
        "ingredients": {"lacewing_flies": 2, "bicorn_horn": 1, "dragon_blood": 1},
        "result_item": "strength_potion",
        "desc":        "+20% к атаке на 3 хода.",
        "unlock":      "level_8",
    },
    "luck_brew": {
        "name":        "Феликс Фелицис",
        "emoji":       "🍀",
        "rarity":      "epic",
        "ingredients": {"phoenix_feather": 1, "dragon_blood": 2, "bezoar": 2},
        "result_item": "luck_potion",
        "desc":        "+50% к удаче. Феликс Фелицис — редчайшее зелье.",
        "unlock":      "boss_kill",
    },
    "shield_brew": {
        "name":        "Зелье щита",
        "emoji":       "🛡️",
        "rarity":      "uncommon",
        "ingredients": {"mandrake_root": 1, "flobberworm_mucus": 2},
        "result_item": "shield_potion",
        "desc":        "+15% к защите на 3 хода.",
        "unlock":      "level_6",
    },
    "antidote_brew": {
        "name":        "Противоядие",
        "emoji":       "💚",
        "rarity":      "common",
        "ingredients": {"bezoar": 1, "lacewing_flies": 1},
        "result_item": "antidote",
        "desc":        "Снимает яд и горение.",
        "unlock":      "start",
    },
    "xp_brew": {
        "name":        "Зелье опыта",
        "emoji":       "✨",
        "rarity":      "epic",
        "ingredients": {"phoenix_feather": 1, "bicorn_horn": 2, "boomslang_skin": 2},
        "result_item": "xp_potion",
        "desc":        "+50% к опыту на 30 минут.",
        "unlock":      "lesson_50",
    },
    "polyjuice": {
        "name":        "Оборотное зелье",
        "emoji":       "🫗",
        "rarity":      "legendary",
        "ingredients": {
            "lacewing_flies":  2,
            "boomslang_skin":  2,
            "flobberworm_mucus": 1,
            "bicorn_horn":     1,
        },
        "result_item": "polyjuice_potion",
        "desc":        "Легендарное зелье. Копирует характеристики врага в бою.",
        "unlock":      "world_boss",
    },
    "veritaserum_brew": {
        "name":        "Правдосыворотка",
        "emoji":       "💎",
        "rarity":      "epic",
        "ingredients": {"bezoar": 2, "boomslang_skin": 1, "gillyweed": 2},
        "result_item": "veritaserum",
        "desc":        "Раскрывает заклинания противника в PvP.",
        "unlock":      "pvp_25",
    },
    "luck_brew": {
        "name":        "Зелье удачи",
        "emoji":       "🍀",
        "rarity":      "rare",
        "ingredients": {"phoenix_feather": 1, "dittany": 2, "mandrake_root": 1},
        "result_item": "luck_potion",
        "desc":        "Повышает удачу — больше шансов на редкий дроп.",
        "unlock":      "level_10",
    },
    "dragon_strength": {
        "name":        "Зелье драконьей силы",
        "emoji":       "💪",
        "rarity":      "very_rare",
        "ingredients": {"dragon_blood": 1, "bicorn_horn": 2, "dragon_heartstring": 1},
        "result_item": "strength_potion",
        "desc":        "Резко повышает атаку в бою.",
        "unlock":      "boss_kill",
    },
}

UNLOCK_LABELS = {
    "start":     "С начала игры",
    "level_5":   "Уровень 5",
    "level_6":   "Уровень 6",
    "level_8":   "Уровень 8",
    "level_10":  "Уровень 10",
    "boss_kill": "Победа над боссом",
    "lesson_50": "50 уроков",
    "pvp_25":    "25 PvP побед",
    "world_boss":"Мировой босс",
}


def _user_has_recipe(user_id: int, recipe_id: str) -> bool:
    with get_conn() as conn:
        row = fetchrow(conn,
            "SELECT 1 FROM user_recipes WHERE user_id = %s AND recipe_id = %s",
            user_id, recipe_id)
        return row is not None


def _get_inventory_item_count(user_id: int, item_id: str) -> int:
    with get_conn() as conn:
        row = fetchrow(conn,
            "SELECT quantity FROM inventory WHERE user_id = %s AND item_id = %s",
            user_id, item_id)
        return row["quantity"] if row else 0


def _can_brew(user_id: int, recipe: dict) -> tuple[bool, list[str]]:
    """Проверить, хватает ли ингредиентов."""
    missing = []
    for item_id, needed in recipe["ingredients"].items():
        have = _get_inventory_item_count(user_id, item_id)
        if have < needed:
            item = ITEMS.get(item_id, {})
            iname = item_display_name(item, "ru") if item else item_id
            missing.append(f"{iname}: {have}/{needed}")
    return len(missing) == 0, missing


def _spend_ingredients(user_id: int, recipe: dict):
    with get_conn() as conn:
        for item_id, qty in recipe["ingredients"].items():
            execute(conn, """
                UPDATE inventory SET quantity = quantity - %s
                WHERE user_id = %s AND item_id = %s
            """, qty, user_id, item_id)
            # Удалить строку если количество 0
            execute(conn, """
                DELETE FROM inventory
                WHERE user_id = %s AND item_id = %s AND quantity <= 0
            """, user_id, item_id)


def _unlock_starter_recipes(user_id: int):
    """Выдать рецепты 'start' всем игрокам."""
    for recipe_id, recipe in RECIPES.items():
        if recipe.get("unlock") == "start":
            with get_conn() as conn:
                execute(conn, """
                    INSERT INTO user_recipes (user_id, recipe_id)
                    VALUES (%s, %s) ON CONFLICT DO NOTHING
                """, user_id, recipe_id)


def unlock_recipe_by_trigger(user_id: int, trigger: str):
    """Открыть рецепты по триггеру (вызывается из других модулей)."""
    for recipe_id, recipe in RECIPES.items():
        if recipe.get("unlock") == trigger:
            with get_conn() as conn:
                execute(conn, """
                    INSERT INTO user_recipes (user_id, recipe_id)
                    VALUES (%s, %s) ON CONFLICT DO NOTHING
                """, user_id, recipe_id)


def unlock_recipes_for_level(user_id: int, level: int):
    trigger = f"level_{level}"
    unlock_recipe_by_trigger(user_id, trigger)


async def cmd_potions(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """/potions — зельеварение."""
    user_id = update.effective_user.id
    if not user_exists(user_id):
        await update.message.reply_text(t(user_id, "not_registered"))
        return

    _unlock_starter_recipes(user_id)

    buttons = [
        [InlineKeyboardButton("📖 Мои рецепты",      callback_data="brew_recipes")],
        [InlineKeyboardButton("🧪 Варить зелье",      callback_data="brew_start")],
        [InlineKeyboardButton("⏳ Котёл (очередь)",   callback_data="brew_queue")],
        [InlineKeyboardButton("🎒 Ингредиенты",       callback_data="brew_ingredients")],
        [InlineKeyboardButton("🏪 Купить ингредиенты",callback_data="brew_shop")],
    ]
    user = get_user(user_id)
    queue = get_brewing_queue(user_id)
    ready = [q for q in queue if datetime.now(timezone.utc) >= q["ready_at"].replace(tzinfo=timezone.utc)]

    text = (
        f"⚗️ *Зельеварение*\n\n"
        f"💰 Золото: {user['gold']}\n"
        f"⏳ В котле: {len(queue)} зелий"
        + (f"\n✅ Готово к сбору: {len(ready)}!" if ready else "")
    )
    await update.message.reply_text(
        text, parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(buttons)
    )


async def cb_brew_recipes(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query   = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    with get_conn() as conn:
        rows = fetchall(conn,
            "SELECT recipe_id FROM user_recipes WHERE user_id = %s",
            user_id)
    owned = {r["recipe_id"] for r in rows}

    if not owned:
        await query.edit_message_text(
            "📖 У тебя нет рецептов.\n\n"
            "Начальные рецепты открываются автоматически.\n"
            "Редкие — с боссов и мировых боссов."
        )
        return

    lines = ["📖 *Твои рецепты*\n"]
    for recipe_id in owned:
        recipe = RECIPES.get(recipe_id)
        if not recipe:
            continue
        rarity_ru = RARITY_NAMES_RU.get(recipe["rarity"], recipe["rarity"])
        brew_time = POTION_BREW_TIME_MINUTES.get(recipe["rarity"], 5)
        lines.append(
            f"{recipe['emoji']} *{recipe['name']}* ({rarity_ru})\n"
            f"   _{recipe['desc']}_\n"
            f"   ⏱ {brew_time} мин."
        )

    markup = InlineKeyboardMarkup([[
        InlineKeyboardButton("🧪 Варить", callback_data="brew_start"),
        InlineKeyboardButton("🔙 Назад",  callback_data="brew_back"),
    ]])
    await query.edit_message_text(
        "\n\n".join(lines),
        parse_mode="Markdown",
        reply_markup=markup
    )


async def cb_brew_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query   = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    with get_conn() as conn:
        rows = fetchall(conn,
            "SELECT recipe_id FROM user_recipes WHERE user_id = %s",
            user_id)
    owned = [r["recipe_id"] for r in rows]

    if not owned:
        await query.edit_message_text("❌ Нет рецептов для варки.")
        return

    buttons = []
    for recipe_id in owned:
        recipe = RECIPES.get(recipe_id)
        if not recipe:
            continue
        can, missing = _can_brew(user_id, recipe)
        mark = "✅" if can else "❌"
        buttons.append([InlineKeyboardButton(
            f"{mark} {recipe['emoji']} {recipe['name']}",
            callback_data=f"brew_select:{recipe_id}"
        )])
    buttons.append([InlineKeyboardButton("🔙 Назад", callback_data="brew_back")])

    await query.edit_message_text(
        "🧪 *Выбери рецепт для варки:*\n\n"
        "✅ — ингредиенты есть\n"
        "❌ — ингредиентов не хватает",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(buttons)
    )


async def cb_brew_select(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query     = update.callback_query
    await query.answer()
    user_id   = query.from_user.id
    recipe_id = query.data.split(":")[1]

    recipe = RECIPES.get(recipe_id)
    if not recipe:
        await query.edit_message_text("❌ Рецепт не найден.")
        return

    can, missing = _can_brew(user_id, recipe)

    # Показываем детали рецепта
    ing_lines = []
    for item_id, needed in recipe["ingredients"].items():
        have  = _get_inventory_item_count(user_id, item_id)
        item  = ITEMS.get(item_id, {})
        iname = item_display_name(item, "ru") if item else item_id
        mark  = "✅" if have >= needed else "❌"
        ing_lines.append(f"{mark} {iname}: {have}/{needed}")

    brew_time = POTION_BREW_TIME_MINUTES.get(recipe["rarity"], 5)
    rarity_ru = RARITY_NAMES_RU.get(recipe["rarity"], recipe["rarity"])

    text = (
        f"{recipe['emoji']} *{recipe['name']}* ({rarity_ru})\n"
        f"_{recipe['desc']}_\n\n"
        f"*Ингредиенты:*\n"
        + "\n".join(ing_lines)
        + f"\n\n⏱ Время варки: {brew_time} мин."
    )

    if can:
        markup = InlineKeyboardMarkup([[
            InlineKeyboardButton("🔥 Начать варку!", callback_data=f"brew_confirm:{recipe_id}"),
            InlineKeyboardButton("🔙 Назад",          callback_data="brew_start"),
        ]])
    else:
        markup = InlineKeyboardMarkup([[
            InlineKeyboardButton("🏪 Купить ингредиенты", callback_data="brew_shop"),
            InlineKeyboardButton("🔙 Назад",              callback_data="brew_start"),
        ]])

    await query.edit_message_text(text, parse_mode="Markdown", reply_markup=markup)


async def cb_brew_confirm(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query     = update.callback_query
    await query.answer()
    user_id   = query.from_user.id
    recipe_id = query.data.split(":")[1]

    recipe = RECIPES.get(recipe_id)
    if not recipe:
        await query.edit_message_text("❌ Рецепт не найден.")
        return

    can, missing = _can_brew(user_id, recipe)
    if not can:
        await query.edit_message_text(
            f"❌ Не хватает ингредиентов:\n" + "\n".join(missing)
        )
        return

    brew_time = POTION_BREW_TIME_MINUTES.get(recipe["rarity"], 5)
    ready_at  = datetime.now(timezone.utc) + timedelta(minutes=brew_time)

    _spend_ingredients(user_id, recipe)

    with get_conn() as conn:
        execute(conn, """
            INSERT INTO brewing_queue (user_id, recipe_id, ready_at)
            VALUES (%s, %s, %s)
        """, user_id, recipe_id, ready_at)
        execute(conn,
            "UPDATE user_stats SET potions_brewed = potions_brewed + 1 WHERE user_id = %s",
            user_id)

    await query.edit_message_text(
        f"🔥 *Варка началась!*\n\n"
        f"{recipe['emoji']} {recipe['name']}\n"
        f"⏱ Готово через: {brew_time} мин.\n\n"
        f"Используй /potions → Котёл чтобы забрать зелье.",
        parse_mode="Markdown"
    )


async def cb_brew_queue(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query   = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    queue = get_brewing_queue(user_id)
    if not queue:
        await query.edit_message_text(
            "⏳ Котёл пуст.\n\nНачни варить через /potions → Варить зелье.",
        )
        return

    now = datetime.now(timezone.utc)
    lines = ["⏳ *Котёл:*\n"]
    collect_ids = []

    for item in queue:
        recipe   = RECIPES.get(item["recipe_id"], {})
        ready_at = item["ready_at"].replace(tzinfo=timezone.utc)
        if now >= ready_at:
            lines.append(f"✅ {recipe.get('emoji','🧪')} {recipe.get('name', item['recipe_id'])} — *Готово!*")
            collect_ids.append(item["id"])
        else:
            remaining = int((ready_at - now).total_seconds() // 60)
            lines.append(f"⏳ {recipe.get('emoji','🧪')} {recipe.get('name', item['recipe_id'])} — {remaining} мин.")

    buttons = []
    if collect_ids:
        buttons.append([InlineKeyboardButton(
            f"🎁 Забрать ({len(collect_ids)})", callback_data="brew_collect"
        )])
    buttons.append([InlineKeyboardButton("🔙 Назад", callback_data="brew_back")])

    await query.edit_message_text(
        "\n".join(lines),
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(buttons)
    )


async def cb_brew_collect(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query   = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    queue = get_brewing_queue(user_id)
    now   = datetime.now(timezone.utc)
    ready = [q for q in queue if now >= q["ready_at"].replace(tzinfo=timezone.utc)]

    if not ready:
        await query.edit_message_text("❌ Нет готовых зелий.")
        return

    collected = []
    for item in ready:
        recipe = RECIPES.get(item["recipe_id"])
        if not recipe:
            continue
        with get_conn() as conn:
            execute(conn, "UPDATE brewing_queue SET collected = TRUE WHERE id = %s", item["id"])
            execute(conn, """
                INSERT INTO inventory (user_id, item_id, quantity)
                VALUES (%s, %s, 1)
                ON CONFLICT (user_id, item_id) DO UPDATE SET quantity = inventory.quantity + 1
            """, user_id, recipe["result_item"])
        collected.append(recipe["name"])

    await query.edit_message_text(
        f"✅ *Забрано зелий: {len(collected)}*\n\n"
        + "\n".join(f"🧪 {n}" for n in collected)
        + "\n\nЗелья добавлены в инвентарь.",
        parse_mode="Markdown"
    )
    try:
        from handlers.daily_bonus import update_task_progress
        update_task_progress(user_id, "potions_brewed", len(collected))
    except Exception:
        pass
    try:
        from handlers.achievements import check_achievements
        await check_achievements(user_id, ctx)
    except Exception:
        pass


async def cb_brew_ingredients(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query   = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    with get_conn() as conn:
        rows = fetchall(conn, """
            SELECT i.item_id, i.quantity, it.name
            FROM inventory i
            LEFT JOIN (VALUES
                ('lacewing_flies','Мухи-кружевницы'),
                ('boomslang_skin','Кожа бумсланга'),
                ('flobberworm_mucus','Слизь флоббервурма'),
                ('bicorn_horn','Рог бикорна'),
                ('bezoar','Безоар'),
                ('gillyweed','Жабрник'),
                ('mandrake_root','Корень мандрагоры'),
                ('dragon_blood','Кровь дракона'),
                ('phoenix_feather','Перо феникса'),
                ('dittany','Диттани')
            ) AS it(item_id, name) ON i.item_id = it.item_id
            WHERE i.user_id = %s AND it.name IS NOT NULL
        """, user_id)

    if not rows:
        await query.edit_message_text(
            "🎒 Ингредиентов нет.\n\n"
            "Добывай их с монстров, покупай в Хогсмиде или в магазине ингредиентов.",
        )
        return

    lines = ["🎒 *Ингредиенты:*\n"]
    for r in rows:
        name = r.get("name") or r["item_id"]
        lines.append(f"• {name}: *{r['quantity']}* шт.")

    markup = InlineKeyboardMarkup([[
        InlineKeyboardButton("🏪 Купить", callback_data="brew_shop"),
        InlineKeyboardButton("🔙 Назад",  callback_data="brew_back"),
    ]])
    await query.edit_message_text(
        "\n".join(lines), parse_mode="Markdown", reply_markup=markup
    )


async def cb_brew_shop(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Магазин ингредиентов прямо в зельеварении."""
    query   = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    user    = get_user(user_id)

    from game.items import INGREDIENTS
    buttons = []
    for item_id, item in INGREDIENTS.items():
        price   = item.get("price", 10)
        name    = item_display_name(item, "ru")
        can_buy = user["gold"] >= price
        mark    = "✅" if can_buy else "❌"
        buttons.append([InlineKeyboardButton(
            f"{mark} {item.get('emoji','')} {name} — {price} 💰",
            callback_data=f"brew_buy:{item_id}:{price}"
        )])
    buttons.append([InlineKeyboardButton("🔙 Назад", callback_data="brew_back")])

    await query.edit_message_text(
        f"🏪 *Магазин ингредиентов*\n\n💰 У тебя: {user['gold']} золота",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(buttons)
    )


async def cb_brew_buy(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query   = update.callback_query
    user_id = query.from_user.id
    parts   = query.data.split(":")
    item_id = parts[1]
    price   = int(parts[2])

    user = get_user(user_id)
    if user["gold"] < price:
        await query.answer(f"❌ Нужно {price} 💰", show_alert=True)
        return

    with get_conn() as conn:
        execute(conn, "UPDATE users SET gold = gold - %s WHERE user_id = %s", price, user_id)
        execute(conn, """
            INSERT INTO inventory (user_id, item_id, quantity)
            VALUES (%s, %s, 1)
            ON CONFLICT (user_id, item_id) DO UPDATE SET quantity = inventory.quantity + 1
        """, user_id, item_id)

    from game.items import INGREDIENTS
    item  = INGREDIENTS.get(item_id, {})
    iname = item_display_name(item, "ru") if item else item_id
    await query.answer(f"✅ Куплено: {iname}", show_alert=True)


async def cb_brew_back(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query   = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    user    = get_user(user_id)
    queue   = get_brewing_queue(user_id)
    now     = datetime.now(timezone.utc)
    ready   = [q for q in queue if now >= q["ready_at"].replace(tzinfo=timezone.utc)]

    buttons = [
        [InlineKeyboardButton("📖 Мои рецепты",       callback_data="brew_recipes")],
        [InlineKeyboardButton("🧪 Варить зелье",       callback_data="brew_start")],
        [InlineKeyboardButton("⏳ Котёл (очередь)",    callback_data="brew_queue")],
        [InlineKeyboardButton("🎒 Ингредиенты",        callback_data="brew_ingredients")],
        [InlineKeyboardButton("🏪 Купить ингредиенты", callback_data="brew_shop")],
    ]
    text = (
        f"⚗️ *Зельеварение*\n\n"
        f"💰 Золото: {user['gold']}\n"
        f"⏳ В котле: {len(queue)}"
        + (f"\n✅ Готово: {len(ready)}!" if ready else "")
    )
    await query.edit_message_text(text, parse_mode="Markdown",
                                  reply_markup=InlineKeyboardMarkup(buttons))


def register_potion_handlers(app):
    app.add_handler(CommandHandler("potions", cmd_potions))
    app.add_handler(CallbackQueryHandler(cb_brew_recipes,     pattern=r"^brew_recipes$"))
    app.add_handler(CallbackQueryHandler(cb_brew_start,       pattern=r"^brew_start$"))
    app.add_handler(CallbackQueryHandler(cb_brew_select,      pattern=r"^brew_select:"))
    app.add_handler(CallbackQueryHandler(cb_brew_confirm,     pattern=r"^brew_confirm:"))
    app.add_handler(CallbackQueryHandler(cb_brew_queue,       pattern=r"^brew_queue$"))
    app.add_handler(CallbackQueryHandler(cb_brew_collect,     pattern=r"^brew_collect$"))
    app.add_handler(CallbackQueryHandler(cb_brew_ingredients, pattern=r"^brew_ingredients$"))
    app.add_handler(CallbackQueryHandler(cb_brew_shop,        pattern=r"^brew_shop$"))
    app.add_handler(CallbackQueryHandler(cb_brew_buy,         pattern=r"^brew_buy:"))
    app.add_handler(CallbackQueryHandler(cb_brew_back,        pattern=r"^brew_back$"))

