"""
Система картинок бота.
Картинки хранятся как Telegram file_id в bot_settings (key = 'image:<slot>').
Админ загружает картинку через панель → бот запоминает file_id → показывает
её на нужных экранах. Если картинка не загружена — экран работает как раньше (текст).
"""
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler, MessageHandler, filters
from config import ADMIN_IDS
from database import get_setting, set_setting

logger = logging.getLogger(__name__)

def _is_admin(uid: int) -> bool:
    return bool(ADMIN_IDS) and uid in ADMIN_IDS

# ── Слоты картинок: ключ → (эмодзи+название, описание для чего) ───────────────
IMAGE_SLOTS = {
    # Баннеры экранов
    "main_menu":  ("🏰 Главное меню",      "Приветственный баннер замка"),
    "profile":    ("📜 Профиль",           "Паспорт волшебника"),
    "duel":       ("⚔️ Дуэли",             "Арена дуэлей"),
    "shop":       ("🏪 Магазин",           "Магическая лавка"),
    "pets":       ("🐾 Питомцы",           "Лавка волшебных существ"),
    "inventory":  ("🎒 Инвентарь",         "Хранилище сокровищ"),
    "forest":     ("🌲 Запретный лес",     "Тёмный лес"),
    "worldboss":  ("🐉 Мировой босс",      "Эпическая арена босса"),
    # Гербы факультетов
    "house_red":    ("🦁 Факультет (лев)",   "Герб красно-золотого факультета"),
    "house_green":  ("🐍 Факультет (змея)",  "Герб зелёно-серебряного факультета"),
    "house_blue":   ("🦅 Факультет (орёл)",  "Герб сине-бронзового факультета"),
    "house_yellow": ("🦡 Факультет (барсук)","Герб жёлто-чёрного факультета"),
    # Боссы
    "boss_basilisk": ("🐍 Босс: Василиск",  "Древний василиск"),
    "boss_dragon":   ("🐉 Босс: Дракон",    "Венгерская хвосторога"),
    "boss_wraith":   ("👻 Босс: Призрак",   "Тёмный призрак / дементор"),
}

# Маппинг факультета на слот картинки
HOUSE_IMAGE_MAP = {
    "gryffindor": "house_red",
    "slytherin":  "house_green",
    "ravenclaw":  "house_blue",
    "hufflepuff": "house_yellow",
}

def get_image(slot: str) -> str | None:
    """Вернуть file_id картинки слота или None если не загружена."""
    try:
        return get_setting(f"image:{slot}", None)
    except Exception:
        return None

async def send_with_image(bot, chat_id: int, slot: str, caption: str,
                          reply_markup=None, parse_mode="Markdown"):
    """Отправить сообщение с картинкой если она есть, иначе обычный текст.
    Telegram ограничивает подпись к фото 1024 символами — длинный текст
    отправляется как фото + отдельное сообщение.
    """
    file_id = get_image(slot)
    if file_id:
        try:
            if len(caption) <= 1024:
                await bot.send_photo(chat_id, file_id, caption=caption,
                                     parse_mode=parse_mode, reply_markup=reply_markup)
            else:
                # Слишком длинно для подписи — фото отдельно, текст отдельно
                await bot.send_photo(chat_id, file_id)
                await bot.send_message(chat_id, caption, parse_mode=parse_mode,
                                       reply_markup=reply_markup)
            return
        except Exception as e:
            logger.warning("send_with_image %s: %s", slot, e)
    # Фолбэк — просто текст
    await bot.send_message(chat_id, caption, parse_mode=parse_mode, reply_markup=reply_markup)

async def reply_with_image(message, slot: str, caption: str,
                           reply_markup=None, parse_mode="Markdown"):
    """Версия для ответа на message (использует chat_id из message)."""
    await send_with_image(message.get_bot(), message.chat_id, slot, caption,
                          reply_markup, parse_mode)

# ── Админская загрузка картинок ───────────────────────────────────────────────
def _slots_keyboard() -> InlineKeyboardMarkup:
    buttons = []
    for slot, (label, _) in IMAGE_SLOTS.items():
        status = "✅" if get_image(slot) else "⬜"
        buttons.append([InlineKeyboardButton(f"{status} {label}", callback_data=f"img_set:{slot}")])
    return InlineKeyboardMarkup(buttons)

async def cmd_images(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not _is_admin(update.effective_user.id):
        return
    loaded = sum(1 for s in IMAGE_SLOTS if get_image(s))
    await update.message.reply_text(
        f"🖼️ *Картинки бота*\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"Загружено: {loaded}/{len(IMAGE_SLOTS)}\n\n"
        f"✅ — картинка загружена, ⬜ — пусто.\n"
        f"Нажми на слот и пришли картинку, чтобы её установить.",
        parse_mode="Markdown",
        reply_markup=_slots_keyboard()
    )

async def cb_img_set(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not _is_admin(query.from_user.id):
        await query.answer("Нет доступа.", show_alert=True)
        return
    await query.answer()
    slot = query.data.split(":")[1]
    if slot not in IMAGE_SLOTS:
        await query.message.reply_text("Слот не найден.")
        return
    ctx.user_data["awaiting_image_slot"] = slot
    label, desc = IMAGE_SLOTS[slot]
    cur = "✅ загружена" if get_image(slot) else "⬜ пусто"
    text = (
        f"🖼️ {label}\n"
        f"{desc}\n\n"
        f"Текущее состояние: {cur}\n\n"
        f"📤 Пришли мне картинку (фото) — я установлю её на этот слот.\n"
        f"Для отмены — /cancel_img"
    )
    markup = InlineKeyboardMarkup([[
        InlineKeyboardButton("🗑️ Удалить картинку", callback_data=f"img_del:{slot}"),
        InlineKeyboardButton("◀️ Назад", callback_data="img_back"),
    ]])
    # Отправляем НОВОЕ сообщение (надёжнее, чем edit — не зависит от типа исходного)
    try:
        await query.message.reply_text(text, reply_markup=markup)
    except Exception as e:
        logger.warning("cb_img_set reply: %s", e)
        await query.message.reply_text(
            f"Слот «{label}» выбран. Пришли картинку для установки. Отмена: /cancel_img"
        )

async def cb_img_del(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not _is_admin(query.from_user.id):
        await query.answer("Нет доступа.", show_alert=True)
        return
    slot = query.data.split(":")[1]
    set_setting(f"image:{slot}", "")
    ctx.user_data.pop("awaiting_image_slot", None)
    await query.answer("🗑️ Картинка удалена.")
    loaded = sum(1 for s in IMAGE_SLOTS if get_image(s))
    await query.message.reply_text(
        f"🖼️ Картинки бота\nЗагружено: {loaded}/{len(IMAGE_SLOTS)}\n\nВыбери слот:",
        reply_markup=_slots_keyboard()
    )

async def cb_img_back(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    ctx.user_data.pop("awaiting_image_slot", None)
    loaded = sum(1 for s in IMAGE_SLOTS if get_image(s))
    await query.message.reply_text(
        f"🖼️ Картинки бота\nЗагружено: {loaded}/{len(IMAGE_SLOTS)}\n\nВыбери слот:",
        reply_markup=_slots_keyboard()
    )

async def handle_image_upload(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Ловит присланное админом фото для текущего слота."""
    if not _is_admin(update.effective_user.id):
        return
    slot = ctx.user_data.get("awaiting_image_slot")
    if not slot:
        return  # не в режиме загрузки — пропускаем
    if not update.message or not update.message.photo:
        return
    # Берём самое большое разрешение
    file_id = update.message.photo[-1].file_id
    set_setting(f"image:{slot}", file_id)
    ctx.user_data.pop("awaiting_image_slot", None)
    label = IMAGE_SLOTS.get(slot, (slot,))[0]
    await update.message.reply_text(
        f"✅ Картинка установлена на слот *{label}*!\n"
        f"Теперь она будет показываться на этом экране.",
        parse_mode="Markdown"
    )

async def cmd_cancel_img(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data.pop("awaiting_image_slot", None)
    await update.message.reply_text("Загрузка картинки отменена.")

def register_images_handlers(app):
    app.add_handler(CommandHandler("images", cmd_images))
    app.add_handler(CommandHandler("cancel_img", cmd_cancel_img))
    app.add_handler(CallbackQueryHandler(cb_img_set,  pattern=r"^img_set:"))
    app.add_handler(CallbackQueryHandler(cb_img_del,  pattern=r"^img_del:"))
    app.add_handler(CallbackQueryHandler(cb_img_back, pattern=r"^img_back$"))
    # Фото-загрузка от админа — отдельный handler в group=2 (до текстовых)
    app.add_handler(MessageHandler(filters.PHOTO, handle_image_upload), group=2)
