from telegram import Update
from telegram.ext import ContextTypes, CommandHandler, MessageHandler, filters
from database import get_leaderboard, get_house_points, user_exists
from utils.i18n import t
from utils.helpers import house_emoji, medal


async def show_rating(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not await user_exists(user_id):
        await update.message.reply_text(t(user_id, "not_registered"))
        return

    rows = await get_leaderboard(10)
    text = t(user_id, "rating_header")
    for i, row in enumerate(rows, 1):
        emoji = house_emoji(row["house"])
        text += t(user_id, "rating_row",
                  pos=medal(i), emoji=emoji,
                  wizard_name=row["wizard_name"],
                  level=row["level"]) + "\n"

    await update.message.reply_text(text)


async def show_house_cup(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    rows = await get_house_points()
    text = t(user_id, "house_cup_header")
    for i, row in enumerate(rows, 1):
        house = row["house"]
        text += t(user_id, "house_cup_row",
                  pos=medal(i),
                  emoji=house_emoji(house),
                  house=t(user_id, f"house_{house}"),
                  points=row["points"]) + "\n"
    await update.message.reply_text(text)


async def handle_rating_button(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if update.message.text == t(user_id, "btn_rating"):
        await show_rating(update, ctx)


def register_rating_handlers(app):
    app.add_handler(CommandHandler("rating", show_rating))
    app.add_handler(CommandHandler("housecup", show_house_cup))
    app.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND,
        handle_rating_button
    ), group=2)
