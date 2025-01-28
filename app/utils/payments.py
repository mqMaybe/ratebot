import os
from dotenv import load_dotenv
from yoomoney import Quickpay
from yoomoney import Client
import random
import string

from app.database.requests import get_db_connection
from app.database.requests import update_payment_status

# Загружаем переменные окружения
load_dotenv()

YOOMONEY_TOKEN = os.getenv('YOOMONEY')

async def create_payment(amount, description):
    """Создание платежа через ЮMoney."""
    payment_url = ''.join(random.choices(string.ascii_letters + string.digits, k=10))

    connection = await get_db_connection()
    cursor = await connection.cursor()

    while True:
            await cursor.execute("SELECT * FROM payments WHERE transaction_id = %s", (payment_url))
            existing_user = await cursor.fetchone()

            if not existing_user:
                break  # Токен уникален, выходим из цикла
            else:
                # Генерируем новый токен, если текущий не уникален
                payment_url = ''.join(random.choices(string.ascii_letters + string.digits, k=10))

    unique_label = payment_url

    quickpay = Quickpay(
        receiver="4100118730636948",
        quickpay_form="shop",
        targets=description,
        paymentType="SB",
        sum=amount,
        label=unique_label  # Уникальная метка
    )
    return quickpay.base_url, unique_label  # Возвращаем URL и метку

async def check_payment_status(transaction_id: str):
    """Проверка статуса платежа через ЮMoney."""
    try:
        client = Client(YOOMONEY_TOKEN)
        history = client.operation_history(label=transaction_id)
        for operation in history.operations:
            print()
            print("Operation:", operation.operation_id)
            print("\tStatus     -->", operation.status)
            print("\tDatetime   -->", operation.datetime)
            print("\tTitle      -->", operation.title)
            print("\tPattern id -->", operation.pattern_id)
            print("\tDirection  -->", operation.direction)
            print("\tAmount     -->", operation.amount)
            print("\tLabel      -->", operation.label)
            print("\tType       -->", operation.type)
            if operation.status == 'success':
                await update_payment_status(transaction_id, operation.status)
                return True  # Возвращаем True, если платеж успешен
        return False  # Если успешный платеж не найден
    except Exception as e:
        print(f"Ошибка при проверке статуса платежа: {e}")
        return False  # Возвращаем False в случае ошибки