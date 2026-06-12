"""
Личная комната игрока — обустройство и пассивный доход (idle-механика).
Покупай улучшения → они дают золото/опыт пассивно. Заходи и собирай ренту.
"""
import logging
from datetime import datetime, timezone
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler
from database import user_exists, get_user, get_conn, execute, fetchrow, fetchall, add_gold, add_xp
from utils.i18n import t
from utils.helpers import progress_bar

logger = logging.getLogger(__name__)

# ── Улучшения комнаты ─────────────────────────────────────────────────────────
# Каждое улучшение можно купить один раз, повышает уровень и доход.
UPGRADES = {
    "bed": {
        "name": "🛏️ Удобная кровать", "price": 300,
        "gold_per_hour": 5, "xp_per_hour": 0,
        "desc": "Хороший отдых восстанавливает силы. +5 💰/час",
    },
    "desk": {
        "name": "📚 Письменный стол", "price": 600,
        "gold_per_hour": 0, "xp_per_hour": 8,
        "desc": "Место для учёбы. +8 XP/час",
    },
    "fireplace": {
        "name": "🔥 Камин", "price": 1200,
        "gold_per_hour": 12, "xp_per_hour": 3,
        "desc": "Уют и тепло. +12 💰/час и +3 XP/час",
    },
    "library": {
        "name": "📖 Личная библиотека", "price": 2500,
        "gold_per_hour": 0, "xp_per_hour": 20,
        "desc": "Знания копятся сами. +20 XP/час",
    },
    "treasury": {
        "name": "💰 Сундук с золотом", "price": 4000,
        "gold_per_hour": 35, "xp_per_hour": 0,
        "desc": "Зачарованный сундук приумножает золото. +35 💰/час",
    },
    "owlery": {
        "name": "🦉 Совятня", "price": 3000,
        "gold_per_hour": 15, "xp_per_hour": 10,
        "desc": "Совы приносят посылки. +15 💰/час и +10 XP/час",
    },
    "garden": {
        "name": "🌿 Травяной сад", "price": 5000,
        "gold_per_hour": 25, "xp_per_hour": 15,
        "desc": "Редкие травы растут сами. +25 💰/час и +15 XP/час",
    },
    "throne": {
        "name": "👑 Трон волшебника", "price": 10000,
        "gold_per_hour": 60, "xp_per_hour": 30,
        "desc": "Символ величия. +60 💰/час и +30 XP/час",
    },
}

MAX_ACCUMULATE_HOURS = 12   # доход копится максимум 12 часов

def _ensure_table():
    try:
        with get_conn() as conn:
            execute(conn, """
                CREATE TABLE IF NOT EXISTS player_room (
                    user_id      BIGINT PRIMARY KEY,
                    upgrades     TEXT DEFAULT '',
                    last_collect TIMESTAMPTZ DEFAULT NOW()
                )
            """)
    except Exception as e:
        logger.warning("player_room table: %s", e)

def _get_room(user_id: int) -> dict:
    _ensure_table()
    try:
        with get_conn() as conn:
            row = fetchrow(conn, "SELECT * FROM player_room WHERE user_id=%s", user_id)
            if not row:
                execute(conn, "INSERT INTO player_room (user_id, upgrades, last_collect) VALUES (%s,'',NOW()) ON CONFLICT DO NOTHING", user_id)
                row = {"user_id": user_id, "upgrades": "", "last_collect": datetime.now(timezone.utc)}
        return row
    except Exception:
        return {"user_id": user_id, "upgrades": "", "last_collect": datetime.now(timezone.utc)}

def _owned_upgrades(room: dict) -> set:
    return set(filter(None, (room.get("upgrades") or "").split(",")))

def _income_rates(owned: set) -> tuple[int, int]:
    gold = sum(UPGRADES[u]["gold_per_hour"] for u in owned if u in UPGRADES)
    xp   = sum(UPGRADES[u]["xp_per_hour"]   for u in owned if u in UPGRADES)
    return gold, xp

def _pending_income(room: dict) -> tuple[int, int, float]:
    owned = _owned_upgrades(room)
    gph, xph = _income_rates(owned)
    last = room.get("last_collect")
    if last and last.tzinfo is None:
        last = last.replace(tzinfo=timezone.utc)
    hours = (datetime.now(timezone.utc) - last).total_seconds() / 3600 if last else 0
    hours = min(hours, MAX_ACCUMULATE_HOURS)
    return int(gph * hours), int(xph * hours), hours

def _room_panel(user_id: int) -> tuple[str, InlineKeyboardMarkup]:
    room  = _get_room(user_id)
    owned = _owned_upgrades(room)
    gph, xph = _income_rates(owned)
    pend_gold, pend_xp, hours = _pending_income(room)

    fill_bar = progress_bar(int(hours), MAX_ACCUMULATE_HOURS)

    text = (
        f"🏠 *Моя комната*\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"Обустраивай комнату — улучшения приносят золото и опыт, пока тебя нет!\n\n"
        f"📦 Улучшений: {len(owned)}/{len(UPGRADES)}\n"
        f"💵 Доход: +{gph} 💰/час, +{xph} XP/час\n"
        f"⏳ Накоплено ({int(hours)}/{MAX_ACCUMULATE_HOURS}ч): {fill_bar}\n"
        f"   💰 {pend_gold}  ✨ {pend_xp} XP\n"
    )
    buttons = []
    if pend_gold > 0 or pend_xp > 0:
        buttons.append([InlineKeyboardButton(f"💰 Собрать (+{pend_gold}💰 +{pend_xp}XP)", callback_data="room_collect")])
    buttons.append([InlineKeyboardButton("🛒 Купить улучшения", callback_data="room_shop")])
    return text, InlineKeyboardMarkup(buttons)

async def cmd_my_room(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not user_exists(user_id):
        await update.message.reply_text(t(user_id, "not_registered"))
        return
    text, markup = _room_panel(user_id)
    await update.message.reply_text(text, parse_mode="Markdown", reply_markup=markup)

async def cb_room_collect(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query   = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    room    = _get_room(user_id)
    pend_gold, pend_xp, hours = _pending_income(room)
    if pend_gold <= 0 and pend_xp <= 0:
        await query.answer("Пока нечего собирать. Загляни позже!", show_alert=True)
        return
    if pend_gold: add_gold(user_id, pend_gold)
    if pend_xp:   add_xp(user_id, pend_xp)
    with get_conn() as conn:
        execute(conn, "UPDATE player_room SET last_collect=NOW() WHERE user_id=%s", user_id)
    await query.answer(f"✅ Собрано: +{pend_gold} 💰, +{pend_xp} XP!", show_alert=True)
    text, markup = _room_panel(user_id)
    await query.edit_message_text(text, parse_mode="Markdown", reply_markup=markup)

async def cb_room_shop(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query   = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    room    = _get_room(user_id)
    owned   = _owned_upgrades(room)
    user    = get_user(user_id)

    buttons = []
    for uid, up in UPGRADES.items():
        if uid in owned:
            buttons.append([InlineKeyboardButton(f"✅ {up['name']} (куплено)", callback_data="room_owned")])
        else:
            buttons.append([InlineKeyboardButton(f"{up['name']} — {up['price']}💰", callback_data=f"room_buy:{uid}")])
    buttons.append([InlineKeyboardButton("◀️ Назад", callback_data="room_back")])

    text = (
        f"🛒 *Улучшения комнаты*\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"💰 Твоё золото: {user['gold']:,}\n\n"
        + "\n".join(f"{up['name']}: _{up['desc']}_" for up in UPGRADES.values())
    )
    await query.edit_message_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(buttons))

async def cb_room_buy(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query   = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    uid     = query.data.split(":")[1]
    up      = UPGRADES.get(uid)
    if not up:
        await query.answer("Улучшение не найдено.", show_alert=True)
        return
    room  = _get_room(user_id)
    owned = _owned_upgrades(room)
    if uid in owned:
        await query.answer("Уже куплено!", show_alert=True)
        return
    user = get_user(user_id)
    if user["gold"] < up["price"]:
        await query.answer(f"❌ Нужно {up['price']} 💰", show_alert=True)
        return
    owned.add(uid)
    with get_conn() as conn:
        execute(conn, "UPDATE users SET gold=gold-%s WHERE user_id=%s", up["price"], user_id)
        execute(conn, "UPDATE player_room SET upgrades=%s WHERE user_id=%s", ",".join(owned), user_id)
    await query.answer(f"✅ Куплено: {up['name']}!", show_alert=True)
    await cb_room_shop(update, ctx)

async def cb_room_back(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query   = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    text, markup = _room_panel(user_id)
    await query.edit_message_text(text, parse_mode="Markdown", reply_markup=markup)

async def cb_room_owned(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer("Это улучшение уже куплено.", show_alert=True)

def register_my_room_handlers(app):
    app.add_handler(CommandHandler("myroom", cmd_my_room))
    app.add_handler(CommandHandler("home", cmd_my_room))
    app.add_handler(CallbackQueryHandler(cb_room_collect, pattern=r"^room_collect$"))
    app.add_handler(CallbackQueryHandler(cb_room_shop,    pattern=r"^room_shop$"))
    app.add_handler(CallbackQueryHandler(cb_room_buy,     pattern=r"^room_buy:"))
    app.add_handler(CallbackQueryHandler(cb_room_back,    pattern=r"^room_back$"))
    app.add_handler(CallbackQueryHandler(cb_room_owned,   pattern=r"^room_owned$"))
