"""
Крестражи Волдеморта — серверный квест.
7 крестражей спрятаны по локациям. Игроки находят и уничтожают их совместно.
Когда все 7 уничтожены — спавнится усиленный Dark Lord (мировой босс).
"""
import logging
import random
from datetime import datetime, timezone, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler
from database import (
    get_user, user_exists, add_xp, add_gold, add_house_points,
    get_conn, execute, fetchrow, fetchall,
)
from utils.i18n import t
from game.items import ITEMS, item_display_name

logger = logging.getLogger(__name__)

# ── 7 крестражей ──────────────────────────────────────────────────────────────
HORCRUXES = [
    {
        "id":       "diary",
        "name":     "Дневник Тома Реддла",
        "emoji":    "📔",
        "location": "chamber_of_secrets",
        "loc_name": "Тайная комната",
        "desc":     "Старый дневник, пронизанный тёмной магией. Внутри живёт часть души Волдеморта.",
        "hint":     "Ищи там, где шипит Василиск.",
        "destroy_item": "basilisk_fang",    # Нужен клык Василиска
        "destroy_spell": None,
        "xp": 300, "gold": 150,
        "number": 1,
    },
    {
        "id":       "ring",
        "name":     "Кольцо Певереллов",
        "emoji":    "💍",
        "location": "forbidden_forest",
        "loc_name": "Запретный лес",
        "desc":     "Кольцо с символом Даров Смерти. Проклято тёмным заклинанием.",
        "hint":     "Хагрид видел странный блеск среди корней вековых деревьев.",
        "destroy_item": None,
        "destroy_spell": "avada_kedavra",
        "xp": 350, "gold": 200,
        "number": 2,
    },
    {
        "id":       "locket",
        "name":     "Медальон Слизерина",
        "emoji":    "📿",
        "location": "azkaban",
        "loc_name": "Азкабан",
        "desc":     "Медальон с символом Слизерина. Тянет к себе тёмную магию.",
        "hint":     "Дементоры стерегут кое-что в заброшенной камере.",
        "destroy_item": "basilisk_fang",
        "destroy_spell": None,
        "xp": 400, "gold": 250,
        "number": 3,
    },
    {
        "id":       "cup",
        "name":     "Кубок Хаффлпаффа",
        "emoji":    "🏆",
        "location": "gringotts_caves",
        "loc_name": "Пещеры Гринготтса",
        "desc":     "Золотой кубок с барсуком. Хранится в самом защищённом хранилище.",
        "hint":     "Гоблины знают, но молчат за вознаграждение.",
        "destroy_item": "basilisk_fang",
        "destroy_spell": None,
        "xp": 450, "gold": 300,
        "number": 4,
    },
    {
        "id":       "diadem",
        "name":     "Диадема Когтеврана",
        "emoji":    "👑",
        "location": "room_of_requirement",
        "loc_name": "Выручай-комната",
        "desc":     "Диадема мудрости, искажённая тёмной магией. Спрятана среди тысяч вещей.",
        "hint":     "Там где хранят всё ненужное — найдёшь что-то очень нужное.",
        "destroy_item": None,
        "destroy_spell": "fiendfyre",
        "xp": 400, "gold": 250,
        "number": 5,
    },
    {
        "id":       "snake",
        "name":     "Нагайна",
        "emoji":    "🐍",
        "location": "dark_forest_depths",
        "loc_name": "Глубины тёмного леса",
        "desc":     "Живой крестраж — змея Волдеморта. Самый опасный из всех.",
        "hint":     "Шипение слышно в глубинах запретного леса ночью.",
        "destroy_item": "basilisk_fang",
        "destroy_spell": "avada_kedavra",
        "xp": 600, "gold": 400,
        "number": 6,
    },
    {
        "id":       "harry",
        "name":     "Невольный крестраж (Гарри Поттер)",
        "emoji":    "⚡",
        "location": "hogwarts_grounds",
        "loc_name": "Территория Хогвартса",
        "desc":     "Сам Гарри стал крестражем — часть души Волдеморта живёт в его шраме.",
        "hint":     "Последний крестраж — там, где началась история.",
        "destroy_item": None,
        "destroy_spell": "avada_kedavra",
        "xp": 800, "gold": 500,
        "number": 7,
    },
]

HORCRUX_MAP = {h["id"]: h for h in HORCRUXES}

def _ensure_horcrux_tables():
    try:
        with get_conn() as conn:
            execute(conn, """
                CREATE TABLE IF NOT EXISTS horcrux_progress (
                    id           SERIAL PRIMARY KEY,
                    horcrux_id   TEXT NOT NULL UNIQUE,
                    found_by     BIGINT,
                    destroyed_by BIGINT,
                    found_at     TIMESTAMPTZ,
                    destroyed_at TIMESTAMPTZ,
                    status       TEXT DEFAULT 'hidden'  -- hidden/found/destroyed
                )
            """)
            execute(conn, """
                CREATE TABLE IF NOT EXISTS horcrux_contributors (
                    user_id     BIGINT NOT NULL,
                    horcrux_id  TEXT NOT NULL,
                    action      TEXT NOT NULL,  -- found/destroyed
                    rewarded    BOOLEAN DEFAULT FALSE,
                    PRIMARY KEY (user_id, horcrux_id, action)
                )
            """)
            # Инициализируем если пусто
            for h in HORCRUXES:
                execute(conn, """
                    INSERT INTO horcrux_progress (horcrux_id, status)
                    VALUES (%s, 'hidden')
                    ON CONFLICT (horcrux_id) DO NOTHING
                """, h["id"])
    except Exception as e:
        logger.warning("horcrux tables: %s", e)

def _get_horcrux_state() -> dict:
    """Возвращает словарь horcrux_id → row."""
    try:
        with get_conn() as conn:
            rows = fetchall(conn, "SELECT * FROM horcrux_progress")
            return {r["horcrux_id"]: r for r in rows}
    except Exception:
        return {}

def _destroyed_count(state: dict) -> int:
    return sum(1 for r in state.values() if r["status"] == "destroyed")

def _horcrux_list_text(state: dict) -> str:
    destroyed = _destroyed_count(state)
    lines = [
        f"💎 *Крестражи Волдеморта*",
        f"━━━━━━━━━━━━━━━━━━━━",
        f"Уничтожено: {destroyed}/7",
        f"{'🔴' * destroyed}{'⚫' * (7 - destroyed)}\n",
    ]
    for h in HORCRUXES:
        row    = state.get(h["id"], {})
        status = row.get("status", "hidden")
        if status == "destroyed":
            icon = "✅"
            status_str = "Уничтожен"
        elif status == "found":
            icon = "🔍"
            status_str = "Найден, ожидает уничтожения"
        else:
            icon = "❓"
            status_str = f"Скрыт — {h['hint']}"

        lines.append(f"{icon} {h['emoji']} *{h['name']}*\n   📍 {h['loc_name']}\n   {status_str}\n")

    if destroyed == 7:
        lines.append("⚠️ *Все крестражи уничтожены! Волдеморт смертен!*\n🔥 Готовьтесь к финальной битве!")
    else:
        lines.append(f"_Уничтожь все 7 крестражей, чтобы открыть финальную битву с Волдемортом._")

    return "\n".join(lines)

def _horcrux_keyboard(state: dict, user_id: int) -> InlineKeyboardMarkup:
    buttons = []
    for h in HORCRUXES:
        row    = state.get(h["id"], {})
        status = row.get("status", "hidden")
        if status == "hidden":
            label = f"🔍 Искать: {h['emoji']} {h['name']}"
            cb    = f"hx_search:{h['id']}"
        elif status == "found":
            label = f"💥 Уничтожить: {h['emoji']} {h['name']}"
            cb    = f"hx_destroy:{h['id']}"
        else:
            label = f"✅ {h['emoji']} {h['name']}"
            cb    = f"hx_info:{h['id']}"
        buttons.append([InlineKeyboardButton(label, callback_data=cb)])
    return InlineKeyboardMarkup(buttons)

async def cmd_horcruxes(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not user_exists(user_id):
        await update.message.reply_text(t(user_id, "not_registered"))
        return
    _ensure_horcrux_tables()
    state = _get_horcrux_state()
    text  = _horcrux_list_text(state)
    await update.message.reply_text(text, parse_mode="Markdown", reply_markup=_horcrux_keyboard(state, user_id))

async def cb_hx_search(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query      = update.callback_query
    user_id    = query.from_user.id
    horcrux_id = query.data.split(":")[1]
    _ensure_horcrux_tables()

    h   = HORCRUX_MAP.get(horcrux_id)
    if not h:
        await query.answer("❌ Крестраж не найден.", show_alert=True)
        return

    state = _get_horcrux_state()
    row   = state.get(horcrux_id, {})
    if row.get("status") in ("found", "destroyed"):
        await query.answer("Этот крестраж уже найден!", show_alert=True)
        return

    # Шанс найти зависит от номера крестража (сложнее чем дальше)
    chance = max(0.15, 0.70 - h["number"] * 0.08)
    found  = random.random() < chance

    if found:
        with get_conn() as conn:
            execute(conn, """
                UPDATE horcrux_progress SET status='found', found_by=%s, found_at=NOW()
                WHERE horcrux_id=%s
            """, user_id, horcrux_id)
            execute(conn, """
                INSERT INTO horcrux_contributors (user_id, horcrux_id, action)
                VALUES (%s, %s, 'found') ON CONFLICT DO NOTHING
            """, user_id, horcrux_id)

        xp_find = h["xp"] // 3
        add_xp(user_id, xp_find)

        await query.edit_message_text(
            f"🔍 *Крестраж найден!*\n\n"
            f"{h['emoji']} *{h['name']}*\n"
            f"📍 {h['loc_name']}\n\n"
            f"_{h['desc']}_\n\n"
            f"⚠️ Крестраж нужно уничтожить!\n"
            f"{'🗡️ Нужен предмет: ' + (ITEMS.get(h['destroy_item'], {}).get('emoji', '') + ' ' + item_display_name(ITEMS.get(h['destroy_item'], {}), 'ru')) if h.get('destroy_item') else ''}"
            f"{'✨ Нужно заклинание: ' + h['destroy_spell'] if h.get('destroy_spell') else ''}\n\n"
            f"+{xp_find} XP за обнаружение",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton(f"💥 Уничтожить {h['emoji']}", callback_data=f"hx_destroy:{horcrux_id}"),
                InlineKeyboardButton("◀️ Назад", callback_data="hx_back"),
            ]])
        )
    else:
        fail_msgs = [
            f"Ты обыскал {h['loc_name']}, но ничего не нашёл.",
            f"Крестраж хорошо спрятан. Попробуй ещё раз.",
            f"Место кажется правильным, но крестраж ускользает.",
        ]
        await query.answer(random.choice(fail_msgs), show_alert=True)

async def cb_hx_destroy(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query      = update.callback_query
    user_id    = query.from_user.id
    horcrux_id = query.data.split(":")[1]
    _ensure_horcrux_tables()

    h   = HORCRUX_MAP.get(horcrux_id)
    if not h:
        await query.answer("❌ Крестраж не найден.", show_alert=True)
        return

    state = _get_horcrux_state()
    row   = state.get(horcrux_id, {})
    if row.get("status") == "destroyed":
        await query.answer("Уже уничтожен!", show_alert=True)
        return
    if row.get("status") == "hidden":
        await query.answer("Сначала найди крестраж!", show_alert=True)
        return

    # Проверить наличие предмета если нужен
    if h.get("destroy_item"):
        try:
            with get_conn() as conn:
                inv = fetchrow(conn,
                    "SELECT quantity FROM inventory WHERE user_id=%s AND item_id=%s",
                    user_id, h["destroy_item"])
            if not inv or inv["quantity"] < 1:
                item_data = ITEMS.get(h["destroy_item"], {})
                item_name = item_display_name(item_data, "ru") if item_data else h["destroy_item"]
                item_emoji = item_data.get("emoji", "🗡️")
                await query.answer(
                    f"❌ Нужен предмет: {item_emoji} {item_name}\n"
                    f"Его можно найти в Запретном лесу 🌲 или выбить с боссов 🐉.",
                    show_alert=True
                )
                return
            # Списываем предмет
            with get_conn() as conn:
                execute(conn, "UPDATE inventory SET quantity=quantity-1 WHERE user_id=%s AND item_id=%s",
                        user_id, h["destroy_item"])
        except Exception:
            pass

    with get_conn() as conn:
        execute(conn, """
            UPDATE horcrux_progress SET status='destroyed', destroyed_by=%s, destroyed_at=NOW()
            WHERE horcrux_id=%s
        """, user_id, horcrux_id)
        execute(conn, """
            INSERT INTO horcrux_contributors (user_id, horcrux_id, action)
            VALUES (%s, %s, 'destroyed') ON CONFLICT DO NOTHING
        """, user_id, horcrux_id)

    add_xp(user_id, h["xp"])
    add_gold(user_id, h["gold"])

    try:
        with get_conn() as conn:
            execute(conn, """
                INSERT INTO player_journal (user_id, event_type, title, description, xp_gained, gold_gained)
                VALUES (%s, 'horcrux', %s, %s, %s, %s)
            """, user_id, f"Крестраж уничтожен: {h['name']}",
                h["desc"], h["xp"], h["gold"])
    except Exception:
        pass

    # Проверить все ли уничтожены
    state_fresh = _get_horcrux_state()
    all_done    = _destroyed_count(state_fresh) == 7

    text = (
        f"💥 *Крестраж уничтожен!*\n\n"
        f"{h['emoji']} *{h['name']}*\n\n"
        f"_{h['desc']}_\n\n"
        f"+{h['xp']} XP | +{h['gold']} 💰\n"
        f"Уничтожено: {_destroyed_count(state_fresh)}/7"
    )
    if all_done:
        text += (
            "\n\n🔥 *ВСЕ КРЕСТРАЖИ УНИЧТОЖЕНЫ!*\n"
            "Волдеморт смертен. Готовьтесь к финальной битве!\n"
            "Используй /worldboss чтобы атаковать его!"
        )
        # Спавним Dark Lord
        try:
            from handlers.world_bosses import spawn_world_boss
            import asyncio
            asyncio.get_event_loop().create_task(spawn_world_boss("dark_lord", ctx))
        except Exception as e:
            logger.error("Failed to spawn dark_lord: %s", e)

    markup = InlineKeyboardMarkup([[InlineKeyboardButton("◀️ К крестражам", callback_data="hx_back")]])
    await query.edit_message_text(text, parse_mode="Markdown", reply_markup=markup)

async def cb_hx_info(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query      = update.callback_query
    await query.answer()
    horcrux_id = query.data.split(":")[1]
    h          = HORCRUX_MAP.get(horcrux_id, {})
    await query.answer(f"✅ {h.get('name','?')} уже уничтожен!", show_alert=True)

async def cb_hx_back(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query   = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    _ensure_horcrux_tables()
    state = _get_horcrux_state()
    text  = _horcrux_list_text(state)
    await query.edit_message_text(text, parse_mode="Markdown", reply_markup=_horcrux_keyboard(state, user_id))

def register_horcrux_handlers(app):
    app.add_handler(CommandHandler("horcruxes", cmd_horcruxes))
    app.add_handler(CallbackQueryHandler(cb_hx_search,  pattern=r"^hx_search:"))
    app.add_handler(CallbackQueryHandler(cb_hx_destroy, pattern=r"^hx_destroy:"))
    app.add_handler(CallbackQueryHandler(cb_hx_info,    pattern=r"^hx_info:"))
    app.add_handler(CallbackQueryHandler(cb_hx_back,    pattern=r"^hx_back$"))
