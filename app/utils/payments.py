import os
from dotenv import load_dotenv
from yoomoney import Quickpay
from yoomoney import Client

# Загружаем переменные окружения
load_dotenv()

YOOMONEY_TOKEN = os.getenv('YOOMONEY')

async def create_payment(amount, description, user_id):
    """Создание платежа через ЮMoney."""
    quickpay = Quickpay(
                receiver="4100118730636948",
                quickpay_form="shop",
                targets=description,
                paymentType="SB",
                sum=amount,
                label=user_id
                )
    return(quickpay.base_url)

async def check_payment_status(transaction_id: str):
    """Проверка статуса платежа через ЮMoney."""
    client = Client(YOOMONEY_TOKEN)
    history = client.operation_history(label=transaction_id)
    for operation in history.operations:
        if operation.status == 'success':
            return True
        else:
            return False
