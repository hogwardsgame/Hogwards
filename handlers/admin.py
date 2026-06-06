from telegram import Update
from telegram.ext import ContextTypes, CommandHandler
from config import ADMIN_IDS
from database import get_conn, fetchval, fetchall, execute
import logging

logger = logging.getLogger(__name__)


def admin_only(func):
    async def wrapper(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        if update.effective_user.id not in ADMIN_IDS:
            await update.message.reply_text("⛔ Access denied.")
            return
        return await func(update, ctx)
    return wrapper


@admin_only
async def cmd_stats(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    with get_conn() as conn:
        total = fetchval(conn, "SELECT COUNT(*) FROM users")
        today = fetchval(conn, "SELECT COUNT(*) FROM users WHERE created_at::date = CURRENT_DATE")
        houses = fetchall(conn, "SELECT house, COUNT(*) as cnt FROM users GROUP BY house ORDER BY cnt DESC")

    lines = [f"📊 *Bot Statistics*\n", f"👥 Total users: {total}", f"🆕 Joined today: {today}", ""]
    for row in houses:
        lines.append(f"• {row['house']}: {row['cnt']}")
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


@admin_only
async def cmd_broadcast(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not ctx.args:
        await update.message.reply_text("Usage: /broadcast <message>")
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
    await update.message.reply_text(f"✅ Sent: {sent}\n❌ Failed: {failed}")


@admin_only
async def cmd_give_gold(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if len(ctx.args) < 2:
        await update.message.reply_text("Usage: /give_gold <user_id> <amount>")
        return
    try:
        target_id, amount = int(ctx.args[0]), int(ctx.args[1])
    except ValueError:
        await update.message.reply_text("❌ Invalid arguments.")
        return
    with get_conn() as conn:
        execute(conn, "UPDATE users SET gold = gold + %s WHERE user_id = %s", amount, target_id)
        execute(conn, "INSERT INTO admin_log (admin_id, action, target_id, details) VALUES (%s, 'give_gold', %s, %s)",
                update.effective_user.id, target_id, str(amount))
    await update.message.reply_text(f"✅ Gave {amount} gold to {target_id}.")


@admin_only
async def cmd_reset_daily(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    with get_conn() as conn:
        execute(conn, "DELETE FROM daily_limits WHERE date = CURRENT_DATE")
    await update.message.reply_text("✅ Daily limits reset.")


@admin_only
async def cmd_admin(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🛠 *Admin Panel*\n\n"
        "/stats — Statistics\n"
        "/broadcast <msg> — Message all\n"
        "/give\\_gold <id> <amount>\n"
        "/reset\\_daily — Reset limits\n",
        parse_mode="Markdown"
    )


def register_admin_handlers(app):
    app.add_handler(CommandHandler("admin", cmd_admin))
    app.add_handler(CommandHandler("stats", cmd_stats))
    app.add_handler(CommandHandler("broadcast", cmd_broadcast))
    app.add_handler(CommandHandler("give_gold", cmd_give_gold))
    app.add_handler(CommandHandler("reset_daily", cmd_reset_daily))
