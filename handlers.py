import os
from asyncio import sleep
from aiogram import F, Router
from aiogram.types import Message, CallbackQuery
from aiogram.filters import CommandStart, Command
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.asyncio import AsyncAttrs, async_sessionmaker, create_async_engine
from sqlalchemy.future import select

import app.keyboards.keyboard as kb
from app.utils.link import generate_unique_link
import app.database.requests as rq
from app.database.models import User
from app.database.models import async_session
from app.utils.payments import create_payment, check_payment_status

router = Router()

# Обработчик команды /start
@router.message(CommandStart())
async def start_command(message: Message):
    # Проверяем/создаем пользователя
    await rq.set_user(message.from_user.id, message.from_user.first_name)

    # Извлекаем аргументы из команды /start
    if message.text and " " in message.text:
        args = message.text.split(" ", 1)[1]  # Извлекаем всё, что после /start
        if args.startswith("rate_"):  # Если аргумент начинается с "rate_"
            token = args.split("rate_")[1]
            user = await rq.get_user_by_token(token)
            if user:
                # Показываем клавиатуру для оценки без проверки отзыва
                await message.answer(
                    f"Вы можете оставить отзыв для пользователя: {user.first_name}. Оцените его от 1 до 5.",
                    reply_markup=kb.generate_rate_keyboard(token)
                )
            else:
                await message.answer("Ссылка недействительна или пользователь не найден.")
        else:
            await message.answer("Неверная команда. Пожалуйста, используйте правильный формат.")
    else:
        # Если аргументы нет, то просто показываем стартовое меню
        await message.answer(
            "Привет! Я помогу собрать оценки о вас. Нажмите на кнопку ниже, чтобы начать.",
            reply_markup=kb.generate_main_menu()
        )

# Обработчик кнопки "Назад в меню"
@router.callback_query(F.data == 'back_to_menu')
async def show_menu(callback: CallbackQuery):
    # Отправляем меню с inline кнопками
    await callback.answer('')
    await callback.message.edit_text("Выберите действие:", reply_markup=kb.menu)

# Обработчик генерации ссылки
@router.callback_query(F.data == "generate_link")
async def generate_link(callback: CallbackQuery):
    user_id = callback.from_user.id
    async with async_session() as session:
        link = await generate_unique_link(user_id, session)  # Генерируем ссылку и токен
        await callback.answer('')
        await callback.message.edit_text(
            f"Ваша персональная ссылка:\n{link}\nОтправьте её друзьям для сбора отзывов!",
        reply_markup=kb.generate_main_menu())

# Обработчик оставления оценки
@router.callback_query(F.data.startswith('rate_'))
async def handle_rating(callback: CallbackQuery):
    # Разделяем callback_data по подчеркиваниям
    data_parts = callback.data.split('_')
    score = int(data_parts[1])  # Оценка пользователя (должна быть в 2-й части)
    token = callback.data.split('=')[1]  # Извлекаем токен после символа '='

    user_id = callback.from_user.id

    # Получаем пользователя, который оценивается
    rated_user = await rq.get_user_by_token(token)
    if not rated_user:
        await callback.message.answer("Ссылка недействительна или пользователь не найден.",
                                      reply_markup=kb.generate_main_menu())
        return

    # Проверяем: пользователь не может оценить сам себя
    if rated_user.tg_id == user_id:
        await callback.message.edit_text("Вы не можете оценить сами себя!",
                                         reply_markup=kb.generate_main_menu())
        return

    # Проверяем: пользователь уже оценивал этого человека
    async with async_session() as session:
        existing_rating = await rq.get_existing_rating(user_id, rated_user.tg_id, session)
        if existing_rating:
            await callback.message.edit_text("Вы уже оценили этого пользователя!",
                                             reply_markup=kb.generate_main_menu())
            return

        # Сохраняем рейтинг
        await rq.save_rating(rater_user_id=user_id, rated_user_id=rated_user.tg_id, score=score)

    # Отправляем сообщение о том, что оценка принята
    await callback.answer('')
    await callback.message.edit_text(
        f"Спасибо за вашу оценку! Вы оценили пользователя {rated_user.first_name} на {score} баллов.",
        reply_markup=kb.generate_main_menu())

# Обработчик для отображения результатов
@router.callback_query(F.data == "show_results")
async def show_results(callback: CallbackQuery):
    user_id = callback.from_user.id
    amount = 1.0

    async with async_session() as session:
        # Получаем последний платеж
        last_payment = await rq.get_last_payment(session, user_id)

        if last_payment:
            # Проверяем статус оплаты через API
            if await check_payment_status(last_payment.transaction_id):
                await callback.answer('')
                await callback.message.edit_text(
                    "Вы уже оплатили подписку. Вот ваша статистика:",
                    reply_markup=kb.stats
                )
                return
            else:
                # Если последний платеж не оплачен, предлагаем оплатить его
                await callback.answer('')
                await callback.message.edit_text(
                    "Для доступа к статистике необходимо оплатить. Перейдите по ссылке для оплаты:",
                    reply_markup=kb.generate_payment_keyboard(last_payment.payment_url, 'Проверить оплату')
                )
                return

        # Если платежа нет, создаем новый
        payment_data = await create_payment(amount, "Оплата за доступ к статистике", user_id)
        await rq.save_payment(user_id, amount, payment_data['payment_url'], payment_data['invoice_id'])
        await callback.answer('')
        await callback.message.edit_text(
            "Для доступа к статистике необходимо оплатить. Перейдите по ссылке для оплаты:",
            reply_markup=kb.generate_payment_keyboard(payment_data['payment_url'], 'Проверить оплату')
        )

# Переменная отсчета
is_countdown_active = False  # Переменная отсчета

# Обработчик проверки статуса оплаты
@router.callback_query(F.data == "check_payment")
async def check_payment(callback: CallbackQuery):
    global is_countdown_active
    user_id = callback.from_user.id
    amount = 1.0
    payment_url = await rq.get_payment_url(user_id)

    if is_countdown_active:
        await callback.answer("Пожалуйста, подождите завершения отсчета.")
        return
    
    countdown_time = 10

    async with async_session() as session:
        payment_data = await rq.get_transaction_id_by_user_id(session, user_id)
        
        if payment_data:
            # Начинаем отсчет
            for i in range(countdown_time, 0, -1):
                # Обновляем кнопку с отсчетом
                await callback.message.edit_reply_markup(
                    reply_markup=kb.generate_payment_keyboard(payment_url, f"Проверить через {i}...")  # Обновляем текст
                )
                is_countdown_active = True
                await sleep(1)
            
            is_countdown_active = False
            
            # После отсчета проверяем статус
            if await check_payment_status(payment_data):
                await callback.message.edit_text("Оплата прошла успешно. Вы можете просматривать статистику.", reply_markup=kb.stats)
            else:
                await callback.message.edit_text("Оплата не прошла. Перейдите по следующей ссылке для оплаты:", reply_markup=kb.generate_payment_keyboard(payment_url, 'Проверить оплату'))
        
        else:
            payment_data = await create_payment(amount, "Оплата за доступ к статистике", user_id)
            await rq.save_payment(user_id, amount, payment_data['payment_url'], payment_data['invoice_id'])
            await callback.message.edit_text(
                "Для доступа к статистике необходимо оплатить. Перейдите по ссылке для оплаты:",
                reply_markup=kb.generate_payment_keyboard(payment_data['payment_url'], 'Проверить оплату')
            )

# Обработчик кнопки "Назад к выбору статистики"
@router.callback_query(F.data == "back_to_stat_choice")
async def back_to_stat_choice(callback: CallbackQuery):
    await callback.answer('')
    await callback.message.edit_text(
        "Выберите период для просмотра статистики:",
        reply_markup=kb.stats  # Кнопки выбора периода
    )

# Обработчик статистики за день
@router.callback_query(F.data == 'stat_to_day')
async def stat_to_day(callback: CallbackQuery):
    user_id = callback.from_user.id
    avg_score, total_ratings = await rq.get_statistics(user_id, "day")
    if total_ratings:
        await callback.answer('')
        await callback.message.edit_text(
            f"📊 Ваша статистика за день:\nСредняя оценка: {avg_score:.2f}\nВсего оценок: {total_ratings}",
            reply_markup=kb.generate_back_button()  # Кнопка назад
        )
    else:
        await callback.answer('')
        await callback.message.edit_text("За последние 24 часа у вас нет оценок.", reply_markup=kb.generate_back_button())

# Обработчик статистики за неделю
@router.callback_query(F.data == 'stat_for_week')
async def stat_for_week(callback: CallbackQuery):
    user_id = callback.from_user.id
    avg_score, total_ratings = await rq.get_statistics(user_id, "week")
    if total_ratings:
        await callback.answer('')
        await callback.message.edit_text(
            f"📊 Ваша статистика за неделю:\nСредняя оценка: {avg_score:.2f}\nВсего оценок: {total_ratings}",
            reply_markup=kb.generate_back_button()  # Кнопка назад
        )
    else:
        await callback.answer('')
        await callback.message.edit_text("За последнюю неделю у вас нет оценок.", reply_markup=kb.generate_back_button())

# Обработчик статистики за месяц
@router.callback_query(F.data == 'month_stat')
async def month_stat(callback: CallbackQuery):
    user_id = callback.from_user.id
    avg_score, total_ratings = await rq.get_statistics(user_id, "month")
    if total_ratings:
        await callback.answer('')
        await callback.message.edit_text(
            f"📊 Ваша статистика за месяц:\nСредняя оценка: {avg_score:.2f}\nВсего оценок: {total_ratings}",
            reply_markup=kb.generate_back_button()  # Кнопка назад
        )
    else:
        await callback.answer('')
        await callback.message.edit_text("За последний месяц у вас нет оценок.", reply_markup=kb.generate_back_button())