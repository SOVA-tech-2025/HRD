"""
Обработчики для активации новых пользователей рекрутером.
Включает workflow выбора роли, группы, объектов стажировки и работы.
"""

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession

from database.db import (
    get_user_by_tg_id, get_unactivated_users, get_all_roles, 
    get_all_groups, get_all_objects, activate_user,
    get_user_by_id, check_user_permission
)
from utils.logger import logger
from keyboards.keyboards import get_main_menu_keyboard
from states.states import UserActivationStates
from utils.logger import log_user_action, log_user_error
from utils.bot_commands import set_bot_commands
from handlers.auth import check_auth

router = Router()

async def show_role_selection(callback: CallbackQuery, state: FSMContext, session: AsyncSession, user_id: int):
    """Универсальная функция для показа выбора роли"""
    user = await get_user_by_id(session, user_id)
    if not user:
        await callback.message.edit_text("❌ Пользователь не найден")
        return False
    
    # Получаем доступные роли
    available_roles = await get_all_roles(session)
    if not available_roles:
        await callback.message.edit_text("❌ В системе нет доступных ролей для назначения.")
        return False
    
    # Формируем клавиатуру с ролями
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    
    keyboard_buttons = []
    for role in available_roles:
        keyboard_buttons.append([
            InlineKeyboardButton(
                text=role.name,
                callback_data=f"select_role:{role.name}"
            )
        ])
    
    # Добавляем кнопку "Назад"
    keyboard_buttons.append([
        InlineKeyboardButton(
            text="⬅️ Назад",
            callback_data="back_to_user_selection"
        )
    ])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
    registration_date = user.registration_date.strftime('%d.%m.%Y %H:%M') if user.registration_date else "Неизвестно"
    
    await callback.message.edit_text(
        f"✏️Укажи <b>роль</b> нового пользователя\n\n"
        f"<b>Пользователь:</b> {user.full_name}\n"
        f"<b>Телефон:</b> {user.phone_number}\n"
        f"<b>Дата регистрации:</b> {registration_date}",
        reply_markup=keyboard,
        parse_mode="HTML"
    )
    
    await state.set_state(UserActivationStates.waiting_for_role_selection)
    return True

async def show_group_selection(callback: CallbackQuery, state: FSMContext, session: AsyncSession, user_id: int, role_name: str):
    """Универсальная функция для показа выбора группы"""
    user = await get_user_by_id(session, user_id)
    if not user:
        await callback.message.edit_text("❌ Пользователь не найден")
        return False
    
    # Получаем список групп
    groups = await get_all_groups(session)
    
    if not groups:
        await callback.message.edit_text("❌ В системе нет групп. Сначала создайте группы.")
        return False
    
    # Формируем клавиатуру с группами
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    
    keyboard_buttons = []
    for group in groups:
        keyboard_buttons.append([
            InlineKeyboardButton(
                text=group.name,
                callback_data=f"select_group:{group.id}"
            )
        ])
    
    # Добавляем кнопку "Назад"
    keyboard_buttons.append([
        InlineKeyboardButton(
            text="⬅️ Назад",
            callback_data="back_to_role_selection"
        )
    ])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
    registration_date = user.registration_date.strftime('%d.%m.%Y %H:%M') if user.registration_date else "Неизвестно"
    
    await callback.message.edit_text(
        f"✏️Укажи <b>группу</b> нового пользователя\n\n"
        f"<b>Пользователь:</b> {user.full_name}\n"
        f"<b>Телефон:</b> {user.phone_number}\n"
        f"<b>Дата регистрации:</b> {registration_date}",
        reply_markup=keyboard,
        parse_mode="HTML"
    )
    
    await state.set_state(UserActivationStates.waiting_for_group_selection)
    return True


async def show_work_object_selection(callback: CallbackQuery, state: FSMContext, session: AsyncSession, user_id: int, role_name: str):
    """Универсальная функция для показа выбора объекта работы"""
    user = await get_user_by_id(session, user_id)
    if not user:
        await callback.message.edit_text("❌ Пользователь не найден")
        return False
    
    # Получаем список объектов
    objects = await get_all_objects(session)
    
    if not objects:
        await callback.message.edit_text("❌ В системе нет объектов. Сначала создайте объекты.")
        return False
    
    # Формируем клавиатуру с объектами работы
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    
    keyboard_buttons = []
    for obj in objects:
        keyboard_buttons.append([
            InlineKeyboardButton(
                text=obj.name,
                callback_data=f"select_work_object:{obj.id}"
            )
        ])
    
    # Добавляем кнопку "Назад"
    keyboard_buttons.append([
        InlineKeyboardButton(
            text="⬅️ Назад",
            callback_data="back_to_previous_step"
        )
    ])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
    registration_date = user.registration_date.strftime('%d.%m.%Y %H:%M') if user.registration_date else "Неизвестно"
    
    await callback.message.edit_text(
        f"✏️Укажи <b>объект работы</b>, к которому будет привязан новый пользователь\n\n"
        f"<b>Пользователь:</b> {user.full_name}\n"
        f"<b>Телефон:</b> {user.phone_number}\n"
        f"<b>Дата регистрации:</b> {registration_date}",
        reply_markup=keyboard,
        parse_mode="HTML"
    )
    
    await state.set_state(UserActivationStates.waiting_for_work_object_selection)
    return True

@router.message(F.text.in_(["Новые пользователи", "Новые пользователи ➕"]))
async def cmd_new_users_list(message: Message, state: FSMContext, session: AsyncSession):
    """Показать список неактивированных пользователей"""
    # Проверяем авторизацию
    is_auth = await check_auth(message, state, session)
    if not is_auth:
        return

    # Получаем пользователя и проверяем права
    user = await get_user_by_tg_id(session, message.from_user.id)
    if not user:
        await message.answer("Пользователь не найден")
        return

    if not await check_user_permission(session, user.id, "manage_groups"):
        await message.answer("❌ Недостаточно прав\nУ вас нет прав для управления пользователями.")
        return

    # Получаем список неактивированных пользователей
    unactivated_users = await get_unactivated_users(session)
    
    if not unactivated_users:
        await message.answer(
            "📋 <b>Новые пользователи</b>\n\n"
            "✅ Все пользователи активированы!\n"
            "Новых пользователей, ожидающих активации, нет.",
            parse_mode="HTML"
        )
        return

    # Формируем клавиатуру с пользователями
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    
    keyboard_buttons = []
    for user_item in unactivated_users:
        registration_date = user_item.registration_date.strftime('%d.%m.%Y') if user_item.registration_date else "Неизвестно"
        button_text = f"{user_item.full_name} ({registration_date})"
        keyboard_buttons.append([
            InlineKeyboardButton(
                text=button_text,
                callback_data=f"activate_user:{user_item.id}"
            )
        ])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)

    await message.answer(
        "📋 <b>Новые пользователи</b>\n\n"
        "Выберите пользователя для активации:",
        parse_mode="HTML",
        reply_markup=keyboard
    )
    
    await state.set_state(UserActivationStates.waiting_for_user_selection)
    log_user_action(message.from_user.id, message.from_user.username, "viewed new users list")


@router.callback_query(UserActivationStates.waiting_for_user_selection, F.data.startswith("activate_user:"))
async def process_user_selection(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Обработка выбора пользователя для активации"""
    user_id = int(callback.data.split(':')[1])
    
    # Получаем данные пользователя
    user = await get_user_by_id(session, user_id)
    if not user:
        await callback.message.edit_text("❌ Пользователь не найден")
        await callback.answer()
        return

    # Проверяем, не активирован ли уже пользователь
    if user.is_activated:
        await callback.message.edit_text(
            f"❌ <b>Пользователь уже активирован!</b>\n\n"
            f"🙋‍♂️Пользователь: {user.full_name}\n"
            f"📊Статус: Уже активирован\n\n"
            f"Этот пользователь не должен был попасть в список новых пользователей.",
            parse_mode="HTML"
        )
        await callback.answer()
        return

    # Сохраняем ID выбранного пользователя в состоянии
    await state.update_data(selected_user_id=user_id)
    
    # Используем универсальную функцию для показа выбора роли
    success = await show_role_selection(callback, state, session, user_id)
    if success:
        await callback.answer()


@router.callback_query(UserActivationStates.waiting_for_role_selection, F.data == "back_to_user_selection")
async def process_back_to_user_selection(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Обработка кнопки 'Назад' - возврат к выбору пользователя"""
    try:
        # Получаем список неактивированных пользователей
        unactivated_users = await get_unactivated_users(session)
        
        if not unactivated_users:
            await callback.message.edit_text(
                "📋 <b>Новые пользователи</b>\n\n"
                "✅ Все пользователи активированы!\n"
                "Новых пользователей, ожидающих активации, нет.",
                parse_mode="HTML"
            )
            await state.set_state(UserActivationStates.waiting_for_user_selection)
            await callback.answer()
            return

        # Формируем клавиатуру с пользователями
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        
        keyboard_buttons = []
        for user_item in unactivated_users:
            registration_date = user_item.registration_date.strftime('%d.%m.%Y') if user_item.registration_date else "Неизвестно"
            button_text = f"{user_item.full_name} ({registration_date})"
            keyboard_buttons.append([
                InlineKeyboardButton(
                    text=button_text,
                    callback_data=f"activate_user:{user_item.id}"
                )
            ])
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)

        await callback.message.edit_text(
            "📋 <b>Новые пользователи</b>\n\n"
            "Выберите пользователя для активации:",
            parse_mode="HTML",
            reply_markup=keyboard
        )
        
        await state.set_state(UserActivationStates.waiting_for_user_selection)
        await callback.answer()
        
    except Exception as e:
        logger.error(f"Ошибка в process_back_to_user_selection: {e}")
        await callback.answer("❌ Ошибка при возврате к списку пользователей", show_alert=True)


@router.callback_query(UserActivationStates.waiting_for_role_selection, F.data.startswith("select_role:"))
async def process_role_selection(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Обработка выбора роли"""
    role_name = callback.data.split(':')[1]
    
    # Сохраняем роль в состоянии
    await state.update_data(selected_role=role_name)
    
    # Получаем данные пользователя
    state_data = await state.get_data()
    user_id = state_data['selected_user_id']
    user = await get_user_by_id(session, user_id)
    
    # Получаем список групп
    groups = await get_all_groups(session)
    
    if not groups:
        await callback.message.edit_text("❌ В системе нет групп. Сначала создайте группы.")
        await callback.answer()
        return
    
    # Формируем клавиатуру с группами
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    
    keyboard_buttons = []
    for group in groups:
        keyboard_buttons.append([
            InlineKeyboardButton(
                text=group.name,
                callback_data=f"select_group:{group.id}"
            )
        ])
    
    # Добавляем кнопку "Назад"
    keyboard_buttons.append([
        InlineKeyboardButton(
            text="⬅️ Назад",
            callback_data="back_to_role_selection"
        )
    ])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
    
    registration_date = user.registration_date.strftime('%d.%m.%Y %H:%M') if user.registration_date else "Неизвестно"
    
    await callback.message.edit_text(
        f"✏️Укажи <b>группу</b> нового пользователя\n\n"
        f"<b>Пользователь:</b> {user.full_name}\n"
        f"<b>Телефон:</b> {user.phone_number}\n"
        f"<b>Дата регистрации:</b> {registration_date}",
        reply_markup=keyboard,
        parse_mode="HTML"
    )
    
    await state.set_state(UserActivationStates.waiting_for_group_selection)
    await callback.answer()


@router.callback_query(UserActivationStates.waiting_for_group_selection, F.data == "back_to_role_selection")
async def process_back_to_role_selection(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Обработка кнопки 'Назад' - возврат к выбору роли"""
    try:
        # Получаем данные из состояния
        state_data = await state.get_data()
        user_id = state_data['selected_user_id']
        
        # Используем универсальную функцию для показа выбора роли
        success = await show_role_selection(callback, state, session, user_id)
        if success:
            await callback.answer()
        
    except Exception as e:
        logger.error(f"Ошибка в process_back_to_role_selection: {e}")
        await callback.answer("❌ Ошибка при возврате к выбору роли", show_alert=True)


@router.callback_query(UserActivationStates.waiting_for_group_selection, F.data.startswith("select_group:"))
async def process_group_selection(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Обработка выбора группы"""
    group_id = int(callback.data.split(':')[1])
    
    # Сохраняем группу в состоянии
    await state.update_data(selected_group_id=group_id)
    
    # Получаем данные из состояния
    state_data = await state.get_data()
    user_id = state_data['selected_user_id']
    role_name = state_data['selected_role']
    
    user = await get_user_by_id(session, user_id)
    
    # Получаем название группы
    from database.db import get_group_by_id
    group = await get_group_by_id(session, group_id)
    group_name = group.name if group else "Неизвестна"
    
    # Проверяем роль - объект стажировки показывается ТОЛЬКО для стажеров
    if role_name == "Стажер":
        # Получаем список объектов для стажировки
        objects = await get_all_objects(session)
        
        if not objects:
            await callback.message.edit_text("❌ В системе нет объектов. Сначала создайте объекты.")
            await callback.answer()
            return
        
        # Формируем клавиатуру с объектами
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        
        keyboard_buttons = []
        for obj in objects:
            keyboard_buttons.append([
                InlineKeyboardButton(
                    text=obj.name,
                    callback_data=f"select_internship_object:{obj.id}"
                )
            ])
        
        # Добавляем кнопку "Назад"
        keyboard_buttons.append([
            InlineKeyboardButton(
                text="⬅️ Назад",
                callback_data="back_to_group_selection"
            )
        ])
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
        
        registration_date = user.registration_date.strftime('%d.%m.%Y %H:%M') if user.registration_date else "Неизвестно"
        
        await callback.message.edit_text(
            f"✏️Укажи <b>объект стажировки</b>, к которому будет привязан новый пользователь\n\n"
            f"<b>Пользователь:</b> {user.full_name}\n"
            f"<b>Телефон:</b> {user.phone_number}\n"
            f"<b>Дата регистрации:</b> {registration_date}",
            reply_markup=keyboard,
            parse_mode="HTML"
        )
        
        await state.set_state(UserActivationStates.waiting_for_internship_object_selection)
        await callback.answer()
    else:
        # Для всех остальных ролей (не стажеры) переходим сразу к выбору объекта работы
        await state.update_data(selected_internship_object_id=None)
        
        # Используем универсальную функцию для показа выбора объекта работы
        success = await show_work_object_selection(callback, state, session, user_id, role_name)
        if success:
            await callback.answer()


@router.callback_query(UserActivationStates.waiting_for_internship_object_selection, F.data == "back_to_group_selection")
async def process_back_to_group_selection(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Обработка кнопки 'Назад' - возврат к выбору группы"""
    try:
        # Получаем данные из состояния
        state_data = await state.get_data()
        user_id = state_data['selected_user_id']
        role_name = state_data['selected_role']
        
        # Используем универсальную функцию для показа выбора группы
        success = await show_group_selection(callback, state, session, user_id, role_name)
        if success:
            await callback.answer()
        
    except Exception as e:
        logger.error(f"Ошибка в process_back_to_group_selection: {e}")
        await callback.answer("❌ Ошибка при возврате к выбору группы", show_alert=True)


@router.callback_query(UserActivationStates.waiting_for_internship_object_selection, F.data.startswith("select_internship_object:"))
async def process_internship_object_selection(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Обработка выбора объекта стажировки"""
    internship_object_id = int(callback.data.split(':')[1])
    
    # Сохраняем объект стажировки в состоянии
    await state.update_data(selected_internship_object_id=internship_object_id)
    
    # Получаем данные из состояния
    state_data = await state.get_data()
    user_id = state_data['selected_user_id']
    role_name = state_data['selected_role']
    group_id = state_data['selected_group_id']
    
    user = await get_user_by_id(session, user_id)
    
    # Получаем названия группы и объекта стажировки
    from database.db import get_group_by_id, get_object_by_id
    group = await get_group_by_id(session, group_id)
    internship_object = await get_object_by_id(session, internship_object_id)
    
    group_name = group.name if group else "Неизвестна"
    internship_object_name = internship_object.name if internship_object else "Неизвестен"
    
    # Используем универсальную функцию для показа выбора объекта работы
    success = await show_work_object_selection(callback, state, session, user_id, role_name)
    await callback.answer()


@router.callback_query(UserActivationStates.waiting_for_work_object_selection, F.data == "back_to_previous_step")
async def process_back_to_previous_step(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Обработка кнопки 'Назад' - возврат к предыдущему шагу в зависимости от роли"""
    try:
        # Получаем данные из состояния
        state_data = await state.get_data()
        user_id = state_data['selected_user_id']
        role_name = state_data['selected_role']
        
        if role_name == "Стажер":
            # Для стажеров возвращаемся к выбору объекта стажировки
            user = await get_user_by_id(session, user_id)
            if not user:
                await callback.message.edit_text("❌ Пользователь не найден")
                await callback.answer()
                return
            
            # Получаем список объектов для стажировки
            objects = await get_all_objects(session)
            
            if not objects:
                await callback.message.edit_text("❌ В системе нет объектов. Сначала создайте объекты.")
                await callback.answer()
                return
            
            # Формируем клавиатуру с объектами
            from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
            
            keyboard_buttons = []
            for obj in objects:
                keyboard_buttons.append([
                    InlineKeyboardButton(
                        text=obj.name,
                        callback_data=f"select_internship_object:{obj.id}"
                    )
                ])
            
            # Добавляем кнопку "Назад"
            keyboard_buttons.append([
                InlineKeyboardButton(
                    text="⬅️ Назад",
                    callback_data="back_to_group_selection"
                )
            ])
            
            keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
            registration_date = user.registration_date.strftime('%d.%m.%Y %H:%M') if user.registration_date else "Неизвестно"
            
            await callback.message.edit_text(
                f"✏️Укажи <b>объект стажировки</b>, к которому будет привязан новый пользователь\n\n"
                f"<b>Пользователь:</b> {user.full_name}\n"
                f"<b>Телефон:</b> {user.phone_number}\n"
                f"<b>Дата регистрации:</b> {registration_date}",
                reply_markup=keyboard,
                parse_mode="HTML"
            )
            
            await state.set_state(UserActivationStates.waiting_for_internship_object_selection)
            await callback.answer()
        else:
            # Для остальных ролей возвращаемся к выбору группы
            success = await show_group_selection(callback, state, session, user_id, role_name)
            if success:
                await callback.answer()
        
    except Exception as e:
        logger.error(f"Ошибка в process_back_to_previous_step: {e}")
        await callback.answer("❌ Ошибка при возврате к предыдущему шагу", show_alert=True)


@router.callback_query(UserActivationStates.waiting_for_work_object_selection, F.data.startswith("select_work_object:"))
async def process_work_object_selection(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Обработка выбора объекта работы"""
    work_object_id = int(callback.data.split(':')[1])
    
    # Сохраняем объект работы в состоянии
    await state.update_data(selected_work_object_id=work_object_id)
    
    # Получаем все данные из состояния
    state_data = await state.get_data()
    user_id = state_data['selected_user_id']
    role_name = state_data['selected_role']
    group_id = state_data['selected_group_id']
    internship_object_id = state_data['selected_internship_object_id']
    
    user = await get_user_by_id(session, user_id)
    
    # Получаем названия
    from database.db import get_group_by_id, get_object_by_id
    group = await get_group_by_id(session, group_id)
    internship_object = await get_object_by_id(session, internship_object_id)
    work_object = await get_object_by_id(session, work_object_id)
    
    group_name = group.name if group else "Неизвестна"
    internship_object_name = internship_object.name if internship_object else "Неизвестен"
    work_object_name = work_object.name if work_object else "Неизвестен"
    
    # Формируем клавиатуру подтверждения
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Добавить", callback_data="confirm_activation")],
        [InlineKeyboardButton(text="❌ Отменить", callback_data="cancel_activation")]
    ])
    
    registration_date = user.registration_date.strftime('%d.%m.%Y %H:%M') if user.registration_date else "Неизвестно"
    
    # Формируем текст с условным отображением объекта стажировки
    confirmation_text = (
        f"🆕Добавить нового пользователя?🆕\n"
        f"🙋‍♂️Новый пользователь: {user.full_name}\n"
        f"🗓️Дата регистрации: {registration_date}\n"
        f"👑Роль: {role_name}\n"
        f"🗂️Группа: {group_name}\n"
    )
    
    # Добавляем объект стажировки только для стажеров
    if role_name == "Стажер":
        confirmation_text += f"📍1️⃣Объект стажировки {internship_object_name}\n"
        confirmation_text += f"📍2️⃣Объект работы {work_object_name}"
    else:
        confirmation_text += f"📍Объект работы {work_object_name}"
    
    await callback.message.edit_text(
        confirmation_text,
        reply_markup=keyboard
    )
    
    await state.set_state(UserActivationStates.waiting_for_activation_confirmation)
    await callback.answer()


@router.callback_query(UserActivationStates.waiting_for_activation_confirmation, F.data == "confirm_activation")
async def process_activation_confirmation(callback: CallbackQuery, state: FSMContext, session: AsyncSession, bot):
    """Подтверждение активации пользователя"""
    # Получаем все данные из состояния
    state_data = await state.get_data()
    user_id = state_data['selected_user_id']
    role_name = state_data['selected_role']
    group_id = state_data['selected_group_id']
    internship_object_id = state_data['selected_internship_object_id']
    work_object_id = state_data['selected_work_object_id']
    
    user = await get_user_by_id(session, user_id)
    
    # Активируем пользователя
    success = await activate_user(
        session, user_id, role_name, group_id, 
        internship_object_id, work_object_id, bot
    )
    
    if success:
        # Получаем названия для отчета
        from database.db import get_group_by_id, get_object_by_id
        group = await get_group_by_id(session, group_id)
        internship_object = await get_object_by_id(session, internship_object_id)
        work_object = await get_object_by_id(session, work_object_id)
        
        group_name = group.name if group else "Неизвестна"
        internship_object_name = internship_object.name if internship_object else "Неизвестен"
        work_object_name = work_object.name if work_object else "Неизвестен"
        
        registration_date = user.registration_date.strftime('%d.%m.%Y %H:%M') if user.registration_date else "Неизвестно"
        
        # Формируем текст с условным отображением объекта стажировки
        success_text = (
            f"✅Вы открыли доступ к чат-боту новому пользователю:\n"
            f"🙋‍♂️Новый пользователь: {user.full_name}\n"
            f"🗓️Дата регистрации: {registration_date}\n"
            f"👑Роль: {role_name}\n"
            f"🗂️Группа: {group_name}\n"
        )
        
        # Добавляем объект стажировки только для стажеров
        if role_name == "Стажер":
            success_text += f"📍1️⃣Объект стажировки {internship_object_name}\n"
            success_text += f"📍2️⃣Объект работы {work_object_name}"
        else:
            success_text += f"📍Объект работы {work_object_name}"
        
        await callback.message.edit_text(
            success_text,
            reply_markup=get_main_menu_keyboard()
        )
        
        # Обновляем команды бота для активированного пользователя
        try:
            await set_bot_commands(bot)
        except Exception as e:
            log_user_error(callback.from_user.id, callback.from_user.username, "bot commands update error", str(e))
        
        log_user_action(
            callback.from_user.id, 
            callback.from_user.username, 
            "activated user", 
            {
                "activated_user_id": user_id, 
                "role": role_name, 
                "group_id": group_id,
                "internship_object_id": internship_object_id,
                "work_object_id": work_object_id
            }
        )
    else:
        await callback.message.edit_text(
            "❌ Произошла ошибка при активации пользователя. Попробуйте еще раз.",
            reply_markup=get_main_menu_keyboard()
        )
        
        log_user_error(
            callback.from_user.id, 
            callback.from_user.username, 
            "user activation failed", 
            {"user_id": user_id}
        )
    
    await state.clear()
    await callback.answer()


@router.callback_query(UserActivationStates.waiting_for_activation_confirmation, F.data == "cancel_activation")
async def process_activation_cancellation(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Отмена активации пользователя"""
    state_data = await state.get_data()
    user_id = state_data['selected_user_id']
    user = await get_user_by_id(session, user_id)
    
    registration_date = user.registration_date.strftime('%d.%m.%Y %H:%M') if user.registration_date else "Неизвестно"
    
    await callback.message.edit_text(
        f"❌Вы отменили активацию нового пользователя\n"
        f"🙋‍♂️Новый пользователь: {user.full_name}\n"
        f"🗓️Дата регистрации: {registration_date}\n"
        f"Вы можете повторно активировать пользователя, нажав кнопку\n"
        f"«Новые пользователи»",
        reply_markup=get_main_menu_keyboard()
    )
    
    log_user_action(
        callback.from_user.id, 
        callback.from_user.username, 
        "cancelled user activation", 
        {"user_id": user_id}
    )
    
    await state.clear()
    await callback.answer()


@router.callback_query(F.data == "show_new_users")
async def callback_show_new_users(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Обработчик инлайн кнопки 'Новые пользователи' из уведомления"""
    # Проверяем авторизацию напрямую (адаптированная проверка для callback)
    user = await get_user_by_tg_id(session, callback.from_user.id)
    if not user:
        await callback.answer("Ты не зарегистрирован в системе. Используй команду /register для регистрации.", show_alert=True)
        return

    if not user.is_active:
        await callback.answer("Твой аккаунт деактивирован. Обратись к администратору.", show_alert=True)
        return

    if not await check_user_permission(session, user.id, "manage_groups"):
        await callback.answer("❌ Недостаточно прав\nУ вас нет прав для управления пользователями.", show_alert=True)
        return

    # Получаем список неактивированных пользователей
    unactivated_users = await get_unactivated_users(session)
    
    if not unactivated_users:
        await callback.message.answer(
            "📋 <b>Новые пользователи</b>\n\n"
            "✅ Все пользователи активированы!\n"
            "Новых пользователей, ожидающих активации, нет.",
            parse_mode="HTML"
        )
        await callback.answer()
        return

    # Формируем клавиатуру с пользователями (точно как в клавиатурном варианте)
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    
    keyboard_buttons = []
    for user_item in unactivated_users:
        registration_date = user_item.registration_date.strftime('%d.%m.%Y') if user_item.registration_date else "Неизвестно"
        button_text = f"{user_item.full_name} ({registration_date})"
        keyboard_buttons.append([
            InlineKeyboardButton(
                text=button_text,
                callback_data=f"activate_user:{user_item.id}"
            )
        ])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)

    await callback.message.answer(
        "📋 <b>Новые пользователи</b>\n\n"
        "Выберите пользователя для активации:",
        parse_mode="HTML",
        reply_markup=keyboard
    )
    
    await state.set_state(UserActivationStates.waiting_for_user_selection)
    log_user_action(callback.from_user.id, callback.from_user.username, "viewed new users list via notification")
    await callback.answer()

