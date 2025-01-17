import os
from crypto_pay_api_sdk import cryptopay
from app.database.models import Payments
from app.database.models import async_session
from sqlalchemy import func
import app.database.requests as rq
from dotenv import load_dotenv

# Загружаем переменные окружения
load_dotenv()

# Получаем API-токен и настройки из окружения
API_TOKEN = os.getenv('CRYPTOBOT_API_KEY')
PUBLIC_URL = os.getenv('PUBLIC_URL')  # Публичный URL

# Проверка наличия API токена
if not API_TOKEN:
    raise ValueError("CRYPTOBOT_API_KEY не установлен")

# Инициализируем объект API
crypto_api = cryptopay.Crypto(API_TOKEN, testnet=True)

# Функция для создания платежа
async def create_payment(amount: float, description: str, user_id: int):
    """Создание платежной ссылки и сохранение в базе данных"""
    payment_request = {
        'description': description,
    }

    # Создаем платеж
    payment = crypto_api.createInvoice("TRX", amount, payment_request)

    if payment['ok']:
        payment_url = payment['result']['pay_url']
        invoice_id = str(payment['result']['invoice_id'])  # Преобразуем в строку

        # Сохраняем информацию о платеже в базе данных
        async with async_session() as db_session:
            new_payment = Payments(
                user_id=user_id,
                amount=amount,
                payment_url=payment_url,
                transaction_id=invoice_id,  # Сохраняем как строку
            )
            db_session.add(new_payment)
            await db_session.commit()

        return {'payment_url': payment_url, 'invoice_id': invoice_id}

    else:
        raise Exception("Ошибка при создании платежа")

async def check_payment_status(transaction_id: str):
    """Проверка статуса платежа"""
    # Параметры запроса, включая статус "paid"
    params = {'invoice_ids': transaction_id, 'status': 'paid'}

    # Получение информации о счете
    result = crypto_api.getInvoices(params)

    if result['ok'] and 'result' in result and 'items' in result['result']:
        items = result['result']['items']
        if not items:  # Если список счетов пуст
            return False
        
        # Проверяем статус первого счета
        invoice = items[0]
        if invoice.get('status') == 'paid':
            return True
        else:
            return False
    else:
        raise Exception("Ошибка при получении статуса платежа или платеж не найден")