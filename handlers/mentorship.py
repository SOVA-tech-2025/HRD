from aiogram import Router, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from database.db import (
    get_unassigned_trainees, get_available_mentors, assign_mentor,
    get_mentor_trainees, get_trainee_mentor, check_user_permission,
    get_user_by_tg_id, get_user_by_id, get_user_test_results,
    get_test_by_id, get_all_active_tests, grant_test_access,
    get_trainee_available_tests
)
from keyboards.keyboards import (
    get_unassigned_trainees_keyboard, get_mentor_selection_keyboard,
    get_assignment_confirmation_keyboard, get_trainee_selection_keyboard,
    get_trainee_actions_keyboard, get_test_access_keyboard,
    get_tests_for_access_keyboard
)
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from states.states import MentorshipStates, TraineeManagementStates
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

@router.message(F.text == "Мой наставник")
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
        f"👨‍🏫 <b>Ваш наставник</b>\n\n"
        f"👤 <b>ФИО:</b> {mentor.full_name}\n"
        f"📞 <b>Телефон:</b> {mentor.phone_number}\n"
        f"📧 <b>Telegram:</b> @{mentor.username or 'не указан'}\n\n"
        "Обращайтесь к наставнику по вопросам прохождения стажировки!",
        parse_mode="HTML"
    )
    
    log_user_action(message.from_user.id, message.from_user.username, "viewed mentor info")

@router.message(F.text == "Мои стажеры")
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
    
    trainees_list = "\n".join([
        f"{i+1}. <b>{trainee.full_name}</b>\n"
        f"   📞 {trainee.phone_number}\n"
        f"   📅 Регистрация: {trainee.registration_date.strftime('%d.%m.%Y')}"
        for i, trainee in enumerate(trainees)
    ])
    
    await message.answer(
        f"👥 <b>Ваши стажеры</b>\n\n{trainees_list}",
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
            "В системе нет пользователей с ролью 'Сотрудник' или 'Управляющий', "
            "которые могли бы стать наставниками.",
            parse_mode="HTML"
        )
        await callback.answer()
        return
    
    await state.update_data(selected_trainee_id=trainee_id)
    
    mentors_list = "\n".join([
        f"👤 <b>{mentor.full_name}</b>\n"
        f"   📞 {mentor.phone_number}\n"
        f"   📧 @{mentor.username or 'не указан'}"
        for mentor in available_mentors[:5]  # Показываем первых 5
    ])
    
    if len(available_mentors) > 5:
        mentors_list += f"\n... и еще {len(available_mentors) - 5} наставников"
    
    await callback.message.edit_text(
        f"👤 <b>Выбран стажер:</b> {trainee.full_name}\n"
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
   • Телефон: {trainee.phone_number}
   • Дата регистрации: {trainee.registration_date.strftime('%d.%m.%Y')}

👨‍🏫 <b>Наставник:</b>
   • ФИО: {mentor.full_name}
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
                [InlineKeyboardButton(text="📋 Главное меню", callback_data="main_menu")]
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
                [InlineKeyboardButton(text="📋 Главное меню", callback_data="main_menu")]
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
            [InlineKeyboardButton(text="📋 Главное меню", callback_data="main_menu")]
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
                [InlineKeyboardButton(text="📋 Главное меню", callback_data="main_menu")]
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
            "Наставниками могут быть пользователи с ролью 'Сотрудник' или 'Управляющий'.",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="📋 Главное меню", callback_data="main_menu")]
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
            [InlineKeyboardButton(text="📋 Главное меню", callback_data="main_menu")]
        ])
    )
    
    await callback.answer()

@router.callback_query(F.data == "main_menu")
async def process_main_menu(callback: CallbackQuery, state: FSMContext):
    """Возврат в главное меню"""
    await callback.message.edit_text(
        "📋 <b>Главное меню</b>\n\n"
        "Используйте команды бота или кнопки клавиатуры для навигации по системе.",
        parse_mode="HTML"
    )
    await state.clear()
    await callback.answer()

@router.message(F.text == "Список Наставников")
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
            "Наставниками могут быть пользователи с ролью 'Сотрудник' или 'Управляющий'.",
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

@router.message(F.text == "Список новых пользователей")
async def cmd_list_new_users(message: Message, state: FSMContext, session: AsyncSession):
    """Обработчик команды просмотра новых пользователей"""
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
            "📋 <b>Список новых пользователей</b>\n\n"
            "✅ Все стажеры уже имеют наставников!\n"
            "Новые пользователи появятся здесь после регистрации.",
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
        f"📋 <b>Список новых пользователей</b>\n\n"
        f"Пользователей без наставника: <b>{len(unassigned_trainees)}</b>\n\n"
        f"{users_list}\n\n"
        f"💡 <b>Рекомендация:</b> Используйте команду 'Назначить наставника' для назначения наставников этим стажерам.",
        parse_mode="HTML"
    )
    
    log_user_action(message.from_user.id, message.from_user.username, "viewed new users list")

# Callback обработчики для уведомлений

@router.callback_query(F.data == "my_trainees")
async def process_my_trainees_callback(callback: CallbackQuery, session: AsyncSession):
    """Обработчик кнопки 'Мои стажёры' из уведомления"""
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
                [InlineKeyboardButton(text="📋 Главное меню", callback_data="main_menu")]
            ])
        )
        await callback.answer()
        return
    
    trainees_list = "\n\n".join([
        f"{i+1}. <b>{trainee.full_name}</b>\n"
        f"   📞 {trainee.phone_number}\n"
        f"   📧 @{trainee.username or 'не указан'}\n"
        f"   📅 Регистрация: {trainee.registration_date.strftime('%d.%m.%Y')}"
        for i, trainee in enumerate(trainees)
    ])
    
    await callback.message.edit_text(
        f"👥 <b>Ваши стажеры</b>\n\n{trainees_list}",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📊 Предоставить доступ к тестам", callback_data="grant_test_access")],
            [InlineKeyboardButton(text="📋 Главное меню", callback_data="main_menu")]
        ])
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
                [InlineKeyboardButton(text="📋 Главное меню", callback_data="main_menu")]
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
                [InlineKeyboardButton(text="📋 Главное меню", callback_data="main_menu")]
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
                [InlineKeyboardButton(text="📋 Главное меню", callback_data="main_menu")]
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
        InlineKeyboardButton(text="📋 Мои доступные тесты", callback_data="available_tests")
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
        results_text += f"{status} <b>{test.name if test else 'Тест удален'}:</b> {res.score}/{res.max_possible_score} баллов\n"

    await callback.message.edit_text(
        results_text,
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ Назад к стажеру", callback_data=f"trainee:{trainee_id}")]
        ])
    )
    await callback.answer()

@router.callback_query(MentorshipStates.waiting_for_trainee_action, F.data.startswith("trainee:"))
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
        last_test_info = f"""
📋 <b>Последний тест:</b>
   • {last_test.name if last_test else 'Тест удален'}
   • {status} ({last_result.score}/{last_result.max_possible_score} баллов)
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
                [InlineKeyboardButton(text="📋 Главное меню", callback_data="main_menu")]
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
                [InlineKeyboardButton(text="📋 Главное меню", callback_data="main_menu")]
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
                [InlineKeyboardButton(text="📋 Главное меню", callback_data="main_menu")]
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
                [InlineKeyboardButton(text="📋 Главное меню", callback_data="main_menu")]
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
            [InlineKeyboardButton(text="📋 Главное меню", callback_data="main_menu")]
        ])
    )
    await callback.answer()