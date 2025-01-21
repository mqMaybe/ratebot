import random
import string
from datetime import datetime
from app.database.requests import get_db_connection

async def generate_unique_link(user_id):
    # Генерация случайного токена
    token = ''.join(random.choices(string.ascii_letters + string.digits, k=8))

    # Подключение к базе данных
    connection = await get_db_connection()
    cursor = await connection.cursor()

    try:
        # Проверка уникальности токена
        while True:
            await cursor.execute("SELECT * FROM users WHERE link_token = %s", (token,))
            existing_user = await cursor.fetchone()

            if not existing_user:
                break  # Токен уникален, выходим из цикла
            else:
                # Генерируем новый токен, если текущий не уникален
                token = ''.join(random.choices(string.ascii_letters + string.digits, k=8))

        # Поиск пользователя по tg_id
        await cursor.execute("SELECT * FROM users WHERE tg_id = %s", (user_id,))
        user = await cursor.fetchone()

        if user:
            # Устанавливаем новый токен и сохраняем в базе данных
            await cursor.execute(
                "UPDATE users SET link_token = %s, link_created_at = %s WHERE tg_id = %s",
                (token, datetime.now(), user_id)
            )
            await connection.commit()
            return f"https://t.me/PeopleRatingsBot?start=rate_{token}"
        else:
            raise ValueError("Пользователь не найден")
    except Exception as e:
        await connection.rollback()
        raise e
    finally:
        await cursor.close()
        connection.close()