import os
import asyncio
from aiogram import Bot, Dispatcher
from dotenv import load_dotenv

from handlers import router  # Импортируем роутер с обработчиками

# Основная асинхронная функция для запуска бота
async def main():
    # Загружаем переменные окружения
    load_dotenv()

    # Инициализация бота и диспетчера
    bot = Bot(token=os.getenv('TOKEN'))  # Токен бота из переменных окружения
    dp = Dispatcher()

    # Регистрируем обработчики
    dp.include_router(router)

    # Запуск опроса бота
    await dp.start_polling(bot)

if __name__ == '__main__':
    try:
        # Запуск бота
        asyncio.run(main())
    except KeyboardInterrupt:
        print('Бот завершил работу.')