"""
Admin handler — TZ section 13.
Commands: /admin /stats /broadcast /give_gold /give_item /ban /unban
          /reset_daily /event_start /maintenance
"""
import logging
from telegram import Update
from telegram.ext import ContextTypes, CommandHandler
from config import ADMIN_IDS
from database import get_conn, fetchval, fetchall, execute, get_user
from game.items import ITEMS, item_display_name
from game.monsters import MONSTERS

logger = logging.getLogger(__name__)
_maintenance_mode = False


def admin_only(func):
    async def wrapper(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        if update.effective_user.id not in ADMIN_IDS:
            await update.message.reply_text("⛔ Доступ запрещён.")
            return
        return await func(update, ctx)
    return wrapper


def is_maintenance() -> bool:
    return _maintenance_mode


@admin_only
async def cmd_admin(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🛠 *Панель администратора*\n\n"
        "/stats — Статистика\n"
        "/broadcast `<текст>` — Рассылка\n"
        "/give\\_gold `<id> <сумма>` — Выдать золото\n"
        "/give\\_item `<id> <item_id>` — Выдать предмет\n"
        "/ban `<id>` — Заблокировать\n"
        "/unban `<id>` — Разблокировать\n"
        "/reset\\_daily — Сброс дейли лимитов\n"
        "/event\\_start `<boss_id>` — Запустить ивент\n"
        "/maintenance — Вкл/выкл тех. обслуживание",
        parse_mode="Markdown"
    )


@admin_only
async def cmd_stats(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    with get_conn() as conn:
        total     = fetchval(conn, "SELECT COUNT(*) FROM users")
        today     = fetchval(conn, "SELECT COUNT(*) FROM users WHERE created_at::date = CURRENT_DATE")
        houses    = fetchall(conn, "SELECT house, COUNT(*) as cnt FROM users GROUP BY house ORDER BY cnt DESC")
        pvp_today = fetchval(conn, "SELECT COUNT(*) FROM duels WHERE started_at::date = CURRENT_DATE")
        pve_today = fetchval(conn, "SELECT COUNT(*) FROM pve_sessions WHERE created_at::date = CURRENT_DATE")
        active_lots = fetchval(conn, "SELECT COUNT(*) FROM auction_lots WHERE status='active'")

    lines = [
        "📊 *Статистика бота*\n",
        f"👥 Всего игроков: {total}",
        f"🆕 Сегодня: {today}",
        f"⚔️ Дуэлей сегодня: {pvp_today}",
        f"🏰 PvE боёв сегодня: {pve_today}",
        f"🏛️ Активных лотов: {active_lots}",
        "",
        "*Факультеты:*",
    ]
    for row in houses:
        lines.append(f"• {row['house']}: {row['cnt']}")
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


@admin_only
async def cmd_broadcast(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not ctx.args:
        await update.message.reply_text("Использование: /broadcast <текст>")
        return
    text = " ".join(ctx.args)
    with get_conn() as conn:
        user_ids = fetchall(conn, "SELECT user_id FROM users")

    sent = failed = 0
    for row in user_ids:
        try:
            await ctx.bot.send_message(row["user_id"], text)
            sent += 1
        except Exception:
            failed += 1
    await update.message.reply_text(f"✅ Отправлено: {sent}\n❌ Ошибок: {failed}")
    _log_admin(update.effective_user.id, "broadcast", None, f"sent={sent}")


@admin_only
async def cmd_give_gold(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if len(ctx.args) < 2:
        await update.message.reply_text("Использование: /give_gold <user_id> <сумма>")
        return
    try:
        target_id = int(ctx.args[0])
        amount    = int(ctx.args[1])
    except ValueError:
        await update.message.reply_text("❌ Неверные аргументы.")
        return
    with get_conn() as conn:
        execute(conn, "UPDATE users SET gold = gold + %s WHERE user_id = %s", amount, target_id)
    _log_admin(update.effective_user.id, "give_gold", target_id, str(amount))
    await update.message.reply_text(f"✅ Выдано {amount} золота игроку {target_id}.")
    try:
        await ctx.bot.send_message(target_id, f"🎁 Администратор выдал вам {amount} 💰!")
    except Exception:
        pass


@admin_only
async def cmd_give_item(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if len(ctx.args) < 2:
        await update.message.reply_text("Использование: /give_item <user_id> <item_id>")
        return
    try:
        target_id = int(ctx.args[0])
    except ValueError:
        await update.message.reply_text("❌ Неверный user_id.")
        return
    item_id = ctx.args[1]
    item = ITEMS.get(item_id)
    if not item:
        await update.message.reply_text(f"❌ Предмет '{item_id}' не найден.")
        return
    with get_conn() as conn:
        execute(conn, "INSERT INTO inventory (user_id, item_id) VALUES (%s, %s)", target_id, item_id)
    name = item_display_name(item, "ru")
    _log_admin(update.effective_user.id, "give_item", target_id, item_id)
    await update.message.reply_text(f"✅ Предмет {name} выдан игроку {target_id}.")
    try:
        await ctx.bot.send_message(target_id, f"🎁 Администратор выдал вам предмет: {name}!")
    except Exception:
        pass


@admin_only
async def cmd_ban(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not ctx.args:
        await update.message.reply_text("Использование: /ban <user_id>")
        return
    try:
        target_id = int(ctx.args[0])
    except ValueError:
        await update.message.reply_text("❌ Неверный user_id.")
        return
    with get_conn() as conn:
        try:
            execute(conn, "ALTER TABLE users ADD COLUMN IF NOT EXISTS banned BOOLEAN DEFAULT FALSE")
        except Exception:
            pass
        execute(conn, "UPDATE users SET banned = TRUE WHERE user_id = %s", target_id)
    _log_admin(update.effective_user.id, "ban", target_id, "")
    await update.message.reply_text(f"🔨 Игрок {target_id} заблокирован.")
    try:
        await ctx.bot.send_message(target_id, "⛔ Вы заблокированы в боте.")
    except Exception:
        pass


@admin_only
async def cmd_unban(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not ctx.args:
        await update.message.reply_text("Использование: /unban <user_id>")
        return
    try:
        target_id = int(ctx.args[0])
    except ValueError:
        await update.message.reply_text("❌ Неверный user_id.")
        return
    with get_conn() as conn:
        execute(conn, "UPDATE users SET banned = FALSE WHERE user_id = %s", target_id)
    _log_admin(update.effective_user.id, "unban", target_id, "")
    await update.message.reply_text(f"✅ Игрок {target_id} разблокирован.")
    try:
        await ctx.bot.send_message(target_id, "✅ Ваша блокировка снята.")
    except Exception:
        pass


@admin_only
async def cmd_reset_daily(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    with get_conn() as conn:
        execute(conn, "DELETE FROM daily_limits WHERE date = CURRENT_DATE")
    _log_admin(update.effective_user.id, "reset_daily", None, "")
    await update.message.reply_text("✅ Дейли лимиты сброшены.")


@admin_only
async def cmd_event_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    boss_id = ctx.args[0] if ctx.args else "aragog"
    if boss_id not in MONSTERS:
        bosses = [bid for bid, m in MONSTERS.items() if m.get("is_boss")]
        await update.message.reply_text(f"❌ Босс не найден. Доступные: {', '.join(bosses)}")
        return
    from handlers.events import start_weekly_event
    await start_weekly_event(ctx.bot, boss_id)
    _log_admin(update.effective_user.id, "event_start", None, boss_id)
    await update.message.reply_text(f"✅ Ивент с боссом {boss_id} запущен!")


@admin_only
async def cmd_maintenance(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    global _maintenance_mode
    _maintenance_mode = not _maintenance_mode
    status = "включён" if _maintenance_mode else "выключен"
    _log_admin(update.effective_user.id, "maintenance", None, str(_maintenance_mode))
    await update.message.reply_text(f"🛠 Режим тех. обслуживания {status}.")


def _log_admin(admin_id: int, action: str, target_id, details: str):
    with get_conn() as conn:
        execute(conn,
            "INSERT INTO admin_log (admin_id, action, target_id, details) VALUES (%s,%s,%s,%s)",
            admin_id, action, target_id, details)


def register_admin_handlers(app):
    app.add_handler(CommandHandler("admin",       cmd_admin))
    app.add_handler(CommandHandler("stats",       cmd_stats))
    app.add_handler(CommandHandler("broadcast",   cmd_broadcast))
    app.add_handler(CommandHandler("give_gold",   cmd_give_gold))
    app.add_handler(CommandHandler("give_item",   cmd_give_item))
    app.add_handler(CommandHandler("ban",         cmd_ban))
    app.add_handler(CommandHandler("unban",       cmd_unban))
    app.add_handler(CommandHandler("reset_daily", cmd_reset_daily))
    app.add_handler(CommandHandler("event_start", cmd_event_start))
    app.add_handler(CommandHandler("maintenance", cmd_maintenance))
