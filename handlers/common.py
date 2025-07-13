from aiogram import Router, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from database.db import get_user_by_tg_id, get_user_roles, check_user_permission
from handlers.auth import check_auth
from keyboards.keyboards import format_help_message

router = Router()

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
            role = roles[0].name if roles else "Неавторизованный"
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
        await message.answer("У вас нет прав для просмотра профиля.")
        return
    
    roles = await get_user_roles(session, user.id)
    roles_str = ", ".join([role.name for role in roles])
    
    profile_text = f"""
    📱 <b>Профиль пользователя</b>
    
    🧑 ФИО: {user.full_name}
    📞 Телефон: {user.phone_number}
    🆔 Telegram ID: {user.tg_id}
    👤 Username: @{user.username or "не указан"}
    📅 Дата регистрации: {user.registration_date.strftime('%d.%m.%Y %H:%M')}
    👑 Роли: {roles_str}
    """
    
    await message.answer(profile_text, parse_mode="HTML")

@router.message(F.text == "Мой профиль")
async def button_profile(message: Message, state: FSMContext, session: AsyncSession):
    await cmd_profile(message, state, session)

@router.message(F.text == "Помощь")
async def button_help(message: Message, state: FSMContext, session: AsyncSession):
    await cmd_help(message, state, session)

@router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext):
    """Отмена текущей операции и очистка состояния"""
    current_state = await state.get_state()
    
    if current_state:
        await state.clear()
        await message.answer(
            "✅ <b>Операция отменена</b>\n\n"
            "Все введенные данные сброшены. Вы можете начать заново.\n\n"
            "Используйте <code>/start</code> для перехода в главное меню.",
            parse_mode="HTML"
        )
    else:
        await message.answer(
            "ℹ️ <b>Нет активных операций</b>\n\n"
            "У вас нет текущих операций для отмены.\n\n"
            "Используйте <code>/start</code> для перехода в главное меню.",
            parse_mode="HTML"
        ) 