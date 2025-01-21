from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# Главная клавиатура
def generate_main_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Меню", callback_data='back_to_menu')]
        ]
    )

# Клавиатура для меню с действиями
menu = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text='Получить ссылку', callback_data='generate_link')],
    [InlineKeyboardButton(text='Посмотреть статистику', callback_data='show_results')],
])

# Клавиатура для статистики
stats = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text='Статистика за этот день', callback_data='stat_to_day')],
    [InlineKeyboardButton(text='Статистика за неделю', callback_data='stat_for_week')],
    [InlineKeyboardButton(text='Статистика за месяц', callback_data='month_stat')],
    [InlineKeyboardButton(text='Меню', callback_data='back_to_menu')]
])

# Генерация клавиатуры для оценки
def generate_rate_keyboard(token: str):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=str(i), callback_data=f"rate_{i}_token={token}") for i in range(1, 6)],
            [InlineKeyboardButton(text='Меню', callback_data='back_to_menu')]
        ]
    )

# Генерация клавиатуры для оплаты
def generate_payment_keyboard(url,text):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Оплатить", url=url)],
            [InlineKeyboardButton(text=text, callback_data='check_payment')],
            [InlineKeyboardButton(text='Меню', callback_data='back_to_menu')]
        ]
    )

# Генерация кнопки "Назад"
def generate_back_button():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Назад", callback_data="back_to_stat_choice")],
        [InlineKeyboardButton(text='Меню', callback_data='back_to_menu')]
    ])