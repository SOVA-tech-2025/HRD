from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.filters import StateFilter
from sqlalchemy.ext.asyncio import AsyncSession

from database.db import (
    check_user_permission, get_all_activated_users, get_users_by_group, get_users_by_object,
    get_user_with_details, get_user_by_id, get_user_by_tg_id, get_user_by_phone,
    update_user_full_name, update_user_phone_number, update_user_role,
    update_user_group, update_user_internship_object, update_user_work_object,
    get_all_groups, get_all_objects, get_object_by_id, get_group_by_id, get_user_roles,
    get_role_change_warnings
)
from handlers.auth import check_auth
from states.states import UserEditStates
from keyboards.keyboards import (
    get_user_editor_keyboard, get_edit_confirmation_keyboard,
    get_role_selection_keyboard, get_group_selection_keyboard,
    get_object_selection_keyboard, get_users_filter_keyboard,
    get_group_filter_keyboard, get_object_filter_keyboard,
    get_users_list_keyboard, get_user_info_keyboard
)
from utils.logger import log_user_action, log_user_error
from utils.validators import validate_full_name, validate_phone_number

router = Router()


@router.message(F.text == "Все пользователи")
async def cmd_all_users(message: Message, session: AsyncSession, state: FSMContext):
    """Отображение фильтров для выбора пользователей"""
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
        await message.answer("❌ У вас нет прав для управления пользователями")
        log_user_error(message.from_user.id, "all_users_access_denied", "Insufficient permissions")
        return
        
    # Получаем группы и объекты для фильтров
    groups = await get_all_groups(session)
    objects = await get_all_objects(session)
    
    # Проверяем, есть ли пользователи вообще
    users = await get_all_activated_users(session)
    if not users:
        await message.answer("📭 Нет активированных пользователей в системе")
        return
        
    text = (
        "👥 <b>УПРАВЛЕНИЕ ПОЛЬЗОВАТЕЛЯМИ</b> 👥\n\n"
        f"📊 Всего пользователей в системе: <b>{len(users)}</b>\n"
        f"🗂️ Доступно групп: <b>{len(groups)}</b>\n"
        f"📍 Доступно объектов: <b>{len(objects)}</b>\n\n"
        "Выберите способ фильтрации пользователей:"
    )
    
    keyboard = get_users_filter_keyboard(groups, objects)
    
    await message.answer(text, reply_markup=keyboard, parse_mode="HTML")
    await state.set_state(UserEditStates.waiting_for_filter_selection)
    
    log_user_action(message.from_user.id, "opened_user_filters", f"Available: {len(users)} users, {len(groups)} groups, {len(objects)} objects")


# ===================== НОВЫЕ ОБРАБОТЧИКИ ФИЛЬТРАЦИИ =====================

@router.callback_query(F.data == "filter_all_users", UserEditStates.waiting_for_filter_selection)
async def callback_filter_all_users(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Показать всех пользователей без фильтрации"""
    try:
        await callback.answer()
        
        users = await get_all_activated_users(session)
        
        if not users:
            await callback.message.edit_text("📭 Нет активированных пользователей в системе")
            return
        
        text = (
            f"👥 <b>ВСЕ ПОЛЬЗОВАТЕЛИ</b> 👥\n\n"
            f"📊 Найдено пользователей: <b>{len(users)}</b>\n\n"
            "Выберите пользователя для просмотра и редактирования:"
        )
        
        keyboard = get_users_list_keyboard(users, 0, 5, "all")
        
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
        await state.set_state(UserEditStates.waiting_for_user_selection)
        await state.update_data(current_users=users, filter_type="all", current_page=0)
        
        log_user_action(callback.from_user.id, "filter_all_users", f"Showing {len(users)} users")
        
    except Exception as e:
        await callback.answer("Произошла ошибка")
        log_user_error(callback.from_user.id, "filter_all_users_error", str(e))


@router.callback_query(F.data == "filter_by_groups", UserEditStates.waiting_for_filter_selection)
async def callback_filter_by_groups(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Показать фильтр по группам"""
    try:
        await callback.answer()
        
        groups = await get_all_groups(session)
        
        if not groups:
            await callback.message.edit_text("📭 Нет доступных групп для фильтрации")
            return
        
        text = (
            f"🗂️ <b>ФИЛЬТР ПО ГРУППАМ</b> 🗂️\n\n"
            f"📊 Доступно групп: <b>{len(groups)}</b>\n\n"
            "Выберите группу для просмотра её участников:"
        )
        
        keyboard = get_group_filter_keyboard(groups, 0, 5)
        
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
        await state.update_data(available_groups=groups, filter_page=0)
        
        log_user_action(callback.from_user.id, "opened_group_filter", f"Available {len(groups)} groups")
        
    except Exception as e:
        await callback.answer("Произошла ошибка")
        log_user_error(callback.from_user.id, "filter_by_groups_error", str(e))


@router.callback_query(F.data == "filter_by_objects", UserEditStates.waiting_for_filter_selection)
async def callback_filter_by_objects(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Показать фильтр по объектам"""
    try:
        await callback.answer()
        
        objects = await get_all_objects(session)
        
        if not objects:
            await callback.message.edit_text("📭 Нет доступных объектов для фильтрации")
            return
        
        text = (
            f"📍 <b>ФИЛЬТР ПО ОБЪЕКТАМ</b> 📍\n\n"
            f"📊 Доступно объектов: <b>{len(objects)}</b>\n\n"
            "Выберите объект для просмотра связанных с ним пользователей:"
        )
        
        keyboard = get_object_filter_keyboard(objects, 0, 5)
        
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
        await state.update_data(available_objects=objects, filter_page=0)
        
        log_user_action(callback.from_user.id, "opened_object_filter", f"Available {len(objects)} objects")
        
    except Exception as e:
        await callback.answer("Произошла ошибка")
        log_user_error(callback.from_user.id, "filter_by_objects_error", str(e))


@router.callback_query(F.data.startswith("filter_group:"), UserEditStates.waiting_for_filter_selection)
async def callback_filter_group(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Показать пользователей выбранной группы"""
    try:
        await callback.answer()
        
        group_id = int(callback.data.split(":")[1])
        group = await get_group_by_id(session, group_id)
        
        if not group:
            await callback.answer("Группа не найдена", show_alert=True)
            return
        
        users = await get_users_by_group(session, group_id)
        
        text = (
            f"🗂️ <b>ГРУППА: {group.name}</b> 🗂️\n\n"
            f"📊 Пользователей в группе: <b>{len(users)}</b>\n\n"
        )
        
        if users:
            text += "Выберите пользователя для просмотра и редактирования:"
            keyboard = get_users_list_keyboard(users, 0, 5, f"group:{group_id}")
            await state.set_state(UserEditStates.waiting_for_user_selection)
            await state.update_data(current_users=users, filter_type=f"group:{group_id}", current_page=0)
        else:
            text += "В данной группе пока нет пользователей."
            keyboard = get_users_filter_keyboard(await get_all_groups(session), await get_all_objects(session))
            await state.set_state(UserEditStates.waiting_for_filter_selection)
        
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
        
        log_user_action(callback.from_user.id, "filter_by_group", f"Group: {group.name}, Users: {len(users)}")
        
    except Exception as e:
        await callback.answer("Произошла ошибка")
        log_user_error(callback.from_user.id, "filter_group_error", str(e))


@router.callback_query(F.data.startswith("filter_object:"), UserEditStates.waiting_for_filter_selection)
async def callback_filter_object(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Показать пользователей выбранного объекта"""
    try:
        await callback.answer()
        
        object_id = int(callback.data.split(":")[1])
        obj = await get_object_by_id(session, object_id)
        
        if not obj:
            await callback.answer("Объект не найден", show_alert=True)
            return
        
        users = await get_users_by_object(session, object_id)
        
        text = (
            f"📍 <b>ОБЪЕКТ: {obj.name}</b> 📍\n\n"
            f"📊 Пользователей на объекте: <b>{len(users)}</b>\n\n"
        )
        
        if users:
            text += "Выберите пользователя для просмотра и редактирования:"
            keyboard = get_users_list_keyboard(users, 0, 5, f"object:{object_id}")
            await state.set_state(UserEditStates.waiting_for_user_selection)
            await state.update_data(current_users=users, filter_type=f"object:{object_id}", current_page=0)
        else:
            text += "К данному объекту пока не привязаны пользователи."
            keyboard = get_users_filter_keyboard(await get_all_groups(session), await get_all_objects(session))
            await state.set_state(UserEditStates.waiting_for_filter_selection)
        
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
        
        log_user_action(callback.from_user.id, "filter_by_object", f"Object: {obj.name}, Users: {len(users)}")
        
    except Exception as e:
        await callback.answer("Произошла ошибка")
        log_user_error(callback.from_user.id, "filter_object_error", str(e))


@router.callback_query(F.data.startswith("view_user:"), UserEditStates.waiting_for_user_selection)
async def callback_view_user(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Просмотр информации о пользователе"""
    try:
        await callback.answer()
        
        user_id = int(callback.data.split(":")[1])
        user = await get_user_with_details(session, user_id)
        
        if not user:
            await callback.answer("Пользователь не найден", show_alert=True)
            return
        
        # Формируем подробную информацию о пользователе
        role_name = user.roles[0].name if user.roles else "Нет роли"
        group_name = user.groups[0].name if user.groups else "Нет группы"
        
        text = (
            f"👤 <b>ИНФОРМАЦИЯ О ПОЛЬЗОВАТЕЛЕ</b> 👤\n\n"
            f"🧑 <b>ФИО:</b> {user.full_name}\n"
            f"📞 <b>Телефон:</b> {user.phone_number}\n"
            f"🆔 <b>Telegram ID:</b> {user.tg_id}\n"
            f"👤 <b>Username:</b> @{user.username if user.username else 'Не указан'}\n"
            f"📅 <b>Дата регистрации:</b> {user.registration_date.strftime('%d.%m.%Y %H:%M') if user.registration_date else 'Не указана'}\n"
            f"👑 <b>Роль:</b> {role_name}\n"
            f"🗂️ <b>Группа:</b> {group_name}\n"
        )
        
        # Добавляем объект стажировки только для стажеров
        if role_name == "Стажер" and user.internship_object:
            text += f"📍 <b>Объект стажировки:</b> {user.internship_object.name}\n"
            
        # Объект работы
        if user.work_object:
            text += f"📍 <b>Объект работы:</b> {user.work_object.name}\n"
        
        # Статус активации
        text += f"✅ <b>Активирован:</b> {'Да' if user.is_activated else 'Нет'}\n"
        
        data = await state.get_data()
        filter_type = data.get('filter_type', 'all')
        
        keyboard = get_user_info_keyboard(user_id, filter_type)
        
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
        await state.set_state(UserEditStates.viewing_user_info)
        await state.update_data(viewing_user_id=user_id)
        
        log_user_action(callback.from_user.id, "view_user_info", f"User: {user.full_name} (ID: {user_id})")
        
    except Exception as e:
        await callback.answer("Произошла ошибка")
        log_user_error(callback.from_user.id, "view_user_error", str(e))


@router.callback_query(F.data.startswith("edit_user:"), UserEditStates.viewing_user_info)
async def callback_edit_user(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Переход к редактированию пользователя"""
    try:
        await callback.answer()
        
        user_id = int(callback.data.split(":")[1])
        user = await get_user_with_details(session, user_id)
        
        if not user:
            await callback.answer("Пользователь не найден", show_alert=True)
            return
        
        # Формируем меню редактора
        role_name = user.roles[0].name if user.roles else "Нет роли"
        is_trainee = role_name == "Стажер"
        
        text = (
            f"✏️ <b>РЕДАКТОР ПОЛЬЗОВАТЕЛЯ</b> ✏️\n\n"
            f"🧑 <b>ФИО:</b> {user.full_name}\n"
            f"📞 <b>Телефон:</b> {user.phone_number}\n"
            f"👑 <b>Роль:</b> {role_name}\n"
            f"🗂️ <b>Группа:</b> {user.groups[0].name if user.groups else 'Нет группы'}\n\n"
            "Выберите параметр для изменения:"
        )
        
        keyboard = get_user_editor_keyboard(is_trainee)
        
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
        await state.update_data(editing_user_id=user_id)
        
        log_user_action(callback.from_user.id, "start_edit_user", f"User: {user.full_name} (ID: {user_id})")
        
    except Exception as e:
        await callback.answer("Произошла ошибка")
        log_user_error(callback.from_user.id, "edit_user_error", str(e))


@router.callback_query(F.data == "back_to_filters")
async def callback_back_to_filters(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Возврат к фильтрам пользователей"""
    try:
        await callback.answer()
        
        # Получаем группы и объекты для фильтров
        groups = await get_all_groups(session)
        objects = await get_all_objects(session)
        users = await get_all_activated_users(session)
        
        text = (
            "👥 <b>УПРАВЛЕНИЕ ПОЛЬЗОВАТЕЛЯМИ</b> 👥\n\n"
            f"📊 Всего пользователей в системе: <b>{len(users)}</b>\n"
            f"🗂️ Доступно групп: <b>{len(groups)}</b>\n"
            f"📍 Доступно объектов: <b>{len(objects)}</b>\n\n"
            "Выберите способ фильтрации пользователей:"
        )
        
        keyboard = get_users_filter_keyboard(groups, objects)
        
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
        await state.set_state(UserEditStates.waiting_for_filter_selection)
        
        log_user_action(callback.from_user.id, "back_to_filters", "Returned to user filters")
        
    except Exception as e:
        await callback.answer("Произошла ошибка")
        log_user_error(callback.from_user.id, "back_to_filters_error", str(e))


@router.callback_query(F.data.startswith("back_to_users:"))
async def callback_back_to_users(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Возврат к списку пользователей"""
    try:
        await callback.answer()
        
        filter_type = callback.data.split(":", 1)[1]
        data = await state.get_data()
        users = data.get('current_users', [])
        current_page = data.get('current_page', 0)
        
        if filter_type == "all":
            text = f"👥 <b>ВСЕ ПОЛЬЗОВАТЕЛИ</b> 👥\n\n📊 Найдено пользователей: <b>{len(users)}</b>\n\nВыберите пользователя для просмотра и редактирования:"
        elif filter_type.startswith("group:"):
            group_id = int(filter_type.split(":")[1])
            group = await get_group_by_id(session, group_id)
            text = f"🗂️ <b>ГРУППА: {group.name if group else 'Неизвестная'}</b> 🗂️\n\n📊 Пользователей в группе: <b>{len(users)}</b>\n\nВыберите пользователя для просмотра и редактирования:"
        elif filter_type.startswith("object:"):
            object_id = int(filter_type.split(":")[1])
            obj = await get_object_by_id(session, object_id)
            text = f"📍 <b>ОБЪЕКТ: {obj.name if obj else 'Неизвестный'}</b> 📍\n\n📊 Пользователей на объекте: <b>{len(users)}</b>\n\nВыберите пользователя для просмотра и редактирования:"
        else:
            text = f"👥 <b>СПИСОК ПОЛЬЗОВАТЕЛЕЙ</b> 👥\n\n📊 Найдено пользователей: <b>{len(users)}</b>\n\nВыберите пользователя для просмотра и редактирования:"
        
        keyboard = get_users_list_keyboard(users, current_page, 5, filter_type)
        
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
        await state.set_state(UserEditStates.waiting_for_user_selection)
        
        log_user_action(callback.from_user.id, "back_to_users", f"Filter: {filter_type}")
        
    except Exception as e:
        await callback.answer("Произошла ошибка")
        log_user_error(callback.from_user.id, "back_to_users_error", str(e))


# ===================== ОБРАБОТЧИКИ ПАГИНАЦИИ =====================

@router.callback_query(F.data.startswith("users_page:"))
async def callback_users_pagination(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Обработка пагинации списка пользователей"""
    try:
        await callback.answer()
        
        # Парсим данные: users_page:{filter_type}:{page}
        # filter_type может содержать двоеточие (например, "group:1")
        parts = callback.data.split(":")
        if len(parts) == 3:
            # Простой случай: users_page:all:0
            filter_type = parts[1]
            page = int(parts[2])
        else:
            # Сложный случай: users_page:group:1:0 или users_page:object:2:1
            filter_type = ":".join(parts[1:-1])  # Все части кроме первой и последней
            page = int(parts[-1])  # Последняя часть - номер страницы
        
        data = await state.get_data()
        users = data.get('current_users', [])
        
        if filter_type == "all":
            text = f"👥 <b>ВСЕ ПОЛЬЗОВАТЕЛИ</b> 👥\n\n📊 Найдено пользователей: <b>{len(users)}</b>\n\nВыберите пользователя для просмотра и редактирования:"
        elif filter_type.startswith("group"):
            group_id = int(filter_type.split(":")[1]) if ":" in filter_type else 0
            group = await get_group_by_id(session, group_id) if group_id else None
            text = f"🗂️ <b>ГРУППА: {group.name if group else 'Неизвестная'}</b> 🗂️\n\n📊 Пользователей в группе: <b>{len(users)}</b>\n\nВыберите пользователя для просмотра и редактирования:"
        elif filter_type.startswith("object"):
            object_id = int(filter_type.split(":")[1]) if ":" in filter_type else 0
            obj = await get_object_by_id(session, object_id) if object_id else None
            text = f"📍 <b>ОБЪЕКТ: {obj.name if obj else 'Неизвестный'}</b> 📍\n\n📊 Пользователей на объекте: <b>{len(users)}</b>\n\nВыберите пользователя для просмотра и редактирования:"
        else:
            text = f"👥 <b>СПИСОК ПОЛЬЗОВАТЕЛЕЙ</b> 👥\n\n📊 Найдено пользователей: <b>{len(users)}</b>\n\nВыберите пользователя для просмотра и редактирования:"
        
        keyboard = get_users_list_keyboard(users, page, 5, filter_type)
        
        await callback.message.edit_reply_markup(reply_markup=keyboard)
        await state.update_data(current_page=page)
        
        log_user_action(callback.from_user.id, "users_pagination", f"Page: {page}, Filter: {filter_type}")
        
    except Exception as e:
        await callback.answer("Произошла ошибка")
        log_user_error(callback.from_user.id, "users_pagination_error", str(e))


@router.callback_query(F.data.startswith("group_filter_page:"))
async def callback_group_filter_pagination(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Обработка пагинации списка групп для фильтрации"""
    try:
        await callback.answer()
        
        page = int(callback.data.split(":")[1])
        data = await state.get_data()
        groups = data.get('available_groups', [])
        
        if not groups:
            groups = await get_all_groups(session)
        
        keyboard = get_group_filter_keyboard(groups, page, 5)
        
        await callback.message.edit_reply_markup(reply_markup=keyboard)
        await state.update_data(filter_page=page)
        
        log_user_action(callback.from_user.id, "group_filter_pagination", f"Page: {page}")
        
    except Exception as e:
        await callback.answer("Произошла ошибка")
        log_user_error(callback.from_user.id, "group_filter_pagination_error", str(e))


@router.callback_query(F.data.startswith("object_filter_page:"))
async def callback_object_filter_pagination(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Обработка пагинации списка объектов для фильтрации"""
    try:
        await callback.answer()
        
        page = int(callback.data.split(":")[1])
        data = await state.get_data()
        objects = data.get('available_objects', [])
        
        if not objects:
            objects = await get_all_objects(session)
        
        keyboard = get_object_filter_keyboard(objects, page, 5)
        
        await callback.message.edit_reply_markup(reply_markup=keyboard)
        await state.update_data(filter_page=page)
        
        log_user_action(callback.from_user.id, "object_filter_pagination", f"Page: {page}")
        
    except Exception as e:
        await callback.answer("Произошла ошибка")
        log_user_error(callback.from_user.id, "object_filter_pagination_error", str(e))


# ===================== СТАРЫЙ ОБРАБОТЧИК ДЛЯ СОВМЕСТИМОСТИ =====================

@router.message(UserEditStates.waiting_for_user_number)
async def process_user_number(message: Message, session: AsyncSession, state: FSMContext):
    """Обработка выбора номера пользователя для редактирования"""
    try:
        user_id = int(message.text.strip())
    except ValueError:
        await message.answer("❌ Пожалуйста, введите корректный номер пользователя")
        return
        
    # Получаем пользователя для редактирования
    target_user = await get_user_with_details(session, user_id)
    
    if not target_user or not target_user.is_activated:
        await message.answer("❌ Пользователь не найден или не активирован")
        return
        
    # Сохраняем ID пользователя для редактирования
    await state.update_data(editing_user_id=user_id)
    
    # Показываем редактор
    await show_user_editor(message, session, target_user, state)
    

async def show_user_editor(message: Message, session: AsyncSession, 
                          target_user, state: FSMContext):
    """Отображение редактора пользователя"""
    # Формируем информацию о пользователе
    role_name = target_user.roles[0].name if target_user.roles else "Нет роли"
    group_name = target_user.groups[0].name if target_user.groups else "Нет группы"
    
    user_info = f"""✏️<b>РЕДАКТОР ПОЛЬЗОВАТЕЛЯ</b>✏️

🧑 ФИО: {target_user.full_name}
📞 Телефон: {target_user.phone_number}
🆔 Telegram ID: {target_user.tg_id}
👤 Username: @{target_user.username if target_user.username else 'Не указан'}
📅 Дата регистрации: {target_user.registration_date.strftime('%d.%m.%Y %H:%M') if target_user.registration_date else 'Не указана'}
👑 Роли: {role_name}
🗂️Группа: {group_name}"""
    
    # Добавляем объект стажировки только для стажеров
    if role_name == "Стажер" and target_user.internship_object:
        user_info += f"\n📍1️⃣Объект стажировки: {target_user.internship_object.name}"
        
    # Объект работы
    if target_user.work_object:
        user_info += f"\n📍2️⃣Объект работы: {target_user.work_object.name}"
        
    user_info += f"\n🎱Номер пользователя: {target_user.id}"
    
    user_info += "\n\nКакую информацию вы хотите изменить?\nВыберите кнопкой ниже👇"
    
    # Получаем клавиатуру редактора
    keyboard = get_user_editor_keyboard(role_name == "Стажер")
    
    await message.answer(user_info, reply_markup=keyboard, parse_mode="HTML")
    await state.set_state(None)  # Сбрасываем состояние, ждем выбора действия


@router.callback_query(F.data == "edit_full_name")
async def process_edit_full_name(callback: CallbackQuery, session: AsyncSession, state: FSMContext):
    """Начало редактирования ФИО"""
    data = await state.get_data()
    editing_user_id = data.get('editing_user_id')
    
    if not editing_user_id:
        await callback.answer("❌ Ошибка: не выбран пользователь")
        return
        
    target_user = await get_user_with_details(session, editing_user_id)
    if not target_user:
        await callback.answer("❌ Пользователь не найден")
        return
        
    message_text = f"""Введите новое ФИО для пользователя:

🧑 ФИО: {target_user.full_name}
📞 Телефон: {target_user.phone_number}
🆔 Telegram ID: {target_user.tg_id}
👤 Username: @{target_user.username if target_user.username else 'Не указан'}"""
    
    await callback.message.edit_text(message_text)
    await state.set_state(UserEditStates.waiting_for_new_full_name)
    await state.update_data(edit_type="full_name")
    await callback.answer()


@router.message(UserEditStates.waiting_for_new_full_name)
async def process_new_full_name(message: Message, session: AsyncSession, state: FSMContext):
    """Обработка нового ФИО"""
    new_full_name = message.text.strip()
    
    # Валидация
    is_valid, error_message = validate_full_name(new_full_name)
    if not is_valid:
        await message.answer(f"❌ {error_message}")
        return
        
    data = await state.get_data()
    editing_user_id = data.get('editing_user_id')
    
    target_user = await get_user_with_details(session, editing_user_id)
    if not target_user:
        await message.answer("❌ Пользователь не найден")
        await state.clear()
        return
        
    # Сохраняем новое значение и показываем подтверждение
    await state.update_data(new_value=new_full_name, old_value=target_user.full_name)
    
    confirmation_text = f"""⚠️НОВОЕ ФИО:
⚠️{new_full_name}

Для пользователя:
🧑 ФИО: {target_user.full_name}
📞 Телефон: {target_user.phone_number}
🆔 Telegram ID: {target_user.tg_id}
👤 Username: @{target_user.username if target_user.username else 'Не указан'}"""
    
    keyboard = get_edit_confirmation_keyboard()
    await message.answer(confirmation_text, reply_markup=keyboard)
    await state.set_state(UserEditStates.waiting_for_change_confirmation)


@router.callback_query(F.data == "edit_phone")
async def process_edit_phone(callback: CallbackQuery, session: AsyncSession, state: FSMContext):
    """Начало редактирования телефона"""
    data = await state.get_data()
    editing_user_id = data.get('editing_user_id')
    
    if not editing_user_id:
        await callback.answer("❌ Ошибка: не выбран пользователь")
        return
        
    target_user = await get_user_with_details(session, editing_user_id)
    if not target_user:
        await callback.answer("❌ Пользователь не найден")
        return
        
    message_text = f"""Введите новый ТЕЛЕФОН для пользователя:

🧑 ФИО: {target_user.full_name}
📞 Телефон: {target_user.phone_number}
🆔 Telegram ID: {target_user.tg_id}
👤 Username: @{target_user.username if target_user.username else 'Не указан'}"""
    
    await callback.message.edit_text(message_text)
    await state.set_state(UserEditStates.waiting_for_new_phone)
    await state.update_data(edit_type="phone")
    await callback.answer()


@router.message(UserEditStates.waiting_for_new_phone)
async def process_new_phone(message: Message, session: AsyncSession, state: FSMContext):
    """Обработка нового телефона"""
    new_phone = message.text.strip()
    
    # Валидация и нормализация
    is_valid, result = validate_phone_number(new_phone)
    if not is_valid:
        await message.answer(f"❌ {result}")
        return
        
    normalized_phone = result
    
    data = await state.get_data()
    editing_user_id = data.get('editing_user_id')
    
    target_user = await get_user_with_details(session, editing_user_id)
    if not target_user:
        await message.answer("❌ Пользователь не найден")
        await state.clear()
        return
        
    # Сохраняем новое значение и показываем подтверждение
    await state.update_data(new_value=normalized_phone, old_value=target_user.phone_number)
    
    confirmation_text = f"""⚠️НОВЫЙ ТЕЛЕФОН:
⚠️{normalized_phone}

Для пользователя:
🧑 ФИО: {target_user.full_name}
📞 Телефон: {target_user.phone_number}
🆔 Telegram ID: {target_user.tg_id}
👤 Username: @{target_user.username if target_user.username else 'Не указан'}"""
    
    keyboard = get_edit_confirmation_keyboard()
    await message.answer(confirmation_text, reply_markup=keyboard)
    await state.set_state(UserEditStates.waiting_for_change_confirmation)


@router.callback_query(F.data == "edit_role")
async def process_edit_role(callback: CallbackQuery, session: AsyncSession, state: FSMContext):
    """Начало редактирования роли"""
    data = await state.get_data()
    editing_user_id = data.get('editing_user_id')
    
    if not editing_user_id:
        await callback.answer("❌ Ошибка: не выбран пользователь")
        return
        
    target_user = await get_user_with_details(session, editing_user_id)
    if not target_user:
        await callback.answer("❌ Пользователь не найден")
        return
        
    current_role = target_user.roles[0].name if target_user.roles else "Нет роли"
    
    message_text = f"""Выберите новую роль для пользователя:

🧑 ФИО: {target_user.full_name}
📞 Телефон: {target_user.phone_number}
🆔 Telegram ID: {target_user.tg_id}
👤 Username: @{target_user.username if target_user.username else 'Не указан'}
📅 Дата регистрации: {target_user.registration_date.strftime('%d.%m.%Y %H:%M') if target_user.registration_date else 'Не указана'}
👑 Роли: {current_role}"""
    
    keyboard = get_role_selection_keyboard()
    await callback.message.edit_text(message_text, reply_markup=keyboard)
    await state.set_state(UserEditStates.waiting_for_new_role)
    await state.update_data(edit_type="role", old_value=current_role)
    await callback.answer()


@router.callback_query(UserEditStates.waiting_for_new_role, F.data.startswith("role:"))
async def process_new_role(callback: CallbackQuery, session: AsyncSession, state: FSMContext):
    """Обработка выбора новой роли"""
    new_role = callback.data.split(":")[1]
    
    data = await state.get_data()
    editing_user_id = data.get('editing_user_id')
    old_role = data.get('old_value')
    
    target_user = await get_user_with_details(session, editing_user_id)
    if not target_user:
        await callback.answer("❌ Пользователь не найден")
        await state.clear()
        return
        
    # Сохраняем новое значение и показываем подтверждение
    await state.update_data(new_value=new_role)
    
    # Получаем текущую роль
    current_role = target_user.roles[0].name if target_user.roles else "Нет роли"
    
    # Формируем предупреждения о последствиях смены роли
    warnings = await get_role_change_warnings(session, target_user.id, current_role, new_role)
    
    confirmation_text = f"""⚠️<b>ИЗМЕНЕНИЕ РОЛИ</b>⚠️

🧑 <b>ФИО:</b> {target_user.full_name}
📞 <b>Телефон:</b> {target_user.phone_number}
🆔 <b>Telegram ID:</b> {target_user.tg_id}
👤 <b>Username:</b> @{target_user.username if target_user.username else 'Не указан'}

👑 <b>Текущая роль:</b> {current_role}
👑 <b>Новая роль:</b> {new_role}

{warnings}"""
    
    keyboard = get_edit_confirmation_keyboard()
    await callback.message.edit_text(confirmation_text, reply_markup=keyboard)
    await state.set_state(UserEditStates.waiting_for_change_confirmation)
    await callback.answer()


@router.callback_query(UserEditStates.waiting_for_new_role, F.data == "cancel_registration")
async def process_cancel_role_selection(callback: CallbackQuery, session: AsyncSession, state: FSMContext):
    """Отмена выбора роли"""
    await callback.message.edit_text("❌ ВЫ ОТМЕНИЛИ РЕДАКТИРОВАНИЕ ПОЛЬЗОВАТЕЛЯ")
    await state.clear()
    await callback.answer()
    log_user_action(callback.from_user.id, "cancel_role_edit", "Cancelled role editing")


@router.callback_query(F.data == "edit_group")
async def process_edit_group(callback: CallbackQuery, session: AsyncSession, state: FSMContext):
    """Начало редактирования группы"""
    data = await state.get_data()
    editing_user_id = data.get('editing_user_id')
    
    if not editing_user_id:
        await callback.answer("❌ Ошибка: не выбран пользователь")
        return
        
    target_user = await get_user_with_details(session, editing_user_id)
    if not target_user:
        await callback.answer("❌ Пользователь не найден")
        return
        
    current_group = target_user.groups[0].name if target_user.groups else "Нет группы"
    
    message_text = f"""Выберите новую группу для пользователя:

🧑 ФИО: {target_user.full_name}
📞 Телефон: {target_user.phone_number}
🆔 Telegram ID: {target_user.tg_id}
👤 Username: @{target_user.username if target_user.username else 'Не указан'}
📅 Дата регистрации: {target_user.registration_date.strftime('%d.%m.%Y %H:%M') if target_user.registration_date else 'Не указана'}
🗂️Группа: {current_group}"""
    
    # Получаем все группы
    groups = await get_all_groups(session)
    
    if not groups:
        await callback.message.edit_text("❌ В системе нет доступных групп")
        await callback.answer()
        return
    
    keyboard = get_group_selection_keyboard(groups, 0)
    
    await callback.message.edit_text(message_text, reply_markup=keyboard)
    await state.set_state(UserEditStates.waiting_for_new_group)
    await state.update_data(edit_type="group", old_value=current_group)
    await callback.answer()


@router.callback_query(UserEditStates.waiting_for_new_group)
async def process_new_group(callback: CallbackQuery, session: AsyncSession, state: FSMContext):
    """Обработка выбора новой группы"""
    if callback.data.startswith("select_group:"):
        group_id = int(callback.data.split(":")[1])
        
        data = await state.get_data()
        editing_user_id = data.get('editing_user_id')
        
        target_user = await get_user_with_details(session, editing_user_id)
        if not target_user:
            await callback.answer("❌ Пользователь не найден")
            await state.clear()
            return
            
        # Получаем название группы
        group = await get_group_by_id(session, group_id)
        if not group:
            await callback.answer("❌ Группа не найдена")
            return
            
        # Сохраняем новое значение и показываем подтверждение
        await state.update_data(new_value=group_id, new_group_name=group.name)
        
        confirmation_text = f"""⚠️НОВАЯ ГРУППА:
⚠️{group.name}

Для пользователя:
🧑 ФИО: {target_user.full_name}
📞 Телефон: {target_user.phone_number}
🆔 Telegram ID: {target_user.tg_id}
👤 Username: @{target_user.username if target_user.username else 'Не указан'}"""
        
        keyboard = get_edit_confirmation_keyboard()
        await callback.message.edit_text(confirmation_text, reply_markup=keyboard)
        await state.set_state(UserEditStates.waiting_for_change_confirmation)
        await callback.answer()
        
    elif callback.data.startswith("groups_page:"):
        # Обработка пагинации
        page = int(callback.data.split(":")[1])
        groups = await get_all_groups(session)
        keyboard = get_group_selection_keyboard(groups, page)
        await callback.message.edit_reply_markup(reply_markup=keyboard)
        await callback.answer()


@router.callback_query(F.data == "edit_internship_object")
async def process_edit_internship_object(callback: CallbackQuery, session: AsyncSession, state: FSMContext):
    """Начало редактирования объекта стажировки"""
    data = await state.get_data()
    editing_user_id = data.get('editing_user_id')
    
    if not editing_user_id:
        await callback.answer("❌ Ошибка: не выбран пользователь")
        return
        
    target_user = await get_user_with_details(session, editing_user_id)
    if not target_user:
        await callback.answer("❌ Пользователь не найден")
        return
        
    current_object = target_user.internship_object.name if target_user.internship_object else "Не назначен"
    
    message_text = f"""Выберите новый 1️⃣Объект стажировки для пользователя:

🧑 ФИО: {target_user.full_name}
📞 Телефон: {target_user.phone_number}
🆔 Telegram ID: {target_user.tg_id}
👤 Username: @{target_user.username if target_user.username else 'Не указан'}
📅 Дата регистрации: {target_user.registration_date.strftime('%d.%m.%Y %H:%M') if target_user.registration_date else 'Не указана'}
👑 Роли: {target_user.roles[0].name if target_user.roles else 'Нет роли'}
🗂️Группа: {target_user.groups[0].name if target_user.groups else 'Нет группы'}
📍1️⃣Объект стажировки: {current_object}"""
    
    # Получаем все объекты
    objects = await get_all_objects(session)
    
    if not objects:
        await callback.message.edit_text("❌ В системе нет доступных объектов стажировки")
        await callback.answer()
        return
    
    keyboard = get_object_selection_keyboard(objects, 0, 5, "internship")
    
    await callback.message.edit_text(message_text, reply_markup=keyboard)
    await state.set_state(UserEditStates.waiting_for_new_internship_object)
    await state.update_data(edit_type="internship_object", old_value=current_object)
    await callback.answer()


@router.callback_query(UserEditStates.waiting_for_new_internship_object)
async def process_new_internship_object(callback: CallbackQuery, session: AsyncSession, state: FSMContext):
    """Обработка выбора нового объекта стажировки"""
    if callback.data.startswith("select_internship_object:"):
        object_id = int(callback.data.split(":")[1])
        
        data = await state.get_data()
        editing_user_id = data.get('editing_user_id')
        
        target_user = await get_user_with_details(session, editing_user_id)
        if not target_user:
            await callback.answer("❌ Пользователь не найден")
            await state.clear()
            return
            
        # Получаем название объекта
        obj = await get_object_by_id(session, object_id)
        if not obj:
            await callback.answer("❌ Объект не найден или неактивен")
            return
            
        # Сохраняем новое значение и показываем подтверждение
        await state.update_data(new_value=object_id, new_object_name=obj.name)
        
        confirmation_text = f"""⚠️НОВЫЙ ОБЪЕКТ СТАЖИРОВКИ:
⚠️{obj.name}

Для пользователя:
🧑 ФИО: {target_user.full_name}
📞 Телефон: {target_user.phone_number}
🆔 Telegram ID: {target_user.tg_id}
👤 Username: @{target_user.username if target_user.username else 'Не указан'}
📅 Дата регистрации: {target_user.registration_date.strftime('%d.%m.%Y %H:%M') if target_user.registration_date else 'Не указана'}
👑 Роли: {target_user.roles[0].name if target_user.roles else 'Нет роли'}
🗂️Группа: {target_user.groups[0].name if target_user.groups else 'Нет группы'}
📍1️⃣Объект стажировки: {target_user.internship_object.name if target_user.internship_object else 'Не назначен'}"""
        
        keyboard = get_edit_confirmation_keyboard()
        await callback.message.edit_text(confirmation_text, reply_markup=keyboard)
        await state.set_state(UserEditStates.waiting_for_change_confirmation)
        await callback.answer()
        
    elif callback.data.startswith("internship_object_page:"):
        # Обработка пагинации
        page = int(callback.data.split(":")[1])
        objects = await get_all_objects(session)
        keyboard = get_object_selection_keyboard(objects, page, 5, "internship")
        await callback.message.edit_reply_markup(reply_markup=keyboard)
        await callback.answer()


@router.callback_query(F.data == "edit_work_object")
async def process_edit_work_object(callback: CallbackQuery, session: AsyncSession, state: FSMContext):
    """Начало редактирования объекта работы"""
    data = await state.get_data()
    editing_user_id = data.get('editing_user_id')
    
    if not editing_user_id:
        await callback.answer("❌ Ошибка: не выбран пользователь")
        return
        
    target_user = await get_user_with_details(session, editing_user_id)
    if not target_user:
        await callback.answer("❌ Пользователь не найден")
        return
        
    current_object = target_user.work_object.name if target_user.work_object else "Не назначен"
    current_role = target_user.roles[0].name if target_user.roles else "Нет роли"
    
    message_text = f"""Выберите новый 2️⃣Объект работы для пользователя:

🧑 ФИО: {target_user.full_name}
📞 Телефон: {target_user.phone_number}
🆔 Telegram ID: {target_user.tg_id}
👤 Username: @{target_user.username if target_user.username else 'Не указан'}
📅 Дата регистрации: {target_user.registration_date.strftime('%d.%m.%Y %H:%M') if target_user.registration_date else 'Не указана'}
👑 Роли: {current_role}
🗂️Группа: {target_user.groups[0].name if target_user.groups else 'Нет группы'}
📍2️⃣Объект работы: {current_object}"""
    
    # Получаем все объекты
    objects = await get_all_objects(session)
    
    if not objects:
        await callback.message.edit_text("❌ В системе нет доступных объектов работы")
        await callback.answer()
        return
    
    keyboard = get_object_selection_keyboard(objects, 0, 5, "work")
    
    await callback.message.edit_text(message_text, reply_markup=keyboard)
    await state.set_state(UserEditStates.waiting_for_new_work_object)
    await state.update_data(edit_type="work_object", old_value=current_object)
    await callback.answer()


@router.callback_query(UserEditStates.waiting_for_new_work_object)
async def process_new_work_object(callback: CallbackQuery, session: AsyncSession, state: FSMContext):
    """Обработка выбора нового объекта работы"""
    if callback.data.startswith("select_work_object:"):
        object_id = int(callback.data.split(":")[1])
        
        data = await state.get_data()
        editing_user_id = data.get('editing_user_id')
        
        target_user = await get_user_with_details(session, editing_user_id)
        if not target_user:
            await callback.answer("❌ Пользователь не найден")
            await state.clear()
            return
            
        # Получаем название объекта
        obj = await get_object_by_id(session, object_id)
        if not obj:
            await callback.answer("❌ Объект не найден или неактивен")
            return
            
        # Сохраняем новое значение и показываем подтверждение
        await state.update_data(new_value=object_id, new_object_name=obj.name)
        
        current_role = target_user.roles[0].name if target_user.roles else "Нет роли"
        
        confirmation_text = f"""⚠️НОВЫЙ ОБЪЕКТ РАБОТЫ:
⚠️{obj.name}

Для пользователя:
🧑 ФИО: {target_user.full_name}
📞 Телефон: {target_user.phone_number}
🆔 Telegram ID: {target_user.tg_id}
👤 Username: @{target_user.username if target_user.username else 'Не указан'}
📅 Дата регистрации: {target_user.registration_date.strftime('%d.%m.%Y %H:%M') if target_user.registration_date else 'Не указана'}
👑 Роли: {current_role}
🗂️Группа: {target_user.groups[0].name if target_user.groups else 'Нет группы'}
📍2️⃣Объект работы: {target_user.work_object.name if target_user.work_object else 'Не назначен'}"""
        
        keyboard = get_edit_confirmation_keyboard()
        await callback.message.edit_text(confirmation_text, reply_markup=keyboard)
        await state.set_state(UserEditStates.waiting_for_change_confirmation)
        await callback.answer()
        
    elif callback.data.startswith("work_object_page:"):
        # Обработка пагинации
        page = int(callback.data.split(":")[1])
        objects = await get_all_objects(session)
        keyboard = get_object_selection_keyboard(objects, page, 5, "work")
        await callback.message.edit_reply_markup(reply_markup=keyboard)
        await callback.answer()


@router.callback_query(UserEditStates.waiting_for_change_confirmation, F.data == "confirm_change")
async def process_confirm_change(callback: CallbackQuery, session: AsyncSession, state: FSMContext):
    """Подтверждение изменений"""
    data = await state.get_data()
    editing_user_id = data.get('editing_user_id')
    edit_type = data.get('edit_type')
    new_value = data.get('new_value')
    
    # Получаем ID рекрутера
    recruiter = await get_user_by_tg_id(session, callback.from_user.id)
    if not recruiter:
        await callback.answer("❌ Ошибка аутентификации")
        await state.clear()
        return
        
    # Выполняем соответствующее обновление
    success = False
    error_message = "Неизвестная ошибка"
    bot = callback.bot
    
    if edit_type == "full_name":
        success = await update_user_full_name(session, editing_user_id, new_value, recruiter.id, bot)
        error_message = "❌ Ошибка при изменении ФИО"
    elif edit_type == "phone":
        # Дополнительная проверка для телефона
        existing_user = await get_user_by_phone(session, new_value)
        if existing_user and existing_user.id != editing_user_id:
            error_message = f"❌ Телефон {new_value} уже используется другим пользователем"
            success = False
        else:
            success = await update_user_phone_number(session, editing_user_id, new_value, recruiter.id, bot)
            error_message = "❌ Ошибка при изменении телефона"
    elif edit_type == "role":
        success = await update_user_role(session, editing_user_id, new_value, recruiter.id, bot)
        error_message = "❌ Ошибка при изменении роли"
    elif edit_type == "group":
        success = await update_user_group(session, editing_user_id, new_value, recruiter.id, bot)
        error_message = "❌ Ошибка при изменении группы"
    elif edit_type == "internship_object":
        success = await update_user_internship_object(session, editing_user_id, new_value, recruiter.id, bot)
        error_message = "❌ Ошибка при изменении объекта стажировки"
    elif edit_type == "work_object":
        success = await update_user_work_object(session, editing_user_id, new_value, recruiter.id, bot)
        error_message = "❌ Ошибка при изменении объекта работы"
        
    if success:
        # Получаем обновленного пользователя и показываем редактор снова
        target_user = await get_user_with_details(session, editing_user_id)
        if target_user:
            # Формируем полное сообщение как требует ТЗ
            role_name = target_user.roles[0].name if target_user.roles else "Нет роли"
            group_name = target_user.groups[0].name if target_user.groups else "Нет группы"
            
            success_message = f"""✅Вы изменили данные пользователя:

✏️<b>РЕДАКТОР ПОЛЬЗОВАТЕЛЯ</b>✏️

🧑 ФИО: {target_user.full_name}
📞 Телефон: {target_user.phone_number}
🆔 Telegram ID: {target_user.tg_id}
👤 Username: @{target_user.username if target_user.username else 'Не указан'}
📅 Дата регистрации: {target_user.registration_date.strftime('%d.%m.%Y %H:%M') if target_user.registration_date else 'Не указана'}
👑 Роли: {role_name}
🗂️Группа: {group_name}"""
            
            # Добавляем объект стажировки только для стажеров
            if role_name == "Стажер" and target_user.internship_object:
                success_message += f"\n📍1️⃣Объект стажировки: {target_user.internship_object.name}"
                
            # Объект работы
            if target_user.work_object:
                success_message += f"\n📍2️⃣Объект работы: {target_user.work_object.name}"
                
            success_message += f"\n🎱Номер пользователя: {target_user.id}"
            success_message += "\n\nКакую информацию вы хотите изменить?\nВыберите кнопкой ниже👇"
            
            # Получаем клавиатуру редактора
            keyboard = get_user_editor_keyboard(role_name == "Стажер")
            
            await callback.message.edit_text(success_message, reply_markup=keyboard, parse_mode="HTML")
            log_user_action(callback.from_user.id, f"edit_user_{edit_type}", 
                          f"Changed {edit_type} for user {editing_user_id}")
    else:
        # Добавляем кнопку возврата к редактору при ошибке
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="↩️ Назад к редактору", callback_data=f"edit_user:{editing_user_id}")],
            [InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")]
        ])
        
        await callback.message.edit_text(error_message, reply_markup=keyboard, parse_mode="HTML")
        log_user_error(callback.from_user.id, f"edit_user_{edit_type}_failed", 
                      f"Failed to change {edit_type} for user {editing_user_id}")
        await state.set_state(UserEditStates.viewing_user_info)
        await state.update_data(viewing_user_id=editing_user_id)
        
    await callback.answer()


@router.callback_query(UserEditStates.waiting_for_change_confirmation, F.data == "cancel_change")
async def process_cancel_change(callback: CallbackQuery, session: AsyncSession, state: FSMContext):
    """Отмена изменений"""
    await callback.message.edit_text("❌ ВЫ ОТМЕНИЛИ РЕДАКТИРОВАНИЕ ПОЛЬЗОВАТЕЛЯ")
    await state.clear()
    await callback.answer()
    log_user_action(callback.from_user.id, "cancel_user_edit", "Cancelled user editing")


@router.callback_query(F.data == "edit_return_to_menu")
async def process_return_to_menu(callback: CallbackQuery, state: FSMContext):
    """Возврат в главное меню из редактора"""
    await callback.message.edit_text("Вы вернулись в главное меню")
    await state.clear()
    await callback.answer()
    log_user_action(callback.from_user.id, "edit_return_to_menu", "Returned to main menu from editor")


@router.callback_query(F.data == "main_menu", StateFilter(UserEditStates))
async def callback_main_menu(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Обработчик возврата в главное меню"""
    try:
        # Получение пользователя
        user = await get_user_by_tg_id(session, callback.from_user.id)
        if not user:
            await callback.message.edit_text("Вы не зарегистрированы в системе.")
            await callback.answer()
            await state.clear()
            return
        
        # Получаем роли пользователя для определения клавиатуры
        user_roles = await get_user_roles(session, user.id)
        
        if not user_roles:
            await callback.message.edit_text("У вас нет назначенных ролей. Обратитесь к администратору.")
            await callback.answer()
            await state.clear()
            return
        
        # Возвращаем в главное меню
        await callback.message.edit_text("Вы вернулись в главное меню")
        await state.clear()
        await callback.answer()
        
        log_user_action(callback.from_user.id, "return_to_main_menu", "Returned to main menu from user edit")
        
    except Exception as e:
        log_user_error(callback.from_user.id, "main_menu_error", str(e))
        await callback.message.edit_text("Произошла ошибка. Попробуйте еще раз.")
        await callback.answer()
        await state.clear()
