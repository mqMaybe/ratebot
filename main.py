import os
import asyncio
from aiogram import Bot, Dispatcher
from dotenv import load_dotenv

from handlers import router
from app.database.models import async_main

# Основная асинхронная функция для запуска бота
async def main():
    # Подключаемся к базе данных и загружаем настройки
    await async_main()
    load_dotenv()

    # Инициализация бота и диспетчера
    bot = Bot(token=os.getenv('TOKEN'))
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
        print('EXIT')