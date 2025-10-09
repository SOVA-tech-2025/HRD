from aiogram import Router, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from datetime import datetime

from database.db import (
    get_unassigned_trainees, get_available_mentors, assign_mentor,
    get_mentor_trainees, get_trainee_mentor, check_user_permission,
    get_user_by_tg_id, get_user_by_id, get_user_test_results, get_user_test_result,
    get_test_by_id, get_all_active_tests, grant_test_access,
    get_trainee_available_tests, get_trainee_learning_path,
    get_trainee_stage_progress, get_stage_session_progress,
    get_learning_path_by_id, get_available_learning_paths_for_mentor,
    assign_learning_path_to_trainee, open_stage_for_trainee,
    get_learning_path_stages, get_available_managers_for_trainee,
    assign_manager_to_trainee, get_trainee_manager, get_manager_trainees,
    get_stage_sessions, get_session_tests, get_attestation_by_id, get_user_attestation_result, get_user_roles,
    get_managers_for_attestation, assign_attestation_to_trainee, get_trainee_attestation_by_id,
    check_all_stages_completed, get_trainee_attestation_status
)
from keyboards.keyboards import (
    get_unassigned_trainees_keyboard, get_mentor_selection_keyboard,
    get_assignment_confirmation_keyboard, get_trainee_selection_keyboard,
    get_trainee_actions_keyboard, get_test_access_keyboard,
    get_tests_for_access_keyboard, get_manager_selection_keyboard,
    get_manager_assignment_confirmation_keyboard, get_manager_actions_keyboard
)

def get_days_word(days: int) -> str:
    """Получение правильного склонения слова 'день' в зависимости от числа"""
    if days % 10 == 1 and days % 100 != 11:
        return "день"
    elif days % 10 in [2, 3, 4] and days % 100 not in [12, 13, 14]:
        return "дня"
    else:
        return "дней"
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from states.states import MentorshipStates, AttestationAssignmentStates, TraineeManagementStates
from utils.logger import log_user_action, log_user_error
from handlers.auth import check_auth

router = Router()

@router.message(Command("assign_mentor"))
async def cmd_assign_mentor_command(message: Message, state: FSMContext, session: AsyncSession):
    """Обработчик команды /assign_mentor"""
    await cmd_assign_mentor(message, state, session)

@router.message(Command("my_trainees"))
async def cmd_my_trainees_command(message: Message, state: FSMContext, session: AsyncSession):
    """Обработчик команды /my_trainees"""
    await cmd_mentor_trainees(message, state, session)

@router.message(Command("my_mentor"))
async def cmd_my_mentor_command(message: Message, state: FSMContext, session: AsyncSession):
    """Обработчик команды /my_mentor"""
    await cmd_my_mentor(message, state, session)

@router.message(F.text == "Назначить наставника")
async def cmd_assign_mentor(message: Message, state: FSMContext, session: AsyncSession):
    """Обработчик команды назначения наставника"""
    is_auth = await check_auth(message, state, session)
    if not is_auth:
        return
    
    user = await get_user_by_tg_id(session, message.from_user.id)
    if not user:
        await message.answer("Вы не зарегистрированы в системе.")
        return
    
    has_permission = await check_user_permission(session, user.id, "assign_mentors")
    if not has_permission:
        await message.answer("У вас нет прав для назначения наставников.")
        return
    
    unassigned_trainees = await get_unassigned_trainees(session)
    
    if not unassigned_trainees:
        await message.answer(
            "✅ <b>Все стажеры уже имеют наставников!</b>\n\n"
            "В настоящее время все зарегистрированные стажеры имеют назначенных наставников.",
            parse_mode="HTML"
        )
        return
    
    await message.answer(
        f"👥 <b>Назначение наставника</b>\n\n"
        f"📊 <b>Статистика системы:</b>\n"
        f"• Стажеров без наставника: <b>{len(unassigned_trainees)}</b>\n"
        f"• Требуется назначение наставников\n\n"
        f"🎯 <b>Ваша задача:</b> Назначить наставника каждому стажеру для:\n"
        f"• Персонального сопровождения\n"
        f"• Контроля прогресса обучения\n"
        f"• Помощи в адаптации\n"
        f"• Предоставления доступа к тестам\n\n"
        f"👇 <b>Выберите стажера для назначения наставника:</b>",
        parse_mode="HTML",
        reply_markup=get_unassigned_trainees_keyboard(unassigned_trainees)
    )
    
    await state.set_state(MentorshipStates.waiting_for_trainee_selection)
    
    log_user_action(message.from_user.id, message.from_user.username, "opened mentor assignment")

@router.message(F.text.in_(["Мой наставник", "🎓 Мой наставник", "Мой наставник 🎓"]))
async def cmd_my_mentor(message: Message, state: FSMContext, session: AsyncSession):
    """Обработчик команды просмотра информации о наставнике"""
    is_auth = await check_auth(message, state, session)
    if not is_auth:
        return
    
    user = await get_user_by_tg_id(session, message.from_user.id)
    if not user:
        await message.answer("Вы не зарегистрированы в системе.")
        return
    
    mentor = await get_trainee_mentor(session, user.id)
    
    if not mentor:
        await message.answer(
            "👨‍🏫 <b>Информация о наставнике</b>\n\n"
            "У вас пока не назначен наставник.\n"
            "Обратитесь к рекрутеру для назначения наставника.",
            parse_mode="HTML"
        )
        return
    
    await message.answer(
        f"🎓 <b>Твой наставник</b>\n\n"
        f"<b>Имя:</b> {mentor.full_name}\n"
        f"<b>Телефон:</b> {mentor.phone_number}\n"
        f"<b>Telegram:</b> @{mentor.username or 'не указан'}\n\n"
        f"<i>Если что-то непонятно по стажировке, сразу напиши наставнику, он подскажет тебе следующий шаг</i>",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")]
        ])
    )
    
    log_user_action(message.from_user.id, message.from_user.username, "viewed mentor info")

@router.message(F.text.in_(["Мои стажеры", "Мои стажеры 👥"]))
async def cmd_mentor_trainees(message: Message, state: FSMContext, session: AsyncSession):
    """Обработчик команды просмотра стажеров наставника"""
    is_auth = await check_auth(message, state, session)
    if not is_auth:
        return
    
    user = await get_user_by_tg_id(session, message.from_user.id)
    if not user:
        await message.answer("Вы не зарегистрированы в системе.")
        return
    
    trainees = await get_mentor_trainees(session, user.id)
    
    if not trainees:
        await message.answer(
            "👥 <b>Ваши стажеры</b>\n\n"
            "У вас пока нет назначенных стажеров.\n"
            "Обратитесь к рекрутеру для назначения стажеров.",
            parse_mode="HTML"
        )
        return
    
    # Создаем клавиатуру со списком стажеров согласно ТЗ
    keyboard = InlineKeyboardMarkup(inline_keyboard=[])

    # Формируем сообщение со списком стажеров
    message_text = "👥 <b>Ваши стажеры</b>\n\n"

    for i, trainee in enumerate(trainees, 1):
        # Получаем информацию о траектории стажера
        trainee_path = await get_trainee_learning_path(session, trainee.id)
        trajectory_name = trainee_path.learning_path.name if trainee_path else "не выбрано"

        # Подсчитываем количество дней в статусе стажера
        days_as_trainee = (datetime.now() - trainee.role_assigned_date).days
        days_word = get_days_word(days_as_trainee)

        # Добавляем информацию о стажере согласно ТЗ
        message_text += f"{i}. <b>{trainee.full_name}</b>\n\n"
        message_text += f"<b>Телефон:</b> {trainee.phone_number}\n"
        message_text += f"<b>В статусе стажера:</b> {days_as_trainee} {days_word}\n"
        message_text += f"<b>Объект стажировки:</b> {trainee.internship_object.name if trainee.internship_object else 'Не указан'}\n"
        message_text += f"<b>Объект работы:</b> {trainee.work_object.name if trainee.work_object else 'Не указан'}\n\n"
        message_text += f"📌<b>Траектория:</b> {trajectory_name}\n\n"
        message_text += "━━━━━━━━━━━━\n\n"

        # Добавляем кнопку для выбора стажера
        keyboard.inline_keyboard.append([
            InlineKeyboardButton(
                text=f"{trainee.full_name}",
                callback_data=f"select_trainee_for_trajectory:{trainee.id}"
            )
        ])

    # Добавляем кнопку главного меню
    keyboard.inline_keyboard.append([
        InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")
    ])
    
    await message.answer(
        message_text + "Выбери стажёра для взаимодействия, откроется карточка с данными, прогрессом и назначением траектории обучения:",
        reply_markup=keyboard,
        parse_mode="HTML"
    )
    
    log_user_action(message.from_user.id, message.from_user.username, "viewed mentor trainees")

@router.callback_query(MentorshipStates.waiting_for_trainee_selection, F.data.startswith("unassigned_trainee:"))
async def process_trainee_selection_for_assignment(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Обработчик выбора стажера для назначения наставника"""
    trainee_id = int(callback.data.split(':')[1])
    
    trainee = await get_user_by_id(session, trainee_id)
    if not trainee:
        await callback.message.answer("❌ Стажер не найден.")
        await callback.answer()
        return
    
    available_mentors = await get_available_mentors(session)
    
    if not available_mentors:
        await callback.message.edit_text(
            "❌ <b>Нет доступных наставников</b>\n\n"
            "В системе нет пользователей с ролью 'Наставник' или 'Руководитель', "
            "которые могли бы стать наставниками.",
            parse_mode="HTML"
        )
        await callback.answer()
        return
    
    await state.update_data(selected_trainee_id=trainee_id)
    
    mentors_list = "\n".join([
        f"👤 <b>{mentor.full_name}</b>\n"
        f"   📍<b>2️⃣Объект работы:</b> {mentor.work_object.name if mentor.work_object else 'Не указан'}\n"
        f"   📞 {mentor.phone_number}\n"
        f"   📧 @{mentor.username or 'не указан'}"
        for mentor in available_mentors[:5]  # Показываем первых 5
    ])
    
    if len(available_mentors) > 5:
        mentors_list += f"\n... и еще {len(available_mentors) - 5} наставников"
    
    await callback.message.edit_text(
        f"👤 <b>Выбран стажер:</b> {trainee.full_name}\n"
        f"📍<b>1️⃣Объект стажировки:</b> {trainee.internship_object.name if trainee.internship_object else 'Не указан'}\n"
        f"📍<b>2️⃣Объект работы:</b> {trainee.work_object.name if trainee.work_object else 'Не указан'}\n"
        f"📞 <b>Телефон:</b> {trainee.phone_number}\n"
        f"📅 <b>Дата регистрации:</b> {trainee.registration_date.strftime('%d.%m.%Y')}\n\n"
        f"👨‍🏫 <b>Доступные наставники:</b>\n\n{mentors_list}\n\n"
        "Выберите наставника для этого стажера:",
        parse_mode="HTML",
        reply_markup=get_mentor_selection_keyboard(available_mentors)
    )
    
    await state.set_state(MentorshipStates.waiting_for_mentor_selection)
    await callback.answer()

@router.callback_query(MentorshipStates.waiting_for_mentor_selection, F.data.startswith("mentor:"))
async def process_mentor_selection(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Обработчик выбора наставника"""
    mentor_id = int(callback.data.split(':')[1])
    
    data = await state.get_data()
    trainee_id = data.get('selected_trainee_id')
    
    trainee = await get_user_by_id(session, trainee_id)
    mentor = await get_user_by_id(session, mentor_id)
    
    if not trainee or not mentor:
        await callback.message.answer("❌ Пользователь не найден.")
        await callback.answer()
        return
    
    # Получаем информацию о текущих стажерах наставника
    current_trainees = await get_mentor_trainees(session, mentor_id)
    trainees_count = len(current_trainees)
    
    confirmation_text = f"""🤝 <b>Подтверждение назначения наставника</b>

👤 <b>Стажер:</b>
   • ФИО: {trainee.full_name}
   📍1️⃣Объект стажировки: {trainee.internship_object.name if trainee.internship_object else 'Не указан'}
   📍2️⃣Объект работы: {trainee.work_object.name if trainee.work_object else 'Не указан'}
   • Телефон: {trainee.phone_number}
   • Дата регистрации: {trainee.registration_date.strftime('%d.%m.%Y')}

👨‍🏫 <b>Наставник:</b>
   • ФИО: {mentor.full_name}
   📍2️⃣Объект работы: {mentor.work_object.name if mentor.work_object else 'Не указан'}
   • Телефон: {mentor.phone_number}
   • Текущих стажеров: {trainees_count}

❓ Подтвердите назначение наставника:"""
    
    await callback.message.edit_text(
        confirmation_text,
        parse_mode="HTML",
        reply_markup=get_assignment_confirmation_keyboard(mentor_id, trainee_id)
    )
    
    await state.set_state(MentorshipStates.waiting_for_assignment_confirmation)
    await callback.answer()

@router.callback_query(MentorshipStates.waiting_for_assignment_confirmation, F.data.startswith("confirm_assignment:"))
async def process_assignment_confirmation(callback: CallbackQuery, state: FSMContext, session: AsyncSession, bot):
    """Обработчик подтверждения назначения наставника"""
    parts = callback.data.split(':')
    mentor_id = int(parts[1])
    trainee_id = int(parts[2])
    
    user = await get_user_by_tg_id(session, callback.from_user.id)
    
    mentorship = await assign_mentor(session, mentor_id, trainee_id, user.id, bot)
    
    if mentorship:
        trainee = await get_user_by_id(session, trainee_id)
        mentor = await get_user_by_id(session, mentor_id)
        
        success_text = f"""✅ <b>Наставник успешно назначен!</b>

👤 <b>Стажер:</b> {trainee.full_name}
👨‍🏫 <b>Наставник:</b> {mentor.full_name}

📅 <b>Дата назначения:</b> {mentorship.assigned_date.strftime('%d.%m.%Y %H:%M')}
👤 <b>Назначил:</b> {user.full_name}

📬 <b>Уведомления отправлены:</b>
• ✅ Стажер получил контакты наставника
• 📞 Телефон: {mentor.phone_number}
• 📧 Telegram: @{mentor.username or 'не указан'}

🎯 Стажер может сразу связаться с наставником для знакомства!"""
        
        await callback.message.edit_text(
            success_text,
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🎯 Назначить еще одного наставника", callback_data="assign_another_mentor")],
                [InlineKeyboardButton(text="👥 Список всех наставников", callback_data="view_all_mentors")],
                [InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")]
            ])
        )
        
        log_user_action(
            callback.from_user.id, 
            callback.from_user.username, 
            "assigned mentor", 
            {"mentor_id": mentor_id, "trainee_id": trainee_id}
        )
    else:
        await callback.message.edit_text(
            "❌ <b>Ошибка назначения наставника</b>\n\n"
            "Произошла ошибка при назначении наставника. Возможные причины:\n"
            "• Стажер уже имеет наставника\n"
            "• Технические проблемы с базой данных\n\n"
            "Попробуйте еще раз или обратитесь к администратору.",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔄 Попробовать еще раз", callback_data="assign_another_mentor")],
                [InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")]
            ])
        )
        
        log_user_error(
            callback.from_user.id, 
            callback.from_user.username, 
            "failed to assign mentor", 
            {"mentor_id": mentor_id, "trainee_id": trainee_id}
        )
    
    await state.clear()
    await callback.answer()

@router.callback_query(F.data == "cancel_assignment")
async def process_cancel_assignment(callback: CallbackQuery, state: FSMContext):
    """Обработчик отмены назначения наставника"""
    await callback.message.edit_text(
        "❌ <b>Назначение наставника отменено</b>\n\n"
        "Операция была прервана пользователем.",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🎯 Назначить наставника", callback_data="assign_another_mentor")],
            [InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")]
        ])
    )
    await state.clear()
    await callback.answer()

@router.callback_query(F.data == "assign_another_mentor")
async def process_assign_another_mentor(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Обработчик назначения еще одного наставника"""
    unassigned_trainees = await get_unassigned_trainees(session)
    
    if not unassigned_trainees:
        await callback.message.edit_text(
            "✅ <b>Все стажеры уже имеют наставников!</b>\n\n"
            "В настоящее время все зарегистрированные стажеры имеют назначенных наставников.\n"
            "Новые стажеры появятся здесь после регистрации.",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="👥 Список всех наставников", callback_data="view_all_mentors")],
                [InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")]
            ])
        )
        await callback.answer()
        return
    
    await callback.message.edit_text(
        "👥 <b>Назначение наставника</b>\n\n"
        f"Найдено стажеров без наставника: <b>{len(unassigned_trainees)}</b>\n\n"
        "Выберите стажера, которому нужно назначить наставника:",
        parse_mode="HTML",
        reply_markup=get_unassigned_trainees_keyboard(unassigned_trainees)
    )
    
    await state.set_state(MentorshipStates.waiting_for_trainee_selection)
    await callback.answer()

@router.callback_query(F.data == "view_all_mentors")
async def process_view_all_mentors(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Просмотр всех наставников с детализацией"""
    mentors = await get_available_mentors(session)
    
    if not mentors:
        await callback.message.edit_text(
            "👨‍🏫 <b>Список наставников</b>\n\n"
            "В системе пока нет пользователей, которые могут быть наставниками.\n"
            "Наставниками могут быть пользователи с ролью 'Наставник' или 'Руководитель'.",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")]
            ])
        )
        await callback.answer()
        return
    
    mentors_info = []
    for mentor in mentors:
        trainees = await get_mentor_trainees(session, mentor.id)
        mentors_info.append(
            f"👤 <b>{mentor.full_name}</b>\n"
            f"   📞 {mentor.phone_number}\n"
            f"   📧 @{mentor.username or 'не указан'}\n"
            f"   👥 Стажеров: {len(trainees)}"
        )
    
    mentors_list = "\n\n".join(mentors_info)
    
    await callback.message.edit_text(
        f"👨‍🏫 <b>Список всех наставников</b>\n\n"
        f"Всего наставников в системе: <b>{len(mentors)}</b>\n\n"
        f"{mentors_list}",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🎯 Назначить наставника", callback_data="assign_another_mentor")],
            [InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")]
        ])
    )
    
    await callback.answer()


@router.message(F.text.in_(["Список Наставников", "Наставники 🦉"]))
async def cmd_list_mentors(message: Message, state: FSMContext, session: AsyncSession):
    """Обработчик команды просмотра списка наставников"""
    is_auth = await check_auth(message, state, session)
    if not is_auth:
        return
    
    user = await get_user_by_tg_id(session, message.from_user.id)
    if not user:
        await message.answer("❌ Вы не зарегистрированы в системе.")
        return
    
    has_permission = await check_user_permission(session, user.id, "view_mentorship")
    if not has_permission:
        await message.answer("❌ У вас нет прав для просмотра информации о наставничестве.")
        return
    
    mentors = await get_available_mentors(session)
    
    if not mentors:
        await message.answer(
            "👨‍🏫 <b>Список наставников</b>\n\n"
            "В системе пока нет пользователей, которые могут быть наставниками.\n"
            "Наставниками могут быть пользователи с ролью 'Наставник' или 'Руководитель'.",
            parse_mode="HTML"
        )
        return
    
    mentors_info = []
    total_trainees = 0
    
    for mentor in mentors:
        trainees = await get_mentor_trainees(session, mentor.id)
        trainees_count = len(trainees)
        total_trainees += trainees_count
        
        # Показываем имена стажеров, если они есть
        if trainees:
            trainees_names = ", ".join([t.full_name for t in trainees[:3]])
            if trainees_count > 3:
                trainees_names += f" и еще {trainees_count - 3}"
            trainees_info = f"Стажеры: {trainees_names}"
        else:
            trainees_info = "Стажеров нет"
        
        mentors_info.append(
            f"👤 <b>{mentor.full_name}</b>\n"
            f"   📞 {mentor.phone_number}\n"
            f"   📧 @{mentor.username or 'не указан'}\n"
            f"   👥 {trainees_info}"
        )
    
    mentors_list = "\n\n".join(mentors_info)
    
    await message.answer(
        f"👨‍🏫 <b>Список всех наставников</b>\n\n"
        f"📊 <b>Статистика:</b>\n"
        f"• Всего наставников: {len(mentors)}\n"
        f"• Всего стажеров под наставничеством: {total_trainees}\n"
        f"• Среднее количество стажеров на наставника: {total_trainees/len(mentors):.1f}\n\n"
        f"{mentors_list}",
        parse_mode="HTML"
    )
    
    log_user_action(message.from_user.id, message.from_user.username, "viewed mentors list")

@router.message(F.text == "Стажеры без наставника")
async def cmd_list_unassigned_trainees(message: Message, state: FSMContext, session: AsyncSession):
    """Обработчик команды просмотра стажеров без наставника"""
    is_auth = await check_auth(message, state, session)
    if not is_auth:
        return
    
    user = await get_user_by_tg_id(session, message.from_user.id)
    if not user:
        await message.answer("❌ Вы не зарегистрированы в системе.")
        return
    
    has_permission = await check_user_permission(session, user.id, "view_trainee_list")
    if not has_permission:
        await message.answer("❌ У вас нет прав для просмотра списка пользователей.")
        return
    
    # Получаем стажеров без наставника (они считаются "новыми")
    unassigned_trainees = await get_unassigned_trainees(session)
    
    if not unassigned_trainees:
        await message.answer(
            "📋 <b>Стажеры без наставника</b>\n\n"
            "✅ Все стажеры уже имеют наставников!\n"
            "Новые стажеры появятся здесь после активации рекрутером.",
            parse_mode="HTML"
        )
        return
    
    users_info = []
    for i, trainee in enumerate(unassigned_trainees, 1):
        users_info.append(
            f"{i}. <b>{trainee.full_name}</b>\n"
            f"   📞 {trainee.phone_number}\n"
            f"   📧 @{trainee.username or 'не указан'}\n"
            f"   📅 Регистрация: {trainee.registration_date.strftime('%d.%m.%Y %H:%M')}"
        )
    
    users_list = "\n\n".join(users_info)
    
    await message.answer(
        f"📋 <b>Стажеры без наставника</b>\n\n"
        f"Стажеров без наставника: <b>{len(unassigned_trainees)}</b>\n\n"
        f"{users_list}\n\n"
        f"💡 <b>Рекомендация:</b> Используйте команду 'Назначить наставника' для назначения наставников этим стажерам.",
        parse_mode="HTML"
    )
    
    log_user_action(message.from_user.id, message.from_user.username, "viewed new users list")

# Callback обработчики для уведомлений

@router.callback_query(F.data.startswith("select_trainee_for_trajectory:"))
async def callback_select_trainee_for_trajectory(callback: CallbackQuery, session: AsyncSession):
    """Обработчик выбора стажера из списка 'Мои стажёры' - ПО ТЗ 6-й задачи шаг 5"""
    trainee_id = int(callback.data.split(":")[1])

    # Получаем данные стажера
    trainee = await get_user_by_id(session, trainee_id)
    if not trainee:
        await callback.message.edit_text("Стажер не найден")
        await callback.answer()
        return

    # Получаем траекторию стажера
    trainee_path = await get_trainee_learning_path(session, trainee.id)
    trajectory_info = ""

    if trainee_path:
        # Получаем этапы траектории
        stages_progress = await get_trainee_stage_progress(session, trainee_path.id)
        # Получаем результаты тестов стажера
        test_results = await get_user_test_results(session, trainee.id)
        trajectory_info = generate_trajectory_progress_for_mentor(trainee_path, stages_progress, test_results)
    else:
        trajectory_info = "🗺️<b>Траектория:</b> не выбрано"

    # Формируем сообщение согласно ТЗ
    profile_text = (
        f"🦸🏻‍♂️ <b>Стажер:</b> {trainee.full_name}\n"
        f"<b>Траектория:</b> {trainee_path.learning_path.name if trainee_path and trainee_path.learning_path else 'не выбрана'}\n\n\n"
        f"<b>Телефон:</b> {trainee.phone_number}\n"
        f"<b>Username:</b> @{trainee.username or 'не указан'}\n"
        f"<b>Номер:</b> #{trainee_id}\n"
        f"<b>Дата регистрации:</b> {trainee.registration_date.strftime('%d.%m.%Y %H:%M')}\n\n\n"
        "━━━━━━━━━━━━\n\n\n"
        "🗂️ <b>Статус:</b>\n"
        f"<b>Группа:</b> {', '.join([group.name for group in trainee.groups]) if trainee.groups else 'Не указана'}\n"
        f"<b>Роль:</b> {', '.join([role.name for role in trainee.roles])}\n\n\n"
        "━━━━━━━━━━━━\n\n\n"
        "📍 <b>Объект:</b>\n"
        f"<b>Стажировки:</b> {trainee.internship_object.name if trainee.internship_object else 'Не указан'}\n"
        f"<b>Работы:</b> {trainee.work_object.name if trainee.work_object else 'Не указан'}\n\n\n"
        f"{trajectory_info}"
    )

    # Клавиатура согласно ТЗ
    keyboard = InlineKeyboardMarkup(inline_keyboard=[])

    if trainee_path:
        keyboard.inline_keyboard.append([
            InlineKeyboardButton(text="🗺️ Выбрать траекторию", callback_data=f"select_trajectory_for_trainee:{trainee_id}")
        ])
        keyboard.inline_keyboard.append([
            InlineKeyboardButton(text="🟡 Этапы", callback_data=f"manage_stages:{trainee_id}")
        ])
        keyboard.inline_keyboard.append([
            InlineKeyboardButton(text="🔍 Аттестация", callback_data=f"view_trainee_attestation:{trainee_id}")
        ])
    else:
        keyboard.inline_keyboard.append([
            InlineKeyboardButton(text="🗺️ Выбрать траекторию", callback_data=f"select_trajectory_for_trainee:{trainee_id}")
        ])

    keyboard.inline_keyboard.append([
        InlineKeyboardButton(text="⬅️ Назад", callback_data="my_trainees")
    ])

    await callback.message.edit_text(
        profile_text,
        parse_mode="HTML",
        reply_markup=keyboard
    )
    await callback.answer()


@router.callback_query(F.data.startswith("select_trajectory_for_trainee:"))
async def callback_select_trajectory_for_trainee(callback: CallbackQuery, session: AsyncSession):
    """Обработчик выбора траектории для стажера - ПО ТЗ 6-й задачи шаг 9"""
    trainee_id = int(callback.data.split(":")[1])

    # Получаем стажера
    trainee = await get_user_by_id(session, trainee_id)
    if not trainee:
        await callback.message.edit_text("Стажер не найден")
        await callback.answer()
        return

    # Получаем текущего пользователя (наставника)
    mentor = await get_user_by_tg_id(session, callback.from_user.id)
    if not mentor:
        await callback.message.edit_text("Пользователь не найден")
        await callback.answer()
        return

    # Получаем доступные траектории для наставника
    available_paths = await get_available_learning_paths_for_mentor(session, mentor.id)

    if not available_paths:
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ Назад", callback_data=f"select_trainee_for_trajectory:{trainee_id}")]
        ])
        
        await callback.message.edit_text(
            f"❌ <b>Нет доступных траекторий</b>\n\n"
            f"👤 <b>Стажер:</b> {trainee.full_name}\n\n"
            "Для вас нет доступных траекторий обучения.\n"
            "Возможно, нет траекторий для вашей группы.",
            parse_mode="HTML",
            reply_markup=keyboard
        )
        await callback.answer()
        return

    # Формируем информацию о стажере
    trainee_info = (
            f"🦸🏻‍♂️ <b>Стажер:</b> {trainee.full_name}\n"
            f"<b>Траектория:</b> не выбрана\n\n\n"
            f"<b>Телефон:</b> {trainee.phone_number}\n"
            f"<b>Username:</b> @{trainee.username or 'не указан'}\n"
            f"<b>Номер:</b> #{trainee_id}\n"
            f"<b>Дата регистрации:</b> {trainee.registration_date.strftime('%d.%m.%Y %H:%M')}\n\n\n"
            "━━━━━━━━━━━━\n\n\n"
            "🗂️ <b>Статус:</b>\n"
            f"<b>Группа:</b> {', '.join([group.name for group in trainee.groups]) if trainee.groups else 'Не указана'}\n"
            f"<b>Роль:</b> {', '.join([role.name for role in trainee.roles])}\n\n\n"
            "━━━━━━━━━━━━\n\n\n"
            "📍 <b>Объект:</b>\n"
            f"<b>Стажировки:</b> {trainee.internship_object.name if trainee.internship_object else 'Не указан'}\n"
            f"<b>Работы:</b> {trainee.work_object.name if trainee.work_object else 'Не указан'}\n\n\n"
            "Выберите траекторию обучения👇"
        )

    # Создаем клавиатуру с доступными траекториями
    keyboard = InlineKeyboardMarkup(inline_keyboard=[])

    for learning_path in available_paths:
        keyboard.inline_keyboard.append([
            InlineKeyboardButton(
                text=f"{learning_path.name}",
                callback_data=f"assign_trajectory:{trainee_id}:{learning_path.id}"
            )
        ])

    # Добавляем кнопку "Назад"
    keyboard.inline_keyboard.append([
        InlineKeyboardButton(text="⬅️ Назад", callback_data=f"select_trainee_for_trajectory:{trainee_id}")
    ])

    await callback.message.edit_text(
        trainee_info,
        parse_mode="HTML",
        reply_markup=keyboard
    )
    await callback.answer()




@router.callback_query(F.data.startswith("assign_trajectory:"))
async def callback_assign_trajectory(callback: CallbackQuery, session: AsyncSession):
    """Обработчик назначения траектории стажеру - ПО ТЗ 6-й задачи шаг 11"""
    bot = callback.message.bot  # Получаем bot для уведомлений
    parts = callback.data.split(":")
    trainee_id = int(parts[1])
    learning_path_id = int(parts[2])

    # Получаем данные
    trainee = await get_user_by_id(session, trainee_id)
    mentor = await get_user_by_tg_id(session, callback.from_user.id)

    if not trainee or not mentor:
        await callback.message.edit_text("Ошибка: данные не найдены")
        await callback.answer()
        return

    # Назначаем траекторию
    success = await assign_learning_path_to_trainee(session, trainee_id, learning_path_id, mentor.id, bot)

    if success:
        # Получаем информацию о назначенной траектории и этапах
        learning_path = await get_learning_path_by_id(session, learning_path_id)
        stages = await get_learning_path_stages(session, learning_path_id)

        # Формируем сообщение согласно ТЗ
        trainee_info = (
            f"🦸🏻‍♂️ <b>Стажер:</b> {trainee.full_name}\n"
            f"<b>Траектория:</b> {learning_path.name}\n\n\n"
            f"<b>Телефон:</b> {trainee.phone_number}\n"
            f"<b>Username:</b> @{trainee.username or 'не указан'}\n"
            f"<b>Номер:</b> #{trainee_id}\n"
            f"<b>Дата регистрации:</b> {trainee.registration_date.strftime('%d.%m.%Y %H:%M')}\n\n\n"
            "━━━━━━━━━━━━\n\n\n"
            "🗂️ <b>Статус:</b>\n"
            f"<b>Группа:</b> {', '.join([group.name for group in trainee.groups]) if trainee.groups else 'Не указана'}\n"
            f"<b>Роль:</b> {', '.join([role.name for role in trainee.roles])}\n\n\n"
            "━━━━━━━━━━━━\n\n\n"
            "📍 <b>Объект:</b>\n"
            f"<b>Стажировки:</b> {trainee.internship_object.name if trainee.internship_object else 'Не указан'}\n"
            f"<b>Работы:</b> {trainee.work_object.name if trainee.work_object else 'Не указан'}\n\n\n"
            "🗺️<b>Управление траекторией</b>\n\n"
            f"⏺️<b>Название траектории:</b> {learning_path.name}\n"
        )

        # Добавляем информацию об этапах
        for stage in sorted(stages, key=lambda s: s.order_number):
            trainee_info += f" ⏺️<b>Этап {stage.order_number}:</b> {stage.name}\n"

            # Получаем сессии этапа
            sessions = await get_stage_sessions(session, stage.id)
            for session_obj in sorted(sessions, key=lambda s: s.order_number):
                trainee_info += f" ⏺️<b>Сессия {session_obj.order_number}:</b> {session_obj.name}\n"

                # Получаем тесты сессии
                tests = await get_session_tests(session, session_obj.id)
                for test in tests:
                    trainee_info += f" ⏺️<b>Тест {test.id}:</b> {test.name}\n"

        # Добавляем аттестацию если есть
        if learning_path.attestation:
            trainee_info += f"🔍 ⏺️<b>Аттестация:</b> {learning_path.attestation.name}\n\n"
        else:
            trainee_info += "\n"

        trainee_info += "🟡 <b>Какой этап необходимо открыть стажеру?</b>"

        # Создаем клавиатуру с этапами для выбора
        keyboard = InlineKeyboardMarkup(inline_keyboard=[])

        for stage in sorted(stages, key=lambda s: s.order_number):
            keyboard.inline_keyboard.append([
                InlineKeyboardButton(
                    text=f"Этап {stage.order_number}",
                    callback_data=f"open_stage:{trainee_id}:{stage.id}"
                )
            ])

        # Добавляем кнопки навигации
        keyboard.inline_keyboard.append([
            InlineKeyboardButton(text="👥 Мои стажеры", callback_data="my_trainees"),
            InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")
        ])

        await callback.message.edit_text(
            trainee_info,
            parse_mode="HTML",
            reply_markup=keyboard
        )
    else:
        await callback.message.edit_text(
            "❌ <b>Ошибка назначения траектории</b>\n\n"
            "Не удалось назначить траекторию стажеру.\n"
            "Попробуйте позже.",
            parse_mode="HTML"
        )

    await callback.answer()


def generate_trajectory_progress_for_mentor(trainee_path, stages_progress, test_results=None):
    """Генерация текста прогресса траектории для наставника"""
    if not trainee_path:
        return "🗺️<b>Траектория:</b> не выбрано"

    progress = f"⏺️<b>Название траектории:</b> {trainee_path.learning_path.name if trainee_path.learning_path else 'Не указано'}\n"

    # Создаем словарь результатов тестов для быстрого поиска
    test_results_dict = {}
    if test_results:
        for result in test_results:
            test_results_dict[result.test_id] = result

    for stage_progress in stages_progress:
        # Определяем статус этапа: 🟢 если все сессии пройдены, 🟡 если открыт, ⏺️ если закрыт
        sessions_progress = stage_progress.session_progress
        
        # Проверяем, все ли тесты в сессиях пройдены (только если этап открыт)
        all_sessions_completed = False
        if sessions_progress and stage_progress.is_opened:
            # Проверяем только если этап открыт
            all_sessions_completed = all(
                all(test.id in test_results_dict and test_results_dict[test.id].is_passed 
                    for test in sp.session.tests) 
                for sp in sessions_progress if hasattr(sp.session, 'tests') and sp.session.tests
            )
        
        if all_sessions_completed and sessions_progress:
            stage_status_icon = "🟢"  # Все сессии пройдены
        elif stage_progress.is_opened:
            stage_status_icon = "🟡"  # Этап открыт
        else:
            stage_status_icon = "⏺️"  # Этап закрыт
            
        progress += f"{stage_status_icon}<b>Этап {stage_progress.stage.order_number}:</b> {stage_progress.stage.name}\n"

        # Получаем сессии этапа
        for session_progress in sessions_progress:
            # Определяем статус сессии: 🟢 если все тесты пройдены, 🟡 если этап открыт, ⏺️ если этап закрыт
            if hasattr(session_progress.session, 'tests') and session_progress.session.tests:
                # ИСПРАВЛЕНИЕ: проверяем пройденность только если этап открыт
                all_tests_passed = False
                if stage_progress.is_opened:
                    all_tests_passed = all(
                        test.id in test_results_dict and test_results_dict[test.id].is_passed 
                        for test in session_progress.session.tests
                    )
                
                if all_tests_passed and stage_progress.is_opened:
                    session_status_icon = "🟢"  # Все тесты пройдены (только если этап открыт)
                elif stage_progress.is_opened:
                    session_status_icon = "🟡"  # Этап открыт, сессия доступна
                else:
                    session_status_icon = "⏺️"  # Этап закрыт
            else:
                session_status_icon = "⏺️"  # Нет тестов
                
            progress += f"{session_status_icon}<b>Сессия {session_progress.session.order_number}:</b> {session_progress.session.name}\n"

            # Получаем тесты сессии
            for test in session_progress.session.tests:
                # Определяем статус теста и процент прохождения
                if test.id in test_results_dict:
                    result = test_results_dict[test.id]
                    # ИСПРАВЛЕНИЕ: показываем зеленый только если этап открыт И тест пройден
                    if result.is_passed and stage_progress.is_opened:
                        test_status = "🟢"
                        # Вычисляем процент прохождения
                        percentage = (result.score / result.max_possible_score) * 100
                        percentage_text = f" - {percentage:.0f}%"
                    else:
                        # Тест не пройден, или этап закрыт
                        test_status = "🟡" if stage_progress.is_opened else "⏺️"
                        percentage_text = ""
                else:
                    # Тест не проходился, статус зависит от открытости этапа
                    test_status = "🟡" if stage_progress.is_opened else "⏺️"
                    percentage_text = ""

                progress += f"{test_status}<b>Тест {len([t for t in session_progress.session.tests if t.id <= test.id])}:</b> {test.name}{percentage_text}\n"

    # Аттестация с базовым статусом (для совместимости) 
    if trainee_path.learning_path.attestation:
        attestation_status = "⏺️"  # По умолчанию не назначена (нужна async версия для точного статуса)
        progress += f"🔍{attestation_status}<b>Аттестация:</b> {trainee_path.learning_path.attestation.name}\n"
    else:
        progress += "🔍⏺️<b>Аттестация:</b> Не указана\n"

    return progress


async def generate_trajectory_progress_with_attestation_status(session, trainee_path, stages_progress, test_results=None):
    """Генерация прогресса траектории с правильным статусом аттестации для Task 7"""
    if not trainee_path:
        return "🗺️<b>Траектория:</b> не выбрано"

    progress = f"⏺️<b>Название траектории:</b> {trainee_path.learning_path.name if trainee_path.learning_path else 'Не указано'}\n"

    # Создаем словарь результатов тестов для быстрого поиска
    test_results_dict = {}
    if test_results:
        for result in test_results:
            test_results_dict[result.test_id] = result

    for stage_progress in stages_progress:
        # Определяем статус этапа: 🟢 если все сессии пройдены, 🟡 если открыт, ⏺️ если закрыт
        sessions_progress = stage_progress.session_progress
        
        # Проверяем, все ли тесты в сессиях пройдены (только если этап открыт)
        all_sessions_completed = False
        if sessions_progress and stage_progress.is_opened:
            # Проверяем только если этап открыт
            all_sessions_completed = all(
                all(test.id in test_results_dict and test_results_dict[test.id].is_passed 
                    for test in sp.session.tests) 
                for sp in sessions_progress if hasattr(sp.session, 'tests') and sp.session.tests
            )
        
        if all_sessions_completed and sessions_progress:
            stage_status_icon = "🟢"  # Все сессии пройдены
        elif stage_progress.is_opened:
            stage_status_icon = "🟡"  # Этап открыт
        else:
            stage_status_icon = "⏺️"  # Этап закрыт
            
        progress += f"{stage_status_icon}<b>Этап {stage_progress.stage.order_number}:</b> {stage_progress.stage.name}\n"

        # Получаем сессии этапа
        for session_progress in sessions_progress:
            # Определяем статус сессии
            if hasattr(session_progress.session, 'tests') and session_progress.session.tests:
                # ИСПРАВЛЕНИЕ: проверяем пройденность только если этап открыт
                all_tests_passed = False
                if stage_progress.is_opened:
                    all_tests_passed = all(
                        test.id in test_results_dict and test_results_dict[test.id].is_passed 
                        for test in session_progress.session.tests
                    )
                
                if all_tests_passed and stage_progress.is_opened:
                    session_status_icon = "🟢"  # Все тесты пройдены (только если этап открыт)
                elif stage_progress.is_opened:
                    session_status_icon = "🟡"  # Этап открыт, сессия доступна
                else:
                    session_status_icon = "⏺️"  # Этап закрыт
            else:
                session_status_icon = "🟡" if stage_progress.is_opened else "⏺️"
                
            progress += f"{session_status_icon}<b>Сессия {session_progress.session.order_number}:</b> {session_progress.session.name}\n"

            # Получаем тесты сессии
            for test in session_progress.session.tests:
                # Определяем статус теста и процент прохождения
                if test.id in test_results_dict:
                    result = test_results_dict[test.id]
                    # ИСПРАВЛЕНИЕ: показываем зеленый только если этап открыт И тест пройден
                    if result.is_passed and stage_progress.is_opened:
                        test_status = "🟢"
                        percentage = (result.score / result.max_possible_score) * 100
                        percentage_text = f" - {percentage:.0f}%"
                    else:
                        # Тест не пройден, или этап закрыт
                        test_status = "🟡" if stage_progress.is_opened else "⏺️"
                        percentage_text = ""
                else:
                    test_status = "🟡" if stage_progress.is_opened else "⏺️"
                    percentage_text = ""

                progress += f"{test_status}<b>Тест {len([t for t in session_progress.session.tests if t.id <= test.id])}:</b> {test.name}{percentage_text}\n"

    # Аттестация с правильным статусом согласно ТЗ Task 7
    if trainee_path.learning_path.attestation:
        attestation_status = await get_trainee_attestation_status(
            session, trainee_path.trainee_id, trainee_path.learning_path.attestation.id
        )
        progress += f"🔍{attestation_status}<b>Аттестация:</b> {trainee_path.learning_path.attestation.name}\n"
    else:
        progress += "🔍⏺️<b>Аттестация:</b> Не указана\n"

    return progress


@router.callback_query(F.data == "my_trainees")
async def process_my_trainees_callback(callback: CallbackQuery, session: AsyncSession):
    """Обработчик кнопки 'Мои стажёры' из уведомления - ПО ТЗ 6-й задачи"""
    user = await get_user_by_tg_id(session, callback.from_user.id)
    if not user:
        await callback.message.answer("❌ Вы не зарегистрированы в системе.")
        await callback.answer()
        return
    
    trainees = await get_mentor_trainees(session, user.id)
    
    if not trainees:
        await callback.message.edit_text(
            "👥 <b>Ваши стажеры</b>\n\n"
            "У вас пока нет назначенных стажеров.\n"
            "Обратитесь к рекрутеру для назначения стажеров.",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")]
            ])
        )
        await callback.answer()
        return
    
    # Создаем клавиатуру со списком стажеров согласно ТЗ
    keyboard = InlineKeyboardMarkup(inline_keyboard=[])

    # Формируем сообщение со списком стажеров
    message_text = "👥 <b>Ваши стажеры</b>\n\n"

    for i, trainee in enumerate(trainees, 1):
        # Получаем информацию о траектории стажера
        trainee_path = await get_trainee_learning_path(session, trainee.id)
        trajectory_name = trainee_path.learning_path.name if trainee_path else "не выбрано"

        # Подсчитываем количество дней в статусе стажера
        days_as_trainee = (datetime.now() - trainee.role_assigned_date).days
        days_word = get_days_word(days_as_trainee)

        # Добавляем информацию о стажере согласно ТЗ
        message_text += f"{i}. <b>{trainee.full_name}</b>\n\n"
        message_text += f"<b>Телефон:</b> {trainee.phone_number}\n"
        message_text += f"<b>В статусе стажера:</b> {days_as_trainee} {days_word}\n"
        message_text += f"<b>Объект стажировки:</b> {trainee.internship_object.name if trainee.internship_object else 'Не указан'}\n"
        message_text += f"<b>Объект работы:</b> {trainee.work_object.name if trainee.work_object else 'Не указан'}\n\n"
        message_text += f"📌<b>Траектория:</b> {trajectory_name}\n\n"
        message_text += "━━━━━━━━━━━━\n\n"

        # Добавляем кнопку для выбора стажера
        keyboard.inline_keyboard.append([
            InlineKeyboardButton(
                text=f"{trainee.full_name}",
                callback_data=f"select_trainee_for_trajectory:{trainee.id}"
            )
        ])

    # Добавляем кнопку главного меню
    keyboard.inline_keyboard.append([
        InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")
    ])
    
    await callback.message.edit_text(
        message_text + "Выбери стажёра для взаимодействия, откроется карточка с данными, прогрессом и назначением траектории обучения:",
        parse_mode="HTML",
        reply_markup=keyboard
    )
    await callback.answer()

@router.callback_query(F.data.startswith("open_first_stage:"))
async def callback_open_first_stage(callback: CallbackQuery, session: AsyncSession, bot):
    """Обработчик открытия первого этапа для стажера"""
    trainee_id = int(callback.data.split(":")[1])

    # Получаем траекторию стажера
    trainee_path = await get_trainee_learning_path(session, trainee_id)
    if not trainee_path:
        await callback.message.edit_text("Траектория не найдена")
        await callback.answer()
        return

    # Получаем первый этап
    stages = await get_learning_path_stages(session, trainee_path.learning_path_id)
    if not stages:
        await callback.message.edit_text("Этапы траектории не найдены")
        await callback.answer()
        return

    first_stage = min(stages, key=lambda s: s.order_number)

    # Открываем первый этап
    success = await open_stage_for_trainee(session, trainee_id, first_stage.id, bot)

    if success:
        success_message = (
            "✅ <b>Первый этап успешно открыт!</b>\n\n"
            f"👤 <b>Стажер:</b> {(await get_user_by_id(session, trainee_id)).full_name}\n"
            f"🟡 <b>Открытый этап:</b> {first_stage.name}\n\n"
            "🗺️ <b>Стажер получил уведомление об открытии этапа!</b>\n\n"
            "Теперь стажер может приступить к прохождению первого этапа через кнопку 'Траектория'"
        )

        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="👥 Мои стажеры", callback_data="my_trainees"),
                InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")
            ]
        ])

        await callback.message.edit_text(
            success_message,
            parse_mode="HTML",
            reply_markup=keyboard
        )
    else:
        await callback.message.edit_text(
            "❌ <b>Ошибка открытия этапа</b>\n\n"
            "Не удалось открыть первый этап для стажера.",
            parse_mode="HTML"
        )

    await callback.answer()


@router.callback_query(F.data == "grant_test_access")
async def process_grant_test_access_callback(callback: CallbackQuery, session: AsyncSession):
    """Обработчик кнопки 'Предоставить доступ к тестам' из уведомления"""
    user = await get_user_by_tg_id(session, callback.from_user.id)
    if not user:
        await callback.message.answer("❌ Вы не зарегистрированы в системе.")
        await callback.answer()
        return
    
    # Проверяем права доступа
    has_permission = await check_user_permission(session, user.id, "grant_test_access")
    if not has_permission:
        await callback.message.edit_text(
            "❌ <b>Недостаточно прав</b>\n\n"
            "У вас нет прав для предоставления доступа к тестам.\n"
            "Обратитесь к администратору.",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")]
            ])
        )
        await callback.answer()
        return
    
    # Получаем стажеров наставника
    trainees = await get_mentor_trainees(session, user.id)
    
    if not trainees:
        await callback.message.edit_text(
            "❌ <b>Нет стажеров</b>\n\n"
            "У вас нет назначенных стажеров.\n"
            "Обратитесь к рекрутеру для назначения стажеров.",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")]
            ])
        )
        await callback.answer()
        return
    
    # Получаем доступные тесты
    tests = await get_all_active_tests(session)
    
    if not tests:
        await callback.message.edit_text(
            "❌ <b>Нет доступных тестов</b>\n\n"
            "В системе нет активных тестов для назначения.",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")]
            ])
        )
        await callback.answer()
        return
    
    # Показываем интерфейс выбора тестов
    tests_info = "\n".join([
        f"📋 <b>{test.name}</b>"
        for test in tests[:5]  # Показываем первые 5 тестов
    ])
    
    if len(tests) > 5:
        tests_info += f"\n... и еще {len(tests) - 5} тестов"
    
    await callback.message.edit_text(
        f"📊 <b>Предоставление доступа к тестам</b>\n\n"
        f"👥 <b>Ваших стажеров:</b> {len(trainees)}\n"
        f"📋 <b>Доступных тестов:</b> {len(tests)}\n\n"
        f"<b>Тесты в системе:</b>\n{tests_info}\n\n"
        "Выберите тест для назначения стажерам:",
        parse_mode="HTML",
        reply_markup=get_tests_for_access_keyboard(tests)
    )
    await callback.answer()

@router.callback_query(F.data == "my_mentor_info")
async def process_my_mentor_info(callback: CallbackQuery, session: AsyncSession):
    """Обработчик кнопки информации о наставнике из уведомления"""
    user = await get_user_by_tg_id(session, callback.from_user.id)
    if not user:
        await callback.message.edit_text("❌ Пользователь не найден.")
        await callback.answer()
        return
    
    mentor = await get_trainee_mentor(session, user.id)
    
    if not mentor:
        await callback.message.edit_text(
            "👨‍🏫 <b>Информация о наставнике</b>\n\n"
            "У вас пока не назначен наставник.\n"
            "Обратитесь к администратору или дождитесь назначения.",
            parse_mode="HTML"
        )
        await callback.answer()
        return
    
    mentor_info = f"""👨‍🏫 <b>Ваш наставник</b>

🧑 <b>ФИО:</b> {mentor.full_name}
📞 <b>Телефон:</b> {mentor.phone_number}
📧 <b>Telegram:</b> @{mentor.username or 'не указан'}

💡 <b>Рекомендации:</b>
• Не стесняйтесь задавать вопросы
• Обсуждайте сложности в обучении  
• Просите помощь с тестами и заданиями
• Регулярно связывайтесь для обратной связи"""

    keyboard_buttons = []
    
    # Кнопка для связи с наставником (если есть username)
    if mentor.username:
        keyboard_buttons.append([
            InlineKeyboardButton(
                text="💬 Написать наставнику", 
                url=f"https://t.me/{mentor.username}"
            )
        ])
    
    keyboard_buttons.append([
        InlineKeyboardButton(text="🗺️ Тесты траектории", callback_data="trajectory_tests_shortcut")
    ])
    
    await callback.message.edit_text(
        mentor_info,
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
    )
    await callback.answer()

@router.callback_query(F.data.startswith("trainee_results:"))
async def process_trainee_results(callback: CallbackQuery, session: AsyncSession):
    """Показывает результаты тестов конкретного стажера"""
    trainee_id = int(callback.data.split(':')[1])
    trainee = await get_user_by_id(session, trainee_id)
    if not trainee:
        await callback.answer("❌ Стажер не найден.", show_alert=True)
        return

    results = await get_user_test_results(session, trainee_id)
    
    if not results:
        await callback.message.edit_text(
            f"📊 <b>Результаты стажера: {trainee.full_name}</b>\n\n"
            "Этот стажер еще не проходил ни одного теста.",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="⬅️ Назад к стажеру", callback_data=f"trainee:{trainee_id}")]
            ])
        )
        await callback.answer()
        return

    # Расширенная статистика
    passed_count = sum(1 for r in results if r.is_passed)
    avg_score = sum(r.score for r in results) / len(results)
    
    results_text = f"📊 <b>Результаты стажера: {trainee.full_name}</b>\n\n"
    results_text += f"<b>Общая статистика:</b>\n"
    results_text += f"  • Пройдено тестов: {passed_count}/{len(results)}\n"
    results_text += f"  • Средний балл: {avg_score:.2f}\n\n"
    
    results_text += "<b>Детальные результаты:</b>\n"
    for res in results:
        test = await get_test_by_id(session, res.test_id)
        status = "✅" if res.is_passed else "❌"
        percentage = (res.score / res.max_possible_score) * 100
        results_text += f"{status} <b>{test.name if test else 'Тест удален'}:</b> {res.score}/{res.max_possible_score} баллов ({percentage:.0f}%)\n"

    await callback.message.edit_text(
        results_text,
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ Назад к стажеру", callback_data=f"trainee:{trainee_id}")]
        ])
    )
    await callback.answer()

@router.callback_query(F.data.startswith("trainee:"))
async def process_trainee_action_selection(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Обработчик выбора стажера для действий"""
    trainee_id = int(callback.data.split(':')[1])
    
    trainee = await get_user_by_id(session, trainee_id)
    if not trainee:
        await callback.answer("❌ Стажер не найден.", show_alert=True)
        return

    # Получаем информацию о стажере
    mentor = await get_trainee_mentor(session, trainee_id)
    results = await get_user_test_results(session, trainee_id)
    passed_count = sum(1 for r in results if r.is_passed)
    avg_score = sum(r.score for r in results) / len(results) if results else 0
    
    trainee_info = f"""👤 <b>Профиль стажера</b>

🧑 <b>ФИО:</b> {trainee.full_name}
📞 <b>Телефон:</b> {trainee.phone_number}
📧 <b>Telegram:</b> @{trainee.username or 'не указан'}
📅 <b>Дата регистрации:</b> {trainee.registration_date.strftime('%d.%m.%Y %H:%M')}

👨‍🏫 <b>Наставник:</b> {mentor.full_name if mentor else 'Не назначен'}

📊 <b>Статистика тестов:</b>
✅ Пройдено: {passed_count}/{len(results)}
📈 Средний балл: {avg_score:.2f}

💡 Выберите действие:"""
    
    await callback.message.edit_text(
        trainee_info,
        parse_mode="HTML",
        reply_markup=get_trainee_actions_keyboard(trainee_id)
    )
    
    await state.clear()
    await callback.answer()

# =================================
# НЕДОСТАЮЩИЕ ОБРАБОТЧИКИ ДЛЯ НАЗНАЧЕНИЯ ТЕСТОВ
# =================================

@router.callback_query(F.data.startswith("add_test_access:"))
async def process_add_test_access(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Обработчик добавления доступа к тесту стажеру"""
    trainee_id = int(callback.data.split(':')[1])
    
    user = await get_user_by_tg_id(session, callback.from_user.id)
    if not user:
        await callback.message.answer("❌ Пользователь не найден.")
        await callback.answer()
        return
    
    # Проверяем права
    has_permission = await check_user_permission(session, user.id, "grant_test_access")
    if not has_permission:
        await callback.message.edit_text(
            "❌ <b>Недостаточно прав</b>\n\n"
            "У вас нет прав для предоставления доступа к тестам.\n"
            "Обратитесь к администратору.",
            parse_mode="HTML"
        )
        await callback.answer()
        return
    
    # Получаем все активные тесты
    tests = await get_all_active_tests(session)
    
    if not tests:
        await callback.message.edit_text(
            "❌ <b>Нет доступных тестов</b>\n\n"
            "В системе пока нет созданных тестов.\n"
            "Обратитесь к рекрутеру для создания тестов.",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="⬅️ Назад к стажеру", callback_data=f"trainee:{trainee_id}")]
            ])
        )
        await callback.answer()
        return
    
    trainee = await get_user_by_id(session, trainee_id)
    if not trainee:
        await callback.message.answer("❌ Стажер не найден.")
        await callback.answer()
        return
    
    await callback.message.edit_text(
        f"📋 <b>Добавление теста стажеру</b>\n\n"
        f"👤 <b>Стажер:</b> {trainee.full_name}\n"
        f"📊 <b>Доступно тестов:</b> {len(tests)}\n\n"
        "Выберите тест, к которому хотите предоставить доступ:",
        parse_mode="HTML",
        reply_markup=get_test_access_keyboard(tests, trainee_id)
    )
    
    await state.set_state(TraineeManagementStates.waiting_for_test_access_grant)
    await callback.answer()

@router.callback_query(TraineeManagementStates.waiting_for_test_access_grant, F.data.startswith("grant_access:"))
async def process_grant_access_to_trainee(callback: CallbackQuery, state: FSMContext, session: AsyncSession, bot):
    """Обработчик предоставления доступа к конкретному тесту"""
    parts = callback.data.split(':')
    trainee_id = int(parts[1])
    test_id = int(parts[2])
    
    user = await get_user_by_tg_id(session, callback.from_user.id)
    test = await get_test_by_id(session, test_id)
    trainee = await get_user_by_id(session, trainee_id)
    
    if not all([user, test, trainee]):
        await callback.message.answer("❌ Данные не найдены.")
        await callback.answer()
        return
    
    # Предоставляем доступ с отправкой уведомления
    success = await grant_test_access(session, trainee_id, test_id, user.id, bot)
    
    if success:
        await callback.message.edit_text(
            f"✅ <b>Доступ предоставлен!</b>\n\n"
            f"👤 <b>Стажер:</b> {trainee.full_name}\n"
            f"📋 <b>Тест:</b> {test.name}\n"
            f"🎯 <b>Проходной балл:</b> {test.threshold_score}/{test.max_score}\n\n"
            f"📬 <b>Уведомление отправлено!</b>\n"
            f"Стажер {trainee.full_name} получил уведомление о новом тесте в личном кабинете.",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="📋 Добавить еще тест", callback_data=f"add_test_access:{trainee_id}")],
                [InlineKeyboardButton(text="⬅️ Назад к стажеру", callback_data=f"trainee:{trainee_id}")]
            ])
        )
        
        log_user_action(
            callback.from_user.id, 
            callback.from_user.username, 
            "granted test access via trainee menu", 
            {"test_id": test_id, "trainee_id": trainee_id}
        )
    else:
        await callback.message.edit_text(
            f"ℹ️ <b>Доступ уже был предоставлен</b>\n\n"
            f"👤 <b>Стажер:</b> {trainee.full_name}\n"
            f"📋 <b>Тест:</b> {test.name}\n\n"
            f"Этот стажер уже имеет доступ к данному тесту.",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="📋 Добавить другой тест", callback_data=f"add_test_access:{trainee_id}")],
                [InlineKeyboardButton(text="⬅️ Назад к стажеру", callback_data=f"trainee:{trainee_id}")]
            ])
        )
    
    await state.clear()
    await callback.answer()

@router.callback_query(F.data.startswith("trainee_profile:"))
async def process_trainee_profile(callback: CallbackQuery, session: AsyncSession):
    """Показывает детальный профиль стажера"""
    trainee_id = int(callback.data.split(':')[1])
    trainee = await get_user_by_id(session, trainee_id)
    if not trainee:
        await callback.answer("❌ Стажер не найден.", show_alert=True)
        return

    # Получаем детальную информацию
    mentor = await get_trainee_mentor(session, trainee_id)
    results = await get_user_test_results(session, trainee_id)
    
    # Получаем список доступных тестов
    available_tests = await get_trainee_available_tests(session, trainee_id)
    
    # Статистика
    passed_count = sum(1 for r in results if r.is_passed)
    failed_count = len(results) - passed_count
    avg_score = sum(r.score for r in results) / len(results) if results else 0
    
    # Последний тест
    last_test_info = ""
    if results:
        last_result = results[0]  # Результаты отсортированы по дате
        last_test = await get_test_by_id(session, last_result.test_id)
        status = "✅ Пройден" if last_result.is_passed else "❌ Не пройден"
        percentage = (last_result.score / last_result.max_possible_score) * 100
        last_test_info = f"""
📋 <b>Последний тест:</b>
   • {last_test.name if last_test else 'Тест удален'}
   • {status} ({last_result.score}/{last_result.max_possible_score} баллов - {percentage:.0f}%)
   • {last_result.created_date.strftime('%d.%m.%Y %H:%M')}"""
    
    profile_text = f"""👤 <b>Детальный профиль стажера</b>

🧑 <b>Личная информация:</b>
   • ФИО: {trainee.full_name}
   • Телефон: {trainee.phone_number}
   • Telegram: @{trainee.username or 'не указан'}
   • ID: {trainee.tg_id}
   • Дата регистрации: {trainee.registration_date.strftime('%d.%m.%Y %H:%M')}

👨‍🏫 <b>Наставничество:</b>
   • Наставник: {mentor.full_name if mentor else 'Не назначен'}

📊 <b>Статистика тестирования:</b>
   • Доступно тестов: {len(available_tests)}
   • Пройдено тестов: {len(results)}
   • Успешно пройдено: {passed_count}
   • Не пройдено: {failed_count}
   • Средний балл: {avg_score:.2f}{last_test_info}

📈 <b>Прогресс:</b> {passed_count}/{len(available_tests)} доступных тестов пройдено"""

    await callback.message.edit_text(
        profile_text,
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ Назад к действиям", callback_data=f"trainee:{trainee_id}")]
        ])
    )
    await callback.answer()

@router.callback_query(F.data == "back_to_trainees")
async def process_back_to_trainees(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Возврат к списку стажеров"""
    user = await get_user_by_tg_id(session, callback.from_user.id)
    trainees = await get_mentor_trainees(session, user.id)
    
    if not trainees:
        await callback.message.edit_text(
            "👥 <b>Ваши стажеры</b>\n\n"
            "У вас пока нет назначенных стажеров.\n"
            "Обратитесь к рекрутеру для назначения стажеров.",
            parse_mode="HTML"
        )
        await callback.answer()
        return
    
    trainees_list = "\n\n".join([
        f"👤 <b>{trainee.full_name}</b>\n"
        f"   📞 {trainee.phone_number}\n"
        f"   📅 Регистрация: {trainee.registration_date.strftime('%d.%m.%Y')}"
        for trainee in trainees
    ])
    
    await callback.message.edit_text(
        f"👥 <b>Ваши стажеры</b>\n\n"
        f"Всего стажеров: <b>{len(trainees)}</b>\n\n{trainees_list}\n\n"
        "Выберите стажера для управления:",
        parse_mode="HTML",
        reply_markup=get_trainee_selection_keyboard(trainees)
    )
    
    await state.set_state(MentorshipStates.waiting_for_trainee_action)
    await callback.answer()

@router.callback_query(F.data == "assign_mentor")
async def process_assign_mentor_callback(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Обработчик кнопки 'Назначить наставника' из уведомления"""
    user = await get_user_by_tg_id(session, callback.from_user.id)
    if not user:
        await callback.message.answer("❌ Вы не зарегистрированы в системе.")
        await callback.answer()
        return
    
    has_permission = await check_user_permission(session, user.id, "assign_mentors")
    if not has_permission:
        await callback.message.edit_text(
            "❌ <b>Недостаточно прав</b>\n\n"
            "У вас нет прав для назначения наставников.\n"
            "Обратитесь к администратору.",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")]
            ])
        )
        await callback.answer()
        return
    
    unassigned_trainees = await get_unassigned_trainees(session)
    
    if not unassigned_trainees:
        await callback.message.edit_text(
            "✅ <b>Все стажеры уже имеют наставников!</b>\n\n"
            "В настоящее время все зарегистрированные стажеры имеют назначенных наставников.",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="👥 Список всех наставников", callback_data="view_all_mentors")],
                [InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")]
            ])
        )
        await callback.answer()
        return
    
    await callback.message.edit_text(
        f"👥 <b>Назначение наставника</b>\n\n"
        f"📊 <b>Статистика системы:</b>\n"
        f"• Стажеров без наставника: <b>{len(unassigned_trainees)}</b>\n"
        f"• Требуется назначение наставников\n\n"
        f"🎯 <b>Ваша задача:</b> Назначить наставника каждому стажеру для:\n"
        f"• Персонального сопровождения\n"
        f"• Контроля прогресса обучения\n"
        f"• Помощи в адаптации\n"
        f"• Предоставления доступа к тестам\n\n"
        f"👇 <b>Выберите стажера для назначения наставника:</b>",
        parse_mode="HTML",
        reply_markup=get_unassigned_trainees_keyboard(unassigned_trainees)
    )
    
    await state.set_state(MentorshipStates.waiting_for_trainee_selection)
    await callback.answer()

@router.callback_query(F.data == "new_trainees_list")
async def process_new_trainees_list_callback(callback: CallbackQuery, session: AsyncSession):
    """Обработчик кнопки 'Список новых стажёров' из уведомления"""
    user = await get_user_by_tg_id(session, callback.from_user.id)
    if not user:
        await callback.message.answer("❌ Вы не зарегистрированы в системе.")
        await callback.answer()
        return
    
    has_permission = await check_user_permission(session, user.id, "view_trainee_list")
    if not has_permission:
        await callback.message.edit_text(
            "❌ <b>Недостаточно прав</b>\n\n"
            "У вас нет прав для просмотра списка стажёров.\n"
            "Обратитесь к администратору.",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")]
            ])
        )
        await callback.answer()
        return
    
    # Получаем стажеров без наставника (они считаются "новыми")
    unassigned_trainees = await get_unassigned_trainees(session)
    
    if not unassigned_trainees:
        await callback.message.edit_text(
            "📋 <b>Список новых стажёров</b>\n\n"
            "✅ Все стажеры уже имеют наставников!\n"
            "Новые стажёры появятся здесь после регистрации.",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="👨‍🏫 Назначить наставника", callback_data="assign_mentor")],
                [InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")]
            ])
        )
        await callback.answer()
        return
    
    users_info = []
    for i, trainee in enumerate(unassigned_trainees, 1):
        users_info.append(
            f"{i}. <b>{trainee.full_name}</b>\n"
            f"   📞 {trainee.phone_number}\n"
            f"   📧 @{trainee.username or 'не указан'}\n"
            f"   📅 Регистрация: {trainee.registration_date.strftime('%d.%m.%Y %H:%M')}"
        )
    
    users_list = "\n\n".join(users_info)
    
    await callback.message.edit_text(
        f"📋 <b>Список новых стажёров</b>\n\n"
        f"Стажёров без наставника: <b>{len(unassigned_trainees)}</b>\n\n"
        f"{users_list}\n\n"
        f"💡 <b>Рекомендация:</b> Используйте кнопку ниже для назначения наставников этим стажёрам.",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="👨‍🏫 Назначить наставника", callback_data="assign_mentor")],
            [InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")]
        ])
    )
    await callback.answer()


# ===== НОВЫЕ ФУНКЦИИ ДЛЯ УПРАВЛЕНИЯ ТРАЕКТОРИЯМИ =====

@router.callback_query(F.data == "assign_trajectory")
async def callback_assign_trajectory(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Обработчик кнопки 'Назначить траекторию' из уведомления - перенаправляет к списку стажеров"""
    try:
        await callback.answer()

        # Получаем текущего пользователя (наставника)
        mentor = await get_user_by_tg_id(session, callback.from_user.id)
        if not mentor:
            await callback.message.edit_text("Пользователь не найден")
            return

        # Получаем стажеров наставника  
        trainees = await get_mentor_trainees(session, mentor.id)

        if not trainees:
            await callback.message.edit_text(
                "👥 <b>Ваши стажеры</b>\n\n"
                "У вас пока нет назначенных стажеров.\n"
                "Обратитесь к рекрутеру для назначения стажеров.",
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")]
                ])
            )
            return

        # Показываем список стажеров для выбора (аналогично cmd_mentor_trainees)
        keyboard = InlineKeyboardMarkup(inline_keyboard=[])
        message_text = "👥 <b>Ваши стажеры</b>\n\n"

        for i, trainee in enumerate(trainees, 1):
            # Получаем информацию о траектории стажера
            trainee_path = await get_trainee_learning_path(session, trainee.id)
            trajectory_name = trainee_path.learning_path.name if trainee_path else "не выбрано"

            # Добавляем информацию о стажере согласно ТЗ
            message_text += f"{i}.  <b>{trainee.full_name}</b>\n"
            message_text += f"📍<b>1️⃣Объект стажировки:</b> {trainee.internship_object.name if trainee.internship_object else 'Не указан'}\n"
            message_text += f"📍<b>2️⃣Объект работы:</b> {trainee.work_object.name if trainee.work_object else 'Не указан'}\n"
            message_text += f"🗺️<b>Траектория:</b> {trajectory_name}\n"
            message_text += f"   📞 {trainee.phone_number}\n"
            message_text += f"   📅 Регистрация: {trainee.registration_date.strftime('%d.%m.%Y')}\n\n"

            # Добавляем кнопку для выбора стажера
            keyboard.inline_keyboard.append([
                InlineKeyboardButton(
                    text=f"{trainee.full_name}",
                    callback_data=f"select_trainee_for_trajectory:{trainee.id}"
                )
            ])

        # Добавляем кнопку главного меню
        keyboard.inline_keyboard.append([
            InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")
        ])

        await callback.message.edit_text(
            message_text + "Выберите стажера для назначения траектории:",
            reply_markup=keyboard,
            parse_mode="HTML"
        )

        log_user_action(callback.from_user.id, "assign_trajectory_from_notification", "Переход к списку стажеров из уведомления")

    except Exception as e:
        await callback.message.edit_text("Произошла ошибка при назначении траектории")
        log_user_error(callback.from_user.id, "assign_trajectory_error", str(e))


@router.callback_query(F.data.startswith("select_trajectory:"), MentorshipStates.selecting_trajectory)
async def callback_select_trajectory(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Обработчик выбора траектории"""
    try:
        await callback.answer()

        trajectory_id = int(callback.data.split(":")[1])

        # Получаем данные из состояния
        state_data = await state.get_data()
        trainee_id = state_data.get("selected_trainee_id")

        if not trainee_id:
            await callback.message.edit_text("Ошибка: стажер не выбран")
            return

        # Получаем данные стажера и траектории
        trainee = await get_user_by_id(session, trainee_id)
        trajectory = await get_learning_path_by_id(session, trajectory_id)

        if not trainee or not trajectory:
            await callback.message.edit_text("Ошибка: данные не найдены")
            return

        # Сохраняем выбранную траекторию в состоянии
        await state.update_data(selected_trajectory_id=trajectory_id)

        # Получаем этапы траектории для отображения
        stages = await get_learning_path_stages(session, trajectory_id)

        # Формируем информацию о траектории
        stages_info = ""
        for stage in stages:
            sessions_count = len(stage.sessions) if stage.sessions else 0
            tests_count = sum(len(session.tests) if session.tests else 0 for session in stage.sessions) if stage.sessions else 0
            stages_info += f"⏺️<b>Этап {stage.order_number}:</b> {stage.name}\n"
            stages_info += f"   📚 Сессий: {sessions_count}, Тестов: {tests_count}\n"

        confirmation_message = (
            "🗺️ <b>Подтверждение назначения траектории</b>\n\n"
            "👤 <b>Стажер:</b>\n"
            f"   • ФИО: {trainee.full_name}\n"
            f"   • Группа: {', '.join([group.name for group in trainee.groups]) if trainee.groups else 'Не указана'}\n\n"
            "📚 <b>Траектория:</b>\n"
            f"   • Название: {trajectory.name}\n"
            f"   • Описание: {trajectory.description or 'Не указано'}\n\n"
            f"<b>Этапы траектории:</b>\n{stages_info}\n"
            "❓ <b>Подтвердите назначение траектории:</b>"
        )

        # Клавиатура подтверждения
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Назначить", callback_data="confirm_trajectory_assignment"),
                InlineKeyboardButton(text="🚫 Отменить", callback_data="cancel_trajectory_assignment")
            ]
        ])

        await callback.message.edit_text(
            confirmation_message,
            reply_markup=keyboard,
            parse_mode="HTML"
        )

        await state.set_state(MentorshipStates.confirming_trajectory_assignment)

    except Exception as e:
        await callback.message.edit_text("Произошла ошибка при выборе траектории")
        log_user_error(callback.from_user.id, "select_trajectory_error", str(e))


@router.callback_query(F.data == "confirm_trajectory_assignment", MentorshipStates.confirming_trajectory_assignment)
async def callback_confirm_trajectory_assignment(callback: CallbackQuery, state: FSMContext, session: AsyncSession, bot):
    """Обработчик подтверждения назначения траектории"""
    try:
        await callback.answer()

        # Получаем данные из состояния
        state_data = await state.get_data()
        trainee_id = state_data.get("selected_trainee_id")
        trajectory_id = state_data.get("selected_trajectory_id")
        mentor_id = callback.from_user.id

        if not trainee_id or not trajectory_id:
            await callback.message.edit_text("Ошибка: данные не найдены")
            return

        # Назначаем траекторию стажеру
        success = await assign_learning_path_to_trainee(session, trainee_id, trajectory_id, mentor_id, bot)

        if success:
            # Получаем обновленные данные для отображения
            trainee = await get_user_by_id(session, trainee_id)
            trajectory = await get_learning_path_by_id(session, trajectory_id)
            mentor = await get_user_by_tg_id(session, mentor_id)

            success_message = (
                "✅ <b>Траектория успешно назначена!</b>\n\n"
                f"👤 <b>Стажер:</b> {trainee.full_name}\n"
                f"🗺️ <b>Траектория:</b> {trajectory.name}\n"
                f"👨‍🏫 <b>Назначил:</b> {mentor.full_name}\n"
            f"📅 <b>Дата назначения:</b> {trainee.registration_date.strftime('%d.%m.%Y %H:%M')}\n\n"
                "📬 <b>Стажер получил уведомление о назначении траектории!</b>\n\n"
                "🎯 <b>Теперь вы можете открывать этапы стажеру по мере необходимости.</b>"
            )

            # Клавиатура для продолжения работы
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [
                    InlineKeyboardButton(text="👥 Мои стажеры", callback_data="my_trainees"),
                    InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")
                ]
            ])

            await callback.message.edit_text(
                success_message,
                reply_markup=keyboard,
                parse_mode="HTML"
            )

            log_user_action(mentor_id, "trajectory_assigned_success",
                          f"Назначена траектория {trajectory.name} (ID: {trajectory_id}) стажеру {trainee.full_name} (ID: {trainee_id})")

        else:
            await callback.message.edit_text(
                    "❌ <b>Ошибка назначения траектории</b>\n\n"
                    "Произошла ошибка при назначении траектории.\n"
                    "Попробуйте позже или обратитесь к администратору.",
                parse_mode="HTML"
            )
            log_user_error(mentor_id, "trajectory_assignment_failed", f"Ошибка назначения траектории {trajectory_id} стажеру {trainee_id}")

        # Очищаем состояние
        await state.clear()

    except Exception as e:
        await callback.message.edit_text("Произошла ошибка при подтверждении назначения")
        log_user_error(callback.from_user.id, "confirm_trajectory_assignment_error", str(e))


@router.callback_query(F.data == "cancel_trajectory_assignment")
async def callback_cancel_trajectory_assignment(callback: CallbackQuery, state: FSMContext):
    """Обработчик отмены назначения траектории"""
    try:
        await callback.answer()

        await callback.message.edit_text(
            "🚫 <b>Назначение траектории отменено</b>\n\n"
            "Вы можете вернуться к этому позже.",
            reply_markup=get_trainee_actions_keyboard(),
                parse_mode="HTML"
        )

        await state.clear()
        log_user_action(callback.from_user.id, "trajectory_assignment_cancelled", "Отменено назначение траектории")

    except Exception as e:
        log_user_error(callback.from_user.id, "cancel_trajectory_assignment_error", str(e))


@router.callback_query(F.data.startswith("view_stage:"))
async def callback_view_stage(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Обработчик просмотра конкретного этапа стажера"""
    try:
        await callback.answer()

        # Получаем ID стажера и этапа из callback_data
        parts = callback.data.split(":")
        trainee_id = int(parts[1])
        stage_id = int(parts[2])

        # Получаем стажера
        trainee = await get_user_by_id(session, trainee_id)
        if not trainee:
            await callback.message.edit_text("Стажер не найден")
            return

        # Получаем траекторию стажера
        trainee_path = await get_trainee_learning_path(session, trainee_id)
        if not trainee_path:
            await callback.message.edit_text("Траектория не найдена")
            return

        # Получаем этапы и находим нужный
        stages_progress = await get_trainee_stage_progress(session, trainee_path.id)
        stage_progress = next((sp for sp in stages_progress if sp.stage_id == stage_id), None)

        if not stage_progress:
            await callback.message.edit_text("Этап не найден")
            return

        # Получаем сессии этапа
        sessions_progress = await get_stage_session_progress(session, stage_progress.id)

        # Формируем детальную информацию об этапе
        stage_info = (
            f"📊<b>ЭТАП {stage_progress.stage.order_number}: {stage_progress.stage.name}</b>📊\n\n"
            f"👤 <b>Стажер:</b> {trainee.full_name}\n"
            f"🗺️<b>Траектория:</b> {trainee_path.learning_path.name if trainee_path.learning_path else 'Не указано'}\n\n"
        )

        # Статус этапа
        if stage_progress.is_completed:
            stage_info += f"🟢 <b>Статус:</b> Пройден\n"
            if stage_progress.completed_date:
                stage_info += f"✅ <b>Завершен:</b> {stage_progress.completed_date.strftime('%d.%m.%Y %H:%M')}\n"
        elif stage_progress.is_opened:
            stage_info += f"🟡 <b>Статус:</b> Открыт\n"
            if stage_progress.opened_date:
                stage_info += f"📅 <b>Открыт:</b> {stage_progress.opened_date.strftime('%d.%m.%Y %H:%M')}\n"
        else:
            stage_info += f"⏺️ <b>Статус:</b> Закрыт\n"

        # Информация о сессиях
        completed_sessions = sum(1 for sp in sessions_progress if sp.is_completed)
        total_sessions = len(sessions_progress)
        stage_info += f"📚 <b>Сессий:</b> {completed_sessions}/{total_sessions}\n\n"

        # Детали по каждой сессии
        if sessions_progress:
            stage_info += "<b>Сессии этапа:</b>\n"
            for session_progress in sessions_progress:
                session_icon = "🟢" if session_progress.is_completed else ("🟡" if session_progress.is_opened else "⏺️")
                stage_info += f"{session_icon}<b>Сессия {session_progress.session.order_number}:</b> {session_progress.session.name}\n"

                # Показываем тесты сессии
                tests = session_progress.session.tests if hasattr(session_progress.session, 'tests') else []
                if tests:
                    for i, test in enumerate(tests, 1):
                        # Определяем статус теста
                        test_result = await get_user_test_result(session, trainee_id, test.id)
                        test_icon = "🟢" if (test_result and test_result.is_passed) else "⏺️"
                        test_status = "пройден" if (test_result and test_result.is_passed) else "не пройден"
                        stage_info += f"   {test_icon}Тест {i}: {test.name} ({test_status})\n"

                        if test_result and test_result.is_passed:
                            # Вычисляем процент прохождения
                            percentage = (test_result.score / test_result.max_possible_score) * 100
                            stage_info += f"      📊 Балл: {test_result.score}/{test_result.max_possible_score} ({percentage:.0f}%)\n"
                            if test_result.completed_date:
                                stage_info += f"      📅 Пройден: {test_result.completed_date.strftime('%d.%m.%Y %H:%M')}\n"
                else:
                    stage_info += "   📝 Тесты не найдены\n"

                stage_info += "\n"

        # Клавиатура действий
        keyboard_buttons = [
            [InlineKeyboardButton(text="↩️ Назад к этапам", callback_data=f"manage_stages:{trainee_id}")]
        ]

        # Если этап не открыт, добавляем кнопку открытия
        if not stage_progress.is_opened:
            keyboard_buttons.insert(0, [
                InlineKeyboardButton(
                    text=f"🟡 Открыть этап {stage_progress.stage.order_number}",
                    callback_data=f"open_stage:{trainee_id}:{stage_id}"
                )
            ])

        keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)

        await callback.message.edit_text(
            stage_info,
            reply_markup=keyboard,
            parse_mode="HTML"
        )

        log_user_action(callback.from_user.id, "stage_viewed",
                       f"Просмотрен этап {stage_progress.stage.order_number} стажера {trainee.full_name}")

    except Exception as e:
        await callback.message.edit_text("Произошла ошибка при просмотре этапа")
        log_user_error(callback.from_user.id, "view_stage_error", str(e))


# СТАРАЯ ЗАГЛУШКА УДАЛЕНА - ФУНКЦИОНАЛ РЕАЛИЗОВАН В TASK 7 НИЖЕ


@router.callback_query(F.data.startswith("stage_available_stub:"))
async def callback_stage_available_stub(callback: CallbackQuery, session: AsyncSession):
    """Заглушка для некликабельной кнопки 'Этап доступен'"""
    await callback.answer("✅ Этап уже открыт для стажера", show_alert=False)


@router.callback_query(F.data.startswith("view_trajectory:"))
async def callback_view_trajectory(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Обработчик просмотра траектории стажера"""
    try:
        await callback.answer()

        # Получаем ID стажера из callback_data
        trainee_id = int(callback.data.split(":")[1])

        # Получаем стажера
        trainee = await get_user_by_id(session, trainee_id)
        if not trainee:
            await callback.message.edit_text("Стажер не найден")
            return

        # Получаем траекторию стажера
        trainee_path = await get_trainee_learning_path(session, trainee_id)

        if not trainee_path:
            await callback.message.edit_text(
                f"❌ <b>Траектория не назначена</b>\n\n"
                f"👤 <b>Стажер:</b> {trainee.full_name}\n\n"
                "Этому стажеру еще не назначена траектория обучения.",
                parse_mode="HTML"
            )
            return

        # Получаем этапы траектории
        stages_progress = await get_trainee_stage_progress(session, trainee_path.id)
        # Получаем результаты тестов стажера
        test_results = await get_user_test_results(session, trainee_id)

        # Формируем информацию о траектории
        trajectory_info = (
            f"🦸🏻‍♂️ <b>Стажер:</b> {trainee.full_name}\n"
            f"<b>Траектория:</b> {trainee_path.learning_path.name if trainee_path.learning_path else 'Не указано'}\n\n\n"
            f"<b>Телефон:</b> {trainee.phone_number}\n"
            f"<b>Username:</b> @{trainee.username or 'не указан'}\n"
            f"<b>Номер:</b> #{trainee_id}\n"
            f"<b>Дата регистрации:</b> {trainee.registration_date.strftime('%d.%m.%Y %H:%M')}\n\n\n"
            "━━━━━━━━━━━━\n\n\n"
            "🗂️ <b>Статус:</b>\n"
            f"<b>Группа:</b> {', '.join([group.name for group in trainee.groups]) if trainee.groups else 'Не указана'}\n"
            f"<b>Роль:</b> {', '.join([role.name for role in trainee.roles])}\n\n\n"
            "━━━━━━━━━━━━\n\n\n"
            "📍 <b>Объект:</b>\n"
            f"<b>Стажировки:</b> {trainee.internship_object.name if trainee.internship_object else 'Не указан'}\n"
            f"<b>Работы:</b> {trainee.work_object.name if trainee.work_object else 'Не указан'}\n\n\n"
            "🗺️<b>Управление траекторией</b>\n\n"
        )

        # Используем новую функцию с правильным статусом аттестации для Task 7
        progress_info = await generate_trajectory_progress_with_attestation_status(session, trainee_path, stages_progress, test_results)

        # Клавиатура действий
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="Выбрать траекторию", callback_data=f"assign_trajectory:{trainee_id}"),
                InlineKeyboardButton(text="Этапы", callback_data=f"manage_stages:{trainee_id}")
            ],
            [
                InlineKeyboardButton(text="Аттестация", callback_data=f"view_trainee_attestation:{trainee_id}"),
                InlineKeyboardButton(text="Назад", callback_data="back_to_trainees")
            ]
        ])

        await callback.message.edit_text(
            trajectory_info + progress_info,
            reply_markup=keyboard,
            parse_mode="HTML"
        )

        log_user_action(callback.from_user.id, "trajectory_viewed", f"Просмотрена траектория стажера {trainee.full_name} (ID: {trainee_id})")

    except Exception as e:
        await callback.message.edit_text("Произошла ошибка при просмотре траектории")
        log_user_error(callback.from_user.id, "view_trajectory_error", str(e))


@router.callback_query(F.data.startswith("manage_stages:"))
async def callback_manage_stages(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Обработчик управления этапами траектории"""
    try:
        await callback.answer()

        trainee_id = int(callback.data.split(":")[1])
        
        # Используем вынесенную функцию для обновления интерфейса
        await update_stages_management_interface(callback, session, trainee_id)
        
        # Получаем имя стажера для логирования
        trainee = await get_user_by_id(session, trainee_id)
        if trainee:
            log_user_action(callback.from_user.id, "stages_management_opened", f"Открыто управление этапами для стажера {trainee.full_name}")

    except Exception as e:
        log_user_error(callback.from_user.id, "manage_stages_error", str(e))
        await callback.message.edit_text("Произошла ошибка при открытии управления этапами")


@router.callback_query(F.data.startswith("open_stage:"))
async def callback_open_stage(callback: CallbackQuery, state: FSMContext, session: AsyncSession, bot):
    """Обработчик открытия этапа для стажера"""
    try:
        await callback.answer()

        parts = callback.data.split(":")
        trainee_id = int(parts[1])
        stage_id = int(parts[2])

        # Открываем этап
        success = await open_stage_for_trainee(session, trainee_id, stage_id, bot)

        if success:
            # Получаем информацию для отображения
            trainee = await get_user_by_id(session, trainee_id)
            trainee_path = await get_trainee_learning_path(session, trainee_id)
            stages = await get_learning_path_stages(session, trainee_path.learning_path_id)
            current_stage = next((s for s in stages if s.id == stage_id), None)
            
            # Получаем обновленные этапы и результаты тестов
            stages_progress = await get_trainee_stage_progress(session, trainee_path.id)
            test_results = await get_user_test_results(session, trainee_id)

            # Формируем полную информацию согласно ТЗ шаг 9
            success_message = (
                f"🦸🏻‍♂️ <b>Стажер:</b> {trainee.full_name}\n"
                f"<b>Траектория:</b> {trainee_path.learning_path.name if trainee_path.learning_path else 'Не указано'}\n\n\n"
                f"<b>Телефон:</b> {trainee.phone_number}\n"
                f"<b>Username:</b> @{trainee.username or 'не указан'}\n"
                f"<b>Номер:</b> #{trainee_id}\n"
                f"<b>Дата регистрации:</b> {trainee.registration_date.strftime('%d.%m.%Y %H:%M')}\n\n\n"
                "━━━━━━━━━━━━\n\n\n"
                "🗂️ <b>Статус:</b>\n"
                f"<b>Группа:</b> {', '.join([group.name for group in trainee.groups]) if trainee.groups else 'Не указана'}\n"
                f"<b>Роль:</b> {', '.join([role.name for role in trainee.roles])}\n\n\n"
                "━━━━━━━━━━━━\n\n\n"
                "📍 <b>Объект:</b>\n"
                f"<b>Стажировки:</b> {trainee.internship_object.name if trainee.internship_object else 'Не указан'}\n"
                f"<b>Работы:</b> {trainee.work_object.name if trainee.work_object else 'Не указан'}\n\n\n"
                "🗺️<b>Управление траекторией</b>\n\n"
            )
            
            # Добавляем полную траекторию с обновленными статусами
            trajectory_progress = generate_trajectory_progress_for_mentor(trainee_path, stages_progress, test_results)
            success_message += trajectory_progress + "\n"
            
            # Добавляем сообщение об успешном открытии
            success_message += f"✅<b>Вы успешно открыли стажёру {current_stage.name}!</b>\n\n"
            success_message += f"<b>Открытые стажёру этапы отображаются значком 🟡</b>\n"
            success_message += f"<b>Пройденные стажёром этапы отображаются значком 🟢</b>\n\n"
            success_message += f"<b>Чтобы следить за прогрессом стажёра:</b>\n"
            success_message += f"1 Нажмите кнопку \"Мои стажёры\"\n"
            success_message += f"2 Выберите нужного стажёра\n"
            success_message += f"3 Откройте просмотр стажёра, чтобы увидеть его результаты"

            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [
                    InlineKeyboardButton(text="👥 Мои стажёры", callback_data="my_trainees"),
                    InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")
                ],
                [
                    InlineKeyboardButton(text="⬅️ Назад к этапам", callback_data=f"manage_stages:{trainee_id}")
                ]
            ])

            await callback.message.edit_text(
                success_message,
                reply_markup=keyboard,
                parse_mode="HTML"
            )

            log_user_action(callback.from_user.id, "stage_opened_success",
                          f"Открыт этап {current_stage.order_number}: {current_stage.name} для стажера {trainee.full_name}")

        else:
            await callback.message.edit_text(
                "❌ <b>Ошибка открытия этапа</b>\n\n"
                "Произошла ошибка при открытии этапа.\n"
                "Попробуйте позже или обратитесь к администратору.",
                parse_mode="HTML"
            )
            log_user_error(callback.from_user.id, "stage_open_failed", f"Ошибка открытия этапа {stage_id} для стажера {trainee_id}")

    except Exception as e:
        await callback.message.edit_text("Произошла ошибка при открытии этапа")
        log_user_error(callback.from_user.id, "open_stage_error", str(e))


# ===== ОБРАБОТЧИКИ ДЛЯ РАБОТЫ С РУКОВОДИТЕЛЯМИ =====

@router.callback_query(F.data.startswith("assign_manager:"))
async def callback_assign_manager(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """
    Обработчик назначения руководителя стажеру
    """
    try:
        await callback.answer()

        # Получаем ID стажера
        trainee_id = int(callback.data.split(":")[1])

        # Получаем стажера
        trainee = await get_user_by_id(session, trainee_id)
        if not trainee:
            await callback.message.edit_text("Стажер не найден")
            return

        # Получаем доступных руководителей
        available_managers = await get_available_managers_for_trainee(session, trainee_id)

        if not available_managers:
            await callback.message.edit_text(
                f"❌ <b>Нет доступных руководителей</b>\n\n"
                f"👤 <b>Стажер:</b> {trainee.full_name}\n\n"
                "Для этого стажера нет доступных руководителей.\n"
                "Возможно, нет руководителей на том же объекте работы.",
                parse_mode="HTML"
            )
            return

        # Сохраняем ID стажера в состоянии
        await state.update_data(selected_trainee_id=trainee_id)

        # Формируем информацию о стажере
        trainee_info = (
            f"👤 <b>Выбран стажер:</b> {trainee.full_name}\n"
            f"📍<b>1️⃣Объект стажировки:</b> {trainee.internship_object.name if trainee.internship_object else 'Не указан'}\n"
            f"📍<b>2️⃣Объект работы:</b> {trainee.work_object.name if trainee.work_object else 'Не указан'}\n"
            f"📞 <b>Телефон:</b> {trainee.phone_number}\n"
            f"📅 <b>Дата регистрации:</b> {trainee.registration_date.strftime('%d.%m.%Y')}\n"
            f"🗂️ <b>Группа:</b> {', '.join([group.name for group in trainee.groups]) if trainee.groups else 'Не указана'}\n\n"
            "👨‍🏫 <b>Выберите руководителя:</b>"
        )

        # Создаем клавиатуру с доступными руководителями
        keyboard = get_manager_selection_keyboard(available_managers)

        await callback.message.edit_text(
            trainee_info,
            parse_mode="HTML",
            reply_markup=keyboard
        )

        await state.set_state(MentorshipStates.selecting_manager)
        log_user_action(callback.from_user.id, "assign_manager_started", f"Начато назначение руководителя стажеру {trainee.full_name}")

    except Exception as e:
        await callback.message.edit_text("Произошла ошибка при назначении руководителя")
        log_user_error(callback.from_user.id, "assign_manager_error", str(e))


@router.callback_query(MentorshipStates.selecting_manager, F.data.startswith("select_manager:"))
async def callback_select_manager(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """
    Обработчик выбора руководителя
    """
    try:
        await callback.answer()

        # Получаем ID руководителя
        manager_id = int(callback.data.split(":")[1])

        # Получаем данные из состояния
        data = await state.get_data()
        trainee_id = data.get('selected_trainee_id')

        if not trainee_id:
            await callback.message.edit_text("Ошибка: стажер не выбран")
            return

        # Получаем стажера и руководителя
        trainee = await get_user_by_id(session, trainee_id)
        manager = await get_user_by_id(session, manager_id)

        if not trainee or not manager:
            await callback.message.edit_text("Ошибка: пользователь не найден")
            return

        # Формируем информацию для подтверждения
        confirmation_info = (
            "🤝 <b>Подтверждение назначения руководителя</b>\n\n"
            "👤 <b>Стажер:</b>\n"
            f"   • ФИО: {trainee.full_name}\n"
            f"📍<b>1️⃣Объект стажировки:</b> {trainee.internship_object.name if trainee.internship_object else 'Не указан'}\n"
            f"📍<b>2️⃣Объект работы:</b> {trainee.work_object.name if trainee.work_object else 'Не указан'}\n"
            f"   • Телефон: {trainee.phone_number}\n"
            f"   • Дата регистрации: {trainee.registration_date.strftime('%d.%m.%Y')}\n\n"
            "👨‍🏫 <b>Руководитель:</b>\n"
            f"   • ФИО: {manager.full_name}\n"
            f"📍<b>2️⃣Объект работы:</b> {manager.work_object.name if manager.work_object else 'Не указан'}\n"
            f"   • Телефон: {manager.phone_number}\n\n"
            "❓ <b>Подтвердите назначение руководителя:</b>"
        )

        keyboard = get_manager_assignment_confirmation_keyboard(trainee_id, manager_id)

        await callback.message.edit_text(
            confirmation_info,
            parse_mode="HTML",
            reply_markup=keyboard
        )

        await state.set_state(MentorshipStates.confirming_manager_assignment)
        log_user_action(callback.from_user.id, "manager_selected", f"Выбран руководитель {manager.full_name} для стажера {trainee.full_name}")

    except Exception as e:
        await callback.message.edit_text("Произошла ошибка при выборе руководителя")
        log_user_error(callback.from_user.id, "select_manager_error", str(e))


@router.callback_query(MentorshipStates.confirming_manager_assignment, F.data.startswith("confirm_manager:"))
async def callback_confirm_manager_assignment(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """
    Обработчик подтверждения назначения руководителя
    """
    try:
        await callback.answer()

        # Получаем IDs
        parts = callback.data.split(":")
        trainee_id = int(parts[1])
        manager_id = int(parts[2])

        # Получаем текущего пользователя (наставника)
        mentor = await get_user_by_tg_id(session, callback.from_user.id)
        if not mentor:
            await callback.message.edit_text("Пользователь не найден")
            return

        # Назначаем руководителя
        trainee_manager = await assign_manager_to_trainee(session, trainee_id, manager_id, mentor.id)

        if not trainee_manager:
            await callback.message.edit_text(
                "❌ <b>Ошибка назначения руководителя</b>\n\n"
                "Не удалось назначить руководителя.\n"
                "Возможно, руководитель уже назначен этому стажеру.",
                parse_mode="HTML"
            )
            await state.clear()
            return

        # Получаем информацию о стажере и руководителе
        trainee = await get_user_by_id(session, trainee_id)
        manager = await get_user_by_id(session, manager_id)

        # Формируем сообщение об успехе
        success_message = (
            "✅ <b>Руководитель успешно назначен!</b>\n\n"
            "👤 <b>Стажер:</b> " + trainee.full_name + "\n"
            "👨‍🏫 <b>Руководитель:</b> " + manager.full_name + "\n"
            "📅 <b>Дата назначения:</b> " + trainee_manager.assigned_date.strftime('%d.%m.%Y %H:%M') + "\n"
            "👤 <b>Назначил:</b> " + mentor.full_name + "\n\n"
            "📬 <b>Уведомления отправлены:</b>\n"
            "• ✅ Стажер получил контакты руководителя\n"
            "• 📞 Телефон: " + manager.phone_number + "\n"
            "• 📧 Telegram: @" + (manager.username or "не указан") + "\n\n"
            "🎯 <b>Следующие шаги:</b>\n"
            "• Руководитель может приступать к подготовке аттестации\n"
            "• Рекомендуется связаться для координации процесса"
        )

        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="👥 Мои стажеры", callback_data="my_trainees")
            ],
            [
                InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")
            ]
        ])

        await callback.message.edit_text(
            success_message,
            parse_mode="HTML",
            reply_markup=keyboard
        )

        await state.clear()
        log_user_action(callback.from_user.id, "manager_assigned", f"Назначен руководитель {manager.full_name} стажеру {trainee.full_name}")

    except Exception as e:
        await callback.message.edit_text("Произошла ошибка при подтверждении назначения руководителя")
        log_user_error(callback.from_user.id, "confirm_manager_error", str(e))
        await state.clear()


@router.callback_query(F.data.startswith("view_manager:"))
async def callback_view_manager(callback: CallbackQuery, session: AsyncSession):
    """
    Обработчик просмотра руководителя стажера
    """
    try:
        await callback.answer()

        # Получаем ID стажера
        trainee_id = int(callback.data.split(":")[1])

        # Получаем связь стажер-руководитель
        trainee_manager = await get_trainee_manager(session, trainee_id)

        if not trainee_manager:
            await callback.message.edit_text(
                "❌ <b>Руководитель не назначен</b>\n\n"
                "Для этого стажера еще не назначен руководитель.\n"
                "Назначьте руководителя перед просмотром.",
                parse_mode="HTML"
            )
            return

        # Получаем информацию о руководителе
        manager = await get_user_by_id(session, trainee_manager.manager_id)
        trainee = await get_user_by_id(session, trainee_id)

        if not manager or not trainee:
            await callback.message.edit_text("Ошибка получения данных пользователя")
            return

        # Формируем информацию
        manager_info = (
            "👨‍🏫 <b>РУКОВОДИТЕЛЬ СТАЖЕРА</b>\n\n"
            f"👤 <b>Стажер:</b> {trainee.full_name}\n"
            f"📍<b>1️⃣Объект стажировки:</b> {trainee.internship_object.name if trainee.internship_object else 'Не указан'}\n"
            f"📍<b>2️⃣Объект работы:</b> {trainee.work_object.name if trainee.work_object else 'Не указан'}\n\n"
            "👨‍🏫 <b>Руководитель:</b>\n"
            f"   • ФИО: {manager.full_name}\n"
            f"   • Телефон: {manager.phone_number}\n"
            f"   • Telegram: @{manager.username or 'не указан'}\n"
            f"   • Объект работы: {manager.work_object.name if manager.work_object else 'Не указан'}\n\n"
            f"📅 <b>Дата назначения:</b> {trainee_manager.assigned_date.strftime('%d.%m.%Y %H:%M')}\n"
            f"👤 <b>Назначил:</b> {trainee_manager.assigned_by.full_name}\n\n"
            "🎯 <b>Статус:</b> Активен"
        )

        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="↩️ Назад к стажеру", callback_data=f"trainee:{trainee_id}")
            ]
        ])

        await callback.message.edit_text(
            manager_info,
            parse_mode="HTML",
            reply_markup=keyboard
        )

        log_user_action(callback.from_user.id, "manager_viewed", f"Просмотрен руководитель {manager.full_name} стажера {trainee.full_name}")

    except Exception as e:
        await callback.message.edit_text("Произошла ошибка при просмотре руководителя")
        log_user_error(callback.from_user.id, "view_manager_error", str(e))


@router.callback_query(F.data.startswith("manager_actions:"))
async def callback_manager_actions(callback: CallbackQuery, session: AsyncSession):
    """
    Обработчик действий с руководителем стажера
    """
    try:
        await callback.answer()

        # Получаем ID стажера
        trainee_id = int(callback.data.split(":")[1])

        # Получаем стажера
        trainee = await get_user_by_id(session, trainee_id)
        if not trainee:
            await callback.message.edit_text("Стажер не найден")
            return

        # Получаем руководителя стажера
        trainee_manager = await get_trainee_manager(session, trainee_id)

        if trainee_manager:
            manager = await get_user_by_id(session, trainee_manager.manager_id)
            manager_info = f"👨‍🏫 <b>Руководитель:</b> {manager.full_name}"
            manager_status = "✅ Назначен"
        else:
            manager_info = "👨‍🏫 <b>Руководитель:</b> Не назначен"
            manager_status = "❌ Не назначен"

        # Формируем меню действий с руководителем
        actions_menu = (
            "👨‍🏫 <b>УПРАВЛЕНИЕ РУКОВОДИТЕЛЕМ</b>\n\n"
            f"👤 <b>Стажер:</b> {trainee.full_name}\n"
            f"📍<b>1️⃣Объект стажировки:</b> {trainee.internship_object.name if trainee.internship_object else 'Не указан'}\n"
            f"📍<b>2️⃣Объект работы:</b> {trainee.work_object.name if trainee.work_object else 'Не указан'}\n\n"
            f"{manager_info}\n"
            f"🎯 <b>Статус:</b> {manager_status}\n\n"
            "📋 <b>Выберите действие:</b>"
        )

        keyboard = get_manager_actions_keyboard(trainee_id)

        await callback.message.edit_text(
            actions_menu,
            parse_mode="HTML",
            reply_markup=keyboard
        )

        log_user_action(callback.from_user.id, "manager_actions_opened", f"Открыто меню управления руководителем стажера {trainee.full_name}")

    except Exception as e:
        await callback.message.edit_text("Произошла ошибка при открытии меню управления руководителем")
        log_user_error(callback.from_user.id, "manager_actions_error", str(e))


# ===============================
# Обработчики для Task 7: Назначение аттестации стажеру
# ===============================

@router.callback_query(F.data.startswith("view_trainee_attestation:"))
async def callback_view_trainee_attestation(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Обработчик кнопки 'Аттестация' для стажера (назначение аттестации наставником)"""
    try:
        await callback.answer()
        
        trainee_id = int(callback.data.split(":")[1])
        
        # Получаем данные стажера
        trainee = await get_user_by_id(session, trainee_id)
        if not trainee:
            await callback.message.edit_text("Стажер не найден")
            return
        
        # Получаем наставника (текущего пользователя)
        mentor = await get_user_by_tg_id(session, callback.from_user.id)
        if not mentor:
            await callback.message.edit_text("Вы не зарегистрированы в системе.")
            return
            
        # Проверяем права доступа наставника
        has_permission = await check_user_permission(session, mentor.id, "view_mentorship")
        if not has_permission:
            await callback.message.edit_text("❌ У вас нет прав для управления аттестациями")
            return
            
        # Получаем аттестацию из траектории стажера
        trainee_path = await get_trainee_learning_path(session, trainee.id)
        if not trainee_path or not trainee_path.learning_path.attestation:
            await callback.message.edit_text(
                "❌ У стажера нет назначенной траектории с аттестацией.\n"
                "Сначала назначьте стажеру траектории обучения с аттестацией."
            )
            return
            
        # КРИТИЧЕСКАЯ ПРОВЕРКА: Все этапы траектории должны быть завершены перед аттестацией
        all_stages_completed = await check_all_stages_completed(session, trainee.id)
        if not all_stages_completed:
            await callback.message.edit_text(
                "❌ <b>Аттестация недоступна</b>\n\n"
                "Стажер еще не завершил все этапы траектории обучения.\n\n"
                "📋 <b>Требования для аттестации:</b>\n"
                "• ✅ Все этапы траектории должны быть пройдены\n"
                "• ✅ Все тесты в этапах должны быть сданы\n\n"
                "Откройте стажеру недостающие этапы и дождитесь их завершения.",
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="⬅️ Назад", callback_data=f"select_trainee_for_trajectory:{trainee_id}")]
                ])
            )
            return
            
        attestation = trainee_path.learning_path.attestation
        
        # Получаем список руководителей для аттестации
        group_id = trainee.groups[0].id if trainee.groups else None
        managers = await get_managers_for_attestation(session, group_id)
        
        if not managers:
            await callback.message.edit_text(
                "❌ Нет доступных руководителей для проведения аттестации.\n"
                "Обратитесь к администратору."
            )
            return
        
        # Сохраняем данные в состоянии
        await state.update_data(
            trainee_id=trainee_id,
            attestation_id=attestation.id
        )
        
        # Формируем сообщение согласно ТЗ
        message_text = (
            f"🦸🏻‍♂️ <b>Стажер:</b> {trainee.full_name}\n"
            f"<b>Траектория:</b> {trainee_path.learning_path.name if trainee_path else 'не выбрана'}\n\n\n"
            f"<b>Телефон:</b> {trainee.phone_number}\n"
            f"<b>Username:</b> @{trainee.username or 'не указан'}\n"
            f"<b>Номер:</b> #{trainee_id}\n"
            f"<b>Дата регистрации:</b> {trainee.registration_date.strftime('%d.%m.%Y %H:%M')}\n\n\n"
            "━━━━━━━━━━━━\n\n\n"
            "🗂️ <b>Статус:</b>\n"
            f"<b>Группа:</b> {', '.join([group.name for group in trainee.groups]) if trainee.groups else 'Не указана'}\n"
            f"<b>Роль:</b> {', '.join([role.name for role in trainee.roles])}\n\n\n"
            "━━━━━━━━━━━━\n\n\n"
            "📍 <b>Объект:</b>\n"
            f"<b>Стажировки:</b> {trainee.internship_object.name if trainee.internship_object else 'Не указан'}\n"
            f"<b>Работы:</b> {trainee.work_object.name if trainee.work_object else 'Не указан'}\n\n\n"
            "🗺️<b>Управление траекторией</b>\n"
            "🔍<b>Аттестация</b>\n\n"
            "🟡<b>Выберите руководителя для аттестации👇</b>"
        )
        
        # Создаем клавиатуру с руководителями согласно ТЗ
        keyboard = InlineKeyboardMarkup(inline_keyboard=[])
        
        for manager in managers:
            keyboard.inline_keyboard.append([
                InlineKeyboardButton(
                    text=f"{manager.full_name}",
                    callback_data=f"select_manager_for_attestation:{manager.id}"
                )
            ])
        
        # Кнопка отмены
        keyboard.inline_keyboard.append([
            InlineKeyboardButton(text="⬅️ Назад", callback_data=f"select_trainee_for_trajectory:{trainee_id}")
        ])
        
        await callback.message.edit_text(
            message_text,
            parse_mode="HTML",
            reply_markup=keyboard
        )
        
        await state.set_state(AttestationAssignmentStates.selecting_manager_for_attestation)
        log_user_action(callback.from_user.id, "attestation_assignment_started", f"Начато назначение аттестации для стажера {trainee.full_name}")
    
    except Exception as e:
        await callback.message.edit_text("Произошла ошибка при открытии меню аттестации")
        log_user_error(callback.from_user.id, "view_trainee_attestation_error", str(e))


@router.callback_query(F.data.startswith("select_manager_for_attestation:"), AttestationAssignmentStates.selecting_manager_for_attestation)
async def callback_select_manager_for_attestation(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Обработчик выбора руководителя для аттестации"""
    try:
        await callback.answer()
        
        manager_id = int(callback.data.split(":")[1])
        
        # Получаем данные из состояния
        state_data = await state.get_data()
        trainee_id = state_data.get("trainee_id")
        attestation_id = state_data.get("attestation_id")
        
        if not trainee_id or not attestation_id:
            await callback.message.edit_text("Ошибка: данные не найдены в состоянии")
            return
            
        # Получаем данные
        trainee = await get_user_by_id(session, trainee_id)
        manager = await get_user_by_id(session, manager_id)
        attestation = await get_attestation_by_id(session, attestation_id)
        trainee_path = await get_trainee_learning_path(session, trainee_id)
        
        if not trainee or not manager or not attestation:
            await callback.message.edit_text("Ошибка: данные не найдены")
            return
            
        # Сохраняем выбранного руководителя
        await state.update_data(manager_id=manager_id)
        
        # Формируем сообщение подтверждения согласно ТЗ
        confirmation_text = (
            f"🦸🏻‍♂️ <b>Стажер:</b> {trainee.full_name}\n"
            f"<b>Траектория:</b> {trainee_path.learning_path.name if trainee_path else 'не выбрана'}\n\n\n"
            f"<b>Телефон:</b> {trainee.phone_number}\n"
            f"<b>Username:</b> @{trainee.username or 'не указан'}\n"
            f"<b>Номер:</b> #{trainee_id}\n"
            f"<b>Дата регистрации:</b> {trainee.registration_date.strftime('%d.%m.%Y %H:%M')}\n\n\n"
            "━━━━━━━━━━━━\n\n\n"
            "🗂️ <b>Статус:</b>\n"
            f"<b>Группа:</b> {', '.join([group.name for group in trainee.groups]) if trainee.groups else 'Не указана'}\n"
            f"<b>Роль:</b> {', '.join([role.name for role in trainee.roles])}\n\n\n"
            "━━━━━━━━━━━━\n\n\n"
            "📍 <b>Объект:</b>\n"
            f"<b>Стажировки:</b> {trainee.internship_object.name if trainee.internship_object else 'Не указан'}\n"
            f"<b>Работы:</b> {trainee.work_object.name if trainee.work_object else 'Не указан'}\n\n\n"
            "🗺️<b>Управление траекторией</b>\n"
            "🔍<b>Аттестация</b>\n\n"
            f"🔍⏺️<b>Аттестация:</b> {attestation.name}\n"
            f"🟢<b>Руководитель:</b> {manager.full_name}\n"
            "🟢<b>Дата:</b> \n"
            "🟢<b>Время:</b> \n\n"
            "🟡<b>Назначить аттестацию для стажера?</b>"
        )
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Да", callback_data="confirm_attestation_assignment"),
                InlineKeyboardButton(text="❌ Отменить", callback_data=f"view_trainee_attestation:{trainee_id}")
            ]
        ])
        
        await callback.message.edit_text(
            confirmation_text,
            parse_mode="HTML",
            reply_markup=keyboard
        )
        
        await state.set_state(AttestationAssignmentStates.confirming_attestation_assignment)
        log_user_action(callback.from_user.id, "manager_selected_for_attestation", f"Выбран руководитель {manager.full_name} для аттестации стажера {trainee.full_name}")
    
    except Exception as e:
        await callback.message.edit_text("Произошла ошибка при выборе руководителя")
        log_user_error(callback.from_user.id, "select_manager_for_attestation_error", str(e))


@router.callback_query(F.data == "confirm_attestation_assignment", AttestationAssignmentStates.confirming_attestation_assignment)
async def callback_confirm_attestation_assignment(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Обработчик подтверждения назначения аттестации"""
    try:
        await callback.answer()
        
        # Получаем данные из состояния
        state_data = await state.get_data()
        trainee_id = state_data.get("trainee_id")
        manager_id = state_data.get("manager_id")
        attestation_id = state_data.get("attestation_id")
        
        if not all([trainee_id, manager_id, attestation_id]):
            await callback.message.edit_text("Ошибка: недостаточно данных для назначения")
            return
            
        # Получаем наставника
        mentor = await get_user_by_tg_id(session, callback.from_user.id)
        if not mentor:
            await callback.message.edit_text("Ошибка: наставник не найден")
            return
            
        # Назначаем аттестацию
        assignment = await assign_attestation_to_trainee(
            session, trainee_id, manager_id, attestation_id, mentor.id
        )
        
        if not assignment:
            await callback.message.edit_text("❌ Ошибка при назначении аттестации. Возможно, аттестация уже назначена.")
            return
            
        await session.commit()
        
        # Получаем данные для уведомлений
        trainee = await get_user_by_id(session, trainee_id)
        manager = await get_user_by_id(session, manager_id)
        attestation = await get_attestation_by_id(session, attestation_id)
        
        # Очищаем состояние
        await state.clear()
        
        # Подтверждение наставнику
        await callback.message.edit_text(
            "✅ <b>Аттестация назначена успешно!</b>\n\n"
            f"👤 <b>Стажер:</b> {trainee.full_name}\n"
            f"👨‍💼 <b>Руководитель:</b> {manager.full_name}\n"
            f"🔍 <b>Аттестация:</b> {attestation.name}\n\n"
            "📨 Уведомления отправлены стажеру и руководителю.",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")]
            ])
        )
        
        # Отправляем уведомление стажеру согласно ТЗ
        await send_attestation_assignment_notification_to_trainee(
            session, callback.message.bot, assignment.id
        )
        
        # Отправляем уведомление руководителю согласно ТЗ
        await send_attestation_assignment_notification_to_manager(
            session, callback.message.bot, assignment.id
        )
        
        log_user_action(callback.from_user.id, "attestation_assigned", f"Назначена аттестация {attestation.name} стажеру {trainee.full_name} с руководителем {manager.full_name}")
    
    except Exception as e:
        await callback.message.edit_text("Произошла ошибка при назначении аттестации")
        log_user_error(callback.from_user.id, "confirm_attestation_assignment_error", str(e))


# Функции уведомлений для Task 7
async def send_attestation_assignment_notification_to_trainee(session: AsyncSession, bot, assignment_id: int):
    """Отправка уведомления стажеру о назначении аттестации (ТЗ шаг 14)"""
    try:
        # Получаем данные назначения
        assignment = await get_trainee_attestation_by_id(session, assignment_id)
        if not assignment:
            return
            
        trainee = assignment.trainee
        manager = assignment.manager
        attestation = assignment.attestation
        
        # Формируем уведомление согласно ТЗ
        notification_text = (
            "<b>Вам назначена аттестация:</b>\n\n"
            f"🔍⏺️<b>Аттестация:</b> {attestation.name}\n"
            f"🟢<b>Руководитель:</b> {manager.full_name}\n"
            f"👤 <b>Username:</b> @{manager.username or 'не указан'}\n"
            f"🟢<b>Дата:</b> {assignment.scheduled_date or ''}\n"
            f"🟢<b>Время:</b> {assignment.scheduled_time or ''}\n\n"
            f"📍<b>1️⃣Объект стажировки:</b> {trainee.internship_object.name if trainee.internship_object else 'Не указан'}\n"
            f"📍<b>2️⃣Объект работы:</b> {trainee.work_object.name if trainee.work_object else 'Не указан'}\n\n"
            "❗️<b>Свяжитесь с руководителем, чтобы точно подтвердить все детали аттестации</b>"
        )
        
        await bot.send_message(
            chat_id=trainee.tg_id,
            text=notification_text,
            parse_mode="HTML"
        )
        
        log_user_action(trainee.tg_id, "attestation_assignment_notification_sent", f"Отправлено уведомление о назначении аттестации {attestation.name}")
        
    except Exception as e:
        log_user_error(0, "send_attestation_notification_to_trainee_error", str(e))


async def send_attestation_assignment_notification_to_manager(session: AsyncSession, bot, assignment_id: int):
    """Отправка уведомления руководителю о назначении стажера на аттестацию (ТЗ шаг 15)"""
    try:
        # Получаем данные назначения
        assignment = await get_trainee_attestation_by_id(session, assignment_id)
        if not assignment:
            return
            
        trainee = assignment.trainee
        manager = assignment.manager
        attestation = assignment.attestation
        
        # Формируем уведомление согласно ТЗ
        notification_text = (
            "<b>Вам назначен стажёр на аттестацию:</b>\n\n"
            f"🧑 <b>ФИО:</b> {trainee.full_name}\n"
            f"📞 <b>Телефон:</b> {trainee.phone_number}\n"
            f"👤 <b>Username:</b> @{trainee.username or 'не указан'}\n"
            f"👑 <b>Роли:</b> {', '.join([role.name for role in trainee.roles])}\n"
            f"🗂️<b>Группа:</b> {', '.join([group.name for group in trainee.groups]) if trainee.groups else 'Не указана'}\n"
            f"📍<b>1️⃣Объект стажировки:</b> {trainee.internship_object.name if trainee.internship_object else 'Не указан'}\n"
            f"📍<b>2️⃣Объект работы:</b> {trainee.work_object.name if trainee.work_object else 'Не указан'}\n\n"
            f"🔍⏺️<b>Аттестация:</b> {attestation.name}\n\n"
            "❗️<b>Свяжитесь со стажером, чтобы точно подтвердить все детали аттестации</b>"
        )
        
        await bot.send_message(
            chat_id=manager.tg_id,
            text=notification_text,
            parse_mode="HTML"
        )
        
        log_user_action(manager.tg_id, "attestation_assignment_notification_sent", f"Отправлено уведомление о назначении стажера {trainee.full_name} на аттестацию")
        
    except Exception as e:
        log_user_error(0, "send_attestation_notification_to_manager_error", str(e))


@router.callback_query(F.data.startswith("toggle_stage:"))
async def callback_toggle_stage(callback: CallbackQuery, state: FSMContext, session: AsyncSession, bot):
    """Обработчик переключения статуса этапа (открыть/закрыть)"""
    try:
        await callback.answer()

        parts = callback.data.split(":")
        trainee_id = int(parts[1])
        stage_id = int(parts[2])

        # Получаем текущий статус этапа
        trainee_path = await get_trainee_learning_path(session, trainee_id)
        if not trainee_path:
            await callback.message.edit_text("Траектория не найдена")
            return

        stages_progress = await get_trainee_stage_progress(session, trainee_path.id)
        current_stage_progress = next((sp for sp in stages_progress if sp.stage_id == stage_id), None)
        
        if not current_stage_progress:
            await callback.message.edit_text("Этап не найден")
            return

        # Проверяем, что этап не завершен (завершенные этапы нельзя изменять)
        if current_stage_progress.is_completed:
            await callback.answer("❌ Завершенные этапы нельзя изменять", show_alert=True)
            return

        # Переключаем статус этапа
        if current_stage_progress.is_opened:
            # Закрываем этап
            from database.models import TraineeStageProgress, TraineeSessionProgress
            await session.execute(
                update(TraineeStageProgress).where(
                    TraineeStageProgress.id == current_stage_progress.id
                ).values(is_opened=False)
            )
            
            # Закрываем все сессии этого этапа
            await session.execute(
                update(TraineeSessionProgress).where(
                    TraineeSessionProgress.stage_progress_id == current_stage_progress.id
                ).values(is_opened=False)
            )
            
            await session.commit()
            
            # Уведомление стажеру о закрытии этапа не отправляем
            # (стажеру не нужно знать о закрытии этапов)
            
            action_text = "закрыт"
        else:
            # Открываем этап
            success = await open_stage_for_trainee(session, trainee_id, stage_id, bot)
            if not success:
                await callback.message.edit_text("Ошибка при открытии этапа")
                return
            action_text = "открыт"

        # Обновляем интерфейс управления этапами
        await update_stages_management_interface(callback, session, trainee_id)
        
        log_user_action(callback.from_user.id, "stage_toggled", f"Этап {stage_id} {action_text} для стажера {trainee_id}")

    except Exception as e:
        log_user_error(callback.from_user.id, "toggle_stage_error", str(e))
        await callback.message.edit_text("Произошла ошибка при изменении статуса этапа")


@router.callback_query(F.data.startswith("stage_available_stub:"))
async def callback_stage_available_stub(callback: CallbackQuery):
    """Заглушка для завершенных этапов"""
    await callback.answer("Этап уже завершен и не может быть изменен", show_alert=True)


@router.callback_query(F.data.startswith("stage_completed_stub:"))
async def callback_stage_completed_stub(callback: CallbackQuery):
    """Заглушка для завершенных этапов"""
    await callback.answer("Этап завершен и не может быть изменен", show_alert=True)


async def update_stages_management_interface(callback: CallbackQuery, session: AsyncSession, trainee_id: int):
    """Обновление интерфейса управления этапами (вынесенная логика)"""
    try:
        # Получаем траекторию стажера
        trainee_path = await get_trainee_learning_path(session, trainee_id)
        if not trainee_path:
            await callback.message.edit_text("Траектория не найдена")
            return

        # Получаем этапы
        stages_progress = await get_trainee_stage_progress(session, trainee_path.id)

        # Формируем информацию об этапах
        stages_info = ""
        keyboard_buttons = []

        for stage_progress in stages_progress:
            stage = stage_progress.stage
            status_icon = "🟢" if stage_progress.is_completed else ("🟡" if stage_progress.is_opened else "⏺️")
            
            status_text = "Пройден" if stage_progress.is_completed else ("Открыт" if stage_progress.is_opened else "Закрыт")

            stages_info += f"{status_icon}<b>Этап {stage.order_number}:</b> {stage.name}\n"
            stages_info += f"   📊 Статус: {status_text}\n"

            # Добавляем кнопки для всех этапов с toggle-функциональностью
            if not stage_progress.is_opened:
                # Кнопка для закрытых этапов
                keyboard_buttons.append([
                    InlineKeyboardButton(
                        text=f"🔓 Открыть этап {stage.order_number}",
                        callback_data=f"toggle_stage:{trainee_id}:{stage.id}"
                    )
                ])
            elif stage_progress.is_opened and not stage_progress.is_completed:
                # Кнопка для открытых этапов (можно закрыть)
                keyboard_buttons.append([
                    InlineKeyboardButton(
                        text=f"🔒 Закрыть этап {stage.order_number}",
                        callback_data=f"toggle_stage:{trainee_id}:{stage.id}"
                    )
                ])
            elif stage_progress.is_completed:
                # Завершенные этапы нельзя закрыть
                keyboard_buttons.append([
                    InlineKeyboardButton(
                        text=f"✅ Этап {stage.order_number} завершен",
                        callback_data=f"stage_completed_stub:{trainee_id}:{stage.id}"
                    )
                ])

        trainee = await get_user_by_id(session, trainee_id)
        
        # Получаем результаты тестов для правильной индикации
        test_results = await get_user_test_results(session, trainee_id)
        
        # Формируем полную информацию согласно ТЗ шаг 6
        header_info = (
            f"🦸🏻‍♂️ <b>Стажер:</b> {trainee.full_name}\n"
            f"<b>Траектория:</b> {trainee_path.learning_path.name if trainee_path else 'не выбрана'}\n\n\n"
            f"<b>Телефон:</b> {trainee.phone_number}\n"
            f"<b>Username:</b> @{trainee.username or 'не указан'}\n"
            f"<b>Номер:</b> #{trainee_id}\n"
            f"<b>Дата регистрации:</b> {trainee.registration_date.strftime('%d.%m.%Y %H:%M')}\n\n\n"
            "━━━━━━━━━━━━\n\n\n"
            "🗂️ <b>Статус:</b>\n"
            f"<b>Группа:</b> {', '.join([group.name for group in trainee.groups]) if trainee.groups else 'Не указана'}\n"
            f"<b>Роль:</b> {', '.join([role.name for role in trainee.roles])}\n\n\n"
            "━━━━━━━━━━━━\n\n\n"
            "📍 <b>Объект:</b>\n"
            f"<b>Стажировки:</b> {trainee.internship_object.name if trainee.internship_object else 'Не указан'}\n"
            f"<b>Работы:</b> {trainee.work_object.name if trainee.work_object else 'Не указан'}\n\n\n"
            "🗺️<b>Управление траекторией</b>\n\n"
        )
        
        # Добавляем полную траекторию согласно ТЗ
        trajectory_progress = generate_trajectory_progress_for_mentor(trainee_path, stages_progress, test_results)
        header_info += trajectory_progress + "\n"
        header_info += "🟡 <b>Какой этап необходимо открыть стажеру?</b>"

        # Добавляем кнопку "Назад" к выбору траектории
        keyboard_buttons.append([
            InlineKeyboardButton(text="⬅️ Назад", callback_data=f"select_trainee_for_trajectory:{trainee_id}")
        ])

        keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)

        await callback.message.edit_text(
            header_info,
            reply_markup=keyboard,
            parse_mode="HTML"
        )

    except Exception as e:
        log_user_error(callback.from_user.id, "update_stages_interface_error", str(e))
        await callback.message.edit_text("Ошибка при обновлении интерфейса")

