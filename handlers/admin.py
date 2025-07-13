from aiogram import Router, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from database.db import (
    get_all_users, get_user_by_id, get_all_roles, 
    add_user_role, remove_user_role, get_user_roles, get_all_trainees,
    get_user_by_tg_id, check_user_permission, get_trainee_mentor,
    get_user_test_results
)
from keyboards.keyboards import (
    get_user_selection_keyboard, get_user_action_keyboard, 
    get_role_change_keyboard, get_confirmation_keyboard
)
from states.states import AdminStates
from utils.logger import log_user_action, log_user_error
from handlers.auth import check_auth

router = Router()


async def check_admin_permission(message: Message, state: FSMContext, session: AsyncSession, permission: str = "manage_users") -> bool:
    """Проверяет, имеет ли пользователь указанное право доступа """

    is_auth = await check_auth(message, state, session)
    if not is_auth:
        return False
    
    user = await get_user_by_tg_id(session, message.from_user.id)
    if not user:
        await message.answer("Вы не зарегистрированы в системе.")
        return False
    
    has_permission = await check_user_permission(session, user.id, permission)
    
    if not has_permission:
        await message.answer("У вас нет прав для выполнения этой команды.")
        return False
    
    return True


@router.message(Command("manage_users"))
async def cmd_manage_users(message: Message, state: FSMContext, session: AsyncSession):
    """Обработчик команды управления пользователями"""
    if not await check_admin_permission(message, state, session):
        return
    
    await show_user_list(message, state, session)


@router.message(F.text == "Управление пользователями")
async def button_manage_users(message: Message, state: FSMContext, session: AsyncSession):
    """Обработчик кнопки управления пользователями"""
    await cmd_manage_users(message, state, session)


async def show_user_list(message: Message, state: FSMContext, session: AsyncSession):
    """Отображает список пользователей с возможностью выбора"""
    users = await get_all_users(session)
    
    if not users:
        await message.answer("В системе пока нет зарегистрированных пользователей.")
        return
    

    keyboard = get_user_selection_keyboard(users)
    
    await message.answer(
        "Выберите пользователя для управления:",
        reply_markup=keyboard
    )
    
    await state.set_state(AdminStates.waiting_for_user_selection)
    
    log_user_action(message.from_user.id, message.from_user.username, "opened user management panel")


@router.callback_query(AdminStates.waiting_for_user_selection, F.data.startswith("user:"))
async def process_user_selection(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Обработчик выбора пользователя из списка"""
    user_id = int(callback.data.split(':')[1])
    
    user = await get_user_by_id(session, user_id)
    
    if not user:
        await callback.message.answer("Пользователь не найден.")
        await callback.answer()
        return
    
    user_roles = await get_user_roles(session, user.id)
    roles_str = ", ".join([role.name for role in user_roles])
    
    extra_info = ""
    if "Стажер" in roles_str:
        mentor = await get_trainee_mentor(session, user.id)
        results = await get_user_test_results(session, user.id)
        passed_count = sum(1 for r in results if r.is_passed)
        avg_score = sum(r.score for r in results) / len(results) if results else 0
        
        extra_info = f"""
    <b>Статистика стажера:</b>
    👨‍🏫 Наставник: {mentor.full_name if mentor else 'Не назначен'}
    ✅ Пройдено тестов: {passed_count}/{len(results)}
    📊 Средний балл: {avg_score:.2f}
    """

    user_info = f"""
    👤 <b>Информация о пользователе</b>
    
    🧑 ФИО: {user.full_name}
    📞 Телефон: {user.phone_number}
    🆔 Telegram ID: {user.tg_id}
    👤 Username: @{user.username or "не указан"}
    📅 Дата регистрации: {user.registration_date.strftime('%d.%m.%Y %H:%M')}
    👑 Роли: {roles_str}
    {extra_info}
    """

    keyboard = get_user_action_keyboard(user.id)

    await callback.message.edit_text(
        user_info,
        reply_markup=keyboard,
        parse_mode="HTML"
    )

    await state.set_state(AdminStates.waiting_for_user_action)
    await state.update_data(selected_user_id=user.id)

    await callback.answer()
    
    log_user_action(
        callback.from_user.id, 
        callback.from_user.username, 
        "selected user for management", 
        {"selected_user_id": user.id}
    )

@router.callback_query(AdminStates.waiting_for_user_action, F.data.startswith("change_role:"))
async def process_change_role(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Обработчик кнопки изменения роли пользователя"""
    user_id = int(callback.data.split(':')[1])
    
    user = await get_user_by_id(session, user_id)
    
    if not user:
        await callback.message.answer("Пользователь не найден.")
        await callback.answer()
        return

    roles = await get_all_roles(session)
    
    if not roles:
        await callback.message.answer("В системе не настроены роли.")
        await callback.answer()
        return

    keyboard = get_role_change_keyboard(user.id, roles)
    
    await callback.message.edit_text(
        f"Выберите новую роль для пользователя {user.full_name}:",
        reply_markup=keyboard
    )

    await state.set_state(AdminStates.waiting_for_role_change)

    await callback.answer()
    
    log_user_action(
        callback.from_user.id, 
        callback.from_user.username, 
        "opened role change menu", 
        {"target_user_id": user.id}
    )


@router.callback_query(AdminStates.waiting_for_role_change, F.data.startswith("set_role:"))
async def process_set_role(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Обработчик выбора новой роли для пользователя"""
    # Извлекаем данные из callback
    parts = callback.data.split(':')
    user_id = int(parts[1])
    role_name = parts[2]

    user = await get_user_by_id(session, user_id)
    
    if not user:
        await callback.message.answer("Пользователь не найден.")
        await callback.answer()
        return

    current_roles = await get_user_roles(session, user.id)
    current_role_names = [role.name for role in current_roles]

    action = "remove" if role_name in current_role_names else "add"
    action_text = "удалить" if action == "remove" else "добавить"

    await callback.message.edit_text(
        f"Вы хотите {action_text} роль '{role_name}' для пользователя {user.full_name}?\n\n"
        f"Текущие роли: {', '.join(current_role_names)}",
        reply_markup=get_confirmation_keyboard(user.id, role_name, action)
    )

    await state.set_state(AdminStates.waiting_for_confirmation)
    await state.update_data(
        user_id=user.id, 
        role_name=role_name, 
        action=action,
        current_roles=current_role_names
    )

    await callback.answer()
    
    log_user_action(
        callback.from_user.id, 
        callback.from_user.username, 
        f"requested role change confirmation", 
        {"target_user_id": user.id, "role": role_name, "action": action}
    )


@router.callback_query(AdminStates.waiting_for_confirmation, F.data.startswith("confirm:"))
async def process_confirm_role_change(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Обработчик подтверждения изменения роли"""
    # КРИТИЧЕСКАЯ ПРОВЕРКА ПРАВ!
    current_user = await get_user_by_tg_id(session, callback.from_user.id)
    if not current_user:
        await callback.answer("❌ Пользователь не найден.", show_alert=True)
        return
        
    has_permission = await check_user_permission(session, current_user.id, "manage_users")
    if not has_permission:
        await callback.message.edit_text(
            "❌ <b>Недостаточно прав</b>\n\n"
            "У вас нет прав для изменения ролей пользователей.\n"
            "Обратитесь к администратору.",
            parse_mode="HTML"
        )
        await callback.answer()
        return
    
    parts = callback.data.split(':')
    action = parts[1]
    user_id = int(parts[2])
    role_name = parts[3]
    
    user = await get_user_by_id(session, user_id)
    
    if not user:
        await callback.message.answer("Пользователь не найден.")
        await callback.answer()
        return

    if action == "add":
        success = await add_user_role(session, user.id, role_name)
        action_text = "добавлена"
    else:
        success = await remove_user_role(session, user.id, role_name)
        action_text = "удалена"
    
    if success:
        updated_roles = await get_user_roles(session, user.id)
        roles_str = ", ".join([role.name for role in updated_roles])
        
        await callback.message.answer(
            f"✅ Роль '{role_name}' успешно {action_text} для пользователя {user.full_name}.\n"
            f"Текущие роли: {roles_str}"
        )
        
        log_user_action(
            callback.from_user.id, 
            callback.from_user.username, 
            f"role {action} confirmed", 
            {"target_user_id": user.id, "role": role_name}
        )
    else:
        await callback.message.answer(f"❌ Не удалось изменить роль для пользователя {user.full_name}.")
        log_user_error(
            callback.from_user.id, 
            callback.from_user.username, 
            "role change failed", 
            {"target_user_id": user.id, "role": role_name, "action": action}
        )

    await show_user_list(callback.message, state, session)

    await callback.answer()


@router.callback_query(F.data.startswith("cancel_role_change:"))
async def process_cancel_role_change(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Обработчик отмены изменения роли"""
    user_id = int(callback.data.split(':')[1])
    
    data = await state.get_data()
    role_name = data.get("role_name")
    
    await callback.message.answer(f"Изменение роли '{role_name}' отменено.")

    user = await get_user_by_id(session, user_id)
    if user:
        keyboard = get_user_action_keyboard(user.id)
        
        user_roles = await get_user_roles(session, user.id)
        roles_str = ", ".join([role.name for role in user_roles])
        
        user_info = f"""
        👤 <b>Информация о пользователе</b>
        
        🧑 ФИО: {user.full_name}
        📞 Телефон: {user.phone_number}
        🆔 Telegram ID: {user.tg_id}
        👤 Username: @{user.username or "не указан"}
        📅 Дата регистрации: {user.registration_date.strftime('%d.%m.%Y %H:%M')}
        👑 Роли: {roles_str}
        """

        await callback.message.edit_text(
            user_info,
            reply_markup=keyboard,
            parse_mode="HTML"
        )
        
        await state.set_state(AdminStates.waiting_for_user_action)
    else:
        await show_user_list(callback.message, state, session)
    
    await callback.answer()
    
    log_user_action(
        callback.from_user.id, 
        callback.from_user.username, 
        "cancelled role change", 
        {"target_user_id": user_id, "role": role_name}
    )


@router.callback_query(F.data == "back_to_users")
async def process_back_to_users(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Обработчик кнопки возврата к списку пользователей"""
    await show_user_list(callback.message, state, session)
    await callback.answer()


@router.callback_query(F.data == "cancel")
async def process_cancel(callback: CallbackQuery, state: FSMContext):
    """Обработчик кнопки отмены"""
    await state.clear()
    await callback.message.edit_text("Операция отменена.")
    await callback.answer()
    
    log_user_action(callback.from_user.id, callback.from_user.username, "cancelled admin operation")


@router.callback_query(F.data.startswith("view_profile:"))
async def process_view_profile(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Обработчик просмотра профиля пользователя"""
    user_id = int(callback.data.split(':')[1])

    user = await get_user_by_id(session, user_id)
    
    if not user:
        await callback.message.answer("Пользователь не найден.")
        await callback.answer()
        return

    user_roles = await get_user_roles(session, user.id)
    roles_str = ", ".join([role.name for role in user_roles])

    user_info = f"""
    👤 <b>Профиль пользователя</b>
    
    🧑 ФИО: {user.full_name}
    📞 Телефон: {user.phone_number}
    🆔 Telegram ID: {user.tg_id}
    👤 Username: @{user.username or "не указан"}
    📅 Дата регистрации: {user.registration_date.strftime('%d.%m.%Y %H:%M')}
    👑 Роли: {roles_str}
    """

    keyboard = get_user_action_keyboard(user.id)

    await callback.message.edit_text(
        user_info,
        reply_markup=keyboard,
        parse_mode="HTML"
    )

    await callback.answer()
    
    log_user_action(
        callback.from_user.id, 
        callback.from_user.username, 
        "viewed user profile", 
        {"viewed_user_id": user.id}
    )


@router.message(Command("trainees"))
async def cmd_trainees(message: Message, state: FSMContext, session: AsyncSession):
    """Обработчик команды просмотра списка Стажеров"""
    if not await check_admin_permission(message, state, session, permission="view_trainee_list"):
        return
    
    trainees = await get_all_trainees(session)
    
    if not trainees:
        await message.answer("В системе пока нет зарегистрированных Стажеров.")
        return

    trainees_list = "\n".join([
        f"{i+1}. {trainee.full_name} (@{trainee.username or 'нет юзернейма'})"
        for i, trainee in enumerate(trainees)
    ])
    
    await message.answer(
        f"📋 <b>Список Стажеров</b>\n\n{trainees_list}\n\n"
        "Для управления Стажерами используйте команду /manage_users",
        parse_mode="HTML"
    )
    
    log_user_action(message.from_user.id, message.from_user.username, "viewed trainees list")


@router.message(F.text == "Список Стажеров")
async def button_trainees(message: Message, state: FSMContext, session: AsyncSession):
    """Обработчик кнопки просмотра списка Стажеров"""
    await cmd_trainees(message, state, session) 