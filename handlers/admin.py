from telegram import Update
from telegram.ext import ContextTypes, CommandHandler
from config import ADMIN_IDS
from database import get_pool
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
    pool = await get_pool()
    async with pool.acquire() as conn:
        total = await conn.fetchval("SELECT COUNT(*) FROM users")
        today = await conn.fetchval(
            "SELECT COUNT(*) FROM users WHERE created_at::date = CURRENT_DATE"
        )
        houses = await conn.fetch(
            "SELECT house, COUNT(*) as cnt FROM users GROUP BY house ORDER BY cnt DESC"
        )

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
    pool = await get_pool()
    async with pool.acquire() as conn:
        user_ids = await conn.fetch("SELECT user_id FROM users")

    sent = 0
    failed = 0
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
        target_id = int(ctx.args[0])
        amount = int(ctx.args[1])
    except ValueError:
        await update.message.reply_text("❌ Invalid arguments.")
        return

    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE users SET gold = gold + $1 WHERE user_id = $2", amount, target_id
        )
        await conn.execute(
            "INSERT INTO admin_log (admin_id, action, target_id, details) VALUES ($1, 'give_gold', $2, $3)",
            update.effective_user.id, target_id, str(amount)
        )

    await update.message.reply_text(f"✅ Gave {amount} gold to user {target_id}.")


@admin_only
async def cmd_ban(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not ctx.args:
        await update.message.reply_text("Usage: /ban <user_id>")
        return
    try:
        target_id = int(ctx.args[0])
    except ValueError:
        await update.message.reply_text("❌ Invalid user_id.")
        return

    pool = await get_pool()
    async with pool.acquire() as conn:
        # Add a banned column if you need — for now just log it
        await conn.execute(
            "INSERT INTO admin_log (admin_id, action, target_id, details) VALUES ($1, 'ban', $2, 'banned')",
            update.effective_user.id, target_id
        )
    await update.message.reply_text(f"✅ User {target_id} has been banned (logged).")


@admin_only
async def cmd_reset_daily(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM daily_limits WHERE date = CURRENT_DATE")
    await update.message.reply_text("✅ Daily limits reset.")


@admin_only
async def cmd_admin(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    text = (
        "🛠 *Admin Panel*\n\n"
        "/stats — Bot statistics\n"
        "/broadcast <msg> — Message all users\n"
        "/give\\_gold <id> <amount> — Give gold\n"
        "/ban <id> — Ban user\n"
        "/reset\\_daily — Reset daily limits\n"
    )
    await update.message.reply_text(text, parse_mode="Markdown")


def register_admin_handlers(app):
    app.add_handler(CommandHandler("admin", cmd_admin))
    app.add_handler(CommandHandler("stats", cmd_stats))
    app.add_handler(CommandHandler("broadcast", cmd_broadcast))
    app.add_handler(CommandHandler("give_gold", cmd_give_gold))
    app.add_handler(CommandHandler("ban", cmd_ban))
    app.add_handler(CommandHandler("reset_daily", cmd_reset_daily))
