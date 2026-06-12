"""
Коллекции — собери наборы предметов/питомцев для наград.
Сильный крючок удержания: даёт цель собирать «мусорные» предметы.
"""
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler
from database import user_exists, get_user, get_conn, execute, fetchrow, fetchall, add_gold, add_xp, add_item_to_inventory
from game.items import ITEMS, item_display_name
from utils.i18n import t
from utils.helpers import progress_bar

logger = logging.getLogger(__name__)

# ── Определения коллекций ─────────────────────────────────────────────────────
COLLECTIONS = {
    "ingredients": {
        "title": "🌿 Гербарий зельевара",
        "desc":  "Собери все ингредиенты для зельеварения.",
        "items": ["boomslang_skin","phoenix_feather","lacewing_flies","flobberworm_mucus",
                  "dragon_blood","mandrake_root","bezoar","gillyweed","dragon_heartstring"],
        "reward": {"xp": 1000, "gold": 500, "title": "Мастер-травник", "item": "felix_felicis"},
    },
    "deathly_hallows": {
        "title": "☠️ Дары Смерти",
        "desc":  "Собери три легендарных артефакта: палочку, камень, мантию.",
        "items": ["wand_elder","cloak_invisibility","amulet_horcrux"],
        "reward": {"xp": 5000, "gold": 2500, "title": "Повелитель Смерти", "item": "time_turner"},
    },
    "dark_artifacts": {
        "title": "🕯️ Тёмные артефакты",
        "desc":  "Собери предметы тёмной магии.",
        "items": ["basilisk_fang","dark_arts_tome","marauders_map","polyjuice_ready"],
        "reward": {"xp": 2000, "gold": 1000, "title": "Тёмный волшебник", "item": "dark_arts_tome"},
    },
    "auror_set": {
        "title": "🛡️ Комплект Аврора",
        "desc":  "Собери легендарное снаряжение Аврора.",
        "items": ["robe_auror","gloves_basilisk","wand_elder"],
        "reward": {"xp": 3000, "gold": 1500, "title": "Аврор", "item": None},
    },
}

def _get_owned_items(user_id: int) -> set:
    try:
        with get_conn() as conn:
            rows = fetchall(conn, "SELECT DISTINCT item_id FROM inventory WHERE user_id=%s", user_id)
            eq   = fetchall(conn, "SELECT item_id FROM equipped_items WHERE user_id=%s", user_id)
        owned = {r["item_id"] for r in rows} | {r["item_id"] for r in eq}
        return owned
    except Exception:
        return set()

def _ensure_table():
    try:
        with get_conn() as conn:
            execute(conn, """
                CREATE TABLE IF NOT EXISTS collection_claims (
                    user_id       BIGINT NOT NULL,
                    collection_id TEXT NOT NULL,
                    claimed_at    TIMESTAMPTZ DEFAULT NOW(),
                    PRIMARY KEY (user_id, collection_id)
                )
            """)
    except Exception as e:
        logger.warning("collection table: %s", e)

def _is_claimed(user_id: int, coll_id: str) -> bool:
    try:
        with get_conn() as conn:
            return fetchrow(conn, "SELECT 1 FROM collection_claims WHERE user_id=%s AND collection_id=%s",
                            user_id, coll_id) is not None
    except Exception:
        return False

def _collection_progress(owned: set, coll: dict) -> tuple[int, int]:
    have = sum(1 for iid in coll["items"] if iid in owned)
    return have, len(coll["items"])

def _list_keyboard(user_id: int, owned: set) -> InlineKeyboardMarkup:
    buttons = []
    for cid, coll in COLLECTIONS.items():
        have, total = _collection_progress(owned, coll)
        done = "✅" if (have == total) else f"{have}/{total}"
        buttons.append([InlineKeyboardButton(f"{coll['title']} — {done}", callback_data=f"coll:view:{cid}")])
    return InlineKeyboardMarkup(buttons)

async def cmd_collections(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not user_exists(user_id):
        await update.message.reply_text(t(user_id, "not_registered"))
        return
    _ensure_table()
    owned = _get_owned_items(user_id)
    completed = sum(1 for c in COLLECTIONS.values()
                    if _collection_progress(owned, c)[0] == _collection_progress(owned, c)[1])
    await update.message.reply_text(
        f"📦 *Коллекции*\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"Собери наборы предметов и получи уникальные награды!\n\n"
        f"Завершено: {completed}/{len(COLLECTIONS)}\n\n"
        f"Выбери коллекцию:",
        parse_mode="Markdown",
        reply_markup=_list_keyboard(user_id, owned),
    )

async def cb_coll(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query   = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    parts   = query.data.split(":")
    action  = parts[1]
    _ensure_table()
    owned = _get_owned_items(user_id)

    if action == "list":
        completed = sum(1 for c in COLLECTIONS.values()
                        if _collection_progress(owned, c)[0] == _collection_progress(owned, c)[1])
        await query.edit_message_text(
            f"📦 *Коллекции*\n━━━━━━━━━━━━━━━━━━━━\n"
            f"Завершено: {completed}/{len(COLLECTIONS)}\n\nВыбери коллекцию:",
            parse_mode="Markdown", reply_markup=_list_keyboard(user_id, owned)
        )
        return

    if action == "view":
        cid  = parts[2]
        coll = COLLECTIONS.get(cid)
        if not coll:
            await query.edit_message_text("❌ Коллекция не найдена.")
            return
        have, total = _collection_progress(owned, coll)
        bar = progress_bar(have, total)

        item_lines = []
        for iid in coll["items"]:
            it = ITEMS.get(iid, {})
            name = item_display_name(it, "ru") if it else iid
            emoji = it.get("emoji", "📦")
            check = "✅" if iid in owned else "⬜"
            item_lines.append(f"{check} {emoji} {name}")

        reward = coll["reward"]
        reward_parts = [f"+{reward['xp']} XP", f"+{reward['gold']} 💰"]
        if reward.get("title"): reward_parts.append(f"титул «{reward['title']}»")
        if reward.get("item"):
            ritem = ITEMS.get(reward["item"], {})
            reward_parts.append(f"{ritem.get('emoji','📦')} {item_display_name(ritem,'ru')}")

        claimed = _is_claimed(user_id, cid)
        complete = (have == total)

        buttons = []
        if complete and not claimed:
            buttons.append([InlineKeyboardButton("🎁 Забрать награду!", callback_data=f"coll:claim:{cid}")])
        buttons.append([InlineKeyboardButton("◀️ К коллекциям", callback_data="coll:list")])

        status = "✅ *Собрана!*" if complete else f"Прогресс: {have}/{total}"
        if claimed: status += "  (награда получена)"

        await query.edit_message_text(
            f"{coll['title']}\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"_{coll['desc']}_\n\n"
            f"{bar}  {status}\n\n"
            + "\n".join(item_lines)
            + f"\n\n🎁 Награда: {', '.join(reward_parts)}",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(buttons),
        )
        return

    if action == "claim":
        cid  = parts[2]
        coll = COLLECTIONS.get(cid)
        if not coll:
            return
        if _is_claimed(user_id, cid):
            await query.answer("Награда уже получена.", show_alert=True)
            return
        have, total = _collection_progress(owned, coll)
        if have < total:
            await query.answer("Коллекция ещё не собрана!", show_alert=True)
            return

        reward = coll["reward"]
        add_xp(user_id, reward["xp"])
        add_gold(user_id, reward["gold"])
        if reward.get("item"):
            add_item_to_inventory(user_id, reward["item"], 1)
        if reward.get("title"):
            try:
                with get_conn() as conn:
                    execute(conn, "INSERT INTO user_titles (user_id, title) VALUES (%s,%s) ON CONFLICT DO NOTHING",
                            user_id, reward["title"])
            except Exception:
                pass
        with get_conn() as conn:
            execute(conn, "INSERT INTO collection_claims (user_id, collection_id) VALUES (%s,%s) ON CONFLICT DO NOTHING",
                    user_id, cid)

        await query.answer("🎉 Награда получена!", show_alert=True)
        await query.edit_message_text(
            f"🎉 *Коллекция собрана!*\n"
            f"{coll['title']}\n\n"
            f"Награда:\n+{reward['xp']} XP\n+{reward['gold']} 💰"
            + (f"\nТитул: «{reward['title']}»" if reward.get('title') else "")
            + (f"\nПредмет получен!" if reward.get('item') else ""),
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("◀️ К коллекциям", callback_data="coll:list")
            ]])
        )

def register_collections_handlers(app):
    app.add_handler(CommandHandler("collections", cmd_collections))
    app.add_handler(CommandHandler("collection",  cmd_collections))
    app.add_handler(CallbackQueryHandler(cb_coll, pattern=r"^coll:"))
