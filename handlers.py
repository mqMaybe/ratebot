from asyncio import sleep
from aiogram import F, Router
from aiogram.types import Message, CallbackQuery
from aiogram.filters import CommandStart, Command
from datetime import timedelta, datetime
from aiogram.fsm.context import FSMContext
from aiogram.filters.state import State, StatesGroup

import app.keyboards.keyboard as kb
from app.utils.link import generate_unique_link
import app.database.requests as rq
from app.utils.payments import create_payment, check_payment_status

class SetPriceState(StatesGroup):
    waiting_for_price = State()

class QuestionLinkState(StatesGroup):
    selecting_questions = State()

class AddQuestions(StatesGroup):
    add_questions = State()

class AnsweringQuestions(StatesGroup):
    answering = State()


router = Router()

# Словарь для перевода периодов
PERIOD_TRANSLATION = {
    "day": "день",
    "week": "неделю",
    "month": "месяц",
    "vip_month": "месяц (VIP)",
    "vip": "месяц (VIP)"
}

@router.callback_query(F.data == "generate_custom_link")
async def start_question_selection(callback: CallbackQuery, state: FSMContext):
    await state.set_state(QuestionLinkState.selecting_questions)
    await state.update_data(selected_questions=[])
    questions = await rq.get_all_questions()
    await callback.message.edit_text("Выберите вопросы для оценки:",
                                     reply_markup=kb.generate_question_selection_keyboard(questions))

@router.callback_query(F.data.startswith("select_q_"))
async def select_question(callback: CallbackQuery, state: FSMContext):
    question_id = int(callback.data.split("_")[2])
    data = await state.get_data()
    selected = set(data.get("selected_questions", []))
    selected.add(question_id)
    await state.update_data(selected_questions=list(selected))
    await callback.answer("Вопрос добавлен")

@router.callback_query(F.data == "finalize_question_link")
async def finalize_link(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    question_ids = data.get("selected_questions", [])
    if not question_ids:
        await callback.answer("Выберите хотя бы один вопрос", show_alert=True)
        return

    token = await rq.create_question_link(callback.from_user.id, question_ids)
    await callback.message.edit_text(f"Ссылка готова:\n{token}",
                                     reply_markup=kb.generate_back_button())
    await state.clear()

@router.callback_query(F.data.startswith("rateq_"))
async def handle_question_rating(callback: CallbackQuery):
    _, qid, score, token = callback.data.split("_", 3)
    qid, score = int(qid), int(score)
    await rq.save_question_rating(token, qid, callback.from_user.id, score)
    await callback.answer("Оценка записана")

@router.callback_query(F.data.startswith("rate_step_"))
async def handle_step_rating(callback: CallbackQuery, state: FSMContext):
    try:
        # Распаковка callback_data
        payload = callback.data[len("rate_step_"):]  # удалить префикс
        qid_str, score_str, token = payload.split("_", 2)
        qid, score = int(qid_str), int(score_str)

        # Сохраняем оценку
        await rq.save_question_rating(token, qid, callback.from_user.id, score)

        # Проверяем наличие данных в FSM
        data = await state.get_data()
        if "questions" not in data or "index" not in data:
            await callback.message.edit_text("⛔ Ошибка: сессия устарела или неверна. Попробуйте начать заново.", reply_markup=kb.generate_back_button())
            await state.clear()
            return

        questions = data["questions"]
        index = data["index"] + 1

        if index < len(questions):
            next_q = questions[index]
            await state.update_data(index=index)
            await callback.message.edit_text(
                f"❓ {next_q['text']}",
                reply_markup=kb.generate_single_question_keyboard(token, next_q['id'])
            )
        else:
            await state.clear()
            await callback.message.edit_text("✅ Спасибо, вы ответили на все вопросы!", reply_markup=kb.generate_back_button())

    except Exception as e:
        await callback.message.edit_text("⚠️ Произошла ошибка при обработке. Попробуйте позже.", reply_markup=kb.generate_back_button())
        raise e

@router.callback_query(F.data == "poll_results")
async def show_poll_results(callback: CallbackQuery):
    user_id = callback.from_user.id

    is_vip = await rq.check_vip_status(user_id)
    results = await rq.get_poll_results(user_id, detailed=is_vip)

    if not results:
        await callback.message.edit_text("⛔️ За ваши вопросы пока никто не голосовал.", reply_markup=kb.generate_back_results())
        return

    if is_vip:
        # Подробные ответы (теперь с средними оценками)
        text = "📊 Результаты опросов (VIP):\n\n"
        for rater in results:
            text += f"@{rater['username'] or 'аноним'}:\n"
            for q in rater['questions']:
                text += f"• {q['text']} — {q['avg_score']:.1f}\n"
            text += "–––\n"
    else:
        # Только средние оценки
        text = "📊 Средние оценки по вопросам:\n\n"
        for row in results:
            text += f"{row['text']}: {row['avg']:.2f}\n"

    await callback.message.edit_text(text, reply_markup=kb.generate_back_results())

# Обработчик команды /start
@router.message(CommandStart())
async def start_command(message: Message, state: FSMContext):
    # Сохраняем пользователя в БД
    await rq.set_user(message.from_user.id, message.from_user.first_name, message.from_user.username)

    # Проверяем, является ли пользователь администратором
    is_admin = await rq.is_admin(message.from_user.id)

    # Обработка /start с аргументом
    if message.text and " " in message.text:
        args = message.text.split(" ", 1)[1]

        if args.startswith("rate_"):
            token = args.split("rate_")[1]

            # 1. Попытка найти пользователя (обычная ссылка)
            user = await rq.get_user_by_token(token)
            if user:
                await message.answer(
                    f"Вы можете оставить отзыв для пользователя: {user['first_name']}.\nОцените его от 1 до 5.",
                    reply_markup=kb.generate_rate_keyboard(token)
                )
                return

            # 2. Попытка найти вопросы (опрос по вопросам)
            questions = await rq.get_questions_by_token(token)
            # Получаем автора токена
            author_id = await rq.get_token_owner(token)
            if author_id == message.from_user.id:
                await message.answer("⛔️ Вы не можете отвечать на собственные вопросы.", reply_markup=kb.generate_back_button())
                return

            # Проверка: уже проходил?
            already_rated = await rq.has_rated_token(token, message.from_user.id)
            if already_rated:
                await message.answer("✅ Вы уже прошли этот опрос.", reply_markup=kb.generate_back_button())
                return
            
            if questions:
                await state.set_state(AnsweringQuestions.answering)
                await state.update_data(token=token, questions=questions, index=0)
                
                current_question = questions[0]
                await message.answer(
                    f"❓ {current_question['text']}",
                    reply_markup=kb.generate_single_question_keyboard(token, current_question['id'])
                )
                return

            # Если ни пользователь, ни вопросы не найдены
            await message.answer("Ссылка недействительна или пользователь/вопросы не найдены.", reply_markup=kb.generate_back_button())
            return

        else:
            await message.answer("Неверная команда. Пожалуйста, используйте правильный формат.", reply_markup=kb.generate_back_button())
            return

    # Если аргумента нет — показать главное меню
    await message.answer(
        "Привет! Я помогу собрать оценки о вас. Нажмите на кнопку ниже, чтобы начать.",
        reply_markup=kb.generate_main_menu(is_admin)
    )

# Обработчик кнопки "Назад в меню"
@router.callback_query(F.data == 'back_to_menu')
async def show_menu(callback: CallbackQuery):
    is_admin = await rq.is_admin(callback.from_user.id)
    # Отправляем меню с inline кнопками
    await callback.answer('')
    await callback.message.edit_text("Выберите действие:", reply_markup=kb.generate_main_menu(is_admin))

# Обработчик генерации ссылки
@router.callback_query(F.data == "generate_link")
async def generate_link(callback: CallbackQuery):
    user_id = callback.from_user.id
    link = await generate_unique_link(user_id)  # Генерируем ссылку и токен
    await callback.answer('')
    await callback.message.edit_text(
        f"Ваша персональная ссылка:\n{link}\nОтправьте её друзьям для сбора отзывов!",
        reply_markup=kb.generate_back_button()
    )

# Обработчик оставления оценки
@router.callback_query(F.data.startswith('rate_'))
async def handle_rating(callback: CallbackQuery):
    # Разделяем callback_data по подчеркиваниям
    data_parts = callback.data.split('_')
    score = int(data_parts[1])  # Оценка пользователя (должна быть в 2-й части)
    token = callback.data.split('=')[1]  # Извлекаем токен после символа '='
    is_admin = await rq.is_admin(callback.from_user.id)

    user_id = callback.from_user.id

    # Получаем пользователя, который оценивается
    rated_user = await rq.get_user_by_token(token)
    if not rated_user:
        await callback.message.answer("Ссылка недействительна или пользователь не найден.",
                                      reply_markup=kb.generate_main_menu(is_admin))
        return

    # Проверяем: пользователь не может оценить сам себя
    if rated_user['tg_id'] == user_id:
        await callback.message.edit_text("Вы не можете оценить сами себя!",
                                         reply_markup=kb.generate_main_menu(is_admin))
        return

    # Проверяем: пользователь уже оценивал этого человека
    existing_rating = await rq.get_existing_rating(user_id, rated_user['tg_id']) #tg_id
    if existing_rating:
        await callback.message.edit_text("Вы уже оценили этого пользователя!",
                                         reply_markup=kb.generate_main_menu(is_admin))
        return

    # Сохраняем рейтинг
    await rq.save_rating(rater_user_id=user_id, rated_user_id=rated_user['tg_id'], score=score) #tg_id

    # Отправляем сообщение о том, что оценка принята
    await callback.answer('')
    await callback.message.edit_text(
        f"Спасибо за вашу оценку! Вы оценили пользователя {rated_user['first_name']} на {score} баллов.", #first_name
        reply_markup=kb.generate_main_menu(is_admin)
    )

@router.callback_query(F.data == "check_subscription")
async def check_subscription(callback: CallbackQuery):
    user_id = callback.from_user.id

    if await rq.has_active_access(user_id):
        # Получаем оставшееся время подписки
        time_left = await rq.get_subscription_time_left(user_id)

        if time_left:
            # Если подписка активна, показываем оставшееся время
            await callback.answer('')
            await callback.message.edit_text(
                f"Ваша подписка активна!\n"
                f"Осталось: {time_left['days']} дней, {time_left['hours']} часов, {time_left['minutes']} минут.",
                reply_markup=kb.generate_back_button()
            )
    else:
        # Если подписки нет, предлагаем оплатить
        await callback.answer('')
        await callback.message.edit_text(
            "У вас нет активной подписки. Хотите оплатить?",
            reply_markup=kb.generate_payment_period_keyboard()
        )
    

@router.callback_query(F.data == "show_results")
async def show_results(callback: CallbackQuery):
    user_id = callback.from_user.id

    is_vip = await rq.check_vip_status(user_id)

    # Проверяем, есть ли успешный платеж
    if await rq.is_payment_successful(user_id):
        await callback.answer('')
        await callback.message.edit_text(
            "Выберите период для просмотра статистики:",
            reply_markup=kb.generate_stats_menu(is_vip)
        )
    else:
        await callback.answer('')
        await callback.message.edit_text(
            "Для доступа к статистике необходимо оплатить подписку. Выберите период оплаты:",
            reply_markup=kb.generate_payment_period_keyboard()
        )

@router.callback_query(F.data == "view_voters")
async def view_voters(callback: CallbackQuery):
    user_id = callback.from_user.id

    # Проверяем, есть ли у пользователя VIP-подписка
    is_vip = await rq.check_vip_status(user_id)
    if not is_vip:
        await callback.answer('')
        await callback.message.edit_text(
            "Для доступа к списку голосовавших необходима VIP-подписка.",
            reply_markup=kb.generate_payment_period_keyboard() # Клавиатура с предложением VIP
        )
        return

    # Получаем список голосовавших
    voters = await rq.get_voters(user_id)
    if not voters:
        await callback.answer('')
        await callback.message.edit_text(
            "За вас еще никто не голосовал.",
            reply_markup=kb.generate_back_button()
        )
        return

    # Формируем сообщение со списком голосовавших
    voters_list = []
    for voter in voters:
        username = voter.get('username', 'без username')  # Если username отсутствует
        voters_list.append(f"@{username}: {voter['score']} баллов")

    voters_message = "Список пользователей, которые оценили вас:\n" + "\n".join(voters_list)
    await callback.answer('')
    await callback.message.edit_text(
        voters_message,
        reply_markup=kb.generate_back_results()
    )

@router.callback_query(F.data.startswith('pay_'))
async def handle_payment(callback: CallbackQuery):
    user_id = callback.from_user.id
    period = callback.data.split('_')[1]  # Извлекаем период из callback_data

    # Проверяем, является ли это VIP-тарифом
    is_vip = "vip" in callback.data

    # Проверяем, есть ли у пользователя активный платеж
    existing_payment = await rq.get_active_payment(user_id)

    if existing_payment:
        # Если активный платеж есть, спрашиваем, хочет ли пользователь создать новый
        await callback.answer('')
        await callback.message.edit_text(
            f"У вас уже есть активный платеж. Хотите создать новый для подписки на другой период?",
            reply_markup=kb.generate_confirm_new_payment_keyboard(period, is_vip)
        )
        return

    # Если активного платежа нет, создаем новый
    await create_new_payment(user_id, period, callback, is_vip)

async def create_new_payment(user_id, period, callback, is_vip=False):
    """Создает новый платеж для выбранного периода."""
    period_name = PERIOD_TRANSLATION.get(period, "неизвестный период")
    if period == 'vip':
        price = await rq.get_subscription_price(period, is_vip)
    else:
        price = await rq.get_subscription_price(period_name, is_vip)

    if price is None:
        await callback.answer('')
        await callback.message.edit_text(
            "Цена для выбранного периода не установлена. Обратитесь к администратору.",
            reply_markup=kb.generate_back_button()
        )
        return

    # Создаем платеж и получаем уникальную метку
    payment_url, unique_label = await create_payment(price, f"Оплата за доступ к статистике на {period_name}")

    # Рассчитываем срок действия доступа
    now = datetime.now()
    if period == "day":
        access_end = now + timedelta(days=1)
    elif period == "week":
        access_end = now + timedelta(weeks=1)
    elif period == "month" or period == "vip_month":  # Обрабатываем vip_month
        access_end = now + timedelta(days=30)
    else:
        # Если период неизвестен, устанавливаем доступ на 1 день по умолчанию
        access_end = now + timedelta(days=1)

    # Сохраняем платеж с уникальной меткой и периодом
    await rq.save_payment(user_id, price, unique_label, payment_url, now, access_end, period, is_vip)

    await callback.answer('')
    await callback.message.edit_text(
        f"Для доступа к статистике на {period_name} необходимо оплатить {price} руб. Перейдите по ссылке для оплаты:",
        reply_markup=kb.generate_payment_keyboard(payment_url, 'Проверить оплату')
    )

@router.callback_query(F.data.startswith('confirm_new_payment_'))
async def confirm_new_payment(callback: CallbackQuery):
    user_id = callback.from_user.id
    data_parts = callback.data.split('_')
    period = data_parts[3]  # Извлекаем период из callback_data
    is_vip = data_parts[4] == "vip"  # Проверяем, является ли это VIP-тарифом

    # Удаляем активный платеж, если он есть
    await rq.delete_active_payment(user_id)

    # Создаем новый платеж для выбранного периода
    await create_new_payment(user_id, period, callback, is_vip)

@router.callback_query(F.data == "buy_vip")
async def buy_vip(callback: CallbackQuery):
    user_id = callback.from_user.id

    # Проверяем, есть ли у пользователя активный платеж
    existing_payment = await rq.get_active_payment(user_id)

    if existing_payment:
        # Если активный платеж есть, спрашиваем, хочет ли пользователь создать новый
        await callback.answer('')
        await callback.message.edit_text(
            f"У вас уже есть активный платеж. Хотите создать новый для VIP-подписки?",
            reply_markup=kb.generate_confirm_new_payment_keyboard(period="vip_month")
        )
        return

    # Если активного платежа нет, создаем новый VIP-платеж
    await create_new_payment(user_id, "vip_month", callback, is_vip=True)

@router.callback_query(F.data == "check_payment")
async def check_payment(callback: CallbackQuery):
    user_id = callback.from_user.id

    # Получаем последний платеж пользователя
    last_payment = await rq.get_last_payment(user_id)

    # Проверяем, вернулся ли корректный словарь
    if not last_payment:
        await callback.answer('')
        await callback.message.edit_text(
            "У вас нет активных платежей.",
            reply_markup=kb.generate_main_menu()
        )
        return

    # Извлекаем ID транзакции и статус из словаря
    transaction_id = last_payment['transaction_id']
    payment_status = last_payment['status']

    # Проверяем, истекло ли время жизни платежа
    if await rq.is_payment_expired(transaction_id):
        await callback.answer('')
        await callback.message.edit_text(
            "Время жизни платежа истекло. Создайте новый платеж.",
            reply_markup=kb.generate_payment_period_keyboard()
        )
        return

    # Если статус уже "success", сразу даем доступ
    if payment_status == 'success':
        await callback.answer('')
        await callback.message.edit_text(
            "Оплата прошла успешно. Вы можете просматривать статистику.",
            reply_markup=kb.generate_stats_menu()
        )
        return

    try:
        # Проверяем статус платежа через API ЮMoney
        if await check_payment_status(transaction_id):
            # Если оплата прошла успешно, активируем подписку
            await callback.answer('')
            await callback.message.edit_text(
                "Оплата прошла успешно. Вы можете просматривать статистику.",
                reply_markup=kb.generate_stats_menu()
            )
            return

        # Если оплата не прошла, начинаем отсчет
        countdown_time = 10
        for i in range(countdown_time, 0, -1):
            # Обновляем кнопку с отсчетом
            await callback.message.edit_reply_markup(
                reply_markup=kb.generate_payment_keyboard(last_payment['payment_url'], f"Проверить через {i}...")
            )
            await sleep(1)

        # После отсчета проверяем статус еще раз
        if await check_payment_status(transaction_id):
            await callback.message.edit_text(
                "Оплата прошла успешно. Вы можете просматривать статистику.",
                reply_markup=kb.generate_stats_menu()
            )
        else:
            await callback.message.edit_text(
                "Оплата не прошла. Перейдите по следующей ссылке для оплаты:",
                reply_markup=kb.generate_payment_keyboard(last_payment['payment_url'], 'Проверить оплату')
            )
    except Exception as e:
        await callback.message.edit_text(
            "Произошла ошибка при проверке статуса платежа. Попробуйте позже.",
            reply_markup=kb.generate_main_menu()
        )

# Обработчик кнопки "Назад к выбору статистики"
@router.callback_query(F.data == "back_to_stat_choice")
async def back_to_stat_choice(callback: CallbackQuery):
    await callback.answer('')
    await callback.message.edit_text(
        "Выберите период для просмотра статистики:",
        reply_markup=kb.generate_stats_menu() # Кнопки выбора периода
    )

@router.callback_query(F.data.startswith('stat_'))
async def handle_statistics(callback: CallbackQuery):
    user_id = callback.from_user.id
    period = callback.data.split('_')[1]

    # Переводим период на русский язык
    period_name = PERIOD_TRANSLATION.get(period, "неизвестный период")

    # Проверяем, есть ли успешный платеж
    if await rq.is_payment_successful(user_id):
        avg_score, total_ratings = await rq.get_statistics(user_id, period)
        if total_ratings:
            await callback.answer('')
            await callback.message.edit_text(
                f"📊 Ваша статистика за {period_name}:\nСредняя оценка: {avg_score:.2f}\nВсего оценок: {total_ratings}",
                reply_markup=kb.generate_back_results()
            )
        else:
            await callback.answer('')
            await callback.message.edit_text(f"За {period_name} у вас нет оценок.", reply_markup=kb.generate_back_results())
    else:
        await callback.answer('')
        await callback.message.edit_text(
            "Для доступа к статистике необходимо оплатить.",
            reply_markup=kb.generate_payment_period_keyboard()
        )

@router.callback_query(F.data == "admin_stats")
async def admin_stats(callback: CallbackQuery):
    user_id = callback.from_user.id

    # Проверяем, является ли пользователь администратором
    if not await rq.is_admin(user_id):
        await callback.answer("У вас нет прав администратора.")
        return

    # Получаем статистику
    total_users = await rq.get_total_users()
    users_with_links = await rq.get_users_with_links()
    payment_stats = await rq.get_payment_stats()
    total_spent = await rq.get_total_spent_on_subscriptions()

    # Формируем сообщение со статистикой
    stats_message = (
        f"📊 Статистика:\n"
        f"👤 Всего пользователей: {total_users}\n"
        f"🔗 Пользователей сгенерировало ссылку: {users_with_links}\n"
        f"💳 Оплачено обычных подписок: {payment_stats['normal_payments']}\n"
        f"🌟 Оплачено VIP-подписок: {payment_stats['vip_payments']}\n"
        f"💰 Потрачено на обычные подписки: {total_spent['total_normal']:.2f} ₽\n"
        f"💎 Потрачено на VIP-подписки: {total_spent['total_vip']:.2f} ₽\n"
        f"💵 Всего потрачено: {total_spent['total']:.2f} ₽"
    )

    await callback.answer('')
    await callback.message.edit_text(stats_message, reply_markup=kb.generate_back_button())

@router.callback_query(F.data == "manage_prices")
async def manage_prices(callback: CallbackQuery):
    """Показывает меню управления ценами на подписки."""
    user_id = callback.from_user.id

    period = callback.data.split('_')[1]  # Извлекаем период из callback_data

    # Проверяем, является ли это VIP-тарифом
    is_vip = "vip" in callback.data

    # Проверяем, является ли пользователь администратором
    if not await rq.is_admin(user_id):
        await callback.answer("У вас нет прав администратора.")
        return

    # Получаем текущие цены на подписки
    prices = await rq.get_subscription_price(period, is_vip)

    # Формируем сообщение с текущими ценами
    prices_message = "Текущие цены на подписки:\n"
    if prices != None: 
        for price in prices:
            prices_message += f"{price['period']} ({'VIP' if price['is_vip'] else 'Обычный'}): {price['price']} руб.\n"
    else:
        prices_message += "Сейчас цен на подписки нет"
    # Показываем меню управления ценами
    await callback.answer('')
    await callback.message.edit_text(
        prices_message,
        reply_markup=kb.generate_manage_prices_keyboard()
    )

@router.callback_query(F.data.startswith("set_price_"))
async def handle_set_price(callback: CallbackQuery, state: FSMContext):
    """Обрабатывает нажатие на кнопку установки цены."""
    user_id = callback.from_user.id

    # Разделяем callback_data на части
    parts = callback.data.split('_')  # Пример: "set_price_day_normal" -> ["set", "price", "day", "normal"]

    # Проверяем, что parts содержит достаточно элементов
    if len(parts) < 4:
        await callback.answer("Неверный формат callback_data.")
        return

    # Извлекаем period и type
    period = parts[2]  # day, week, month
    subscription_type = parts[3]  # normal или vip

    period_name = PERIOD_TRANSLATION.get(period, "неизвестный период")

    # Определяем, является ли подписка VIP
    is_vip = subscription_type == "vip"

    # Проверяем, является ли пользователь администратором
    if not await rq.is_admin(user_id):
        await callback.answer("У вас нет прав администратора.")
        return

    # Сохраняем period и is_vip в состояние
    await state.update_data(period=period, is_vip=is_vip)

    # Запрашиваем у пользователя новую цену
    await callback.answer('')
    await callback.message.answer(
        f"Введите новую цену для подписки на {period_name} ({'VIP' if is_vip else 'Обычный'})"
    )

    # Устанавливаем состояние ожидания ввода цены
    await state.set_state(SetPriceState.waiting_for_price)

@router.message(SetPriceState.waiting_for_price)
async def handle_price_input(message: Message, state: FSMContext):
    """Обрабатывает ввод новой цены."""
    user_id = message.from_user.id

    # Проверяем, является ли пользователь администратором
    if not await rq.is_admin(user_id):
        await message.answer("У вас нет прав администратора.")
        return

    # Получаем данные из состояния
    data = await state.get_data()
    period = data.get("period")
    is_vip = data.get("is_vip")

    period_name = PERIOD_TRANSLATION.get(period, "неизвестный период")

    # Проверяем, что введенное значение является числом
    try:
        price = float(message.text)
    except ValueError:
        await message.answer("Пожалуйста, введите корректное число.")
        return
    
    if is_vip:
        success = await rq.update_subscription_price("vip", price, is_vip)
    else:
        success = await rq.update_subscription_price(period_name, price, is_vip)

    if success:
        await message.answer(f"Цена для подписки {period_name} ({'VIP' if is_vip else 'Обычный'}) успешно обновлена!")
    else:
        await message.answer("Произошла ошибка при обновлении цены.")

    # Сбрасываем состояние
    await state.clear()

@router.callback_query(F.data.startswith("add_questions"))
async def add_questions(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id

    if not await rq.is_admin(user_id):
        await callback.answer("У вас нет прав администратора.", reply_markup=kb.generate_back_button())
        return
    
    await callback.answer('')
    await state.set_state(AddQuestions.add_questions)  # устанавливаем состояние
    await callback.message.edit_text("Введите новый вопрос:", reply_markup=kb.generate_back_button())

@router.message(AddQuestions.add_questions)
async def handle_question_input(message: Message, state: FSMContext):
    user_id = message.from_user.id

    if not await rq.is_admin(user_id):
        await message.answer("У вас нет прав администратора.", reply_markup=kb.generate_back_button())
        await state.clear()
        return
    
    question = message.text.strip()
    if not question:
        await message.answer("Вопрос не может быть пустым.", reply_markup=kb.generate_back_button())
        return

    try:
        if await rq.question_exists(question):
            await message.answer("Такой вопрос уже существует!", reply_markup=kb.generate_back_button())
            return

        success = await rq.update_questions_list(question)
        if success:
            await message.answer(f"✅ Вопрос добавлен: {question}", reply_markup=kb.generate_back_button())
        else:
            await message.answer("❌ Ошибка при добавлении вопроса.", reply_markup=kb.generate_back_button())
    except Exception as e:
        await message.answer(f"⚠️ Критическая ошибка: {e}", reply_markup=kb.generate_back_button())
    finally:
        await state.clear()