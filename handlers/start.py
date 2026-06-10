# handlers/start.py

from aiogram import Dispatcher, types
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

# Команда /start
async def cmd_start(message: types.Message):
    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        InlineKeyboardButton("Дуэль", callback_data="duel"),
        InlineKeyboardButton("Профиль", callback_data="profile"),
        InlineKeyboardButton("Помощь", callback_data="help")
    )
    await message.answer("Привет! Выберите действие:", reply_markup=keyboard)

# Команда /help
async def cmd_help(message: types.Message):
    text = (
        "Список команд и действий:\n"
        "/start - Главное меню\n"
        "/help - Подсказки\n"
        "Кнопка 'Дуэль' - начать дуэль\n"
        "Кнопка 'Профиль' - ваш профиль и игровой ID"
    )
    await message.answer(text)

# Регистрация обработчиков
def register_start_handlers(dp: Dispatcher):
    dp.register_message_handler(cmd_start, commands=["start"])
    dp.register_message_handler(cmd_help, commands=["help"])# Исправленный код start.py с кнопкой Дуэль и help
