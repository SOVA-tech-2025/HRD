from aiogram import Router, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from database.db import get_user_by_tg_id, get_user_roles, check_user_permission
from handlers.auth import check_auth
from keyboards.keyboards import format_help_message
from utils.logger import logger, log_user_action

router = Router()


async def format_profile_text(user, session: AsyncSession) -> str:
    """Универсальная функция формирования текста профиля для всех ролей"""
    # Получаем роли и определяем приоритетную
    roles = await get_user_roles(session, user.id)
    role_priority = {
        "Руководитель": 5,
        "Рекрутер": 4, 
        "Наставник": 3,
        "Сотрудник": 2,
        "Стажер": 1
    }
    user_roles = [r.name for r in roles]
    primary_role = max(user_roles, key=lambda r: role_priority.get(r, 0))
    
    # Формируем информацию о группах
    groups_str = ", ".join([group.name for group in user.groups]) if user.groups else "Не указана"
    
    # Формируем информацию об объектах
    internship_obj = user.internship_object.name if user.internship_object else "Не указан"
    work_obj = user.work_object.name if user.work_object else "Не указан"
    
    # Формируем username с экранированием
    username_display = f"@{user.username}" if user.username else "Не указан"
    if user.username and "_" in user.username:
        username_display = f"@{user.username.replace('_', '_')}"
    
    profile_text = f"""🦸🏻‍♂️ <b>Пользователь:</b> {user.full_name}

<b>Телефон:</b> {user.phone_number}
<b>Username:</b> {username_display}
<b>Номер:</b> #{user.id}
<b>Дата регистрации:</b> {user.registration_date.strftime('%d.%m.%Y %H:%M')}

━━━━━━━━━━━━

🗂️ <b>Статус:</b>
<b>Группа:</b> {groups_str}
<b>Роль:</b> {primary_role}

━━━━━━━━━━━━

📍 <b>Объект:</b>"""

    # Добавляем информацию об объектах в зависимости от роли
    if primary_role == "Стажер":
        profile_text += f"""
<b>Стажировки:</b> {internship_obj}
<b>Работы:</b> {work_obj}"""
    else:
        profile_text += f"""
<b>Работы:</b> {work_obj}"""
    
    return profile_text


@router.message(Command("help"))
async def cmd_help(message: Message, state: FSMContext, session: AsyncSession):
    """Показывает справку в зависимости от роли"""
    # Сначала проверяем авторизацию
    is_auth = await check_auth(message, state, session)
    if not is_auth:
        await message.answer(format_help_message("Неавторизованный"))
        return
    
    # Получаем роль из состояния или базы данных
    data = await state.get_data()
    role = data.get("role")
    
    # Если роли нет в состоянии, получаем из БД
    if not role:
        user = await get_user_by_tg_id(session, message.from_user.id)
        if user:
            roles = await get_user_roles(session, user.id)
            if roles:
                # Определяем приоритетную роль (по иерархии)
                role_priority = {
                    "Руководитель": 5,
                    "Рекрутер": 4, 
                    "Наставник": 3,
                    "Сотрудник": 2,
                    "Стажер": 1
                }
                # Берем роль с наивысшим приоритетом
                user_roles = [r.name for r in roles]
                role = max(user_roles, key=lambda r: role_priority.get(r, 0))
            else:
                role = "Неавторизованный"
        else:
            role = "Неавторизованный"

    await message.answer(format_help_message(role))

@router.message(Command("profile"))
async def cmd_profile(message: Message, state: FSMContext, session: AsyncSession):
    is_auth = await check_auth(message, state, session)
    if not is_auth:
        return
    
    user = await get_user_by_tg_id(session, message.from_user.id)
    
    has_permission = await check_user_permission(session, user.id, "view_profile")
    if not has_permission:
        await message.answer("У тебя нет прав для просмотра профиля.")
        return
    
    # Используем универсальную функцию формирования профиля
    profile_text = await format_profile_text(user, session)
    await message.answer(profile_text, parse_mode="HTML")

@router.message(F.text.in_(["Мой профиль", "🦸🏻‍♂️ Мой профиль", "Мой профиль 🦸🏻‍♂️"]))
async def button_profile(message: Message, state: FSMContext, session: AsyncSession):
    await cmd_profile(message, state, session)

@router.message(F.text.in_(["Помощь", "❓ Помощь", "Помощь ❓"]))
async def button_help(message: Message, state: FSMContext, session: AsyncSession):
    await cmd_help(message, state, session)

@router.callback_query(F.data == "main_menu")
async def process_main_menu(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Универсальный обработчик возврата в главное меню с обновлением клавиатуры согласно роли"""
    try:
        # Получаем пользователя
        user = await get_user_by_tg_id(session, callback.from_user.id)
        if not user:
            await callback.answer("❌ Пользователь не найден", show_alert=True)
            return

        if not user.is_active:
            await callback.answer("❌ Твой аккаунт деактивирован", show_alert=True)
            return

        # Получаем роли пользователя
        roles = await get_user_roles(session, user.id)
        if not roles:
            await callback.answer("❌ Роли не назначены", show_alert=True)
            return

        # Определяем приоритетную роль
        role_priority = {
            "Руководитель": 5,
            "Рекрутер": 4, 
            "Наставник": 3,
            "Сотрудник": 2,
            "Стажер": 1
        }
        
        primary_role = max(roles, key=lambda r: role_priority.get(r.name, 0))
        
        # Получаем клавиатуру согласно роли
        from keyboards.keyboards import get_keyboard_by_role
        keyboard = get_keyboard_by_role(primary_role.name)
        
        # Отправляем новое сообщение с правильной клавиатурой (ReplyKeyboardMarkup нельзя использовать в edit_text)
        await callback.message.answer(
            "🏠 <b>Главное меню</b>\n\n"
            "Используй команды бота или кнопки клавиатуры для навигации по системе.",
            parse_mode="HTML",
            reply_markup=keyboard
        )
        
        # Удаляем старое inline сообщение
        try:
            await callback.message.delete()
        except:
            pass
        
        # Очищаем состояние
        await state.clear()
        await callback.answer()
        
        # Логируем действие
        log_user_action(callback.from_user.id, callback.from_user.username, "returned_to_main_menu")
        
    except Exception as e:
        logger.error(f"Ошибка в process_main_menu: {e}")
        await callback.answer("❌ Ошибка при возврате в главное меню", show_alert=True)


@router.callback_query(F.data == "reload_menu")
async def process_reload_menu(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Обработчик кнопки 'Перезагрузка' - обновляет клавиатуру согласно роли пользователя"""
    try:
        # Получаем пользователя
        user = await get_user_by_tg_id(session, callback.from_user.id)
        if not user:
            await callback.answer("❌ Пользователь не найден", show_alert=True)
            return

        if not user.is_active:
            await callback.answer("❌ Твой аккаунт деактивирован", show_alert=True)
            return

        # Получаем роли пользователя
        roles = await get_user_roles(session, user.id)
        if not roles:
            await callback.answer("❌ Роли не назначены", show_alert=True)
            return

        # Определяем приоритетную роль
        role_priority = {
            "Руководитель": 5,
            "Рекрутер": 4, 
            "Наставник": 3,
            "Сотрудник": 2,
            "Стажер": 1
        }
        
        primary_role = max(roles, key=lambda r: role_priority.get(r.name, 0))
        
        # Получаем клавиатуру согласно роли
        from keyboards.keyboards import get_keyboard_by_role
        keyboard = get_keyboard_by_role(primary_role.name)
        
        # Отправляем новое сообщение с правильной клавиатурой
        await callback.message.answer(
            "🔄 <b>Клавиатура обновлена</b>\n\n"
            "Твоя клавиатура обновлена согласно текущей роли. Используй кнопки для навигации по системе.",
            parse_mode="HTML",
            reply_markup=keyboard
        )
        
        # Удаляем старое inline сообщение
        try:
            await callback.message.delete()
        except:
            pass
        
        # Очищаем состояние
        await state.clear()
        await callback.answer()
        
        # Логируем действие
        log_user_action(callback.from_user.id, callback.from_user.username, "reloaded_menu")
        
    except Exception as e:
        logger.error(f"Ошибка в process_reload_menu: {e}")
        await callback.answer("❌ Ошибка при обновлении клавиатуры", show_alert=True)
