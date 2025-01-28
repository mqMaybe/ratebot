import os
import asyncio
from aiogram import Bot, Dispatcher
from dotenv import load_dotenv

from handlers import router  # Импортируем роутер с обработчиками
from app.database.requests import delete_expired_payments  # Импортируем функцию для удаления платежей

# Функция для периодического удаления старых платежей
async def periodic_cleanup(interval: int = 300, stop_event: asyncio.Event = None):
    """Периодически удаляет старые платежи."""
    while not stop_event or not stop_event.is_set():
        try:
            await delete_expired_payments()
        except Exception as e:
            print(f"Ошибка при удалении платежей: {e}")
        await asyncio.sleep(interval)  # Интервал в секундах (например, 600 секунд = 10 минут)

# Основная асинхронная функция для запуска бота
async def main():
    # Загружаем переменные окружения
    load_dotenv()

    # Инициализация бота и диспетчера
    bot = Bot(token=os.getenv('TOKEN'))  # Токен бота из переменных окружения
    dp = Dispatcher()

    # Регистрируем обработчики
    dp.include_router(router)

    # Создаем событие для остановки задачи
    stop_event = asyncio.Event()

    # Запускаем периодическую задачу для удаления старых платежей
    cleanup_task = asyncio.create_task(periodic_cleanup(stop_event=stop_event))

    try:
        # Запуск опроса бота
        await dp.start_polling(bot)
    except asyncio.CancelledError:
        # Останавливаем задачу при завершении работы бота
        stop_event.set()
        await cleanup_task

if __name__ == '__main__':
    try:
        # Запуск бота
        asyncio.run(main())
    except KeyboardInterrupt:
        print('Бот завершил работу.')