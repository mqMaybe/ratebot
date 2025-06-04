from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# Главная клавиатура
def generate_main_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Меню", callback_data='back_to_menu')]
        ]
    )

# Клавиатура для меню с действиями
def generate_main_menu(is_admin=False):
    """Генерирует главное меню."""
    buttons = [
        [InlineKeyboardButton(text="Сгенерировать ссылку", callback_data="generate_link")],
        [InlineKeyboardButton(text="Ссылка с вопросами", callback_data="generate_custom_link")],  # Новая кнопка
        [InlineKeyboardButton(text="Просмотреть результаты", callback_data="show_results")],
        [InlineKeyboardButton(text="Проверить подписку", callback_data="check_subscription")],
    ]
    if is_admin:
        buttons.append([InlineKeyboardButton(text="📊 Статистика", callback_data="admin_stats")])
        buttons.append([InlineKeyboardButton(text="💰 Управление ценами", callback_data="manage_prices")])
        buttons.append([InlineKeyboardButton(text="➕ Добавить вопросы", callback_data="add_questions")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def generate_question_selection_keyboard(questions):
    buttons = [[InlineKeyboardButton(text=q['text'], callback_data=f"select_q_{q['id']}")] for q in questions]
    buttons.append([InlineKeyboardButton(text="✅ Готово", callback_data="finalize_question_link")])
    buttons.append([InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_menu")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def generate_rate_keyboard_for_questions(token, questions):
    keyboard = []
    for q in questions:
        row = [InlineKeyboardButton(text=f"{i}", callback_data=f"rateq_{q['id']}_{i}_{token}") for i in range(1, 6)]
        keyboard.append(row)
    keyboard.append([InlineKeyboardButton(text="Меню", callback_data="back_to_menu")])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def generate_single_question_keyboard(token, question_id):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=str(i), callback_data=f"rate_step_{question_id}_{i}_{token}") for i in range(1, 6)]
        ]
    )


# Клавиатура для статистики
def generate_stats_menu(is_vip=False):
        buttons = [
            [InlineKeyboardButton(text='Статистика за этот день', callback_data='stat_day')],
            [InlineKeyboardButton(text='Статистика за неделю', callback_data='stat_week')],
            [InlineKeyboardButton(text='Статистика за месяц', callback_data='stat_month')],
            [InlineKeyboardButton(text='Результаты по вопросам', callback_data='poll_results')],
        ]
        if is_vip:
            buttons.append([InlineKeyboardButton(text="Просмотреть голосовавших", callback_data="view_voters")])
        buttons.append([InlineKeyboardButton(text='Назад', callback_data='back_to_menu')])
        
        return InlineKeyboardMarkup(inline_keyboard=buttons)

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
        [InlineKeyboardButton(text="Назад", callback_data='back_to_menu')]
    ])
# Генерация кнопки "Назад" в выборе стастистики
def generate_back_results():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Назад", callback_data="show_results")]
        ]
    )

def generate_vip_menu():
    """Генерирует клавиатуру для VIP-меню."""
    buttons = [
        [InlineKeyboardButton(text="Просмотреть голосовавших", callback_data="view_voters")],
        [InlineKeyboardButton(text="Назад в меню", callback_data="back_to_menu")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def generate_payment_period_keyboard():
    """Генерирует клавиатуру для выбора периода оплаты."""
    buttons = [
        [InlineKeyboardButton(text="1 день (обычный)", callback_data="pay_day")],
        [InlineKeyboardButton(text="1 неделя (обычный)", callback_data="pay_week")],
        [InlineKeyboardButton(text="1 месяц (обычный)", callback_data="pay_month")],
        [InlineKeyboardButton(text="1 месяц (VIP)", callback_data="pay_vip_month")],  # VIP-тариф
        [InlineKeyboardButton(text="Назад в меню", callback_data="back_to_menu")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def generate_confirm_new_payment_keyboard(period, is_vip=False):
    """Генерирует клавиатуру для подтверждения создания нового платежа."""
    buttons = [
        [InlineKeyboardButton(text="Да, создать новый", callback_data=f"confirm_new_payment_{period}_{'vip' if is_vip else 'normal'}")],
        [InlineKeyboardButton(text="Нет, вернуться в меню", callback_data="back_to_menu")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def generate_manage_prices_keyboard():
    """Генерирует клавиатуру для управления ценами на подписки."""
    buttons = [
        [InlineKeyboardButton(text="Установить цену на день (Обычный)", callback_data="set_price_day_normal")],
        [InlineKeyboardButton(text="Установить цену на неделю (Обычный)", callback_data="set_price_week_normal")],
        [InlineKeyboardButton(text="Установить цену на месяц (Обычный)", callback_data="set_price_month_normal")],
        [InlineKeyboardButton(text="Установить цену на месяц (VIP)", callback_data="set_price_month_vip")],
        [InlineKeyboardButton(text="Назад в меню", callback_data="back_to_menu")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def generate_back_to_prices_button():
    """Генерирует кнопку для возврата к управлению ценами."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Назад к ценам", callback_data="manage_prices")]
    ])