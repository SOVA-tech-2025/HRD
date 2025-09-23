from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession

from database.db import (
    create_group, get_all_groups, get_group_by_id, 
    update_group_name, get_group_users, get_user_roles,
    check_user_permission, get_user_by_tg_id
)
from handlers.auth import check_auth
from states.states import GroupManagementStates
from keyboards.keyboards import (
    get_group_management_keyboard, get_group_selection_keyboard,
    get_group_rename_confirmation_keyboard, get_main_menu_keyboard,
    get_keyboard_by_role
)
from utils.logger import log_user_action, log_user_error
from utils.validators import validate_name

router = Router()


@router.message(F.text == "Группы пользователей")
async def cmd_groups(message: Message, state: FSMContext, session: AsyncSession):
    """Обработчик команды 'Группы пользователей'"""
    try:
        # Проверка авторизации
        is_auth = await check_auth(message, state, session)
        if not is_auth:
            return
        
        # Получение пользователя
        user = await get_user_by_tg_id(session, message.from_user.id)
        if not user:
            await message.answer("Вы не зарегистрированы в системе.")
            return
        
        # Проверка прав доступа
        has_permission = await check_user_permission(session, user.id, "manage_groups")
        if not has_permission:
            await message.answer(
                "❌ <b>Недостаточно прав</b>\n\n"
                "У вас нет прав для управления группами.\n"
                "Обратитесь к администратору.",
                parse_mode="HTML"
            )
            log_user_error(user.tg_id, "groups_access_denied", "Попытка доступа без прав")
            return
        
        await message.answer(
            "🗂️<b>УПРАВЛЕНИЕ ГРУППАМИ</b>🗂️\n\n"
            "В данном меню вы можете:\n"
            "1. Создавать группы\n"
            "2. Посмотреть существующие группы\n"
            "3. Менять названия группе",
            reply_markup=get_group_management_keyboard(),
            parse_mode="HTML"
        )
        log_user_action(user.tg_id, "groups_menu_opened", "Открыл меню управления группами")
    except Exception as e:
        await message.answer("Произошла ошибка при открытии меню групп")
        log_user_error(message.from_user.id, "groups_menu_error", str(e))


@router.callback_query(F.data == "create_group")
async def callback_create_group(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Обработчик создания новой группы"""
    try:
        # Получение пользователя
        user = await get_user_by_tg_id(session, callback.from_user.id)
        if not user:
            await callback.message.edit_text("Вы не зарегистрированы в системе.")
            await callback.answer()
            return
        
        # Проверка прав доступа
        has_permission = await check_user_permission(session, user.id, "manage_groups")
        if not has_permission:
            await callback.message.edit_text(
                "❌ <b>Недостаточно прав</b>\n\n"
                "У вас нет прав для управления группами.",
                parse_mode="HTML"
            )
            await callback.answer()
            return
        
        await callback.message.edit_text(
            "🗂️<b>УПРАВЛЕНИЕ ГРУППАМИ</b>🗂️\n"
            "➕<b>Создание группы</b>➕\n"
            "Введите название группы на клавиатуре",
            parse_mode="HTML"
        )
        await state.set_state(GroupManagementStates.waiting_for_group_name)
        await callback.answer()
        log_user_action(user.tg_id, "group_creation_started", "Начал создание группы")
    except Exception as e:
        await callback.message.edit_text("Произошла ошибка")
        log_user_error(callback.from_user.id, "group_creation_start_error", str(e))


@router.message(GroupManagementStates.waiting_for_group_name)
async def process_group_name(message: Message, state: FSMContext, session: AsyncSession):
    """Обработка введенного названия группы"""
    try:
        # Получение пользователя
        user = await get_user_by_tg_id(session, message.from_user.id)
        if not user:
            await message.answer("Вы не зарегистрированы в системе.")
            await state.clear()
            return
        
        group_name = message.text.strip()
        
        # Валидация названия
        if not validate_name(group_name):
            await message.answer(
                "❌ Некорректное название группы.\n"
                "Название должно содержать только буквы, цифры, пробелы и знаки препинания.\n"
                "Попробуйте еще раз:"
            )
            return
        
        # Создаем группу
        group = await create_group(session, group_name, user.id)
        if group:
            await message.answer(
                f"🗂️<b>УПРАВЛЕНИЕ ГРУППАМИ</b>🗂️\n"
                f"✅<b>Группа успешно создана</b>\n"
                f"Название группы: <b>{group_name}</b>",
                reply_markup=get_main_menu_keyboard(),
                parse_mode="HTML"
            )
            log_user_action(user.tg_id, "group_created", f"Создал группу: {group_name}")
        else:
            await message.answer(
                "❌ Ошибка создания группы. Возможно, группа с таким названием уже существует.\n"
                "Попробуйте другое название:",
            )
            return
        
        await state.clear()
    except Exception as e:
        await message.answer("Произошла ошибка при создании группы")
        log_user_error(message.from_user.id, "group_creation_error", str(e))
        await state.clear()


@router.callback_query(F.data == "manage_edit_group")
async def callback_edit_group(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Обработчик изменения групп"""
    try:
        # Получение пользователя
        user = await get_user_by_tg_id(session, callback.from_user.id)
        if not user:
            await callback.message.edit_text("Вы не зарегистрированы в системе.")
            await callback.answer()
            return
        
        # Проверка прав доступа
        has_permission = await check_user_permission(session, user.id, "manage_groups")
        if not has_permission:
            await callback.message.edit_text(
                "❌ <b>Недостаточно прав</b>\n\n"
                "У вас нет прав для управления группами.",
                parse_mode="HTML"
            )
            await callback.answer()
            return
        
        groups = await get_all_groups(session)
        
        if not groups:
            await callback.message.edit_text(
                "🗂️<b>УПРАВЛЕНИЕ ГРУППАМИ</b>🗂️\n"
                "❌ Групп не найдено. Сначала создайте группу.",
                reply_markup=get_main_menu_keyboard(),
                parse_mode="HTML"
            )
            await callback.answer()
            return
        
        await callback.message.edit_text(
            "🗂️<b>УПРАВЛЕНИЕ ГРУППАМИ</b>🗂️\n"
            "👇<b>Выберите группу для изменения:</b>",
            reply_markup=get_group_selection_keyboard(groups, page=0),
            parse_mode="HTML"
        )
        await state.update_data(groups=groups, current_page=0)
        await state.set_state(GroupManagementStates.waiting_for_group_selection)
        await callback.answer()
        log_user_action(user.tg_id, "group_edit_started", "Начал изменение группы")
    except Exception as e:
        await callback.message.edit_text("Произошла ошибка")
        log_user_error(callback.from_user.id, "group_edit_start_error", str(e))


@router.callback_query(F.data.startswith("select_group:"), GroupManagementStates.waiting_for_group_selection)
async def callback_select_group(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Обработчик выбора группы для изменения"""
    try:
        group_id = int(callback.data.split(":")[1])
        group = await get_group_by_id(session, group_id)
        
        if not group:
            await callback.message.edit_text(
                "❌ Группа не найдена",
                reply_markup=get_main_menu_keyboard()
            )
            await callback.answer()
            await state.clear()
            return
        
        # Получаем пользователей группы
        group_users = await get_group_users(session, group_id)
        
        # Формируем список пользователей
        user_list = ""
        if group_users:
            for group_user in group_users:
                user_roles = await get_user_roles(session, group_user.id)
                role_names = ", ".join([role.name for role in user_roles])
                user_list += f"{group_user.full_name} ({role_names})\n"
        else:
            user_list = "Пользователей в группе нет"
        
        await callback.message.edit_text(
            f"🗂️<b>УПРАВЛЕНИЕ ГРУППАМИ</b>🗂️\n"
            f"👉Вы выбрали группу: <b>{group.name}</b>\n"
            f"Сотрудников в группе: <b>{len(group_users)}</b>\n\n"
            f"<b>ФИО сотрудников:</b>\n"
            f"{user_list}\n\n"
            f"Введите новое название для данной группы и отправьте чат-боту",
            parse_mode="HTML"
        )
        
        # Сохраняем данные группы для дальнейшего использования
        await state.update_data(group_id=group_id, old_name=group.name)
        await state.set_state(GroupManagementStates.waiting_for_new_group_name)
        await callback.answer()
        # Получение пользователя
        user = await get_user_by_tg_id(session, callback.from_user.id)
        if not user:
            await callback.message.edit_text("Вы не зарегистрированы в системе.")
            await callback.answer()
            await state.clear()
            return
        
        log_user_action(user.tg_id, "group_selected", f"Выбрал группу для изменения: {group.name}")
    except Exception as e:
        await callback.message.edit_text("Произошла ошибка")
        log_user_error(callback.from_user.id, "group_selection_error", str(e))
        await state.clear()


@router.callback_query(F.data.startswith("groups_page:"), GroupManagementStates.waiting_for_group_selection)
async def callback_groups_pagination(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Обработчик пагинации групп"""
    try:
        page = int(callback.data.split(":")[1])
        data = await state.get_data()
        groups = data.get('groups', [])
        
        await callback.message.edit_text(
            "🗂️<b>УПРАВЛЕНИЕ ГРУППАМИ</b>🗂️\n"
            "👇<b>Выберите группу для изменения:</b>",
            reply_markup=get_group_selection_keyboard(groups, page=page),
            parse_mode="HTML"
        )
        await state.update_data(current_page=page)
        await callback.answer()
    except Exception as e:
        await callback.answer("Ошибка пагинации", show_alert=True)
        log_user_error(callback.from_user.id, "groups_pagination_error", str(e))


@router.callback_query(F.data == "page_info")
async def callback_page_info(callback: CallbackQuery):
    """Обработчик информации о странице (заглушка)"""
    await callback.answer()


@router.message(GroupManagementStates.waiting_for_new_group_name)
async def process_new_group_name(message: Message, state: FSMContext, session: AsyncSession):
    """Обработка нового названия группы"""
    try:
        new_name = message.text.strip()
        
        # Получение пользователя
        user = await get_user_by_tg_id(session, message.from_user.id)
        if not user:
            await message.answer("Вы не зарегистрированы в системе.")
            await state.clear()
            return
        
        # Валидация названия
        if not validate_name(new_name):
            await message.answer(
                "❌ Некорректное название группы.\n"
                "Название должно содержать только буквы, цифры, пробелы и знаки препинания.\n"
                "Попробуйте еще раз:"
            )
            return
        
        # Получаем данные из состояния
        data = await state.get_data()
        group_id = data.get('group_id')
        old_name = data.get('old_name')
        
        await message.answer(
            f"🗂️<b>УПРАВЛЕНИЕ ГРУППАМИ</b>🗂️\n"
            f"Вы уверены, что хотите изменить название?\n\n"
            f"Старое название: <b>{old_name}</b>\n"
            f"Новое название: <b>{new_name}</b>",
            reply_markup=get_group_rename_confirmation_keyboard(group_id),
            parse_mode="HTML"
        )
        
        # Сохраняем новое название
        await state.update_data(new_name=new_name)
        await state.set_state(GroupManagementStates.waiting_for_rename_confirmation)
        log_user_action(user.tg_id, "group_rename_confirmation", f"Подтверждение переименования: {old_name} -> {new_name}")
    except Exception as e:
        await message.answer("Произошла ошибка при обработке названия")
        log_user_error(message.from_user.id, "group_rename_process_error", str(e))
        await state.clear()


@router.callback_query(F.data.startswith("confirm_rename:"), GroupManagementStates.waiting_for_rename_confirmation)
async def callback_confirm_rename(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Обработчик подтверждения переименования"""
    try:
        # Получение пользователя
        user = await get_user_by_tg_id(session, callback.from_user.id)
        if not user:
            await callback.message.edit_text("Вы не зарегистрированы в системе.")
            await callback.answer()
            await state.clear()
            return
        
        group_id = int(callback.data.split(":")[1])
        data = await state.get_data()
        new_name = data.get('new_name')
        old_name = data.get('old_name')
        
        # Обновляем название группы
        success = await update_group_name(session, group_id, new_name)
        
        if success:
            await callback.message.edit_text(
                f"🗂️<b>УПРАВЛЕНИЕ ГРУППАМИ</b>🗂️\n"
                f"✅<b>Название успешно изменено на:</b>\n"
                f"<b>{new_name}</b>",
                reply_markup=get_main_menu_keyboard(),
                parse_mode="HTML"
            )
            log_user_action(user.tg_id, "group_renamed", f"Переименовал группу: {old_name} -> {new_name}")
        else:
            await callback.message.edit_text(
                "❌ Ошибка изменения названия. Возможно, группа с таким названием уже существует.",
                reply_markup=get_main_menu_keyboard()
            )
        
        await callback.answer()
        await state.clear()
    except Exception as e:
        await callback.message.edit_text("Произошла ошибка")
        log_user_error(callback.from_user.id, "group_rename_confirm_error", str(e))
        await state.clear()


@router.callback_query(F.data == "cancel_rename", GroupManagementStates.waiting_for_rename_confirmation)
async def callback_cancel_rename(callback: CallbackQuery, state: FSMContext):
    """Обработчик отмены переименования"""
    try:
        await callback.message.edit_text(
            "🗂️<b>УПРАВЛЕНИЕ ГРУППАМИ</b>🗂️\n"
            "❌<b>Вы отменили изменение</b>",
            reply_markup=get_main_menu_keyboard(),
            parse_mode="HTML"
        )
        await callback.answer()
        await state.clear()
        log_user_action(callback.from_user.id, "group_rename_cancelled", "Отменил переименование группы")
    except Exception as e:
        await callback.message.edit_text("Произошла ошибка")
        log_user_error(callback.from_user.id, "group_rename_cancel_error", str(e))
        await state.clear()


@router.callback_query(F.data == "main_menu")
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
        
        if user_roles:
            role_name = user_roles[0].name  # Берем первую роль
            keyboard = get_keyboard_by_role(role_name)
            
            await callback.message.delete()
            await callback.message.answer(
                f"Вы вернулись в главное меню",
                reply_markup=keyboard
            )
        else:
            await callback.message.edit_text("Ошибка: роль пользователя не найдена")
        
        await callback.answer()
        await state.clear()
        log_user_action(user.tg_id, "returned_to_main_menu", "Вернулся в главное меню")
    except Exception as e:
        await callback.message.edit_text("Произошла ошибка")
        log_user_error(callback.from_user.id, "main_menu_error", str(e))
        await state.clear()
