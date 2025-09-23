"""
Обработчики для управления объектами.
Включает создание, изменение и управление объектами.
"""

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession

from database.db import (
    create_object, get_all_objects, get_object_by_id, 
    update_object_name, get_object_users, get_user_roles,
    check_user_permission, get_user_by_tg_id
)
from handlers.auth import check_auth
from states.states import ObjectManagementStates
from keyboards.keyboards import (
    get_object_management_keyboard, get_object_selection_keyboard,
    get_object_rename_confirmation_keyboard, get_main_menu_keyboard,
    get_keyboard_by_role
)
from utils.logger import log_user_action, log_user_error
from utils.validators import validate_name

router = Router()


@router.message(F.text == "Объекты")
async def cmd_objects(message: Message, state: FSMContext, session: AsyncSession):
    """Обработчик команды 'Объекты'"""
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
        has_permission = await check_user_permission(session, user.id, "manage_objects")
        if not has_permission:
            await message.answer(
                "❌ <b>Недостаточно прав</b>\n\n"
                "У вас нет прав для управления объектами.",
                parse_mode="HTML"
            )
            return
        
        await message.answer(
            "📍<b>УПРАВЛЕНИЕ ОБЪЕКТАМИ</b>📍\n\n"
            "В данном меню вы можете:\n"
            "1. Создавать объекты\n"
            "2. Посмотреть существующие объекты\n"
            "3. Менять названия объектам",
            reply_markup=get_object_management_keyboard(),
            parse_mode="HTML"
        )
        log_user_action(user.tg_id, "objects_menu_opened", "Открыл меню управления объектами")
    except Exception as e:
        await message.answer("Произошла ошибка при открытии меню объектов")
        log_user_error(message.from_user.id, "objects_menu_error", str(e))


@router.callback_query(F.data == "create_object")
async def callback_create_object(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Обработчик создания нового объекта"""
    try:
        # Получение пользователя
        user = await get_user_by_tg_id(session, callback.from_user.id)
        if not user:
            await callback.message.edit_text("Вы не зарегистрированы в системе.")
            await callback.answer()
            return
        
        # Проверка прав доступа
        has_permission = await check_user_permission(session, user.id, "manage_objects")
        if not has_permission:
            await callback.message.edit_text(
                "❌ <b>Недостаточно прав</b>\n\n"
                "У вас нет прав для управления объектами.",
                parse_mode="HTML"
            )
            await callback.answer()
            return
        
        await callback.message.edit_text(
            "📍<b>УПРАВЛЕНИЕ ОБЪЕКТАМИ</b>📍\n"
            "➕<b>Создание объекта</b>➕\n"
            "Введите название объекта на клавиатуре",
            parse_mode="HTML"
        )
        await state.set_state(ObjectManagementStates.waiting_for_object_name)
        await callback.answer()
        log_user_action(user.tg_id, "object_creation_started", "Начал создание объекта")
    except Exception as e:
        await callback.message.edit_text("Произошла ошибка")
        log_user_error(callback.from_user.id, "object_creation_start_error", str(e))


@router.message(ObjectManagementStates.waiting_for_object_name)
async def process_object_name(message: Message, state: FSMContext, session: AsyncSession):
    """Обработка введенного названия объекта"""
    try:
        # Получение пользователя
        user = await get_user_by_tg_id(session, message.from_user.id)
        if not user:
            await message.answer("Вы не зарегистрированы в системе.")
            await state.clear()
            return
        
        object_name = message.text.strip()
        
        # Валидация названия
        if not validate_name(object_name):
            await message.answer(
                "❌ Некорректное название объекта.\n"
                "Название должно содержать только буквы, цифры, пробелы и знаки препинания.\n"
                "Попробуйте еще раз:"
            )
            return
        
        # Создаем объект
        obj = await create_object(session, object_name, user.id)
        if obj:
            await message.answer(
                f"📍<b>УПРАВЛЕНИЕ ОБЪЕКТАМИ</b>📍\n"
                f"✅<b>Объект успешно создан</b>\n"
                f"Название объекта: <b>{object_name}</b>",
                reply_markup=get_main_menu_keyboard(),
                parse_mode="HTML"
            )
            log_user_action(user.tg_id, "object_created", f"Создал объект: {object_name}")
        else:
            await message.answer(
                "❌ Ошибка создания объекта. Возможно, объект с таким названием уже существует.\n"
                "Попробуйте другое название:",
            )
            return
        
        await state.clear()
    except Exception as e:
        await message.answer("Произошла ошибка при создании объекта")
        log_user_error(message.from_user.id, "object_creation_error", str(e))
        await state.clear()


@router.callback_query(F.data == "edit_object")
async def callback_edit_object(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Обработчик изменения объектов"""
    try:
        # Получение пользователя
        user = await get_user_by_tg_id(session, callback.from_user.id)
        if not user:
            await callback.message.edit_text("Вы не зарегистрированы в системе.")
            await callback.answer()
            return
        
        # Проверка прав доступа
        has_permission = await check_user_permission(session, user.id, "manage_objects")
        if not has_permission:
            await callback.message.edit_text(
                "❌ <b>Недостаточно прав</b>\n\n"
                "У вас нет прав для управления объектами.",
                parse_mode="HTML"
            )
            await callback.answer()
            return
        
        objects = await get_all_objects(session)
        
        if not objects:
            await callback.message.edit_text(
                "📍<b>УПРАВЛЕНИЕ ОБЪЕКТАМИ</b>📍\n"
                "❌ Объектов не найдено. Сначала создайте объект.",
                reply_markup=get_main_menu_keyboard(),
                parse_mode="HTML"
            )
            await callback.answer()
            return
        
        await callback.message.edit_text(
            "📍<b>УПРАВЛЕНИЕ ОБЪЕКТАМИ</b>📍\n"
            "👇<b>Выберите объект для изменения:</b>",
            reply_markup=get_object_selection_keyboard(objects, page=0),
            parse_mode="HTML"
        )
        await state.update_data(objects=objects, current_page=0)
        await state.set_state(ObjectManagementStates.waiting_for_object_selection)
        await callback.answer()
        log_user_action(user.tg_id, "object_edit_started", "Начал изменение объекта")
    except Exception as e:
        await callback.message.edit_text("Произошла ошибка")
        log_user_error(callback.from_user.id, "object_edit_start_error", str(e))


@router.callback_query(F.data.startswith("select_object:"), ObjectManagementStates.waiting_for_object_selection)
async def callback_select_object(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Обработчик выбора объекта для изменения"""
    try:
        # Получение пользователя
        user = await get_user_by_tg_id(session, callback.from_user.id)
        if not user:
            await callback.message.edit_text("Вы не зарегистрированы в системе.")
            await callback.answer()
            await state.clear()
            return
        
        object_id = int(callback.data.split(":")[1])
        obj = await get_object_by_id(session, object_id)
        
        if not obj:
            await callback.message.edit_text("Объект не найден")
            await callback.answer()
            await state.clear()
            return
        
        # Получаем пользователей объекта
        object_users = await get_object_users(session, object_id)
        user_list = ""
        if object_users:
            for object_user in object_users:
                user_roles = await get_user_roles(session, object_user.id)
                role_names = ", ".join([role.name for role in user_roles])
                user_list += f"{object_user.full_name} ({role_names})\n"
        else:
            user_list = "Пользователей на объекте нет"
        
        await callback.message.edit_text(
            f"📍<b>УПРАВЛЕНИЕ ОБЪЕКТАМИ</b>📍\n"
            f"👉Вы выбрали объект: <b>{obj.name}</b>\n"
            f"Сотрудников на объекте: <b>{len(object_users)}</b>\n\n"
            f"<b>ФИО сотрудников:</b>\n"
            f"{user_list}\n\n"
            f"Введите новое название для данного объекта и отправьте чат-боту",
            parse_mode="HTML"
        )
        
        # Сохраняем данные объекта для дальнейшего использования
        await state.update_data(object_id=object_id, old_name=obj.name)
        await state.set_state(ObjectManagementStates.waiting_for_new_object_name)
        await callback.answer()
        
        log_user_action(user.tg_id, "object_selected", f"Выбрал объект для изменения: {obj.name}")
    except Exception as e:
        await callback.message.edit_text("Произошла ошибка")
        log_user_error(callback.from_user.id, "object_selection_error", str(e))
        await state.clear()


@router.callback_query(F.data.startswith("objects_page:"), ObjectManagementStates.waiting_for_object_selection)
async def callback_objects_pagination(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Обработчик пагинации объектов"""
    try:
        page = int(callback.data.split(":")[1])
        data = await state.get_data()
        objects = data.get("objects", [])
        
        await callback.message.edit_text(
            "📍<b>УПРАВЛЕНИЕ ОБЪЕКТАМИ</b>📍\n"
            "👇<b>Выберите объект для изменения:</b>",
            reply_markup=get_object_selection_keyboard(objects, page=page),
            parse_mode="HTML"
        )
        await state.update_data(current_page=page)
        await callback.answer()
    except Exception as e:
        await callback.message.edit_text("Произошла ошибка при навигации")
        log_user_error(callback.from_user.id, "objects_pagination_error", str(e))


@router.message(ObjectManagementStates.waiting_for_new_object_name)
async def process_new_object_name(message: Message, state: FSMContext, session: AsyncSession):
    """Обработка нового названия объекта"""
    try:
        # Получение пользователя
        user = await get_user_by_tg_id(session, message.from_user.id)
        if not user:
            await message.answer("Вы не зарегистрированы в системе.")
            await state.clear()
            return
        
        new_name = message.text.strip()
        data = await state.get_data()
        object_id = data.get("object_id")
        old_name = data.get("old_name")
        
        # Валидация названия
        if not validate_name(new_name):
            await message.answer(
                "❌ Некорректное название объекта.\n"
                "Название должно содержать только буквы, цифры, пробелы и знаки препинания.\n"
                "Попробуйте еще раз:"
            )
            return
        
        # Проверяем, что название отличается от старого
        if new_name == old_name:
            await message.answer(
                "❌ Новое название совпадает со старым.\n"
                "Введите другое название:"
            )
            return
        
        await message.answer(
            f"📍<b>УПРАВЛЕНИЕ ОБЪЕКТАМИ</b>📍\n"
            f"Вы уверены, что хотите изменить название?\n\n"
            f"Старое название: <b>{old_name}</b>\n"
            f"Новое название: <b>{new_name}</b>",
            reply_markup=get_object_rename_confirmation_keyboard(object_id),
            parse_mode="HTML"
        )
        
        await state.update_data(new_name=new_name)
        await state.set_state(ObjectManagementStates.waiting_for_object_rename_confirmation)
        log_user_action(user.tg_id, "object_rename_confirmation", f"Подтверждение переименования: {old_name} -> {new_name}")
    except Exception as e:
        await message.answer("Произошла ошибка при обработке нового названия")
        log_user_error(message.from_user.id, "object_rename_process_error", str(e))
        await state.clear()


@router.callback_query(F.data.startswith("confirm_object_rename:"), ObjectManagementStates.waiting_for_object_rename_confirmation)
async def callback_confirm_object_rename(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Обработчик подтверждения переименования объекта"""
    try:
        # Получение пользователя
        user = await get_user_by_tg_id(session, callback.from_user.id)
        if not user:
            await callback.message.edit_text("Вы не зарегистрированы в системе.")
            await callback.answer()
            await state.clear()
            return
        
        object_id = int(callback.data.split(":")[1])
        data = await state.get_data()
        new_name = data.get("new_name")
        old_name = data.get("old_name")
        
        if await update_object_name(session, object_id, new_name):
            await callback.message.edit_text(
                f"📍<b>УПРАВЛЕНИЕ ОБЪЕКТАМИ</b>📍\n"
                f"✅<b>Название успешно изменено на:</b>\n"
                f"<b>{new_name}</b>",
                reply_markup=get_main_menu_keyboard(),
                parse_mode="HTML"
            )
            log_user_action(user.tg_id, "object_renamed", f"Переименовал объект: {old_name} -> {new_name}")
        else:
            await callback.message.edit_text(
                "❌ Ошибка переименования объекта. Возможно, объект с таким названием уже существует.",
                reply_markup=get_main_menu_keyboard()
            )
        
        await state.clear()
        await callback.answer()
    except Exception as e:
        await callback.message.edit_text("Произошла ошибка при переименовании")
        log_user_error(callback.from_user.id, "object_rename_confirm_error", str(e))
        await state.clear()


@router.callback_query(F.data == "cancel_object_rename", ObjectManagementStates.waiting_for_object_rename_confirmation)
async def callback_cancel_object_rename(callback: CallbackQuery, state: FSMContext):
    """Обработчик отмены переименования объекта"""
    try:
        await callback.message.edit_text(
            "📍<b>УПРАВЛЕНИЕ ОБЪЕКТАМИ</b>📍\n"
            "❌<b>Вы отменили изменение</b>",
            reply_markup=get_main_menu_keyboard(),
            parse_mode="HTML"
        )
        await state.clear()
        await callback.answer()
        log_user_action(callback.from_user.id, "object_rename_cancelled", "Отменил переименование объекта")
    except Exception as e:
        await callback.message.edit_text("Произошла ошибка")
        log_user_error(callback.from_user.id, "object_rename_cancel_error", str(e))
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
        role_names = [role.name for role in user_roles]
        
        # Отправляем соответствующую клавиатуру
        keyboard = get_keyboard_by_role(role_names)
        
        await callback.message.answer(
            "🏠 <b>Главное меню</b>\n\n"
            "Выберите действие:",
            reply_markup=keyboard,
            parse_mode="HTML"
        )
        
        # Удаляем старое сообщение
        await callback.message.delete()
        await state.clear()
        await callback.answer()
        log_user_action(user.tg_id, "returned_to_main_menu", "Вернулся в главное меню")
    except Exception as e:
        await callback.message.edit_text("Произошла ошибка")
        log_user_error(callback.from_user.id, "main_menu_error", str(e))
        await state.clear()
