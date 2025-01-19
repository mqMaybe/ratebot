# Импортируем необходимые модули
from sqlalchemy import select
from sqlalchemy import func

from app.database.models import User, Ratings, Payments
from app.database.models import async_session
from app.utils.payments import check_payment_status

from datetime import timedelta, datetime

# Функция для создания или получения пользователя
async def set_user(tg_id, first_name):
    async with async_session() as session:
        # Проверяем, существует ли пользователь с указанным tg_id
        user = await session.scalar(select(User).where(User.tg_id == tg_id))
        
        if not user:
            # Если пользователь не найден, создаем нового пользователя
            new_user = User(tg_id=tg_id, link_token='', first_name=first_name)  # link_token будет установлен позже
            session.add(new_user)
            await session.commit()
            return new_user  # Возвращаем нового пользователя
        return user  # Возвращаем существующего пользователя

# Функция для получения пользователя по токену
async def get_user_by_token(token):
    async with async_session() as session:
        result = await session.execute(select(User).where(User.link_token == token))
        return result.scalars().first()  # Возвращаем первого найденного пользователя

# Функция для сохранения рейтинга
async def save_rating(rater_user_id: int, rated_user_id: int, score: int):
    async with async_session() as session:
        # Создаем новый объект рейтинга
        rating = Ratings(
            rated_user_id=rated_user_id,
            rater_user_id=rater_user_id,
            score=score
        )
        
        # Добавляем и сохраняем рейтинг в базе данных
        session.add(rating)
        await session.commit()

# Функция для получения всех рейтингов для пользователя
async def get_ratings_for_user(user_id: int):
    async with async_session() as session:
        result = await session.execute(select(Ratings).filter(Ratings.rated_user_id == user_id))
        return result.scalars().all()  # Возвращаем список всех рейтингов

# Проверка на повторную оценку
async def get_existing_rating(rater_user_id: int, rated_user_id: int, session):
    result = await session.execute(
        select(Ratings).filter(
            Ratings.rater_user_id == rater_user_id,
            Ratings.rated_user_id == rated_user_id
        )
    )
    return result.scalars().first()  # Возвращаем первый найденный рейтинг или None

# Функция для получения статистики (средний балл и количество оценок) за указанный период
async def get_statistics(user_id: int, period: str):
    async with async_session() as session:
        # Определяем временной интервал на основе переданного периода
        now = datetime.utcnow()
        if period == "day":
            start_time = now - timedelta(days=1)
        elif period == "week":
            start_time = now - timedelta(weeks=1)
        elif period == "month":
            start_time = now - timedelta(days=30)
        else:
            raise ValueError("Invalid period specified")  # Если период некорректен, выбрасываем исключение

        # Запрашиваем статистику за указанный период
        result = await session.execute(
            select(func.avg(Ratings.score).label("avg_score"), func.count(Ratings.id).label("total_ratings"))
            .where(Ratings.rated_user_id == user_id, Ratings.created_at >= start_time)
        )
        stats = result.fetchone()  # Получаем результаты запроса
        if stats:
            avg_score = stats[0]  # Средняя оценка
            total_ratings = stats[1]  # Общее количество оценок
            return avg_score, total_ratings
        else:
            return None, 0  # Если статистики нет, возвращаем None и 0

# Проверка, действителен ли токен (срок действия токена — 1 неделя)
async def is_token_valid(user_id):
    async with async_session() as session:
        # Извлекаем пользователя по tg_id
        result = await session.execute(select(User).where(User.tg_id == user_id))
        user = result.scalars().first()

        if user and user.link_token:
            # Рассчитываем время окончания действия токена
            expiration_time = user.link_created_at + timedelta(weeks=1)

            # Сравниваем с текущим временем
            if expiration_time > datetime.now():
                return True  # Токен действителен
            else:
                # Если токен истек, очищаем его и дату создания
                user.link_token = None
                user.link_created_at = None
                await session.commit()
                return False  # Токен просрочен
        return False  # Если пользователь не найден или токен отсутствует

# Функция для сохранения платежа
async def save_payment(user_id, amount, transaction_id, payment_url):
    async with async_session() as session:
        # Проверяем, существует ли платеж с таким transaction_id
        existing_payment = await session.execute(
            select(Payments).filter(Payments.transaction_id == transaction_id)
        )
        if existing_payment.scalars().first():
            return  # Платеж уже существует
        
        # Сохранение нового платежа
        new_payment = Payments(
            user_id=user_id,
            amount=amount,
            payment_url=payment_url,
            transaction_id=transaction_id,
        )
        session.add(new_payment)
        await session.commit()

# Получение transaction_id по user_id
async def get_transaction_id_by_user_id(db, user_id: int):
    async with async_session() as session:
        result = await session.execute(select(Payments.transaction_id).filter(Payments.user_id == user_id))
        payment = result.scalars().first()  # Получаем transaction_id напрямую
        return payment if payment else None  # Возвращаем transaction_id или None, если не найдено

# Функция для получения ссылки на оплату
async def get_payment_url(user_id: int):
    async with async_session() as session:
        result = await session.execute(
            select(Payments).filter(Payments.user_id == user_id).order_by(Payments.payment_url.desc())
        )
        payment = result.scalars().first()
        return payment.payment_url if payment else None
    
# Функция для получения последнего платежа пользователя с учетом сессии
async def get_last_payment(session, user_id: int):
    result = await session.execute(
        select(Payments).filter(Payments.user_id == user_id).order_by(Payments.id.desc())  # Используем id для сортировки по автоинкременту
    )
    return result.scalars().first()  # Возвращаем последний найденный платеж
