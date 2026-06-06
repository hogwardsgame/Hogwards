from telegram import Update
from telegram.ext import ContextTypes, CommandHandler, MessageHandler, filters
from database import get_user, get_user_stats, get_spells_count, user_exists
from utils.i18n import t
from utils.helpers import xp_needed_for_level, house_emoji


async def show_profile(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not user_exists(user_id):
        await update.message.reply_text(t(user_id, "not_registered"))
        return

    user = get_user(user_id)
    stats = get_user_stats(user_id)
    spells_count = get_spells_count(user_id)
    xp_needed = xp_needed_for_level(user["level"])
    house = user["house"]

    header = t(user_id, "profile_header", wizard_name=user["wizard_name"])
    body = t(
        user_id, "profile_body",
        house_emoji=house_emoji(house),
        house=t(user_id, f"house_{house}"),
        level=user["level"],
        hp=user["hp"], max_hp=user["max_hp"],
        mana=user["mana"], max_mana=user["max_mana"],
        attack=user["attack"], defense=user["defense"],
        speed=user["speed"], luck=user["luck"],
        xp=user["xp"], xp_needed=xp_needed,
        gold=user["gold"],
        spells_count=spells_count,
        pvp_total=stats["pvp_total"] if stats else 0,
        pvp_wins=stats["pvp_wins"] if stats else 0,
    )
    await update.message.reply_text(f"{header}\n{body}", parse_mode="Markdown")


async def handle_profile_button(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if update.message.text == t(user_id, "btn_profile"):
        await show_profile(update, ctx)


def register_profile_handlers(app):
    app.add_handler(CommandHandler("profile", show_profile))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_profile_button), group=1)
