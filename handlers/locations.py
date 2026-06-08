"""
Locations — исследование локаций мира.
Уникальные монстры, события, дроп и квесты для каждой зоны.
Команда: /explore
"""
import logging
import random
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler
from database import (
    get_user, user_exists, add_xp, add_gold, add_house_points,
    get_conn, execute, fetchrow, fetchall,
)
from utils.i18n import t
from game.monsters import available_zones, ZONES
from config import XP_REWARDS, GOLD_REWARDS

logger = logging.getLogger(__name__)

# Уникальные события для каждой локации
LOCATION_EVENTS: dict[str, list[dict]] = {
    "forbidden_forest": [
        {
            "title":   "Следы на земле",
            "desc":    "Ты заметил странные следы, ведущие вглубь леса. Огромные.",
            "options": ["Следовать по следам", "Обойти стороной"],
            "outcomes":[
                {"xp": 60,  "gold": 30, "msg": "Следы привели к поляне с кладом кентавров!"},
                {"xp": 20,  "gold": 10, "msg": "Мудрое решение. Спокойно прошёл мимо."},
            ],
        },
        {
            "title":   "Сияющий гриб",
            "desc":    "Среди деревьев мерцает гриб с золотыми пятнами. Ядовит? Магичен?",
            "options": ["Взять гриб", "Изучить издали"],
            "outcomes":[
                {"xp": 80,  "gold": 0,  "item": "lacewing_flies", "msg": "Гриб оказался магическим ингредиентом!"},
                {"xp": 40,  "gold": 20, "msg": "Записал наблюдения. Флитвик оценит."},
            ],
        },
        {
            "title":   "Заблудший единорог",
            "desc":    "Молодой единорог смотрит на тебя испуганными глазами.",
            "options": ["Подойти медленно", "Позвать на помощь"],
            "outcomes":[
                {"xp": 120, "gold": 0,  "msg": "Единорог позволил погладить себя и оставил перо!"},
                {"xp": 30,  "gold": 15, "msg": "Прибежал Хагрид и забрал единорога в безопасное место."},
            ],
        },
    ],
    "azkaban": [
        {
            "title":   "Заброшенная камера",
            "desc":    "Дверь камеры приоткрыта. Внутри слышен тихий плач.",
            "options": ["Войти внутрь", "Уйти"],
            "outcomes":[
                {"xp": 80,  "gold": 50, "msg": "Нашёл спрятанные ценности старого заключённого."},
                {"xp": 20,  "gold": 0,  "msg": "Мудрое решение — дементоры рядом."},
            ],
        },
        {
            "title":   "Старая карта",
            "desc":    "На стене нацарапана карта с отметкой «X».",
            "options": ["Следовать карте", "Скопировать"],
            "outcomes":[
                {"xp": 100, "gold": 80, "msg": "Карта привела к тайнику побывавшего здесь аврора!"},
                {"xp": 50,  "gold": 10, "msg": "Полезная информация. Пригодится."},
            ],
        },
    ],
    "chamber_of_secrets": [
        {
            "title":   "Шипение в стенах",
            "desc":    "Ты слышишь шипение. Кто-то говорит на парселтанге.",
            "options": ["Ответить на парселтанге", "Игнорировать"],
            "outcomes":[
                {"xp": 100, "gold": 40, "msg": "Змея указала на спрятанный крестраж — артефакт Слизерина!"},
                {"xp": 20,  "gold": 0,  "msg": "Тишина. Мудро."},
            ],
        },
        {
            "title":   "Бассейн с водой",
            "desc":    "В центре комнаты — бассейн с тёмной водой. Что-то блестит на дне.",
            "options": ["Нырнуть", "Использовать Акцио"],
            "outcomes":[
                {"xp": 60,  "gold": 100, "msg": "Нашёл золотой медальон Слизерина!"},
                {"xp": 80,  "gold": 60,  "msg": "Акцио принесло ларец с золотом!"},
            ],
        },
    ],
    "gringotts_caves": [
        {
            "title":   "Тележка гоблинов",
            "desc":    "Брошенная тележка с чем-то тяжёлым. Гоблины ушли.",
            "options": ["Взять ценности", "Оставить"],
            "outcomes":[
                {"xp": 50,  "gold": 120, "msg": "Золото! Но теперь гоблины злятся."},
                {"xp": 80,  "gold": 0,   "msg": "Честность вознаграждена — гоблин дал premium reward."},
            ],
        },
        {
            "title":   "Горячий источник",
            "desc":    "Геотермальный источник. Вода мерцает магией.",
            "options": ["Выпить воды", "Набрать в флягу"],
            "outcomes":[
                {"xp": 100, "gold": 0,  "msg": "Магическая вода восстановила силы!"},
                {"xp": 60,  "gold": 40, "msg": "Флага с зельеварением. Ингредиент!"},
            ],
        },
    ],
    "voldemort_castle": [
        {
            "title":   "Тронный зал",
            "desc":    "Огромный зал с чёрным троном. На нём — тёмный артефакт.",
            "options": ["Взять артефакт", "Уничтожить"],
            "outcomes":[
                {"xp": 120, "gold": 150, "msg": "Мощный тёмный артефакт! Опасен, но ценен."},
                {"xp": 200, "gold": 50,  "msg": "Крестраж уничтожен! +200 XP за смелость."},
            ],
        },
    ],
    "hogwarts_dungeons": [
        {
            "title":   "Тайный проход",
            "desc":    "За старым гобеленом — проход в неизвестную комнату.",
            "options": ["Войти", "Отметить на карте"],
            "outcomes":[
                {"xp": 70,  "gold": 60,  "msg": "Тайная комната Снейпа с редкими ингредиентами!"},
                {"xp": 40,  "gold": 20,  "msg": "Полезная информация для будущих авантюр."},
            ],
        },
        {
            "title":   "Странный шум",
            "desc":    "За стеной — ритмичный стук. Кто-то или что-то заперто.",
            "options": ["Открыть дверь", "Позвать преподавателя"],
            "outcomes":[
                {"xp": 50,  "gold": 40, "msg": "Нюхлер с золотом! Он делится благодарностью."},
                {"xp": 30,  "gold": 10, "msg": "Профессор наградил за бдительность."},
            ],
        },
    ],
    "black_lake": [
        {
            "title":   "Светящийся камень",
            "desc":    "На берегу озера лежит светящийся зелёным камень.",
            "options": ["Взять камень", "Бросить в воду"],
            "outcomes":[
                {"xp": 60,  "gold": 50, "item": "bezoar", "msg": "Магический камень оказался безоаром!"},
                {"xp": 80,  "gold": 0,  "msg": "Русалки благодарны — они отдарились кораллами."},
            ],
        },
        {
            "title":   "Брошенная лодка",
            "desc":    "Старая лодка у берега. Под сиденьем что-то спрятано.",
            "options": ["Обыскать лодку", "Поплыть к центру"],
            "outcomes":[
                {"xp": 50,  "gold": 70, "msg": "Нашёл старую шкатулку с золотом!"},
                {"xp": 90,  "gold": 30, "msg": "В центре озера — магическое место силы. +XP."},
            ],
        },
    ],
}

# Прогресс исследования
def _get_progress(user_id: int, location_id: str) -> int:
    with get_conn() as conn:
        row = fetchrow(conn,
            "SELECT visits FROM location_progress WHERE user_id = %s AND location_id = %s",
            user_id, location_id)
        return row["visits"] if row else 0


def _increment_visits(user_id: int, location_id: str):
    with get_conn() as conn:
        execute(conn, """
            INSERT INTO location_progress (user_id, location_id, visits, last_visit)
            VALUES (%s, %s, 1, NOW())
            ON CONFLICT (user_id, location_id)
            DO UPDATE SET visits = location_progress.visits + 1, last_visit = NOW()
        """, user_id, location_id)


async def cmd_explore(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """/explore — выбрать локацию для исследования."""
    user_id = update.effective_user.id
    if not user_exists(user_id):
        await update.message.reply_text(t(user_id, "not_registered"))
        return

    user  = get_user(user_id)
    zones = available_zones(user["level"])

    buttons = []
    for zone in zones:
        visits   = _get_progress(user_id, zone["id"])
        name     = zone["name"].get("ru", zone["id"])
        min_lvl  = zone["min_level"]
        progress = "🔥" * min(visits // 5, 5)  # каждые 5 посещений — звёздочка
        buttons.append([InlineKeyboardButton(
            f"{zone['emoji']} {name} (ур.{min_lvl}+) {progress}",
            callback_data=f"explore_zone:{zone['id']}"
        )])

    await update.message.reply_text(
        f"🗺️ *Исследование мира*\n\n"
        f"Твой уровень: {user['level']}\n"
        f"Доступно локаций: {len(zones)}\n\n"
        f"Каждая локация содержит уникальные события и дроп.\n"
        f"Выбери куда отправиться:",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(buttons)
    )


async def cb_explore_zone(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query   = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    zone_id = query.data.split(":")[1]

    zone = ZONES.get(zone_id)
    if not zone:
        await query.edit_message_text("❌ Локация не найдена.")
        return

    user   = get_user(user_id)
    visits = _get_progress(user_id, zone_id)
    name   = zone["name"].get("ru", zone_id)
    desc   = zone.get("desc_ru", "")

    events   = LOCATION_EVENTS.get(zone_id, [])
    monsters = zone.get("monsters", [])

    buttons = [
        [InlineKeyboardButton("🎲 Случайное событие", callback_data=f"explore_event:{zone_id}")],
        [InlineKeyboardButton("⚔️ Сразиться с монстром", callback_data=f"pve_enter:{zone_id}")],
    ]
    if visits >= 10:
        buttons.append([InlineKeyboardButton("🗝️ Тайник (10+ посещений)", callback_data=f"explore_secret:{zone_id}")])

    await query.edit_message_text(
        f"{zone['emoji']} *{name}*\n\n"
        f"_{desc}_\n\n"
        f"📊 Твои посещения: {visits}\n"
        f"🐉 Монстров: {len(monsters)}\n"
        f"🎲 Событий: {len(events)}\n\n"
        f"Что ты хочешь сделать?",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(buttons)
    )


async def cb_explore_event(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query   = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    zone_id = query.data.split(":")[1]

    events = LOCATION_EVENTS.get(zone_id)
    if not events:
        await query.edit_message_text("😔 В этой локации пока нет событий.")
        return

    event = random.choice(events)
    _increment_visits(user_id, zone_id)

    buttons = []
    for i, opt in enumerate(event["options"]):
        buttons.append([InlineKeyboardButton(
            opt, callback_data=f"explore_choice:{zone_id}:{event['title']}:{i}"
        )])

    await query.edit_message_text(
        f"🎲 *{event['title']}*\n\n"
        f"{event['desc']}\n\n"
        f"Что ты сделаешь?",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(buttons)
    )


async def cb_explore_choice(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query   = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    parts   = query.data.split(":")
    zone_id = parts[1]
    choice  = int(parts[3])

    events = LOCATION_EVENTS.get(zone_id, [])
    title  = parts[2]
    event  = next((e for e in events if e["title"] == title), None)

    if not event:
        await query.edit_message_text("❌ Событие не найдено.")
        return

    outcomes = event.get("outcomes", [])
    if choice >= len(outcomes):
        await query.edit_message_text("❌ Неверный выбор.")
        return

    outcome = outcomes[choice]
    xp      = outcome.get("xp", 0)
    gold    = outcome.get("gold", 0)
    item_id = outcome.get("item")

    add_xp(user_id, xp)
    if gold:
        add_gold(user_id, gold)

    user = get_user(user_id)
    add_house_points(user_id, user["house"], 2, "explore")

    item_text = ""
    if item_id:
        with get_conn() as conn:
            execute(conn, """
                INSERT INTO inventory (user_id, item_id, quantity)
                VALUES (%s, %s, 1)
                ON CONFLICT (user_id, item_id) DO UPDATE SET quantity = inventory.quantity + 1
            """, user_id, item_id)
        item_text = f"\n🎁 Найден: `{item_id}`"

    markup = InlineKeyboardMarkup([[
        InlineKeyboardButton("🔙 К локации", callback_data=f"explore_zone:{zone_id}"),
        InlineKeyboardButton("🗺️ К карте",  callback_data="explore_back"),
    ]])

    await query.edit_message_text(
        f"✨ *{outcome['msg']}*\n\n"
        f"+{xp} XP"
        + (f" | +{gold} 💰" if gold else "")
        + item_text,
        parse_mode="Markdown",
        reply_markup=markup
    )


async def cb_explore_secret(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Тайник — открывается после 10 посещений."""
    query   = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    zone_id = query.data.split(":")[1]

    visits = _get_progress(user_id, zone_id)
    if visits < 10:
        await query.edit_message_text("❌ Нужно минимум 10 посещений.")
        return

    # Сброс счётчика посещений для тайника
    with get_conn() as conn:
        execute(conn, """
            UPDATE location_progress SET visits = 0
            WHERE user_id = %s AND location_id = %s
        """, user_id, zone_id)

    from game.items import roll_equipment
    rarity = random.choices(
        ["rare", "very_rare", "epic"],
        weights=[0.60, 0.30, 0.10], k=1
    )[0]
    item = roll_equipment(rarity)
    xp   = random.randint(100, 250)
    gold = random.randint(50, 150)

    add_xp(user_id, xp)
    add_gold(user_id, gold)
    with get_conn() as conn:
        execute(conn, """
            INSERT INTO inventory (user_id, item_id, quantity) VALUES (%s, %s, 1)
            ON CONFLICT (user_id, item_id) DO UPDATE SET quantity = inventory.quantity + 1
        """, user_id, item["id"])

    zone = ZONES.get(zone_id, {})
    name = zone.get("name", {}).get("ru", zone_id)

    await query.edit_message_text(
        f"🗝️ *Тайник {name} открыт!*\n\n"
        f"Найдено: *{item['id']}* ({rarity})\n"
        f"+{xp} XP | +{gold} 💰\n\n"
        f"Счётчик посещений сброшен — начинай снова!",
        parse_mode="Markdown"
    )


async def cb_explore_back(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query   = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    user    = get_user(user_id)
    zones   = available_zones(user["level"])

    buttons = []
    for zone in zones:
        visits  = _get_progress(user_id, zone["id"])
        name    = zone["name"].get("ru", zone["id"])
        buttons.append([InlineKeyboardButton(
            f"{zone['emoji']} {name} (посещений: {visits})",
            callback_data=f"explore_zone:{zone['id']}"
        )])

    await query.edit_message_text(
        "🗺️ *Карта мира*\n\nВыбери локацию:",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(buttons)
    )


def register_locations_handlers(app):
    app.add_handler(CommandHandler("explore", cmd_explore))
    app.add_handler(CallbackQueryHandler(cb_explore_zone,   pattern=r"^explore_zone:"))
    app.add_handler(CallbackQueryHandler(cb_explore_event,  pattern=r"^explore_event:"))
    app.add_handler(CallbackQueryHandler(cb_explore_choice, pattern=r"^explore_choice:"))
    app.add_handler(CallbackQueryHandler(cb_explore_secret, pattern=r"^explore_secret:"))
    app.add_handler(CallbackQueryHandler(cb_explore_back,   pattern=r"^explore_back$"))
