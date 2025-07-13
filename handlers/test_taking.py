from aiogram import Router, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession
import json
import random
from datetime import datetime

from database.db import (
    get_trainee_available_tests, get_user_test_results, check_user_permission,
    get_user_by_tg_id, get_test_by_id, check_test_access, get_user_test_result,
    get_test_questions, save_test_result, get_user_test_attempts_count, can_user_take_test
)
from database.models import InternshipStage, TestResult
from sqlalchemy import select
from keyboards.keyboards import get_test_selection_keyboard, get_test_start_keyboard, get_test_selection_for_taking_keyboard
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from states.states import TestTakingStates
from utils.logger import log_user_action, log_user_error, logger
from handlers.auth import check_auth

router = Router()

@router.message(Command("my_tests"))
async def cmd_my_tests_command(message: Message, state: FSMContext, session: AsyncSession):
    """Обработчик команды /my_tests"""
    await cmd_take_test(message, state, session)

@router.message(Command("all_tests"))
async def cmd_all_tests_command(message: Message, state: FSMContext, session: AsyncSession):
    """Обработчик команды /all_tests"""
    # Для команды all_tests используем функцию cmd_list_tests из tests.py
    # Но импортируем её туда, где она нужна
    from handlers.tests import cmd_list_tests
    await cmd_list_tests(message, state, session)

@router.message(F.text == "Доступные тесты")
async def cmd_take_test(message: Message, state: FSMContext, session: AsyncSession):
    """Обработчик команды прохождения теста"""
    is_auth = await check_auth(message, state, session)
    if not is_auth:
        return
    
    user = await get_user_by_tg_id(session, message.from_user.id)
    if not user:
        await message.answer("Вы не зарегистрированы в системе.")
        return
    
    has_permission = await check_user_permission(session, user.id, "take_tests")
    if not has_permission:
        await message.answer("У вас нет прав для прохождения тестов.")
        return
    
    available_tests = await get_trainee_available_tests(session, user.id)
    
    if not available_tests:
        await message.answer(
            "📋 <b>Доступные тесты</b>\n\n"
            "У вас пока нет доступных тестов для прохождения.\n"
            "Обратитесь к наставнику для получения доступа к тестам.",
            parse_mode="HTML"
        )
        return
    
    tests_list = []
    for i, test in enumerate(available_tests, 1):
        stage_info = ""
        if test.stage_id:
            stage = await session.execute(select(InternshipStage).where(InternshipStage.id == test.stage_id))
            stage_obj = stage.scalar_one_or_none()
            if stage_obj:
                stage_info = f" | Этап: {stage_obj.name}"
        
        materials_info = " | 📚 Есть материалы" if test.material_link else ""
        
        tests_list.append(
            f"<b>{i}. {test.name}</b>\n"
            f"   🎯 Порог: {test.threshold_score}/{test.max_score} баллов{stage_info}{materials_info}\n"
            f"   📝 {test.description or 'Описание не указано'}"
        )
    
    tests_display = "\n\n".join(tests_list)
    
    await message.answer(
        f"📋 <b>Доступные тесты</b>\n\n"
        f"У вас есть доступ к <b>{len(available_tests)}</b> тестам:\n\n"
        f"{tests_display}\n\n"
        "💡 <b>Рекомендация:</b> Изучите материалы перед прохождением теста!",
        parse_mode="HTML",
        reply_markup=get_test_selection_for_taking_keyboard(available_tests)
    )
    
    await state.set_state(TestTakingStates.waiting_for_test_selection)
    
    log_user_action(message.from_user.id, message.from_user.username, "opened test taking")

@router.message(F.text == "Посмотреть баллы")
async def cmd_view_scores(message: Message, state: FSMContext, session: AsyncSession):
    """Обработчик команды просмотра баллов стажера"""
    is_auth = await check_auth(message, state, session)
    if not is_auth:
        return
    
    user = await get_user_by_tg_id(session, message.from_user.id)
    if not user:
        await message.answer("Вы не зарегистрированы в системе.")
        return
    
    has_permission = await check_user_permission(session, user.id, "view_test_results")
    if not has_permission:
        await message.answer("У вас нет прав для просмотра результатов тестов.")
        return
    
    test_results = await get_user_test_results(session, user.id)
    
    if not test_results:
        await message.answer(
            "📊 <b>Ваши результаты</b>\n\n"
            "Вы пока не проходили тестов.\n"
            "Используйте кнопку 'Доступные тесты' для прохождения доступных тестов.",
            parse_mode="HTML"
        )
        return
    
    results_list = []
    total_score = 0
    passed_count = 0
    total_tests_taken = len(test_results)
    
    for result in test_results:
        test = await get_test_by_id(session, result.test_id)
        status = "✅ Пройден" if result.is_passed else "❌ Не пройден"
        percentage = (result.score / result.max_possible_score * 100) if result.max_possible_score > 0 else 0
        
        results_list.append(
            f"📋 <b>{test.name if test else 'Неизвестный тест'}</b>\n"
            f"   📊 Баллы: {result.score}/{result.max_possible_score} ({percentage:.1f}%)\n"
            f"   {status}\n"
            f"   📅 Дата: {result.created_date.strftime('%d.%m.%Y %H:%M')}\n"
            f"   ⏱️ Время: {(result.end_time - result.start_time).total_seconds():.0f} сек"
        )
        
        total_score += result.score
        if result.is_passed:
            passed_count += 1
    
    results_text = "\n\n".join(results_list)
    
    # Статистика прогресса
    success_rate = (passed_count / total_tests_taken * 100) if total_tests_taken > 0 else 0
    
    await message.answer(
        f"📊 <b>Ваши результаты тестирования</b>\n\n"
        f"📈 <b>Общая статистика:</b>\n"
        f"• Пройдено тестов: {passed_count}/{total_tests_taken}\n"
        f"• Процент успеха: {success_rate:.1f}%\n"
        f"• Общий набранный балл: {total_score}\n"
        f"• Последний тест: {test_results[0].created_date.strftime('%d.%m.%Y') if test_results else 'Нет'}\n\n"
        f"📋 <b>Детальные результаты:</b>\n\n{results_text}\n\n"
        f"💡 <b>Совет:</b> Обратитесь к наставнику для получения доступа к новым тестам!",
        parse_mode="HTML"
    )
    
    log_user_action(message.from_user.id, message.from_user.username, "viewed test results")

@router.callback_query(TestTakingStates.waiting_for_test_selection, F.data.startswith("test:"))
async def process_test_selection_for_taking(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Обработчик выбора теста для прохождения"""
    test_id = int(callback.data.split(':')[1])
    
    test = await get_test_by_id(session, test_id)
    if not test:
        await callback.message.answer("❌ Тест не найден.")
        await callback.answer()
        return
    
    # Проверяем доступ к тесту
    user = await get_user_by_tg_id(session, callback.from_user.id)
    has_access = await check_test_access(session, user.id, test_id)
    
    if not has_access:
        await callback.message.edit_text(
            "❌ <b>Доступ запрещен</b>\n\n"
            "У вас нет доступа к этому тесту. Обратитесь к наставнику.",
            parse_mode="HTML"
        )
        await callback.answer()
        return
    
    # Проверяем количество попыток
    attempts_count = await get_user_test_attempts_count(session, user.id, test_id)
    
    # Проверяем, есть ли уже результат
    existing_result = await get_user_test_result(session, user.id, test_id)
    
    # Получаем информацию о тесте
    questions = await get_test_questions(session, test_id)
    questions_count = len(questions)
    
    stage_info = ""
    if test.stage_id:
        stage = await session.execute(select(InternshipStage).where(InternshipStage.id == test.stage_id))
        stage_obj = stage.scalar_one_or_none()
        if stage_obj:
            stage_info = f"🎯 <b>Этап:</b> {stage_obj.name}\n"
    
    materials_info = ""
    if test.material_link:
        if test.material_file_path:
            # Если есть прикрепленный файл
            materials_info = f"📚 <b>Материалы для изучения:</b>\n🔗 {test.material_link}\n\n"
        else:
            # Если это ссылка
            materials_info = f"📚 <b>Материалы для изучения:</b>\n{test.material_link}\n\n"
    
    # Информация о попытках
    attempts_info = ""
    if test.max_attempts > 0:
        attempts_info = f"🔢 <b>Попытки:</b> {attempts_count}/{test.max_attempts}\n"
    else:
        attempts_info = f"♾️ <b>Попытки:</b> бесконечно (текущая: {attempts_count + 1})\n"
    
    previous_result_info = ""
    if existing_result:
        status = "пройден" if existing_result.is_passed else "не пройден"
        previous_result_info = f"""
🔄 <b>Предыдущий результат:</b>
   • Статус: {status}
   • Баллы: {existing_result.score}/{existing_result.max_possible_score}
   • Дата: {existing_result.created_date.strftime('%d.%m.%Y %H:%M')}

"""
    
    test_info = f"""📋 <b>Информация о тесте</b>

📌 <b>Название:</b> {test.name}
📝 <b>Описание:</b> {test.description or 'Не указано'}
{stage_info}❓ <b>Количество вопросов:</b> {questions_count}
🎯 <b>Порог прохождения:</b> {test.threshold_score} из {test.max_score} баллов
{attempts_info}{materials_info}{previous_result_info}"""
    
    await callback.message.edit_text(
        test_info,
        parse_mode="HTML",
        reply_markup=get_test_start_keyboard(test_id, bool(existing_result))
    )
    
    await state.update_data(selected_test_id=test_id)
    await state.set_state(TestTakingStates.waiting_for_test_start)
    
    await callback.answer()
    
    log_user_action(
        callback.from_user.id, 
        callback.from_user.username, 
        "selected test for taking", 
        {"test_id": test_id}
    )

@router.callback_query(TestTakingStates.waiting_for_test_start, F.data.startswith("start_test:"))
async def process_start_test(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Обработчик начала прохождения теста"""
    test_id = int(callback.data.split(':')[1])
    user_id = callback.from_user.id
    
    test = await get_test_by_id(session, test_id)
    if not test:
        await callback.message.edit_text("❌ Тест не найден.")
        await state.clear()
        return
    
    # Получаем пользователя и проверяем количество попыток
    user = await get_user_by_tg_id(session, callback.from_user.id)
    if not user:
        await callback.message.edit_text("❌ Пользователь не найден.")
        await state.clear()
        return
    
    # Проверяем, может ли пользователь пройти тест (с учетом ограничений попыток)
    can_take, error_message = await can_user_take_test(session, user.id, test_id)
    if not can_take:
        attempts_count = await get_user_test_attempts_count(session, user.id, test_id)
        attempts_info = ""
        if test.max_attempts > 0:
            attempts_info = f"\n🔢 <b>Попытки:</b> {attempts_count}/{test.max_attempts}"
        
        await callback.message.edit_text(
            f"🚫 <b>Тест недоступен для прохождения</b>\n\n"
            f"📋 <b>Тест:</b> {test.name}\n"
            f"❌ <b>Причина:</b> {error_message}{attempts_info}\n\n"
            f"💡 <b>Что делать:</b>\n"
            f"{'• Обратитесь к наставнику для увеличения лимита попыток' if test.max_attempts > 0 else '• Этот тест можно пройти только один раз'}\n"
            f"• Изучите материалы к тесту более внимательно\n"
            f"• Просмотрите свои ошибки в предыдущих попытках",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="📋 К списку тестов", callback_data="back_to_test_list")]
            ])
        )
        await state.clear()
        await callback.answer()
        return
    
    questions = await get_test_questions(session, test_id)
    if not questions:
        await callback.message.edit_text("❌ В этом тесте нет вопросов. Обратитесь к наставнику.")
        await state.clear()
        return

    # Перемешиваем вопросы, если настройка включена
    questions_list = list(questions)
    if test.shuffle_questions:
        random.shuffle(questions_list)

    await state.update_data(
        test_id=test_id,
        questions=questions_list,
        current_question_index=0,
        user_answers={},
        answers_details=[],
        start_time=datetime.now(),
        shuffle_enabled=test.shuffle_questions,
        user_id=callback.from_user.id  # Сохраняем Telegram ID пользователя
    )

    await show_question(callback.message, state)
    await callback.answer()

async def show_question(message: Message, state: FSMContext):
    """Отображает текущий вопрос"""
    data = await state.get_data()
    questions = data['questions']
    index = data['current_question_index']
    shuffle_enabled = data.get('shuffle_enabled', False)
    
    question = questions[index]
    
    # Засекаем время начала показа вопроса
    await state.update_data(question_start_time=datetime.now())
    
    # Подготавливаем варианты ответов для текущего вопроса
    current_options = None
    keyboard = []
    
    if question.question_type == 'single_choice':
        options = list(question.options)
        # Перемешиваем варианты только если включена настройка перемешивания
        if shuffle_enabled:
            random.shuffle(options)
        
        current_options = options
        # Сохраняем порядок вариантов для корректного сопоставления ответов
        await state.update_data(current_options_order=options)
        
        for i, option in enumerate(options):
            keyboard.append([InlineKeyboardButton(text=option, callback_data=f"answer:{i}")])
    elif question.question_type == 'multiple_choice':
        options = list(question.options)
        # Перемешиваем варианты только если включена настройка перемешивания
        if shuffle_enabled:
            random.shuffle(options)
        
        current_options = options
        # Сохраняем порядок вариантов для корректного сопоставления ответов
        await state.update_data(current_options_order=options)
        
        # Для множественного выбора показываем только инструкцию, без кнопок выбора
        keyboard.append([InlineKeyboardButton(text="📝 Отправьте номера вариантов через запятую", callback_data="info")])
    elif question.question_type == 'yes_no':
        keyboard.append([
            InlineKeyboardButton(text="👍 Да", callback_data="answer:Да"),
            InlineKeyboardButton(text="👎 Нет", callback_data="answer:Нет")
        ])
    
    keyboard.append([InlineKeyboardButton(text="❌ Прервать тест", callback_data=f"cancel_test:{question.test_id}")])

    question_text = f"<b>Вопрос {index + 1}/{len(questions)}:</b>\n\n{question.question_text}"
    
    if question.question_type == 'text' or question.question_type == 'number':
        question_text += "\n\n<i>Отправьте ваш ответ сообщением.</i>"
    elif question.question_type == 'multiple_choice':
        # Показываем варианты ответов в тексте - используем текущие варианты для этого вопроса
        options_text = "\n".join([f"{i+1}. {option}" for i, option in enumerate(current_options)])
        question_text += f"\n\n<b>Варианты ответов:</b>\n{options_text}"
        question_text += "\n\n<i>Отправьте номера правильных ответов через запятую (например: 1, 3)</i>"

    # Пытаемся отредактировать сообщение, если не получается - отправляем новое
    try:
        sent_message = await message.edit_text(
            question_text,
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard)
        )
        # Сохраняем ID последнего сообщения бота для будущего редактирования
        await state.update_data(last_bot_message_id=sent_message.message_id)
    except Exception:
        # Если не можем отредактировать (например, это текстовый ответ пользователя),
        # отправляем новое сообщение
        sent_message = await message.answer(
            question_text,
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard)
        )
        # Сохраняем ID нового сообщения бота
        await state.update_data(last_bot_message_id=sent_message.message_id)
    
    await state.set_state(TestTakingStates.taking_test)

@router.message(TestTakingStates.taking_test)
async def process_text_answer(message: Message, state: FSMContext, session: AsyncSession):
    """Обработка текстового, числового или множественного ответа"""
    data = await state.get_data()
    questions = data['questions']
    index = data['current_question_index']
    question = questions[index]

    # Рассчитываем время ответа
    start_time = data.get('question_start_time', datetime.now())
    time_spent = (datetime.now() - start_time).total_seconds()

    user_answers = data.get('user_answers', {})
    answers_details = data.get('answers_details', [])
    
    user_answer = message.text.strip()
    
    if question.question_type == 'number':
        try:
            float(user_answer)
        except ValueError:
            await message.answer("❌ Пожалуйста, введите число.")
            return
    elif question.question_type == 'multiple_choice':
        # Обработка множественного выбора
        current_options = data.get('current_options_order', question.options)
        selected_answers = []
        
        # Сначала пробуем обработать как номера вариантов
        try:
            # Разделяем по запятым и пытаемся преобразовать в числа
            parts = [part.strip() for part in user_answer.split(',')]
            indices = [int(part) - 1 for part in parts]
            
            # Проверяем, что все индексы в допустимом диапазоне
            for idx in indices:
                if 0 <= idx < len(current_options):
                    selected_answers.append(current_options[idx])
            
            if len(selected_answers) != len(indices):
                raise ValueError("Некоторые номера вне диапазона")
                
        except (ValueError, IndexError):
            # Если не получилось как номера, пробуем как сами варианты ответов
            parts = [part.strip() for part in user_answer.split(',')]
            selected_answers = []
            
            for part in parts:
                # Ищем точное совпадение среди вариантов
                matching_option = None
                for option in current_options:
                    if part.lower() == option.lower():  # Сравниваем без учета регистра
                        matching_option = option
                        break
                
                if matching_option:
                    selected_answers.append(matching_option)
            
            # Если не нашли ни одного совпадения, показываем ошибку
            if not selected_answers:
                await message.answer(
                    "❌ Пожалуйста, введите:\n"
                    "• Номера вариантов через запятую (например: 1, 3)\n"
                    "• Или сами варианты ответов через запятую"
                )
                return
        
        user_answer = selected_answers

    user_answers[index] = user_answer
    
    # Проверка правильности ответа
    is_correct = False
    if question.question_type == 'multiple_choice':
        # Для множественного выбора сравниваем списки
        try:
            correct_answers = json.loads(question.correct_answer) if isinstance(question.correct_answer, str) else question.correct_answer
            is_correct = set(user_answer) == set(correct_answers)
        except Exception as e:
            logger.error(f"Ошибка обработки множественного выбора для вопроса {question.id}: {e}")
            is_correct = user_answer == question.correct_answer
    else:
        is_correct = user_answer == question.correct_answer
    
    answers_details.append({
        "question_id": question.id,
        "answer": user_answer,
        "is_correct": is_correct,
        "time_spent": time_spent
    })
    
    await state.update_data(user_answers=user_answers, answers_details=answers_details)
    
    await process_next_step(message, state, session)

@router.callback_query(TestTakingStates.taking_test, F.data.startswith("answer:"))
async def process_answer_selection(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Обработка ответа на вопрос с выбором"""
    data = await state.get_data()
    questions = data['questions']
    index = data['current_question_index']
    question = questions[index]
    
    # Рассчитываем время ответа
    start_time = data.get('question_start_time', datetime.now())
    time_spent = (datetime.now() - start_time).total_seconds()
    
    # Сохраняем ответ
    user_answers = data.get('user_answers', {})
    answers_details = data.get('answers_details', [])
    
    if question.question_type == 'single_choice':
        selected_option_index = int(callback.data.split(':')[1])
        # Используем сохраненный порядок вариантов
        current_options = data.get('current_options_order', question.options)
        user_answers[index] = current_options[selected_option_index]
    elif question.question_type == 'yes_no':
        user_answers[index] = callback.data.split(':')[1]
    elif question.question_type == 'multiple_choice':
        # Multiple choice должен обрабатываться только через текстовый ввод
        await callback.answer("❌ Для множественного выбора отправьте номера вариантов сообщением.", show_alert=True)
        return
    
    # Проверка правильности ответа (multiple_choice не попадает сюда)
    is_correct = user_answers[index] == question.correct_answer
    
    answers_details.append({
        "question_id": question.id,
        "answer": user_answers[index],
        "is_correct": is_correct,
        "time_spent": time_spent
    })

    await state.update_data(user_answers=user_answers, answers_details=answers_details)
    
    await process_next_step(callback.message, state, session)
    await callback.answer()

async def process_next_step(message: Message, state: FSMContext, session: AsyncSession):
    """Переходит к следующему вопросу или завершает тест"""
    data = await state.get_data()
    index = data['current_question_index']
    questions = data['questions']

    new_index = index + 1
    if new_index < len(questions):
        await state.update_data(current_question_index=new_index)
        await show_question(message, state)
    else:
        await finish_test(message, state, session)

async def finish_test(message: Message, state: FSMContext, session: AsyncSession):
    """Завершение теста и подсчет результатов"""
    data = await state.get_data()
    questions = data['questions']
    user_answers = data['user_answers']
    test_id = data['test_id']
    
    score = 0
    wrong_answers_data = []
    
    # Используем уже собранные правильные answers_details из состояния
    answers_details = data.get('answers_details', [])
    
    # Подсчитываем очки на основе уже правильно рассчитанных answers_details
    for answer_detail in answers_details:
        question_id = answer_detail['question_id']
        is_correct = answer_detail['is_correct']
        
        # Находим соответствующий вопрос
        question = next((q for q in questions if q.id == question_id), None)
        if not question:
            continue
            
        if is_correct:
            score += question.points
        else:
            score -= question.penalty_points
            # Добавляем в список ошибок
            # Форматируем правильный ответ для удобного отображения
            correct_answer_display = question.correct_answer
            if question.question_type == 'multiple_choice':
                try:
                    correct_answers = json.loads(question.correct_answer) if isinstance(question.correct_answer, str) else question.correct_answer
                    if isinstance(correct_answers, list):
                        correct_answer_display = ', '.join(correct_answers)
                except Exception:
                    pass  # Если не удается распарсить, оставляем как есть
            
            # Форматируем пользовательский ответ для удобного отображения
            user_answer_display = answer_detail['answer']
            if question.question_type == 'multiple_choice' and isinstance(user_answer_display, list):
                user_answer_display = ', '.join(user_answer_display)
            
            wrong_answers_data.append({
                "question": question.question_text,
                "user_answer": user_answer_display,
                "correct_answer": correct_answer_display
            })
    
    test = await get_test_by_id(session, test_id)
    score = max(0, score) # Не уходим в минус
    is_passed = score >= test.threshold_score
    
    # Получаем пользователя и используем его внутренний ID
    user_tg_id = data.get('user_id')  # Получаем Telegram ID из состояния
    if not user_tg_id:
        # Fallback для старых сессий
        user_tg_id = message.from_user.id if hasattr(message, 'from_user') and message.from_user else None
    
    if not user_tg_id:
        await message.answer(
            "❌ <b>Ошибка сохранения результата</b>\n\n"
            "Не удалось определить пользователя. Обратитесь к администратору.",
            parse_mode="HTML"
        )
        await state.clear()
        return
    
    user = await get_user_by_tg_id(session, user_tg_id)
    if not user:
        await message.answer(
            "❌ <b>Ошибка сохранения результата</b>\n\n"
            "Пользователь не найден в системе. Обратитесь к администратору.",
            parse_mode="HTML"
        )
        await state.clear()
        return
    
    # Сохраняем результат
    result_data = {
        'user_id': user.id,  # Используем внутренний ID пользователя из БД
        'test_id': test_id,
        'score': score,
        'max_possible_score': test.max_score,
        'is_passed': is_passed,
        'start_time': data['start_time'],
        'end_time': datetime.now(),
        'answers_details': data.get('answers_details', []),
        'wrong_answers': wrong_answers_data
    }
    result = await save_test_result(session, result_data)
    
    if not result:
        await message.answer(
            "❌ <b>Ошибка сохранения результата</b>\n\n"
            "Не удалось сохранить результат теста. Обратитесь к администратору.",
            parse_mode="HTML"
        )
        await state.clear()
        return
    
    status_text = "✅ <b>Тест успешно пройден!</b>" if is_passed else "❌ <b>Тест не пройден</b>"
    
    keyboard = []
    # Показываем кнопку "Показать мои ошибки" только если есть ошибки
    # и тест содержит вопросы с вариантами ответов (не только свободный ввод)
    if wrong_answers_data:
        # Проверяем, есть ли в тесте вопросы с вариантами ответов
        has_choice_questions = any(q.question_type in ['single_choice', 'multiple_choice', 'yes_no'] for q in questions)
        if has_choice_questions:
            keyboard.append([InlineKeyboardButton(text="🔍 Показать мои ошибки", callback_data=f"show_errors:{result.id}")])

    try:
        await message.edit_text(
            f"{status_text}\n\n"
            f"Ваш результат: <b>{score}</b> из <b>{test.max_score}</b> баллов.\n"
            f"Проходной балл: {test.threshold_score}\n\n"
            "Вы можете посмотреть детальную статистику в разделе 'Посмотреть баллы'.",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard)
        )
    except Exception:
        # Если не можем отредактировать сообщение (например, это текстовый ответ пользователя),
        # отправляем новое сообщение
        await message.answer(
            f"{status_text}\n\n"
            f"Ваш результат: <b>{score}</b> из <b>{test.max_score}</b> баллов.\n"
            f"Проходной балл: {test.threshold_score}\n\n"
            "Вы можете посмотреть детальную статистику в разделе 'Посмотреть баллы'.",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard)
        )
    await state.clear()

@router.callback_query(F.data.startswith("show_errors:"))
async def show_wrong_answers(callback: CallbackQuery, session: AsyncSession):
    """Показывает неверные ответы пользователя"""
    result_id = int(callback.data.split(':')[1])
    test_result = await session.get(TestResult, result_id)
    
    if not test_result or not test_result.wrong_answers:
        await callback.answer("✅ У вас не было ошибок в этом тесте!", show_alert=True)
        return
        
    errors_text = "<b>🔍 Ваши ошибки:</b>\n\n"
    for i, error in enumerate(test_result.wrong_answers, 1):
        errors_text += (
            f"<b>{i}. Вопрос:</b> {error['question']}\n"
            f"   - Ваш ответ: <code>{error['user_answer']}</code>\n"
            f"   - Правильный ответ: <code>{error['correct_answer']}</code>\n\n"
        )
        
    await callback.message.answer(errors_text, parse_mode="HTML")
    await callback.answer()

@router.callback_query(F.data.startswith("view_materials:"))
async def process_view_materials(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Обработчик просмотра материалов к тесту"""
    test_id = int(callback.data.split(':')[1])
    
    test = await get_test_by_id(session, test_id)
    if not test or not test.material_link:
        await callback.message.edit_text(
            "📚 <b>Материалы для изучения</b>\n\n"
            "К этому тесту не прикреплены материалы для изучения.",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="⬅️ Назад к тесту", callback_data=f"take_test:{test_id}")],
                [InlineKeyboardButton(text="📋 К списку тестов", callback_data="back_to_test_list")]
            ])
        )
        await callback.answer()
        return
    
    if test.material_file_path:
        # Если есть прикрепленный файл - отправляем его
        try:
            await callback.message.answer_document(
                document=test.material_file_path,
                caption=f"📚 <b>Материалы для изучения</b>\n\n"
                       f"📌 <b>Тест:</b> {test.name}\n\n"
                       f"💡 <b>Рекомендация:</b> Внимательно изучите материалы перед прохождением теста!",
                parse_mode="HTML"
            )
            await callback.message.edit_text(
                f"✅ <b>Материалы отправлены!</b>\n\n"
                f"📌 <b>Тест:</b> {test.name}\n\n"
                f"📎 Документ с материалами отправлен выше.",
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="⬅️ Назад к тесту", callback_data=f"take_test:{test_id}")],
                    [InlineKeyboardButton(text="📋 К списку тестов", callback_data="back_to_test_list")]
                ])
            )
        except Exception as e:
            await callback.message.edit_text(
                f"❌ <b>Ошибка загрузки файла</b>\n\n"
                f"Не удалось загрузить прикрепленный файл.\n"
                f"Обратитесь к наставнику.\n\n"
                f"📌 <b>Тест:</b> {test.name}",
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="⬅️ Назад к тесту", callback_data=f"take_test:{test_id}")],
                    [InlineKeyboardButton(text="📋 К списку тестов", callback_data="back_to_test_list")]
                ])
            )
    else:
        # Если это ссылка
        await callback.message.edit_text(
            f"📚 <b>Материалы для изучения</b>\n\n"
            f"📌 <b>Тест:</b> {test.name}\n\n"
            f"🔗 <b>Ссылка на материалы:</b>\n{test.material_link}\n\n"
            f"💡 <b>Рекомендация:</b> Внимательно изучите материалы перед прохождением теста!",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="⬅️ Назад к тесту", callback_data=f"take_test:{test_id}")],
                [InlineKeyboardButton(text="📋 К списку тестов", callback_data="back_to_test_list")]
            ])
        )
    
    await callback.answer()
    
    log_user_action(
        callback.from_user.id, 
        callback.from_user.username, 
        "viewed test materials", 
        {"test_id": test_id}
    )

@router.callback_query(F.data == "back_to_test_list")
async def process_back_to_test_list(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Возврат к списку тестов"""
    user = await get_user_by_tg_id(session, callback.from_user.id)
    available_tests = await get_trainee_available_tests(session, user.id)
    
    if not available_tests:
        await callback.message.edit_text(
            "📋 <b>Доступные тесты</b>\n\n"
            "У вас пока нет доступных тестов.\n"
            "Обратитесь к наставнику для получения доступа.",
            parse_mode="HTML"
        )
        await callback.answer()
        return
    
    tests_list = []
    for i, test in enumerate(available_tests, 1):
        stage_info = ""
        if test.stage_id:
            stage = await session.execute(select(InternshipStage).where(InternshipStage.id == test.stage_id))
            stage_obj = stage.scalar_one_or_none()
            if stage_obj:
                stage_info = f" | Этап: {stage_obj.name}"
        
        materials_info = " | 📚 Есть материалы" if test.material_link else ""
        
        tests_list.append(
            f"<b>{i}. {test.name}</b>\n"
            f"   🎯 Порог: {test.threshold_score}/{test.max_score} баллов{stage_info}{materials_info}\n"
            f"   📝 {test.description or 'Описание не указано'}"
        )
    
    tests_display = "\n\n".join(tests_list)
    
    await callback.message.edit_text(
        f"📋 <b>Доступные тесты</b>\n\n"
        f"У вас есть доступ к <b>{len(available_tests)}</b> тестам:\n\n"
        f"{tests_display}\n\n"
        "💡 <b>Рекомендация:</b> Изучите материалы перед прохождением теста!",
        parse_mode="HTML",
        reply_markup=get_test_selection_for_taking_keyboard(available_tests)
    )
    
    await state.set_state(TestTakingStates.waiting_for_test_selection)
    await callback.answer()

@router.callback_query(F.data.startswith("cancel_test:"))
async def process_cancel_test(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Обработчик отмены/прерывания теста"""
    test_id = int(callback.data.split(':')[1])
    
    test = await get_test_by_id(session, test_id)
    test_name = test.name if test else "Неизвестный тест"
    
    await callback.message.edit_text(
        f"❌ <b>Тест прерван</b>\n\n"
        f"Прохождение теста <b>«{test_name}»</b> было прервано.\n"
        "Вы можете вернуться к прохождению в любое время.",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔄 Попробовать снова", callback_data=f"take_test:{test_id}")],
            [InlineKeyboardButton(text="📋 К списку тестов", callback_data="back_to_test_list")]
        ])
    )
    
    await state.clear()
    await callback.answer()
    
    log_user_action(
        callback.from_user.id, 
        callback.from_user.username, 
        "cancelled test", 
        {"test_id": test_id}
    )

@router.callback_query(F.data == "cancel")
async def process_general_cancel(callback: CallbackQuery, state: FSMContext):
    """Обработчик общей отмены в контексте прохождения тестов"""
    await callback.message.edit_text(
        "❌ <b>Операция отменена</b>\n\n"
        "Используйте команды бота или кнопки клавиатуры для навигации.",
        parse_mode="HTML"
    )
    await state.clear()
    await callback.answer()

@router.callback_query(TestTakingStates.waiting_for_test_start, F.data.startswith("take_test:"))
async def process_back_to_test_details(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Обработчик возврата к деталям теста"""
    await process_test_selection_for_taking(callback, state, session)

@router.callback_query(F.data == "info")
async def process_info_button(callback: CallbackQuery):
    """Обработчик информационных кнопок с инструкциями"""
    await callback.answer(
        "💡 Для ответа введите номера вариантов через запятую.\n"
        "Например: 1, 3 или 2, 4, 5",
        show_alert=True
    )

@router.callback_query(F.data.startswith("take_test:"))
async def process_take_test_from_notification(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Обработчик кнопки 'Перейти к тесту' из уведомления"""
    test_id = int(callback.data.split(':')[1])
    
    test = await get_test_by_id(session, test_id)
    if not test:
        await callback.message.edit_text("❌ Тест не найден.")
        await callback.answer()
        return
    
    # Проверяем доступ к тесту
    user = await get_user_by_tg_id(session, callback.from_user.id)
    if not user:
        await callback.message.edit_text("❌ Пользователь не найден.")
        await callback.answer()
        return
        
    has_access = await check_test_access(session, user.id, test_id)
    
    if not has_access:
        await callback.message.edit_text(
            "❌ <b>Доступ запрещен</b>\n\n"
            "У вас нет доступа к этому тесту. Обратитесь к наставнику.",
            parse_mode="HTML"
        )
        await callback.answer()
        return
    
    # Проверяем количество попыток
    attempts_count = await get_user_test_attempts_count(session, user.id, test_id)
    
    # Проверяем, есть ли уже результат
    existing_result = await get_user_test_result(session, user.id, test_id)
    
    # Получаем информацию о тесте
    questions = await get_test_questions(session, test_id)
    questions_count = len(questions)
    
    stage_info = ""
    if test.stage_id:
        stage = await session.execute(select(InternshipStage).where(InternshipStage.id == test.stage_id))
        stage_obj = stage.scalar_one_or_none()
        if stage_obj:
            stage_info = f"🎯 <b>Этап:</b> {stage_obj.name}\n"
    
    materials_info = ""
    if test.material_link:
        if test.material_file_path:
            # Если есть прикрепленный файл
            materials_info = f"📚 <b>Материалы для изучения:</b>\n🔗 {test.material_link}\n\n"
        else:
            # Если это ссылка
            materials_info = f"📚 <b>Материалы для изучения:</b>\n{test.material_link}\n\n"
    
    # Информация о попытках
    attempts_info = ""
    if test.max_attempts > 0:
        attempts_info = f"🔢 <b>Попытки:</b> {attempts_count}/{test.max_attempts}\n"
    else:
        attempts_info = f"♾️ <b>Попытки:</b> бесконечно (текущая: {attempts_count + 1})\n"
    
    previous_result_info = ""
    if existing_result:
        status = "пройден" if existing_result.is_passed else "не пройден"
        previous_result_info = f"""
🔄 <b>Предыдущий результат:</b>
   • Статус: {status}
   • Баллы: {existing_result.score}/{existing_result.max_possible_score}
   • Дата: {existing_result.created_date.strftime('%d.%m.%Y %H:%M')}

"""
    
    test_info = f"""📋 <b>Информация о тесте</b>

📌 <b>Название:</b> {test.name}
📝 <b>Описание:</b> {test.description or 'Не указано'}
{stage_info}❓ <b>Количество вопросов:</b> {questions_count}
🎯 <b>Порог прохождения:</b> {test.threshold_score} из {test.max_score} баллов
{attempts_info}{materials_info}{previous_result_info}"""
    
    await callback.message.edit_text(
        test_info,
        parse_mode="HTML",
        reply_markup=get_test_start_keyboard(test_id, bool(existing_result))
    )
    
    await state.update_data(selected_test_id=test_id)
    await state.set_state(TestTakingStates.waiting_for_test_start)
    
    await callback.answer()
    
    log_user_action(
        callback.from_user.id, 
        callback.from_user.username, 
        "took test from notification", 
        {"test_id": test_id}
    )

@router.callback_query(F.data == "available_tests")
async def process_available_tests_shortcut(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Обработчик быстрого перехода к доступным тестам из уведомления"""
    user = await get_user_by_tg_id(session, callback.from_user.id)
    if not user:
        await callback.message.edit_text("❌ Пользователь не найден.")
        await callback.answer()
        return
    
    # Проверяем права
    has_permission = await check_user_permission(session, user.id, "take_tests")
    if not has_permission:
        await callback.message.edit_text("❌ У вас нет прав для прохождения тестов.")
        await callback.answer()
        return
    
    available_tests = await get_trainee_available_tests(session, user.id)
    
    if not available_tests:
        await callback.message.edit_text(
            "📋 <b>Доступные тесты</b>\n\n"
            "У вас пока нет доступных тестов для прохождения.\n"
            "Обратитесь к наставнику для получения доступа к тестам.",
            parse_mode="HTML"
        )
        await callback.answer()
        return
    
    tests_list = []
    for i, test in enumerate(available_tests, 1):
        stage_info = ""
        if test.stage_id:
            stage = await session.execute(select(InternshipStage).where(InternshipStage.id == test.stage_id))
            stage_obj = stage.scalar_one_or_none()
            if stage_obj:
                stage_info = f" | Этап: {stage_obj.name}"
        
        materials_info = " | 📚 Есть материалы" if test.material_link else ""
        
        tests_list.append(
            f"<b>{i}. {test.name}</b>\n"
            f"   🎯 Порог: {test.threshold_score}/{test.max_score} баллов{stage_info}{materials_info}\n"
            f"   📝 {test.description or 'Описание не указано'}"
        )
    
    tests_display = "\n\n".join(tests_list)
    
    await callback.message.edit_text(
        f"📋 <b>Доступные тесты</b>\n\n"
        f"У вас есть доступ к <b>{len(available_tests)}</b> тестам:\n\n"
        f"{tests_display}\n\n"
        "💡 <b>Рекомендация:</b> Изучите материалы перед прохождением теста!",
        parse_mode="HTML",
        reply_markup=get_test_selection_for_taking_keyboard(available_tests)
    )
    
    await state.set_state(TestTakingStates.waiting_for_test_selection)
    await callback.answer()
    
    log_user_action(callback.from_user.id, callback.from_user.username, "opened tests from notification")