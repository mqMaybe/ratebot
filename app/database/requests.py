import aiomysql
from datetime import timedelta, datetime
import os
from dotenv import load_dotenv

# Загружаем переменные окружения из файла .env
load_dotenv()

# Настройки подключения к базе данных
db_config = {
    'host': os.getenv('DB_HOST'),  # Адрес сервера MySQL
    'user': os.getenv('DB_USER'),  # Имя пользователя MySQL
    'password': os.getenv('DB_PASSWORD'),  # Пароль пользователя MySQL
    'db': os.getenv('DB_NAME'),  # Имя базы данных
    'port': int(os.getenv('MYSQL_PORT', 3306))  # Порт MySQL (по умолчанию 3306)
}

# Функция для подключения к базе данных
async def get_db_connection():
    """Возвращает асинхронное подключение к базе данных."""
    try:
        connection = await aiomysql.connect(**db_config)
        return connection
    except Exception as e:
        raise

# Функция для создания или получения пользователя
async def set_user(tg_id, first_name):
    """Создает или возвращает пользователя по tg_id."""
    connection = await get_db_connection()
    cursor = await connection.cursor()

    try:
        # Проверяем, существует ли пользователь с указанным tg_id
        await cursor.execute("SELECT * FROM users WHERE tg_id = %s", (tg_id,))
        user = await cursor.fetchone()

        if not user:
            # Если пользователь не найден, создаем нового
            await cursor.execute(
                "INSERT INTO users (tg_id, link_token, first_name) VALUES (%s, %s, %s)",
                (tg_id, '', first_name)
            )
            await connection.commit()
            return True
        else:
            return False
    except Exception as e:
        await connection.rollback()
        raise
    finally:
        await cursor.close()
        connection.close()

# Функция для получения пользователя по токену
async def get_user_by_token(token):
    """Возвращает пользователя по токену."""
    connection = await get_db_connection()
    cursor = await connection.cursor()

    try:
        await cursor.execute("SELECT * FROM users WHERE link_token = %s", (token,))
        user = await cursor.fetchone()
        return user
    except Exception as e:
        raise
    finally:
        await cursor.close()
        connection.close()

# Функция для сохранения рейтинга
async def save_rating(rater_user_id, rated_user_id, score):
    """Сохраняет оценку, которую один пользователь поставил другому."""
    connection = await get_db_connection()
    cursor = await connection.cursor()

    try:
        # Проверяем, существует ли уже такая оценка
        await cursor.execute(
            "SELECT * FROM ratings WHERE rater_user_id = %s AND rated_user_id = %s",
            (rater_user_id, rated_user_id)
        )
        existing_rating = await cursor.fetchone()

        if existing_rating:
            return False

        # Сохраняем новую оценку
        await cursor.execute(
            "INSERT INTO ratings (rated_user_id, rater_user_id, score) VALUES (%s, %s, %s)",
            (rated_user_id, rater_user_id, score)
        )
        await connection.commit()
        return True
    except Exception as e:
        await connection.rollback()
        raise
    finally:
        await cursor.close()
        connection.close()

# Функция для получения всех рейтингов для пользователя
async def get_ratings_for_user(user_id):
    """Возвращает все оценки, которые получил пользователь."""
    connection = await get_db_connection()
    cursor = await connection.cursor()

    try:
        await cursor.execute("SELECT * FROM ratings WHERE rated_user_id = %s", (user_id,))
        ratings = await cursor.fetchall()
        return ratings
    except Exception as e:
        raise
    finally:
        await cursor.close()
        connection.close()

# Проверка на повторную оценку
async def get_existing_rating(rater_user_id, rated_user_id):
    """Проверяет, существует ли уже оценка от одного пользователя другому."""
    connection = await get_db_connection()
    cursor = await connection.cursor()

    try:
        await cursor.execute(
            "SELECT * FROM ratings WHERE rater_user_id = %s AND rated_user_id = %s",
            (rater_user_id, rated_user_id)
        )
        existing_rating = await cursor.fetchone()
        return existing_rating
    except Exception as e:
        raise
    finally:
        await cursor.close()
        connection.close()

# Функция для получения статистики (средний балл и количество оценок) за указанный период
async def get_statistics(user_id, period):
    """Возвращает средний балл и количество оценок за указанный период."""
    connection = await get_db_connection()
    cursor = await connection.cursor()

    try:
        # Определяем временной интервал
        now = datetime.now()
        if period == "day":
            start_time = now - timedelta(days=1)
        elif period == "week":
            start_time = now - timedelta(weeks=1)
        elif period == "month":
            start_time = now - timedelta(days=30)
        else:
            raise ValueError("Некорректный период")

        # Запрашиваем статистику
        await cursor.execute(
            "SELECT AVG(score), COUNT(id) FROM ratings WHERE rated_user_id = %s AND created_at >= %s",
            (user_id, start_time)
        )
        stats = await cursor.fetchone()
        return stats
    except Exception as e:
        raise
    finally:
        await cursor.close()
        connection.close()

# Проверка, действителен ли токен (срок действия токена — 1 неделя)
async def is_token_valid(user_id):
    """Проверяет, действителен ли токен пользователя."""
    connection = await get_db_connection()
    cursor = await connection.cursor()

    try:
        # Извлекаем пользователя по tg_id
        await cursor.execute("SELECT * FROM users WHERE tg_id = %s", (user_id,))
        user = await cursor.fetchone()

        if user and user['link_token']:
            # Рассчитываем время окончания действия токена
            expiration_time = user['link_created_at'] + timedelta(weeks=1)

            # Сравниваем с текущим временем
            if expiration_time > datetime.now():
                return True  # Токен действителен
            else:
                # Если токен истек, очищаем его и дату создания
                await cursor.execute(
                    "UPDATE users SET link_token = NULL, link_created_at = NULL WHERE tg_id = %s",
                    (user_id,)
                )
                await connection.commit()
                return False  # Токен просрочен
        return False  # Если пользователь не найден или токен отсутствует
    except Exception as e:
        await connection.rollback()
        raise
    finally:
        await cursor.close()
        connection.close()

# Функция для сохранения платежа
async def save_payment(user_id, amount, transaction_id, payment_url):
    """Сохраняет информацию о платеже."""
    connection = await get_db_connection()
    cursor = await connection.cursor()

    try:
        # Проверяем, существует ли платеж с таким transaction_id
        await cursor.execute("SELECT * FROM payments WHERE transaction_id = %s", (transaction_id,))
        existing_payment = await cursor.fetchone()

        if existing_payment:
            return False

        # Сохраняем новый платеж
        await cursor.execute(
            "INSERT INTO payments (user_id, amount, transaction_id, payment_url) VALUES (%s, %s, %s, %s)",
            (user_id, amount, transaction_id, payment_url)
        )
        await connection.commit()
        return True
    except Exception as e:
        await connection.rollback()
        raise
    finally:
        await cursor.close()
        connection.close()

# Получение transaction_id по user_id
async def get_transaction_id_by_user_id(user_id):
    """Возвращает transaction_id по user_id."""
    connection = await get_db_connection()
    cursor = await connection.cursor()

    try:
        await cursor.execute(
            "SELECT transaction_id FROM payments WHERE user_id = %s ORDER BY id DESC LIMIT 1",
            (user_id,)
        )
        payment = await cursor.fetchone()
        return payment[0] if payment else None
    except Exception as e:
        raise
    finally:
        await cursor.close()
        connection.close()

# Функция для получения ссылки на оплату
async def get_payment_url(user_id):
    """Возвращает ссылку на оплату для пользователя."""
    connection = await get_db_connection()
    cursor = await connection.cursor()

    try:
        await cursor.execute(
            "SELECT payment_url FROM payments WHERE user_id = %s ORDER BY id DESC LIMIT 1",
            (user_id,)
        )
        payment = await cursor.fetchone()
        return payment[0] if payment else None
    except Exception as e:
        raise
    finally:
        await cursor.close()
        connection.close()

# Функция для получения последнего платежа пользователя
async def get_last_payment(user_id):
    """Возвращает последний платеж пользователя."""
    connection = await get_db_connection()
    cursor = await connection.cursor()

    try:
        await cursor.execute(
            "SELECT * FROM payments WHERE user_id = %s ORDER BY id DESC LIMIT 1",
            (user_id,)
        )
        payment = await cursor.fetchone()
        return payment
    except Exception as e:
        raise
    finally:
        await cursor.close()
        connection.close()