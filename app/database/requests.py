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
    'port': 3306 # Порт MySQL
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
async def set_user(user_id, first_name, username=None):
    """Создает или обновляет пользователя в базе данных."""
    async with await get_db_connection() as connection:
        async with connection.cursor(aiomysql.DictCursor) as cursor:
            try:
                await cursor.execute(
                    """
                    INSERT INTO users (tg_id, first_name, username)
                    VALUES (%s, %s, %s)
                    ON DUPLICATE KEY UPDATE
                    first_name = VALUES(first_name),
                    username = VALUES(username)
                    """,
                    (user_id, first_name, username)
                )
                await connection.commit()
                return True
            except Exception as e:
                await connection.rollback()
                raise

# Функция для получения пользователя по токену
async def get_user_by_token(token):
    """Возвращает пользователя по токену."""
    connection = await get_db_connection()
    cursor = await connection.cursor(aiomysql.DictCursor)

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
    cursor = await connection.cursor(aiomysql.DictCursor)

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
    cursor = await connection.cursor(aiomysql.DictCursor)

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
    cursor = await connection.cursor(aiomysql.DictCursor)

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
    cursor = await connection.cursor(aiomysql.DictCursor)

    try:
        # Извлекаем пользователя по tg_id
        await cursor.execute("SELECT link_token, link_created_at FROM users WHERE tg_id = %s", (user_id,))
        user = await cursor.fetchone()

        if user and user['link_token']:  # Обращаемся по имени поля
            # Рассчитываем время окончания действия токена
            expiration_time = user['link_created_at'] + timedelta(weeks=1)  # Обращаемся по имени поля

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
async def save_payment(user_id, amount, transaction_id, payment_url, access_start, access_end, period, is_vip=False):
    """Сохраняет информацию о платеже."""
    async with await get_db_connection() as connection:
        async with connection.cursor(aiomysql.DictCursor) as cursor:
            try:
                await cursor.execute(
                    """
                    INSERT INTO payments (user_id, amount, transaction_id, payment_url, access_start, access_end, period, is_vip, status, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'pending', NOW())
                    """,
                    (user_id, amount, transaction_id, payment_url, access_start, access_end, period, is_vip)
                )
                await connection.commit()
                return True
            except Exception as e:
                await connection.rollback()
                raise

# Функция для получения ссылки на оплату
async def get_payment_url(user_id):
    """Возвращает ссылку на оплату для пользователя."""
    connection = await get_db_connection()
    cursor = await connection.cursor(aiomysql.DictCursor)

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
    cursor = await connection.cursor(aiomysql.DictCursor)

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

async def has_active_access(user_id: int) -> bool:
    """Проверяет, есть ли у пользователя активная подписка."""
    connection = await get_db_connection()
    cursor = await connection.cursor(aiomysql.DictCursor)

    try:
        await cursor.execute(
            """
            SELECT * FROM payments 
            WHERE user_id = %s 
              AND access_end > NOW() 
              AND status = 'success' 
            ORDER BY access_end DESC 
            LIMIT 1
            """,
            (user_id,)
        )
        active_payment = await cursor.fetchone()
        return active_payment is not None
    except Exception as e:
        raise
    finally:
        await cursor.close()
        connection.close()

async def get_subscription_time_left(user_id):
    """Возвращает оставшееся время подписки в днях, часах и минутах."""
    connection = await get_db_connection()
    cursor = await connection.cursor(aiomysql.DictCursor)
    try:
        # Получаем самую позднюю активную подписку
        await cursor.execute(
            "SELECT access_end FROM payments WHERE user_id = %s AND access_end > NOW() ORDER BY access_end DESC LIMIT 1",
            (user_id,)
        )
        subscription = await cursor.fetchone()

        if subscription:
            access_end = subscription['access_end']  # Дата окончания подписки
            now = datetime.now()
            time_left = access_end - now  # Оставшееся время

            # Преобразуем время в дни, часы и минуты
            days_left = time_left.days
            hours_left, remainder = divmod(time_left.seconds, 3600)
            minutes_left, _ = divmod(remainder, 60)

            return {
                "days": days_left,
                "hours": hours_left,
                "minutes": minutes_left
            }
        else:
            return None  # Если активной подписки нет
    except Exception as e:
        raise
    finally:
        await cursor.close()
        connection.close()

async def update_payment_status(transaction_id, new_status):
    """Обновляет статус платежа."""
    connection = await get_db_connection()
    cursor = await connection.cursor(aiomysql.DictCursor)

    try:
        await cursor.execute(
            "UPDATE payments SET status = %s WHERE transaction_id = %s",
            (new_status, transaction_id)
        )
        await connection.commit()
        return True
    except Exception as e:
        await connection.rollback()
        raise
    finally:
        await cursor.close()
        connection.close()

async def is_payment_successful(user_id: int) -> bool:
    """Проверяет, есть ли у пользователя успешный платеж."""
    connection = await get_db_connection()
    cursor = await connection.cursor(aiomysql.DictCursor)

    try:
        await cursor.execute(
            """
            SELECT status FROM payments 
            WHERE user_id = %s AND status = 'success' 
            ORDER BY id DESC 
            LIMIT 1
            """,
            (user_id,)
        )
        payment = await cursor.fetchone()
        return payment is not None  # Возвращает True, если есть успешный платеж
    except Exception as e:
        print(f"Ошибка при проверке статуса платежа: {e}")
        raise
    finally:
        await cursor.close()
        connection.close()

async def is_payment_expired(transaction_id: str) -> bool:
    """Проверяет, истекло ли время жизни платежа."""
    connection = await get_db_connection()
    cursor = await connection.cursor(aiomysql.DictCursor)

    try:
        await cursor.execute(
            """
            SELECT created_at, status FROM payments 
            WHERE transaction_id = %s
            """,
            (transaction_id,)
        )
        payment = await cursor.fetchone()

        if payment:
            created_at = payment['created_at']
            status = payment['status']

            # Если платеж не оплачен и создан более 10 минут назад
            if status == 'pending' and datetime.now() - created_at > timedelta(minutes=10):
                return True  # Платеж истек
        return False  # Платеж не истек
    except Exception as e:
        raise
    finally:
        await cursor.close()
        connection.close()


async def delete_expired_payments(interval_minutes: int = 5) -> int:
    """Удаляет платежи, которые не были оплачены в течение указанного интервала,
    а также платежи, у которых закончилась подписка.
    Возвращает количество удаленных записей."""
    async with await get_db_connection() as connection:
        async with connection.cursor(aiomysql.DictCursor) as cursor:
            try:
                # Удаляем платежи, которые не были оплачены в течение указанного интервала
                # ИЛИ у которых закончилась подписка
                await cursor.execute(
                    """
                    DELETE FROM payments 
                    WHERE (status = 'pending' AND created_at < NOW() - INTERVAL %s MINUTE)
                       OR (access_end < NOW())
                    """,
                    (interval_minutes,)
                )
                await connection.commit()
            except Exception as e:
                await connection.rollback()
                return 0
            
async def get_active_payment(user_id):
    """Получает активный платеж пользователя, если он существует."""
    async with await get_db_connection() as connection:
        async with connection.cursor(aiomysql.DictCursor) as cursor:
            await cursor.execute(
                """
                SELECT payment_url FROM payments 
                WHERE user_id = %s 
                AND status = 'pending'
                LIMIT 1
                """,
                (user_id,)
            )
            return await cursor.fetchone()
        
async def delete_active_payment(user_id):
    """Удаляет активный платеж пользователя."""
    async with await get_db_connection() as connection:
        async with connection.cursor(aiomysql.DictCursor) as cursor:
            try:
                await cursor.execute(
                    """
                    DELETE FROM payments 
                    WHERE user_id = %s 
                    AND status = 'pending'
                    """,
                    (user_id,)
                )
                await connection.commit()
                return True
            except Exception as e:
                await connection.rollback()
                raise

async def get_voters(user_id):
    """Возвращает список пользователей, которые оценили текущего пользователя, и их оценки."""
    async with await get_db_connection() as connection:
        async with connection.cursor(aiomysql.DictCursor) as cursor:
            await cursor.execute(
                """
                SELECT u.first_name, u.username, r.score 
                FROM ratings r
                JOIN users u ON r.rater_user_id = u.tg_id
                WHERE r.rated_user_id = %s
                """,
                (user_id,)
            )
            return await cursor.fetchall()
        
async def check_vip_status(user_id):
    """Проверяет, есть ли у пользователя активная VIP-подписка."""
    async with await get_db_connection() as connection:
        async with connection.cursor(aiomysql.DictCursor) as cursor:
            try:
                await cursor.execute(
                    """
                    SELECT id FROM payments 
                    WHERE user_id = %s 
                    AND is_vip = TRUE 
                    AND access_end > NOW() 
                    AND status = 'success'
                    LIMIT 1
                    """,
                    (user_id,)
                )
                result = await cursor.fetchone()
                return bool(result)  # Возвращаем True, если есть активная VIP-подписка
            except Exception as e:
                return False

async def get_total_users():
    """Возвращает общее количество пользователей, зашедших в бота."""
    async with await get_db_connection() as connection:
        async with connection.cursor(aiomysql.DictCursor) as cursor:
            await cursor.execute("SELECT COUNT(*) as total FROM users")
            result = await cursor.fetchone()
            return result.get('total', 0)

async def get_users_with_links():
    """Возвращает количество пользователей, сгенерировавших ссылку."""
    async with await get_db_connection() as connection:
        async with connection.cursor(aiomysql.DictCursor) as cursor:
            await cursor.execute("SELECT COUNT(DISTINCT user_id) as total FROM payments")
            result = await cursor.fetchone()
            return result.get('total', 0)

async def get_payment_stats():
    """Возвращает статистику по оплаченным тарифам."""
    async with await get_db_connection() as connection:
        async with connection.cursor(aiomysql.DictCursor) as cursor:
            await cursor.execute(
                """
                SELECT 
                    SUM(CASE WHEN is_vip = FALSE AND status = 'success' THEN 1 ELSE 0 END) as normal_payments,
                    SUM(CASE WHEN is_vip = TRUE AND status = 'success' THEN 1 ELSE 0 END) as vip_payments
                FROM payments
                """
            )
            result = await cursor.fetchone()
            return result
        
async def is_admin(tg_id):
    async with await get_db_connection() as connection:
        async with connection.cursor(aiomysql.DictCursor) as cursor:
            await cursor.execute(
                """
                SELECT id from users
                WHERE tg_id = %s
                AND is_admin = TRUE
                """,
                (tg_id,)
            )
            result = await cursor.fetchone()
            return result
        
async def get_subscription_price(period, is_vip=False):
    """Возвращает цену подписки для указанного периода и типа (VIP или обычный)."""
    async with await get_db_connection() as connection:
        async with connection.cursor(aiomysql.DictCursor) as cursor:
            await cursor.execute(
                "SELECT price FROM subscription_prices WHERE period = %s AND is_vip = %s",
                (period, is_vip)
            )
            result = await cursor.fetchone()
            return result['price'] if result else None

async def update_subscription_price(period, price, is_vip=False):
    """Обновляет цену на подписку для указанного периода и удаляет старые записи."""
    async with await get_db_connection() as connection:
        async with connection.cursor(aiomysql.DictCursor) as cursor:
            try:
                # Начало транзакции
                await connection.begin()

                # Проверка существования записи
                await cursor.execute(
                    "SELECT price FROM subscription_prices WHERE period = %s AND is_vip = %s",
                    (period, is_vip)
                )
                existing_record = await cursor.fetchone()

                if existing_record:
                    existing_price = existing_record['price']
                    if existing_price != price:
                        # Если цена отличается, обновляем запись и удаляем старые
                        await cursor.execute(
                            """
                            UPDATE subscription_prices
                            SET price = %s
                            WHERE period = %s AND is_vip = %s
                            """,
                            (price, period, is_vip)
                        )
                        await cursor.execute(
                            """
                            DELETE FROM subscription_prices
                            WHERE period = %s AND is_vip = %s AND price != %s
                            """,
                            (period, is_vip, price)
                        )
                    else:
                        # Если цена совпадает, ничего не делаем
                        await connection.commit()
                        return True
                else:
                    # Если записи не существует, создаем новую
                    await cursor.execute(
                        """
                        INSERT INTO subscription_prices (period, price, is_vip)
                        VALUES (%s, %s, %s)
                        """,
                        (period, price, is_vip)
                    )

                # Фиксация транзакции
                await connection.commit()
                return True
            except Exception as e:
                # Откат транзакции в случае ошибки
                await connection.rollback()
                raise e
            
async def get_total_spent_on_subscriptions():
    """Возвращает общую сумму, потраченную на обычные и VIP-подписки (только успешные платежи)."""
    async with await get_db_connection() as connection:
        async with connection.cursor(aiomysql.DictCursor) as cursor:
            # Сумма для обычных подписок (только успешные платежи)
            await cursor.execute(
                """
                SELECT SUM(amount) as total_normal 
                FROM payments 
                WHERE is_vip = FALSE AND status = 'success'
                """
            )
            total_normal = await cursor.fetchone()
            total_normal = total_normal.get('total_normal', 0) or 0

            # Сумма для VIP-подписок (только успешные платежи)
            await cursor.execute(
                """
                SELECT SUM(amount) as total_vip 
                FROM payments 
                WHERE is_vip = TRUE AND status = 'success'
                """
            )
            total_vip = await cursor.fetchone()
            total_vip = total_vip.get('total_vip', 0) or 0

            return {
                'total_normal': total_normal,
                'total_vip': total_vip,
                'total': total_normal + total_vip
            }