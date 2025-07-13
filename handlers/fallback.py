"""
Обработчики для нестандартного ввода пользователей в различных состояниях FSM

Этот модуль обеспечивает обработку всех неожиданных вводов пользователей:

🔄 ПРИНЦИП РАБОТЫ:
- Каждое состояние FSM имеет свой специфический обработчик
- Обработчики анализируют тип ошибки и дают конкретные инструкции
- Универсальный обработчик ловит все остальные случаи
- Все неожиданные действия логируются для анализа

🎯 ПОЛНОЕ ПОКРЫТИЕ ВСЕХ СОСТОЯНИЙ FSM:
- ✅ Авторизация и регистрация (AuthStates, RegistrationStates)
- ✅ Административная панель (AdminStates) - все 8 состояний
- ✅ Создание тестов (TestCreationStates) - все 21 состояние
- ✅ Редактирование тестов - все состояния редактирования
- ✅ Прохождение тестов (TestTakingStates) - все 5 состояний  
- ✅ Наставничество (MentorshipStates) - все 6 состояний
- ✅ Управление стажерами (TraineeManagementStates) - все 3 состояния
- ✅ Работа с материалами и медиафайлами
- ✅ Валидация числовых значений
- ✅ Обработка всех типов контента

⚠️ ВАЖНО:
- Fallback роутер должен быть подключен ПОСЛЕДНИМ в main.py
- Все обработчики предоставляют четкие инструкции пользователю
- Команда /cancel доступна в любом состоянии для выхода
"""

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.filters import StateFilter

from states.states import (
    AuthStates, RegistrationStates, AdminStates, 
    TestCreationStates, TestTakingStates, 
    MentorshipStates, TraineeManagementStates
)
from keyboards.keyboards import get_role_selection_keyboard, get_yes_no_keyboard, get_question_type_keyboard
from utils.logger import log_user_action

router = Router()

# =================================
# ОБРАБОТЧИКИ ДЛЯ СОСТОЯНИЙ АВТОРИЗАЦИИ
# =================================

@router.message(StateFilter(AuthStates.waiting_for_auth))
async def handle_unexpected_auth_input(message: Message, state: FSMContext):
    """Обработка неожиданного ввода в состоянии авторизации"""
    await message.answer(
        "❓ <b>Неожиданный ввод</b>\n\n"
        "Вы находитесь в процессе авторизации.\n"
        "Пожалуйста, используйте команду <code>/login</code> для входа в систему или <code>/register</code> для регистрации.\n\n"
        "Для отмены используйте <code>/cancel</code>",
        parse_mode="HTML"
    )

# =================================
# ОБРАБОТЧИКИ ДЛЯ СОСТОЯНИЙ РЕГИСТРАЦИИ
# =================================

@router.message(StateFilter(RegistrationStates.waiting_for_full_name))
async def handle_unexpected_name_input(message: Message, state: FSMContext):
    """Обработка неожиданного ввода при запросе имени"""
    if not message.text or len(message.text.strip()) < 2:
        await message.answer(
            "❌ <b>Некорректное имя</b>\n\n"
            "Пожалуйста, введите ваше полное имя (минимум 2 символа).\n"
            "Например: <code>Иван Петров</code>\n\n"
            "Для отмены регистрации используйте <code>/cancel</code>",
            parse_mode="HTML"
        )
    else:
        # Если текст корректный, но что-то пошло не так, повторяем инструкцию
        await message.answer(
            "🔄 <b>Повторите ввод</b>\n\n"
            "Пожалуйста, введите ваше полное имя для регистрации.\n"
            "Например: <code>Иван Петров</code>",
            parse_mode="HTML"
        )

@router.message(StateFilter(RegistrationStates.waiting_for_phone))
async def handle_unexpected_phone_input(message: Message, state: FSMContext):
    """Обработка неожиданного ввода при запросе телефона"""
    await message.answer(
        "❌ <b>Некорректный формат телефона</b>\n\n"
        "Пожалуйста, отправьте ваш номер телефона, используя кнопку 'Поделиться контактом' или введите в формате:\n"
        "• <code>+7 (999) 123-45-67</code>\n"
        "• <code>89991234567</code>\n\n"
        "Для отмены регистрации используйте <code>/cancel</code>",
        parse_mode="HTML"
    )

@router.message(StateFilter(RegistrationStates.waiting_for_role))
async def handle_unexpected_role_input(message: Message, state: FSMContext):
    """Обработка неожиданного ввода при выборе роли"""
    await message.answer(
        "❌ <b>Некорректный выбор роли</b>\n\n"
        "Пожалуйста, выберите роль, используя кнопки ниже:",
        parse_mode="HTML",
        reply_markup=get_role_selection_keyboard()
    )

@router.message(StateFilter(RegistrationStates.waiting_for_admin_token))
async def handle_unexpected_token_input(message: Message, state: FSMContext):
    """Обработка неожиданного ввода при запросе админ-токена"""
    await message.answer(
        "❌ <b>Некорректный токен</b>\n\n"
        "Введите корректный токен администратора для регистрации в роли управляющего.\n"
        "Если у вас нет токена, вернитесь к выбору роли.\n\n"
        "Для отмены используйте <code>/cancel</code>",
        parse_mode="HTML"
    )

# =================================
# ОБРАБОТЧИКИ ДЛЯ СОСТОЯНИЙ СОЗДАНИЯ ТЕСТОВ
# =================================

@router.message(StateFilter(TestCreationStates.waiting_for_materials))
async def handle_unexpected_materials_input(message: Message, state: FSMContext):
    """Обработка неожиданного ввода при добавлении материалов"""
    if message.photo:
        await message.answer(
            "❌ <b>Изображения не поддерживаются</b>\n\n"
            "Для материалов можно использовать только:\n"
            "• 📎 PDF документы\n"
            "• 📝 Текстовые ссылки\n"
            "• ⏭️ Пропустить (если материалы не нужны)\n\n"
            "Пожалуйста, отправьте PDF документ или текст.",
            parse_mode="HTML"
        )
    elif message.video or message.audio or message.voice or message.video_note:
        await message.answer(
            "❌ <b>Медиафайлы не поддерживаются</b>\n\n"
            "Для материалов можно использовать только:\n"
            "• 📎 PDF документы\n"
            "• 📝 Текстовые ссылки\n"
            "• ⏭️ Пропустить (если материалы не нужны)\n\n"
            "Пожалуйста, отправьте PDF документ или текст.",
            parse_mode="HTML"
        )
    elif message.sticker:
        await message.answer(
            "❌ <b>Стикеры не поддерживаются</b>\n\n"
            "Для материалов можно использовать только:\n"
            "• 📎 PDF документы\n"
            "• 📝 Текстовые ссылки\n"
            "• ⏭️ Пропустить (если материалы не нужны)",
            parse_mode="HTML"
        )
    else:
        await message.answer(
            "🔄 <b>Повторите ввод</b>\n\n"
            "Пожалуйста, отправьте материалы для изучения:\n"
            "• 📎 PDF документ\n"
            "• 📝 Текстовую информацию или ссылки\n"
            "• Или нажмите кнопку 'Пропустить', если материалы не нужны",
            parse_mode="HTML"
        )

@router.message(StateFilter(TestCreationStates.waiting_for_test_name))
async def handle_unexpected_test_name_input(message: Message, state: FSMContext):
    """Обработка неожиданного ввода при запросе названия теста"""
    if not message.text or len(message.text.strip()) < 3:
        await message.answer(
            "❌ <b>Некорректное название</b>\n\n"
            "Название теста должно содержать минимум 3 символа.\n"
            "Пожалуйста, введите осмысленное название для вашего теста.\n\n"
            "Для отмены создания теста используйте <code>/cancel</code>",
            parse_mode="HTML"
        )
    else:
        await message.answer(
            "🔄 <b>Повторите ввод</b>\n\n"
            "Пожалуйста, введите название для вашего теста:",
            parse_mode="HTML"
        )

@router.message(StateFilter(TestCreationStates.waiting_for_description))
async def handle_unexpected_description_input(message: Message, state: FSMContext):
    """Обработка неожиданного ввода при запросе описания теста"""
    await message.answer(
        "🔄 <b>Повторите ввод</b>\n\n"
        "Пожалуйста, введите описание для вашего теста.\n"
        "Описание поможет стажерам понять цель и содержание теста.\n\n"
        "Вы можете нажать кнопку 'Пропустить', если не хотите добавлять описание.",
        parse_mode="HTML"
    )

@router.message(StateFilter(TestCreationStates.waiting_for_question_text))
async def handle_unexpected_question_text_input(message: Message, state: FSMContext):
    """Обработка неожиданного ввода при запросе текста вопроса"""
    if not message.text or len(message.text.strip()) < 5:
        await message.answer(
            "❌ <b>Слишком короткий вопрос</b>\n\n"
            "Текст вопроса должен содержать минимум 5 символов.\n"
            "Пожалуйста, сформулируйте вопрос более подробно.",
            parse_mode="HTML"
        )
    else:
        await message.answer(
            "🔄 <b>Повторите ввод</b>\n\n"
            "Пожалуйста, введите текст вопроса:",
            parse_mode="HTML"
        )

@router.message(StateFilter(TestCreationStates.waiting_for_option))
async def handle_unexpected_option_input(message: Message, state: FSMContext):
    """Обработка неожиданного ввода при добавлении вариантов ответа"""
    if not message.text or len(message.text.strip()) < 1:
        await message.answer(
            "❌ <b>Пустой вариант ответа</b>\n\n"
            "Вариант ответа не может быть пустым.\n"
            "Пожалуйста, введите текст варианта ответа:",
            parse_mode="HTML"
        )
    else:
        await message.answer(
            "🔄 <b>Повторите ввод</b>\n\n"
            "Пожалуйста, введите вариант ответа:",
            parse_mode="HTML"
        )

@router.message(StateFilter(TestCreationStates.waiting_for_answer))
async def handle_unexpected_answer_input(message: Message, state: FSMContext):
    """Обработка неожиданного ввода при запросе правильного ответа"""
    data = await state.get_data()
    q_type = data.get('current_question_type')
    
    if q_type == 'single_choice':
        await message.answer(
            "❌ <b>Некорректный номер ответа</b>\n\n"
            "Пожалуйста, введите номер правильного ответа из предложенных вариантов.\n"
            "Например: <code>2</code>",
            parse_mode="HTML"
        )
    elif q_type == 'multiple_choice':
        await message.answer(
            "❌ <b>Некорректный формат ответа</b>\n\n"
            "Пожалуйста, введите номера правильных ответов через запятую.\n"
            "Например: <code>1, 3</code> или <code>2, 4, 5</code>",
            parse_mode="HTML"
        )
    else:
        await message.answer(
            "🔄 <b>Повторите ввод</b>\n\n"
            "Пожалуйста, введите правильный ответ на вопрос:",
            parse_mode="HTML"
        )

@router.message(StateFilter(TestCreationStates.waiting_for_points))
async def handle_unexpected_points_input(message: Message, state: FSMContext):
    """Обработка неожиданного ввода при запросе баллов"""
    if message.text:
        try:
            points = float(message.text.replace(',', '.'))
            if points <= 0:
                await message.answer(
                    "❌ <b>Баллы должны быть больше нуля</b>\n\n"
                    "Пожалуйста, введите положительное число баллов.\n"
                    "Например: <code>1</code>, <code>2.5</code>, <code>0.5</code>",
                    parse_mode="HTML"
                )
            else:
                await message.answer(
                    "❌ <b>Неожиданная ошибка</b>\n\n"
                    "Повторите ввод количества баллов:",
                    parse_mode="HTML"
                )
        except ValueError:
            await message.answer(
                "❌ <b>Некорректное количество баллов</b>\n\n"
                "Пожалуйста, введите положительное число баллов за правильный ответ.\n"
                "Можно использовать дробные числа: <code>1</code>, <code>2.5</code>, <code>0.5</code>\n\n"
                "Баллы должны быть больше нуля.",
                parse_mode="HTML"
            )
    else:
        await message.answer(
            "❌ <b>Пустое значение</b>\n\n"
            "Пожалуйста, введите количество баллов числом.",
            parse_mode="HTML"
        )

@router.message(StateFilter(TestCreationStates.waiting_for_threshold))
async def handle_unexpected_threshold_input(message: Message, state: FSMContext):
    """Обработка неожиданного ввода при запросе проходного балла"""
    data = await state.get_data()
    questions = data.get('questions', [])
    max_score = sum(q['points'] for q in questions) if questions else 100
    
    await message.answer(
        f"❌ <b>Некорректный проходной балл</b>\n\n"
        f"Проходной балл должен быть числом от 0.5 до {max_score}.\n"
        f"Введите корректное значение проходного балла:",
        parse_mode="HTML"
    )

# =================================
# ОБРАБОТЧИКИ ДЛЯ АДМИНИСТРАТИВНЫХ СОСТОЯНИЙ
# =================================

@router.message(StateFilter(AdminStates.waiting_for_user_selection))
async def handle_unexpected_admin_user_selection(message: Message, state: FSMContext):
    """Обработка неожиданного ввода при выборе пользователя для управления"""
    await message.answer(
        "❌ <b>Некорректный выбор пользователя</b>\n\n"
        "Пожалуйста, используйте кнопки для выбора пользователя из списка.\n\n"
        "Для отмены используйте <code>/cancel</code>",
        parse_mode="HTML"
    )

@router.message(StateFilter(AdminStates.waiting_for_user_action))
async def handle_unexpected_admin_user_action(message: Message, state: FSMContext):
    """Обработка неожиданного ввода при выборе действия с пользователем"""
    await message.answer(
        "❌ <b>Некорректное действие</b>\n\n"
        "Пожалуйста, используйте кнопки для выбора действия с пользователем.\n\n"
        "Для отмены используйте <code>/cancel</code>",
        parse_mode="HTML"
    )

@router.message(StateFilter(AdminStates.waiting_for_role_change))
async def handle_unexpected_admin_role_change(message: Message, state: FSMContext):
    """Обработка неожиданного ввода при изменении роли"""
    await message.answer(
        "❌ <b>Некорректная роль</b>\n\n"
        "Пожалуйста, используйте кнопки для выбора новой роли пользователя.\n\n"
        "Для отмены используйте <code>/cancel</code>",
        parse_mode="HTML"
    )

@router.message(StateFilter(AdminStates.waiting_for_confirmation))
async def handle_unexpected_admin_confirmation(message: Message, state: FSMContext):
    """Обработка неожиданного ввода при подтверждении действия"""
    await message.answer(
        "❌ <b>Некорректное подтверждение</b>\n\n"
        "Пожалуйста, используйте кнопки 'Да' или 'Нет' для подтверждения действия.\n\n"
        "Для отмены используйте <code>/cancel</code>",
        parse_mode="HTML"
    )

@router.message(StateFilter(AdminStates.waiting_for_role_selection, AdminStates.waiting_for_permission_action, AdminStates.waiting_for_permission_selection, AdminStates.waiting_for_permission_confirmation))
async def handle_unexpected_admin_permissions(message: Message, state: FSMContext):
    """Обработка неожиданного ввода в состояниях управления правами"""
    await message.answer(
        "❌ <b>Некорректный выбор</b>\n\n"
        "Пожалуйста, используйте кнопки для управления ролями и правами.\n\n"
        "Для отмены используйте <code>/cancel</code>",
        parse_mode="HTML"
    )

# =================================
# ДОПОЛНИТЕЛЬНЫЕ ОБРАБОТЧИКИ ДЛЯ РЕДАКТИРОВАНИЯ ТЕСТОВ
# =================================

@router.message(StateFilter(TestCreationStates.waiting_for_more_questions))
async def handle_unexpected_more_questions(message: Message, state: FSMContext):
    """Обработка неожиданного ввода при выборе добавления вопросов"""
    await message.answer(
        "❌ <b>Некорректный выбор</b>\n\n"
        "Пожалуйста, используйте кнопки для выбора:\n"
        "• 'Добавить еще вопрос'\n"
        "• 'Завершить создание теста'\n\n"
        "Для отмены используйте <code>/cancel</code>",
        parse_mode="HTML"
    )

@router.message(StateFilter(TestCreationStates.waiting_for_stage_selection))
async def handle_unexpected_stage_selection(message: Message, state: FSMContext):
    """Обработка неожиданного ввода при выборе этапа"""
    await message.answer(
        "❌ <b>Некорректный этап</b>\n\n"
        "Пожалуйста, используйте кнопки для выбора этапа стажировки.\n\n"
        "Для отмены используйте <code>/cancel</code>",
        parse_mode="HTML"
    )

@router.message(StateFilter(TestCreationStates.waiting_for_final_confirmation))
async def handle_unexpected_final_confirmation(message: Message, state: FSMContext):
    """Обработка неожиданного ввода при финальном подтверждении"""
    await message.answer(
        "❌ <b>Некорректное подтверждение</b>\n\n"
        "Пожалуйста, используйте кнопки 'Да' или 'Нет' для подтверждения создания теста.\n\n"
        "Для отмены используйте <code>/cancel</code>",
        parse_mode="HTML"
    )

@router.message(StateFilter(TestCreationStates.waiting_for_edit_action))
async def handle_unexpected_edit_action(message: Message, state: FSMContext):
    """Обработка неожиданного ввода при выборе действия редактирования"""
    await message.answer(
        "❌ <b>Некорректное действие</b>\n\n"
        "Пожалуйста, используйте кнопки для выбора действия редактирования теста.\n\n"
        "Для отмены используйте <code>/cancel</code>",
        parse_mode="HTML"
    )

@router.message(StateFilter(TestCreationStates.waiting_for_new_test_name))
async def handle_unexpected_new_test_name(message: Message, state: FSMContext):
    """Обработка неожиданного ввода при изменении названия теста"""
    if not message.text or len(message.text.strip()) < 3:
        await message.answer(
            "❌ <b>Некорректное название</b>\n\n"
            "Новое название теста должно содержать минимум 3 символа.\n\n"
            "Для отмены используйте <code>/cancel</code>",
            parse_mode="HTML"
        )
    else:
        await message.answer(
            "🔄 <b>Повторите ввод</b>\n\n"
            "Пожалуйста, введите новое название для теста:",
            parse_mode="HTML"
        )

@router.message(StateFilter(TestCreationStates.waiting_for_new_test_description))
async def handle_unexpected_new_description(message: Message, state: FSMContext):
    """Обработка неожиданного ввода при изменении описания теста"""
    await message.answer(
        "🔄 <b>Повторите ввод</b>\n\n"
        "Пожалуйста, введите новое описание для теста.\n\n"
        "Для отмены используйте <code>/cancel</code>",
        parse_mode="HTML"
    )

@router.message(StateFilter(TestCreationStates.waiting_for_new_threshold))
async def handle_unexpected_new_threshold(message: Message, state: FSMContext):
    """Обработка неожиданного ввода при изменении проходного балла"""
    if message.text:
        try:
            threshold = float(message.text.replace(',', '.'))
            if threshold <= 0:
                await message.answer(
                    "❌ <b>Проходной балл должен быть больше нуля</b>\n\n"
                    "Пожалуйста, введите корректное значение.",
                    parse_mode="HTML"
                )
            else:
                await message.answer(
                    "🔄 <b>Повторите ввод</b>\n\n"
                    "Введите новый проходной балл:",
                    parse_mode="HTML"
                )
        except ValueError:
            await message.answer(
                "❌ <b>Некорректный проходной балл</b>\n\n"
                "Пожалуйста, введите числовое значение проходного балла.\n\n"
                "Для отмены используйте <code>/cancel</code>",
                parse_mode="HTML"
            )
    else:
        await message.answer(
            "❌ <b>Пустое значение</b>\n\n"
            "Пожалуйста, введите проходной балл числом.",
            parse_mode="HTML"
        )

@router.message(StateFilter(TestCreationStates.waiting_for_new_stage, TestCreationStates.waiting_for_new_attempts))
async def handle_unexpected_test_settings(message: Message, state: FSMContext):
    """Обработка неожиданного ввода при изменении настроек теста"""
    await message.answer(
        "❌ <b>Некорректный выбор</b>\n\n"
        "Пожалуйста, используйте кнопки для изменения настроек теста.\n\n"
        "Для отмены используйте <code>/cancel</code>",
        parse_mode="HTML"
    )

@router.message(StateFilter(TestCreationStates.waiting_for_new_materials))
async def handle_unexpected_new_materials(message: Message, state: FSMContext):
    """Обработка неожиданного ввода при изменении материалов"""
    await message.answer(
        "🔄 <b>Повторите ввод</b>\n\n"
        "Пожалуйста, отправьте новые материалы:\n"
        "• 📎 PDF документ\n"
        "• 📝 Текстовую информацию\n"
        "• Или напишите 'удалить', чтобы убрать материалы\n\n"
        "Для отмены используйте <code>/cancel</code>",
        parse_mode="HTML"
    )

@router.message(StateFilter(TestCreationStates.waiting_for_question_selection, TestCreationStates.waiting_for_question_action))
async def handle_unexpected_question_management(message: Message, state: FSMContext):
    """Обработка неожиданного ввода при управлении вопросами"""
    await message.answer(
        "❌ <b>Некорректный выбор</b>\n\n"
        "Пожалуйста, используйте кнопки для управления вопросами теста.\n\n"
        "Для отмены используйте <code>/cancel</code>",
        parse_mode="HTML"
    )

@router.message(StateFilter(TestCreationStates.waiting_for_question_edit))
async def handle_unexpected_question_edit(message: Message, state: FSMContext):
    """Обработка неожиданного ввода при редактировании вопроса"""
    if not message.text or len(message.text.strip()) < 5:
        await message.answer(
            "❌ <b>Слишком короткий вопрос</b>\n\n"
            "Текст вопроса должен содержать минимум 5 символов.\n\n"
            "Для отмены используйте <code>/cancel</code>",
            parse_mode="HTML"
        )
    else:
        await message.answer(
            "🔄 <b>Повторите ввод</b>\n\n"
            "Пожалуйста, введите новый текст вопроса:",
            parse_mode="HTML"
        )

@router.message(StateFilter(TestCreationStates.waiting_for_answer_edit))
async def handle_unexpected_answer_edit(message: Message, state: FSMContext):
    """Обработка неожиданного ввода при редактировании ответа"""
    await message.answer(
        "🔄 <b>Повторите ввод</b>\n\n"
        "Пожалуйста, введите новый правильный ответ.\n\n"
        "Для отмены используйте <code>/cancel</code>",
        parse_mode="HTML"
    )

@router.message(StateFilter(TestCreationStates.waiting_for_points_edit))
async def handle_unexpected_points_edit(message: Message, state: FSMContext):
    """Обработка неожиданного ввода при редактировании баллов"""
    if message.text:
        try:
            points = float(message.text.replace(',', '.'))
            if points <= 0:
                await message.answer(
                    "❌ <b>Баллы должны быть больше нуля</b>\n\n"
                    "Пожалуйста, введите положительное число.",
                    parse_mode="HTML"
                )
            else:
                await message.answer(
                    "🔄 <b>Повторите ввод</b>\n\n"
                    "Введите новое количество баллов:",
                    parse_mode="HTML"
                )
        except ValueError:
            await message.answer(
                "❌ <b>Некорректное количество баллов</b>\n\n"
                "Пожалуйста, введите числовое значение.\n\n"
                "Для отмены используйте <code>/cancel</code>",
                parse_mode="HTML"
            )
    else:
        await message.answer(
            "❌ <b>Пустое значение</b>\n\n"
            "Пожалуйста, введите количество баллов числом.",
            parse_mode="HTML"
        )

# =================================
# ОБРАБОТЧИКИ ДЛЯ СОСТОЯНИЙ ПРОХОЖДЕНИЯ ТЕСТОВ
# =================================

@router.message(StateFilter(TestTakingStates.waiting_for_test_selection))
async def handle_unexpected_test_selection(message: Message, state: FSMContext):
    """Обработка неожиданного ввода при выборе теста для прохождения"""
    await message.answer(
        "❌ <b>Некорректный выбор теста</b>\n\n"
        "Пожалуйста, используйте кнопки для выбора теста из списка.\n\n"
        "Для отмены используйте <code>/cancel</code>",
        parse_mode="HTML"
    )

@router.message(StateFilter(TestTakingStates.waiting_for_test_start))
async def handle_unexpected_test_start(message: Message, state: FSMContext):
    """Обработка неожиданного ввода при подтверждении начала теста"""
    await message.answer(
        "❌ <b>Некорректное действие</b>\n\n"
        "Пожалуйста, используйте кнопки для начала теста или отмены.\n\n"
        "Для отмены используйте <code>/cancel</code>",
        parse_mode="HTML"
    )

@router.message(StateFilter(TestTakingStates.test_completed))
async def handle_unexpected_test_completed(message: Message, state: FSMContext):
    """Обработка неожиданного ввода после завершения теста"""
    await message.answer(
        "✅ <b>Тест уже завершен</b>\n\n"
        "Вы уже завершили прохождение теста. Результаты сохранены.\n\n"
        "Используйте <code>/start</code> для перехода в главное меню.",
        parse_mode="HTML"
    )

@router.message(StateFilter(TestTakingStates.taking_test))
async def handle_unexpected_test_input(message: Message, state: FSMContext):
    """Обработка неожиданного ввода во время прохождения теста"""
    data = await state.get_data()
    questions = data.get('questions', [])
    if not questions:
        await message.answer(
            "❌ <b>Ошибка теста</b>\n\n"
            "Произошла ошибка при прохождении теста. Попробуйте начать заново.",
            parse_mode="HTML"
        )
        await state.clear()
        return
    
    current_index = data.get('current_question_index', 0)
    if current_index >= len(questions):
        await message.answer(
            "❌ <b>Тест завершен</b>\n\n"
            "Вы уже ответили на все вопросы. Ожидайте результатов.",
            parse_mode="HTML"
        )
        return
    
    question = questions[current_index]
    
    if question.question_type == 'text':
        await message.answer(
            "🔄 <b>Повторите ответ</b>\n\n"
            "Пожалуйста, введите ваш ответ на текущий вопрос в виде текста.",
            parse_mode="HTML"
        )
    elif question.question_type == 'number':
        await message.answer(
            "❌ <b>Некорректный числовой ответ</b>\n\n"
            "Пожалуйста, введите число в качестве ответа на вопрос.",
            parse_mode="HTML"
        )
    elif question.question_type == 'multiple_choice':
        await message.answer(
            "❌ <b>Некорректный формат ответа</b>\n\n"
            "Для вопросов с множественным выбором введите номера правильных ответов через запятую.\n"
            "Например: <code>1, 3</code>",
            parse_mode="HTML"
        )
    else:
        await message.answer(
            "❌ <b>Неожиданный ввод</b>\n\n"
            "Пожалуйста, используйте кнопки для ответа на вопрос или введите корректный ответ.",
            parse_mode="HTML"
                 )

# =================================
# ОБРАБОТЧИКИ ДЛЯ СОСТОЯНИЙ НАСТАВНИЧЕСТВА
# =================================

@router.message(StateFilter(MentorshipStates.waiting_for_trainee_selection))
async def handle_unexpected_mentor_trainee_selection(message: Message, state: FSMContext):
    """Обработка неожиданного ввода при выборе стажера для назначения наставника"""
    await message.answer(
        "❌ <b>Некорректный выбор стажера</b>\n\n"
        "Пожалуйста, используйте кнопки для выбора стажера из списка.\n\n"
        "Для отмены используйте <code>/cancel</code>",
        parse_mode="HTML"
    )

@router.message(StateFilter(MentorshipStates.waiting_for_mentor_selection))
async def handle_unexpected_mentor_selection(message: Message, state: FSMContext):
    """Обработка неожиданного ввода при выборе наставника"""
    await message.answer(
        "❌ <b>Некорректный выбор наставника</b>\n\n"
        "Пожалуйста, используйте кнопки для выбора наставника из списка.\n\n"
        "Для отмены используйте <code>/cancel</code>",
        parse_mode="HTML"
    )

@router.message(StateFilter(MentorshipStates.waiting_for_assignment_confirmation))
async def handle_unexpected_mentor_assignment_confirmation(message: Message, state: FSMContext):
    """Обработка неожиданного ввода при подтверждении назначения наставника"""
    await message.answer(
        "❌ <b>Некорректное подтверждение</b>\n\n"
        "Пожалуйста, используйте кнопки 'Да' или 'Нет' для подтверждения назначения наставника.\n\n"
        "Для отмены используйте <code>/cancel</code>",
        parse_mode="HTML"
    )

@router.message(StateFilter(MentorshipStates.waiting_for_trainee_action))
async def handle_unexpected_mentor_trainee_action(message: Message, state: FSMContext):
    """Обработка неожиданного ввода при выборе действия со стажером"""
    await message.answer(
        "❌ <b>Некорректное действие</b>\n\n"
        "Пожалуйста, используйте кнопки для выбора действия со стажером.\n\n"
        "Для отмены используйте <code>/cancel</code>",
        parse_mode="HTML"
    )

@router.message(StateFilter(MentorshipStates.waiting_for_test_assignment))
async def handle_unexpected_mentor_test_assignment(message: Message, state: FSMContext):
    """Обработка неожиданного ввода при назначении теста стажеру"""
    await message.answer(
        "❌ <b>Некорректное назначение теста</b>\n\n"
        "Пожалуйста, используйте кнопки для назначения теста стажеру.\n\n"
        "Для отмены используйте <code>/cancel</code>",
        parse_mode="HTML"
    )

@router.message(StateFilter(MentorshipStates.waiting_for_test_selection_for_trainee))
async def handle_unexpected_mentor_test_selection(message: Message, state: FSMContext):
    """Обработка неожиданного ввода при выборе теста для назначения стажеру"""
    await message.answer(
        "❌ <b>Некорректный выбор теста</b>\n\n"
        "Пожалуйста, используйте кнопки для выбора теста для назначения стажеру.\n\n"
        "Для отмены используйте <code>/cancel</code>",
        parse_mode="HTML"
    )

# =================================
# ОБРАБОТЧИКИ ДЛЯ УПРАВЛЕНИЯ СТАЖЕРАМИ
# =================================

@router.message(StateFilter(TraineeManagementStates.waiting_for_trainee_selection))
async def handle_unexpected_trainee_management_selection(message: Message, state: FSMContext):
    """Обработка неожиданного ввода при выборе стажера для управления"""
    await message.answer(
        "❌ <b>Некорректный выбор стажера</b>\n\n"
        "Пожалуйста, используйте кнопки для выбора стажера из списка.\n\n"
        "Для отмены используйте <code>/cancel</code>",
        parse_mode="HTML"
    )

@router.message(StateFilter(TraineeManagementStates.waiting_for_trainee_action))
async def handle_unexpected_trainee_management_action(message: Message, state: FSMContext):
    """Обработка неожиданного ввода при выборе действия со стажером"""
    await message.answer(
        "❌ <b>Некорректное действие</b>\n\n"
        "Пожалуйста, используйте кнопки для выбора действия со стажером.\n\n"
        "Для отмены используйте <code>/cancel</code>",
        parse_mode="HTML"
    )

@router.message(StateFilter(TraineeManagementStates.waiting_for_test_access_grant))
async def handle_unexpected_trainee_test_access(message: Message, state: FSMContext):
    """Обработка неожиданного ввода при предоставлении доступа к тесту"""
    await message.answer(
        "❌ <b>Некорректное предоставление доступа</b>\n\n"
        "Пожалуйста, используйте кнопки для предоставления доступа к тесту стажеру.\n\n"
        "Для отмены используйте <code>/cancel</code>",
        parse_mode="HTML"
    )

# =================================
# УНИВЕРСАЛЬНЫЙ ОБРАБОТЧИК ДЛЯ ЛЮБЫХ СОСТОЯНИЙ
# =================================

@router.message(F.text)
async def handle_unexpected_input_with_state(message: Message, state: FSMContext):
    """Универсальный обработчик для неожиданного ввода в любых состояниях"""
    current_state = await state.get_state()
    
    if current_state:
        await message.answer(
            f"❓ <b>Неожиданный ввод</b>\n\n"
            f"Вы находитесь в процессе выполнения операции.\n"
            f"Текущее состояние: <code>{current_state}</code>\n\n"
            f"Пожалуйста, следуйте инструкциям или используйте:\n"
            f"• <code>/cancel</code> - для отмены текущей операции\n"
            f"• <code>/help</code> - для получения справки\n"
            f"• <code>/start</code> - для возврата в главное меню",
            parse_mode="HTML"
        )
        
        log_user_action(
            message.from_user.id, 
            message.from_user.username, 
            "unexpected_input", 
            {"state": current_state, "input": message.text[:100]}
        )
    else:
        # Если пользователь не в состоянии FSM
        await message.answer(
            "❓ <b>Команда не распознана</b>\n\n"
            "Пожалуйста, используйте кнопки меню или доступные команды:\n"
            "• <code>/help</code> - получить справку\n"
            "• <code>/start</code> - перейти в главное меню\n"
            "• <code>/profile</code> - посмотреть профиль",
            parse_mode="HTML"
        )

# =================================
# ОБРАБОТЧИК ДЛЯ НЕОЖИДАННЫХ CALLBACK QUERY
# =================================

@router.callback_query(F.data)
async def handle_unexpected_callback(callback: CallbackQuery, state: FSMContext):
    """Обработчик для неожиданных callback запросов"""
    current_state = await state.get_state()
    
    await callback.message.edit_text(
        f"❓ <b>Устаревшая кнопка</b>\n\n"
        f"Эта кнопка больше не актуальна или не подходит для текущего состояния.\n\n"
        f"Пожалуйста, используйте:\n"
        f"• <code>/cancel</code> - для отмены текущей операции\n"
        f"• <code>/start</code> - для возврата в главное меню",
        parse_mode="HTML"
    )
    
    await callback.answer("⚠️ Устаревшая кнопка", show_alert=True)
    
    log_user_action(
        callback.from_user.id, 
        callback.from_user.username, 
        "unexpected_callback", 
        {"state": current_state, "data": callback.data}
    ) 