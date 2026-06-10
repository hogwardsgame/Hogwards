# bot.py
import logging
from telegram.ext import ApplicationBuilder
from handlers.start import register_start_handlers
from handlers.settings import register_settings_handlers

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

def main():
    # Вставьте сюда ваш токен
    TOKEN = "YOUR_BOT_TOKEN"

    # Создаем приложение бота
    app = ApplicationBuilder().token(TOKEN).build()

    # Подключаем все хендлеры
    register_start_handlers(app)
    register_settings_handlers(app)

    # Запуск бота
    logger.info("Bot started...")
    app.run_polling()

if __name__ == "__main__":
    main()
