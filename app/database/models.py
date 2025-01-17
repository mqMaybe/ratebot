# Импорт необходимых модулей из библиотеки SQLAlchemy
from sqlalchemy import Column, Integer, String, ForeignKey, SmallInteger, Text, Numeric, TIMESTAMP, BigInteger, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.ext.asyncio import AsyncAttrs, async_sessionmaker, create_async_engine
from sqlalchemy.sql import func
import os
from dotenv import load_dotenv

# Загружаем переменные окружения из файла .env
load_dotenv()

# Создание подключения к базе данных с использованием URL из переменных окружения
engine = create_async_engine(url=os.getenv('SQLALCHEMY_SQL'))

# Создание асинхронной сессии для работы с базой данных
async_session = async_sessionmaker(engine)

# Базовый класс для всех моделей, наследующий AsyncAttrs и DeclarativeBase
class Base(AsyncAttrs, DeclarativeBase):
    pass

# Модель пользователя
class User(Base):
    __tablename__ = 'users'

    # Основные поля модели пользователя
    id: Mapped[int] = mapped_column(primary_key=True)  # Идентификатор пользователя
    first_name: Mapped[str] = mapped_column(String, unique=False, nullable=True)  # Имя пользователя
    tg_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False)  # Telegram ID пользователя
    link_token: Mapped[str] = mapped_column(String, unique=False, nullable=True)  # Токен для ссылки на пользователя
    link_created_at: Mapped[TIMESTAMP] = mapped_column(TIMESTAMP, server_default=func.current_timestamp(), nullable=True)  # Время создания токена

    # Связи с моделью Rating: пользователи, которые ставят оценки (ratings_given) и получают их (ratings_received)
    ratings_given = relationship('Ratings', foreign_keys='Ratings.rater_user_id', back_populates='rater', cascade="all, delete-orphan")
    ratings_received = relationship('Ratings', foreign_keys='Ratings.rated_user_id', back_populates='rated_user', cascade="all, delete-orphan")

# Модель рейтингов
class Ratings(Base):
    __tablename__ = 'ratings'

    # Основные поля модели рейтинга
    id: Mapped[int] = mapped_column(primary_key=True)  # Идентификатор рейтинга
    rated_user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey('users.tg_id', ondelete='CASCADE'), nullable=False)  # ID пользователя, которому ставят рейтинг
    rater_user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey('users.tg_id', ondelete='SET NULL'), nullable=True)  # ID пользователя, ставящего рейтинг
    score: Mapped[SmallInteger] = mapped_column(SmallInteger, nullable=False)  # Оценка от 1 до 5
    created_at: Mapped[TIMESTAMP] = mapped_column(TIMESTAMP, server_default=func.current_timestamp())  # Время создания рейтинга

    # Связи с пользователями для получателя и ставящего рейтинг
    rated_user = relationship('User', foreign_keys=[rated_user_id], back_populates='ratings_received')
    rater = relationship('User', foreign_keys=[rater_user_id], back_populates='ratings_given')

# Модель платежей
class Payments(Base):
    __tablename__ = 'payments'

    # Основные поля модели платежа
    id: Mapped[int] = mapped_column(primary_key=True)  # Идентификатор платежа
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey('users.tg_id', ondelete='CASCADE'), nullable=False)  # ID пользователя, который совершает платеж
    amount: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)  # Сумма платежа

    # Идентификатор транзакции от внешнего API (например, от Crypto Bot)
    transaction_id: Mapped[str] = mapped_column(String, nullable=True)

    # URL ссылки на оплату (если используется Crypto Bot API)
    payment_url: Mapped[str] = mapped_column(String, nullable=True)

    # Связь с моделью User (для получения информации о пользователе, который совершил платеж)
    user = relationship('User')

# Функция для создания всех таблиц в базе данных
async def async_main():
    async with engine.begin() as conn:
        # Создание таблиц в базе данных
        await conn.run_sync(Base.metadata.create_all)
