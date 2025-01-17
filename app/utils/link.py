import random
import string
from sqlalchemy import func
from sqlalchemy.future import select
from app.database.models import User

async def generate_unique_link(user_id, session):
    """Генерация уникальной ссылки для пользователя"""
    # Генерация случайного токена
    token = ''.join(random.choices(string.ascii_letters + string.digits, k=8))
    
    # Проверка уникальности токена
    while True:
        result = await session.execute(select(User).where(User.link_token == token))
        existing_user = result.scalars().first()
        
        if not existing_user:
            break  # Токен уникален, выходим из цикла
        else:
            # Генерируем новый токен, если текущий не уникален
            token = ''.join(random.choices(string.ascii_letters + string.digits, k=8))
    
    # Поиск пользователя по tg_id
    result = await session.execute(select(User).where(User.tg_id == user_id))
    user = result.scalars().first()
    
    if user:
        # Устанавливаем новый токен и сохраняем в базе данных
        user.link_token = token
        user.link_created_at = func.current_timestamp()
        await session.commit()
        return f"https://t.me/PeopleRatingsBot?start=rate_{token}"
    else:
        raise ValueError("Пользователь не найден")