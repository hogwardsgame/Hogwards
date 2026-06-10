"""
Squads — отряды волшебников.
Создание, приглашение, управление составом, совместные бонусы.
Команда: /squad
"""
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler, MessageHandler, filters
from database import (
    get_user, user_exists, get_squad, get_squad_members, create_squad,
    add_gold, get_conn, execute, fetchrow, fetchall, fetchval,
)
from utils.i18n import t
from config import SQUAD_MAX_MEMBERS, SQUAD_CREATE_COST

logger = logging.getLogger(__name__)

# in-memory: user_id → ожидаем ввод названия
_awaiting_squad_name: set[int] = set()
# user_id → {inviter_id, squad_id}
_pending_squad_invites: dict[int, dict] = {}


def _squad_card(squad: dict, members: list, leader: dict) -> str:
    member_lines = []
    for m in members:
        crown = "👑" if m["user_id"] == squad["leader_id"] else "⚔️"
        member_lines.append(f"{crown} {m['wizard_name']} (ур.{m['level']})")
    return (
        f"🛡️ *Отряд «{squad['name']}»*\n"
        f"Командир: *{leader['wizard_name']}*\n"
        f"Состав: {len(members)}/{SQUAD_MAX_MEMBERS}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        + "\n".join(member_lines)
    )


async def cmd_squad(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not user_exists(user_id):
        await update.message.reply_text(t(user_id, "not_registered"))
        return

    user = get_user(user_id)

    # Игрок уже в отряде
    if user.get("squad_id"):
        squad   = get_squad(user["squad_id"])
        members = get_squad_members(user["squad_id"])
        leader  = get_user(squad["leader_id"])
        text    = _squad_card(squad, members, leader)

        is_leader = (user_id == squad["leader_id"])
        buttons = []
        if is_leader:
            buttons.append([InlineKeyboardButton("📨 Пригласить по ID", callback_data="squad_invite")])
            buttons.append([InlineKeyboardButton("🚪 Распустить отряд",  callback_data="squad_disband")])
        else:
            buttons.append([InlineKeyboardButton("🚪 Покинуть отряд", callback_data="squad_leave")])

        await update.message.reply_text(text, parse_mode="Markdown",
                                        reply_markup=InlineKeyboardMarkup(buttons))
        return

    # Не в отряде
    markup = InlineKeyboardMarkup([
        [InlineKeyboardButton(f"⚔️ Создать отряд ({SQUAD_CREATE_COST} 💰)", callback_data="squad_create")],
        [InlineKeyboardButton("🔍 Найти отряд", callback_data="squad_browse")],
    ])
    await update.message.reply_text(
        f"🛡️ *Отряды*\n\n"
        f"Ты не состоишь ни в каком отряде.\n"
        f"Создай свой или вступи в существующий!\n\n"
        f"Максимум {SQUAD_MAX_MEMBERS} участников в отряде.",
        parse_mode="Markdown",
        reply_markup=markup
    )


async def cb_squad_create(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query   = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    user = get_user(user_id)
    if user.get("squad_id"):
        await query.edit_message_text("❌ Ты уже состоишь в отряде.")
        return
    if user["gold"] < SQUAD_CREATE_COST:
        await query.edit_message_text(f"❌ Недостаточно золота! Нужно {SQUAD_CREATE_COST} 💰")
        return

    _awaiting_squad_name.add(user_id)
    await query.edit_message_text(
        f"✏️ Введи *название отряда* (2–24 символа):\n\n"
        f"Стоимость: {SQUAD_CREATE_COST} 💰 (спишется после подтверждения)",
        parse_mode="Markdown"
    )


async def cb_squad_invite(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query   = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    user = get_user(user_id)
    if not user.get("squad_id"):
        await query.edit_message_text("❌ У тебя нет отряда.")
        return

    squad = get_squad(user["squad_id"])
    if squad["leader_id"] != user_id:
        await query.edit_message_text("❌ Только командир может приглашать.")
        return

    members = get_squad_members(user["squad_id"])
    if len(members) >= SQUAD_MAX_MEMBERS:
        await query.edit_message_text(f"❌ Отряд заполнен ({SQUAD_MAX_MEMBERS}/{SQUAD_MAX_MEMBERS}).")
        return

    ctx.user_data["awaiting_squad_invite"] = user["squad_id"]
    await query.edit_message_text(
        "🔢 Введи *Telegram ID* игрока для приглашения:\n\n"
        "💡 ID можно узнать из /profile игрока.",
        parse_mode="Markdown"
    )


async def cb_squad_leave(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query   = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    user = get_user(user_id)
    if not user.get("squad_id"):
        await query.edit_message_text("❌ Ты не в отряде.")
        return

    squad = get_squad(user["squad_id"])
    if squad["leader_id"] == user_id:
        await query.edit_message_text(
            "❌ Ты командир — сначала передай командование или распусти отряд.",
        )
        return

    with get_conn() as conn:
        execute(conn, "UPDATE users SET squad_id = NULL WHERE user_id = %s", user_id)

    await query.edit_message_text("✅ Ты покинул отряд.")


async def cb_squad_disband(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query   = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    user = get_user(user_id)
    if not user.get("squad_id"):
        await query.edit_message_text("❌ У тебя нет отряда.")
        return

    squad = get_squad(user["squad_id"])
    if squad["leader_id"] != user_id:
        await query.edit_message_text("❌ Только командир может распустить отряд.")
        return

    markup = InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ Да, распустить", callback_data="squad_disband_confirm"),
        InlineKeyboardButton("❌ Отмена",          callback_data="squad_disband_cancel"),
    ]])
    await query.edit_message_text(
        f"⚠️ Распустить отряд «{squad['name']}»?\n\nВсе участники будут исключены.",
        reply_markup=markup
    )


async def cb_squad_disband_confirm(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query   = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    user = get_user(user_id)
    if not user.get("squad_id"):
        await query.edit_message_text("❌ У тебя нет отряда.")
        return

    squad_id = user["squad_id"]
    with get_conn() as conn:
        execute(conn, "UPDATE users SET squad_id = NULL WHERE squad_id = %s", squad_id)
        execute(conn, "DELETE FROM squads WHERE id = %s", squad_id)

    await query.edit_message_text("✅ Отряд распущен.")


async def cb_squad_disband_cancel(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("❌ Отмена. Отряд сохранён.")


async def cb_squad_browse(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query   = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    user = get_user(user_id)
    if user.get("squad_id"):
        await query.edit_message_text("❌ Ты уже в отряде.")
        return

    with get_conn() as conn:
        squads = fetchall(conn, """
            SELECT s.id, s.name, s.leader_id, COUNT(u.user_id) as member_count
            FROM squads s
            LEFT JOIN users u ON u.squad_id = s.id
            GROUP BY s.id, s.name, s.leader_id
            HAVING COUNT(u.user_id) < %s
            ORDER BY member_count DESC
            LIMIT 8
        """, SQUAD_MAX_MEMBERS)

    if not squads:
        await query.edit_message_text("😔 Пока нет открытых отрядов. Создай свой!")
        return

    buttons = []
    for sq in squads:
        leader = get_user(sq["leader_id"])
        leader_name = leader["wizard_name"] if leader else "?"
        buttons.append([InlineKeyboardButton(
            f"🛡️ {sq['name']} ({sq['member_count']}/{SQUAD_MAX_MEMBERS}) — {leader_name}",
            callback_data=f"squad_request:{sq['id']}"
        )])

    await query.edit_message_text(
        "🔍 *Открытые отряды:*",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(buttons)
    )


async def cb_squad_request(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query    = update.callback_query
    await query.answer()
    user_id  = query.from_user.id
    squad_id = int(query.data.split(":")[1])

    user = get_user(user_id)
    if user.get("squad_id"):
        await query.edit_message_text("❌ Ты уже в отряде.")
        return

    squad   = get_squad(squad_id)
    members = get_squad_members(squad_id)
    if len(members) >= SQUAD_MAX_MEMBERS:
        await query.edit_message_text("❌ Отряд заполнен.")
        return

    leader_id = squad["leader_id"]
    markup = InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ Принять", callback_data=f"squad_accept:{user_id}:{squad_id}"),
        InlineKeyboardButton("❌ Отклонить", callback_data=f"squad_decline:{user_id}"),
    ]])
    try:
        await ctx.bot.send_message(
            leader_id,
            f"📨 *{user['wizard_name']}* (ур.{user['level']}) хочет вступить в отряд «{squad['name']}»!",
            parse_mode="Markdown",
            reply_markup=markup
        )
        await query.edit_message_text(f"✅ Заявка отправлена командиру отряда «{squad['name']}»!")
    except Exception:
        await query.edit_message_text("❌ Не удалось отправить заявку командиру.")


async def cb_squad_accept(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query    = update.callback_query
    parts    = query.data.split(":")
    new_uid  = int(parts[1])
    squad_id = int(parts[2])
    leader_id = query.from_user.id

    squad = get_squad(squad_id)
    if not squad or squad["leader_id"] != leader_id:
        await query.answer("❌ Только командир принимает.", show_alert=True)
        return

    members = get_squad_members(squad_id)
    if len(members) >= SQUAD_MAX_MEMBERS:
        await query.edit_message_text("❌ Отряд уже заполнен.")
        return

    new_user = get_user(new_uid)
    if not new_user or new_user.get("squad_id"):
        await query.edit_message_text("❌ Игрок уже в другом отряде.")
        return

    with get_conn() as conn:
        execute(conn, "UPDATE users SET squad_id = %s WHERE user_id = %s", squad_id, new_uid)

    await query.edit_message_text(f"✅ {new_user['wizard_name']} принят в отряд!")
    try:
        await ctx.bot.send_message(new_uid, f"✅ Тебя приняли в отряд «{squad['name']}»!")
    except Exception:
        pass


async def cb_squad_decline(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query   = update.callback_query
    await query.answer()
    new_uid = int(query.data.split(":")[1])
    await query.edit_message_text("❌ Заявка отклонена.")
    try:
        await ctx.bot.send_message(new_uid, "❌ Командир отклонил твою заявку в отряд.")
    except Exception:
        pass


async def handle_squad_text(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    # Ввод названия нового отряда
    if user_id in _awaiting_squad_name:
        _awaiting_squad_name.discard(user_id)
        name = update.message.text.strip()

        if len(name) < 2 or len(name) > 24:
            await update.message.reply_text("❌ Название должно быть от 2 до 24 символов.")
            return

        user = get_user(user_id)
        if user["gold"] < SQUAD_CREATE_COST:
            await update.message.reply_text(f"❌ Недостаточно золота ({SQUAD_CREATE_COST} 💰).")
            return

        with get_conn() as conn:
            existing = fetchrow(conn, "SELECT id FROM squads WHERE LOWER(name) = LOWER(%s)", name)
        if existing:
            await update.message.reply_text("❌ Отряд с таким названием уже существует.")
            return

        squad_id = create_squad(name, user_id)
        add_gold(user_id, -SQUAD_CREATE_COST)

        await update.message.reply_text(
            f"✅ *Отряд «{name}» создан!*\n\n"
            f"Потрачено: {SQUAD_CREATE_COST} 💰\n"
            f"Приглашай игроков через /squad → Пригласить по ID.",
            parse_mode="Markdown"
        )
        return

    # Ввод ID для приглашения
    squad_id = ctx.user_data.pop("awaiting_squad_invite", None)
    if squad_id:
        arg = update.message.text.strip()
        if not arg.isdigit():
            await update.message.reply_text("❌ ID должен быть числом.")
            return
        target_id = int(arg)
        target = get_user(target_id)
        if not target:
            await update.message.reply_text("❌ Игрок не найден.")
            return
        if target.get("squad_id"):
            await update.message.reply_text("❌ Этот игрок уже в отряде.")
            return

        squad = get_squad(squad_id)
        members = get_squad_members(squad_id)
        if len(members) >= SQUAD_MAX_MEMBERS:
            await update.message.reply_text(f"❌ Отряд заполнен ({SQUAD_MAX_MEMBERS}).")
            return

        markup = InlineKeyboardMarkup([[
            InlineKeyboardButton("✅ Принять", callback_data=f"squad_accept:{target_id}:{squad_id}"),
            InlineKeyboardButton("❌ Отклонить", callback_data=f"squad_decline:{target_id}"),
        ]])
        try:
            user = get_user(user_id)
            await ctx.bot.send_message(
                target_id,
                f"📨 *{user['wizard_name']}* приглашает тебя в отряд «{squad['name']}»!",
                parse_mode="Markdown",
                reply_markup=markup
            )
            await update.message.reply_text(f"✅ Приглашение отправлено {target['wizard_name']}!")
        except Exception:
            await update.message.reply_text("❌ Не удалось отправить приглашение.")


def register_squads_handlers(app):
    app.add_handler(CommandHandler("squad", cmd_squad))
    app.add_handler(CallbackQueryHandler(cb_squad_create,          pattern=r"^squad_create$"))
    app.add_handler(CallbackQueryHandler(cb_squad_invite,          pattern=r"^squad_invite$"))
    app.add_handler(CallbackQueryHandler(cb_squad_leave,           pattern=r"^squad_leave$"))
    app.add_handler(CallbackQueryHandler(cb_squad_disband,         pattern=r"^squad_disband$"))
    app.add_handler(CallbackQueryHandler(cb_squad_disband_confirm, pattern=r"^squad_disband_confirm$"))
    app.add_handler(CallbackQueryHandler(cb_squad_disband_cancel,  pattern=r"^squad_disband_cancel$"))
    app.add_handler(CallbackQueryHandler(cb_squad_browse,          pattern=r"^squad_browse$"))
    app.add_handler(CallbackQueryHandler(cb_squad_request,         pattern=r"^squad_request:"))
    app.add_handler(CallbackQueryHandler(cb_squad_accept,          pattern=r"^squad_accept:"))
    app.add_handler(CallbackQueryHandler(cb_squad_decline,         pattern=r"^squad_decline:"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_squad_text), group=12)
