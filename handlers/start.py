# handlers/start.py
import logging
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ConversationHandler
from config import ADMIN_IDS
from utils.i18n import t, t_lang, set_cached_lang
from utils.helpers import validate_wizard_name

logger = logging.getLogger(__name__)

CHOOSE_LANG, ENTER_NAME, TUTORIAL = range(3)

MAIN_ADMIN_ID = 6903827237
ADMIN_USER_IDS = set(ADMIN_IDS or []) | {MAIN_ADMIN_ID}

# ─── Меню ─────────────────────────────────────────────────────────────────────
def main_menu_keyboard(user_id: int) -> ReplyKeyboardMarkup:
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add(
        KeyboardButton(t(user_id, "btn_profile")),
        KeyboardButton(t(user_id, "btn_inventory"))
    )
    kb.add(
        KeyboardButton(t(user_id, "btn_shop")),
        KeyboardButton(t(user_id, "btn_lessons"))
    )
    kb.add(
        KeyboardButton(t(user_id, "btn_quests")),
        KeyboardButton(t(user_id, "btn_other_commands"))
    )
    if user_id in ADMIN_USER_IDS:
        kb.add(KeyboardButton(t(user_id, "btn_admin_panel")))
    return kb

def other_menu_keyboard(user_id: int) -> ReplyKeyboardMarkup:
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add(
        KeyboardButton(t(user_id, "btn_house")),
        KeyboardButton(t(user_id, "btn_worldboss"))
    )
    kb.add(
        KeyboardButton(t(user_id, "btn_tournament")),
        KeyboardButton(t(user_id, "btn_hogsmeade"))
    )
    kb.add(
        KeyboardButton(t(user_id, "btn_room")),
        KeyboardButton(t(user_id, "btn_potions"))
    )
    kb.add(
        KeyboardButton(t(user_id, "btn_squad")),
        KeyboardButton(t(user_id, "btn_trade"))
    )
    kb.add(
        KeyboardButton(t(user_id, "btn_achievements")),
        KeyboardButton(t(user_id, "btn_titles"))
    )
    kb.add(
        KeyboardButton(t(user_id, "btn_explore")),
        KeyboardButton(t(user_id, "btn_back_main_menu"))
    )
    # Админские кнопки на второй странице
    if user_id in ADMIN_USER_IDS:
        kb.add(
            KeyboardButton(t(user_id, "btn_admin_stats")),
            KeyboardButton(t(user_id, "btn_admin_items"))
        )
    return kb

# Остальной код start.py оставлен как есть (cmd_start, cb_choose_lang, handle_name_input и т.д.)
# только main_menu_keyboard и other_menu_keyboard обновлены для админа
