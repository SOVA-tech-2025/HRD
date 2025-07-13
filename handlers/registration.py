from aiogram import Router, F, Bot
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from sqlalchemy.ext.asyncio import AsyncSession
import os

from database.db import get_user_by_tg_id, create_user, check_phone_exists, create_initial_admin_with_token, get_users_by_role
from keyboards.keyboards import get_contact_keyboard, get_role_selection_keyboard
from states.states import RegistrationStates
from utils.validators import validate_full_name, validate_phone_number
from utils.logger import log_user_action, log_user_error

router = Router()

@router.message(Command("register"))
async def cmd_register(message: Message, state: FSMContext, session: AsyncSession):
    user = await get_user_by_tg_id(session, message.from_user.id)
    
    if user:
        await message.answer("Вы уже зарегистрированы в системе. Используйте команду /login для входа.")
        log_user_action(message.from_user.id, message.from_user.username, "attempted to register again")
        return
    
    await message.answer("Начинаем регистрацию! Пожалуйста, введите ваше ФИО (имя и фамилию).")
    await state.set_state(RegistrationStates.waiting_for_full_name)
    log_user_action(message.from_user.id, message.from_user.username, "started registration")

@router.message(RegistrationStates.waiting_for_full_name)
async def process_full_name(message: Message, state: FSMContext):
    is_valid, formatted_name = validate_full_name(message.text)
    
    if not is_valid:
        await message.answer(
            "Некорректный формат ФИО. Пожалуйста, введите имя и фамилию, используя только буквы, пробелы и дефисы."
        )
        log_user_error(message.from_user.id, message.from_user.username, f"invalid full name: {message.text}")
        return
    
    await state.update_data(full_name=formatted_name)
    log_user_action(message.from_user.id, message.from_user.username, "provided full name", {"full_name": formatted_name})
    
    await message.answer(
        "Спасибо! Теперь, пожалуйста, отправьте свой номер телефона. "
        "Вы можете нажать на кнопку 'Отправить контакт' или ввести номер вручную в формате +7XXXXXXXXXX.",
        reply_markup=get_contact_keyboard()
    )
    await state.set_state(RegistrationStates.waiting_for_phone)

@router.message(RegistrationStates.waiting_for_phone, F.contact)
async def process_contact(message: Message, state: FSMContext, session: AsyncSession, bot: Bot):
    phone_number = message.contact.phone_number
    
    is_valid, normalized_phone = validate_phone_number(phone_number)
    
    if not is_valid:
        await message.answer(
            "Некорректный формат номера телефона. Пожалуйста, введите номер в формате +7XXXXXXXXXX.",
            reply_markup=get_contact_keyboard()
        )
        log_user_error(message.from_user.id, message.from_user.username, f"invalid phone from contact: {phone_number}")
        return
    
    if await check_phone_exists(session, normalized_phone):
        await message.answer(
            "Этот номер телефона уже зарегистрирован в системе. "
            "Один пользователь не может регистрироваться с разных аккаунтов Telegram."
        )
        log_user_error(message.from_user.id, message.from_user.username, f"attempted to register with existing phone: {normalized_phone}")
        await state.clear()
        return
    
    await state.update_data(phone_number=normalized_phone)
    log_user_action(message.from_user.id, message.from_user.username, "provided phone via contact", {"phone": normalized_phone})
    
    # Проверяем настройки для показа опции токена администратора
    import os
    max_admins = int(os.getenv("MAX_ADMINS", "5"))
    existing_managers = await get_users_by_role(session, "Управляющий")
    admin_tokens_str = os.getenv("ADMIN_INIT_TOKENS", os.getenv("ADMIN_INIT_TOKEN", ""))
    allow_auto_role = os.getenv("ALLOW_AUTO_ROLE_ASSIGNMENT", "false").lower() == "true"
    
    # ПРИОРИТЕТ 1: Если есть токены админов и не достигнут лимит - ВСЕГДА показываем возможность стать админом
    if admin_tokens_str and len(existing_managers) < max_admins:
        if len(existing_managers) == 0:
            # Если нет ни одного админа - это первый
            await message.answer(
                "🔐 <b>Инициализация системы</b>\n\n"
                "В системе еще нет администраторов. Если вы хотите стать первым администратором, "
                "введите токен инициализации. Если у вас нет токена, нажмите кнопку 'Пропустить'.\n\n"
                "Введите токен инициализации:",
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="⏭️ Пропустить", callback_data="admin_token:skip")]
                ])
            )
        else:
            # Есть админы, но можно добавить еще
            await message.answer(
                "🔐 <b>Регистрация администратора</b>\n\n"
                f"В системе уже есть {len(existing_managers)} администратор(ов), можно создать еще {max_admins - len(existing_managers)}.\n\n"
                "Если у вас есть токен администратора, введите его. "
                "Если нет - нажмите кнопку 'Пропустить'.\n\n"
                "Введите токен инициализации:",
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="⏭️ Пропустить", callback_data="admin_token:skip")]
                ])
            )
        await state.set_state(RegistrationStates.waiting_for_admin_token)
        return
    
    # ПРИОРИТЕТ 2: Автоматическое назначение роли (если включено)
    if allow_auto_role:
        # Автоматическое назначение роли по умолчанию
        default_role = os.getenv("DEFAULT_ROLE", "Стажер")
        user_data = await state.get_data()
        user_data['tg_id'] = message.from_user.id
        user_data['username'] = message.from_user.username
        
        try:
            await create_user(session, user_data, default_role, bot)
            
            auto_auth_allowed = os.getenv("ALLOW_AUTO_AUTH", "true").lower() == "true"
            if auto_auth_allowed:
                await message.answer(
                    f"🎉 <b>Добро пожаловать!</b>\n\n"
                    f"Вы автоматически зарегистрированы как <b>{default_role}</b>.\n"
                    f"Вы можете сразу начать работу - авторизация произойдет автоматически.\n\n"
                    f"При необходимости администратор может изменить вашу роль.",
                    parse_mode="HTML"
                )
            else:
                await message.answer(
                    f"🎉 <b>Добро пожаловать!</b>\n\n"
                    f"Вы автоматически зарегистрированы как <b>{default_role}</b>.\n"
                    f"Используйте команду /login для входа.\n\n"
                    f"При необходимости администратор может изменить вашу роль.",
                    parse_mode="HTML"
                )
            
            log_user_action(
                message.from_user.id, 
                message.from_user.username, 
                "auto registration completed", 
                {"role": default_role, "full_name": user_data['full_name']}
            )
            
            await state.clear()
            return
        except Exception as e:
            log_user_error(message.from_user.id, message.from_user.username, "auto registration error", e)
            await message.answer(f"Произошла ошибка при автоматической регистрации. Выберите роль вручную:")
    
    # Если автоматическое назначение отключено или произошла ошибка
    await message.answer(
        "Выберите вашу роль:",
        reply_markup=get_role_selection_keyboard()
    )
    await state.set_state(RegistrationStates.waiting_for_role)

@router.message(RegistrationStates.waiting_for_phone)
async def process_phone_manually(message: Message, state: FSMContext, session: AsyncSession, bot: Bot):
    is_valid, normalized_phone = validate_phone_number(message.text)
    
    if not is_valid:
        await message.answer(
            "Некорректный формат номера телефона. Пожалуйста, введите номер в формате +7XXXXXXXXXX или используйте кнопку 'Отправить контакт'.",
            reply_markup=get_contact_keyboard()
        )
        log_user_error(message.from_user.id, message.from_user.username, f"invalid phone manual entry: {message.text}")
        return
    
    if await check_phone_exists(session, normalized_phone):
        await message.answer(
            "Этот номер телефона уже зарегистрирован в системе. "
            "Один пользователь не может регистрироваться с разных аккаунтов Telegram."
        )
        log_user_error(message.from_user.id, message.from_user.username, f"attempted to register with existing phone: {normalized_phone}")
        await state.clear()
        return
    
    await state.update_data(phone_number=normalized_phone)
    log_user_action(message.from_user.id, message.from_user.username, "provided phone manually", {"phone": normalized_phone})
    
    # Проверяем настройки для показа опции токена администратора
    import os
    max_admins = int(os.getenv("MAX_ADMINS", "5"))
    existing_managers = await get_users_by_role(session, "Управляющий")
    admin_tokens_str = os.getenv("ADMIN_INIT_TOKENS", os.getenv("ADMIN_INIT_TOKEN", ""))
    allow_auto_role = os.getenv("ALLOW_AUTO_ROLE_ASSIGNMENT", "false").lower() == "true"
    
    # ПРИОРИТЕТ 1: Если есть токены админов и не достигнут лимит - ВСЕГДА показываем возможность стать админом
    if admin_tokens_str and len(existing_managers) < max_admins:
        if len(existing_managers) == 0:
            # Если нет ни одного админа - это первый
            await message.answer(
                "🔐 <b>Инициализация системы</b>\n\n"
                "В системе еще нет администраторов. Если вы хотите стать первым администратором, "
                "введите токен инициализации. Если у вас нет токена, нажмите кнопку 'Пропустить'.\n\n"
                "Введите токен инициализации:",
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="⏭️ Пропустить", callback_data="admin_token:skip")]
                ])
            )
        else:
            # Есть админы, но можно добавить еще
            await message.answer(
                "🔐 <b>Регистрация администратора</b>\n\n"
                f"В системе уже есть {len(existing_managers)} администратор(ов), можно создать еще {max_admins - len(existing_managers)}.\n\n"
                "Если у вас есть токен администратора, введите его. "
                "Если нет - нажмите кнопку 'Пропустить'.\n\n"
                "Введите токен инициализации:",
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="⏭️ Пропустить", callback_data="admin_token:skip")]
                ])
            )
        await state.set_state(RegistrationStates.waiting_for_admin_token)
        return
    
    # ПРИОРИТЕТ 2: Автоматическое назначение роли (если включено)
    if allow_auto_role:
        # Автоматическое назначение роли по умолчанию
        default_role = os.getenv("DEFAULT_ROLE", "Стажер")
        user_data = await state.get_data()
        user_data['tg_id'] = message.from_user.id
        user_data['username'] = message.from_user.username
        
        try:
            await create_user(session, user_data, default_role, bot)
            
            auto_auth_allowed = os.getenv("ALLOW_AUTO_AUTH", "true").lower() == "true"
            if auto_auth_allowed:
                await message.answer(
                    f"🎉 <b>Добро пожаловать!</b>\n\n"
                    f"Вы автоматически зарегистрированы как <b>{default_role}</b>.\n"
                    f"Вы можете сразу начать работу - авторизация произойдет автоматически.\n\n"
                    f"При необходимости администратор может изменить вашу роль.",
                    parse_mode="HTML"
                )
            else:
                await message.answer(
                    f"🎉 <b>Добро пожаловать!</b>\n\n"
                    f"Вы автоматически зарегистрированы как <b>{default_role}</b>.\n"
                    f"Используйте команду /login для входа.\n\n"
                    f"При необходимости администратор может изменить вашу роль.",
                    parse_mode="HTML"
                )
            
            log_user_action(
                message.from_user.id, 
                message.from_user.username, 
                "auto registration completed", 
                {"role": default_role, "full_name": user_data['full_name']}
            )
            
            await state.clear()
            return
        except Exception as e:
            log_user_error(message.from_user.id, message.from_user.username, "auto registration error", e)
            await message.answer(f"Произошла ошибка при автоматической регистрации. Выберите роль вручную:")
    
    # Если автоматическое назначение отключено или произошла ошибка
    await message.answer(
        "Выберите вашу роль:",
        reply_markup=get_role_selection_keyboard()
    )
    await state.set_state(RegistrationStates.waiting_for_role)

@router.callback_query(RegistrationStates.waiting_for_admin_token, F.data == "admin_token:skip")
async def process_skip_admin_token(callback: CallbackQuery, state: FSMContext):
    """Обработка пропуска токена администратора"""
    await callback.message.edit_text(
        "Выберите вашу роль:",
        reply_markup=get_role_selection_keyboard()
    )
    await state.set_state(RegistrationStates.waiting_for_role)
    await callback.answer()

@router.message(RegistrationStates.waiting_for_admin_token)
async def process_admin_token(message: Message, state: FSMContext, session: AsyncSession):
    """Обработка токена администратора"""
    if message.text.lower() == 'пропустить':
        await message.answer(
            "Выберите вашу роль:",
            reply_markup=get_role_selection_keyboard()
        )
        await state.set_state(RegistrationStates.waiting_for_role)
        return
    
    user_data = await state.get_data()
    user_data['tg_id'] = message.from_user.id
    user_data['username'] = message.from_user.username
    
    success = await create_initial_admin_with_token(session, user_data, message.text.strip())
    
    if success:
        await message.answer(
            "🎉 <b>Поздравляем!</b>\n\n"
            "Вы успешно стали администратором системы.\n"
            "Используйте команду /login для входа.",
            parse_mode="HTML"
        )
        log_user_action(
            message.from_user.id, 
            message.from_user.username, 
            "became admin", 
            {"full_name": user_data['full_name']}
        )
        await state.clear()
    else:
        await message.answer(
            "❌ <b>Неверный токен или достигнут лимит</b>\n\n"
            "Токен инициализации неверный или достигнут лимит администраторов.\n"
            "Выберите обычную роль:",
            parse_mode="HTML",
            reply_markup=get_role_selection_keyboard()
        )
        await state.set_state(RegistrationStates.waiting_for_role)

@router.callback_query(RegistrationStates.waiting_for_role, F.data.startswith("role:"))
async def process_role_selection(callback: CallbackQuery, state: FSMContext, session: AsyncSession, bot: Bot):
    selected_role = callback.data.split(':')[1]
    
    user_data = await state.get_data()
    
    user_data['tg_id'] = callback.from_user.id
    user_data['username'] = callback.from_user.username
    
    try:
        await create_user(session, user_data, selected_role, bot)
        
        auto_auth_allowed = os.getenv("ALLOW_AUTO_AUTH", "true").lower() == "true"
        if auto_auth_allowed:
            await callback.message.answer(f"🎉 Поздравляем! Вы успешно зарегистрированы как {selected_role}.\n\nВы можете сразу начать работу - авторизация произойдет автоматически.")
        else:
            await callback.message.answer(f"🎉 Поздравляем! Вы успешно зарегистрированы как {selected_role}.\n\nИспользуйте команду /login для входа.")
        
        await callback.message.edit_reply_markup(reply_markup=None)
        
        log_user_action(
            callback.from_user.id, 
            callback.from_user.username, 
            "completed registration", 
            {"role": selected_role, "full_name": user_data['full_name']}
        )
        
        await state.clear()
    except Exception as e:
        log_user_error(callback.from_user.id, callback.from_user.username, "registration error", e)
        await callback.message.answer(f"Произошла ошибка при регистрации. Пожалуйста, попробуйте позже или обратитесь к управляющему.")
    
    await callback.answer()

@router.callback_query(RegistrationStates.waiting_for_role, F.data == "cancel_registration")
async def process_cancel_registration(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    
    await callback.message.answer("Регистрация отменена. Используйте /register, чтобы начать заново.")
    
    await callback.message.edit_reply_markup(reply_markup=None)
    
    log_user_action(callback.from_user.id, callback.from_user.username, "cancelled registration via button")
    
    await callback.answer()

@router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext):
    current_state = await state.get_state()
    if current_state is None:
        await message.answer("Нет активных операций для отмены.")
        return
    
    await state.clear()
    await message.answer("Регистрация отменена. Используйте /register, чтобы начать заново.")
    log_user_action(message.from_user.id, message.from_user.username, "cancelled registration")

@router.message(RegistrationStates.waiting_for_role)
async def role_selection_error(message: Message, state: FSMContext, session: AsyncSession):
    # Проверяем, может быть пользователь пытается ввести токен администратора
    import os
    admin_tokens_str = os.getenv("ADMIN_INIT_TOKENS", os.getenv("ADMIN_INIT_TOKEN", ""))
    max_admins = int(os.getenv("MAX_ADMINS", "5"))
    existing_managers = await get_users_by_role(session, "Управляющий")
    
    # Если есть токены и не достигнут лимит, проверяем введенный текст как потенциальный токен
    if admin_tokens_str and len(existing_managers) < max_admins:
        user_data = await state.get_data()
        user_data['tg_id'] = message.from_user.id
        user_data['username'] = message.from_user.username
        
        success = await create_initial_admin_with_token(session, user_data, message.text.strip())
        
        if success:
            await message.answer(
                "🎉 <b>Поздравляем!</b>\n\n"
                "Вы успешно стали администратором системы.\n"
                "Используйте команду /login для входа.",
                parse_mode="HTML"
            )
            log_user_action(
                message.from_user.id, 
                message.from_user.username, 
                "became admin via fallback", 
                {"full_name": user_data['full_name']}
            )
            await state.clear()
            return
    
    await message.answer("Пожалуйста, выберите роль из предложенного списка.")

@router.message(RegistrationStates.waiting_for_phone)
async def phone_error(message: Message):
    await message.answer(
        "Пожалуйста, отправьте свой номер телефона через кнопку 'Отправить контакт' или введите номер в формате +7XXXXXXXXXX.",
        reply_markup=get_contact_keyboard()
    )

@router.message(RegistrationStates.waiting_for_full_name)
async def full_name_error(message: Message):
    await message.answer("Пожалуйста, введите имя и фамилию, используя только буквы, пробелы и дефисы.") 