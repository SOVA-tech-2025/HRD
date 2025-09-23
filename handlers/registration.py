from aiogram import Router, F, Bot
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from sqlalchemy.ext.asyncio import AsyncSession
import os

from database.db import get_user_by_tg_id, create_user, create_user_without_role, check_phone_exists, create_initial_admin_with_token, get_users_by_role, validate_admin_token
from keyboards.keyboards import get_contact_keyboard, get_role_selection_keyboard
from states.states import RegistrationStates
from utils.validators import validate_full_name, validate_phone_number
from utils.logger import log_user_action, log_user_error

router = Router()

async def get_admin_settings() -> tuple[int, str]:
    """Получает настройки администраторов из переменных окружения"""
    max_admins = int(os.getenv("MAX_ADMINS", "5"))
    admin_tokens_str = os.getenv("ADMIN_INIT_TOKENS", os.getenv("ADMIN_INIT_TOKEN", ""))
    return max_admins, admin_tokens_str

async def show_admin_token_prompt(message: Message, state: FSMContext, max_admins: int, existing_managers: list):
    """Показывает сообщение о возможности ввода токена администратора"""
    if len(existing_managers) == 0:
        # Если нет ни одного админа - это первый
        await message.answer(
            "🔐 <b>Регистрация администратора</b>\n\n"
            "Для получения прав администратора введите токен инициализации. "
            "Если у вас нет токена, нажмите кнопку 'Пропустить'.\n\n"
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
            f"В системе уже есть {len(existing_managers)} администратор(ов).\n\n"
            "Если у вас есть токен администратора, введите его. "
            "Если нет - нажмите кнопку 'Пропустить'.\n\n"
            "Введите токен инициализации:",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="⏭️ Пропустить", callback_data="admin_token:skip")]
            ])
        )
    await state.set_state(RegistrationStates.waiting_for_admin_token)

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
    max_admins, admin_tokens_str = await get_admin_settings()
    existing_managers = await get_users_by_role(session, "Руководитель")
    allow_auto_role = os.getenv("ALLOW_AUTO_ROLE_ASSIGNMENT", "false").lower() == "true"

    # ПРИОРИТЕТ 1: Если есть токены админов и не достигнут лимит - ВСЕГДА показываем возможность стать админом
    if admin_tokens_str and len(existing_managers) < max_admins:
        await show_admin_token_prompt(message, state, max_admins, existing_managers)
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
            await message.answer(f"Произошла ошибка при автоматической регистрации. Попробуем зарегистрировать вас для активации рекрутером.")
    
    # Создаем пользователя без роли для последующей активации рекрутером
    user_data = await state.get_data()
    user_data['tg_id'] = message.from_user.id
    user_data['username'] = message.from_user.username
    
    try:
        await create_user_without_role(session, user_data, bot)
        
        await message.answer(
            "✅ Регистрация завершена!\n\n"
            "Ваши данные переданы рекрутеру для активации доступа к чат-боту.\n"
            "Ожидайте подтверждения. Вам придет уведомление, как только доступ будет открыт."
        )
        
        log_user_action(
            message.from_user.id, 
            message.from_user.username, 
            "registration completed (waiting activation)", 
            {"full_name": user_data['full_name'], "phone": user_data['phone_number']}
        )
        
        await state.clear()
        
    except Exception as e:
        log_user_error(message.from_user.id, message.from_user.username, "registration error", str(e))
        await message.answer(
            "❌ Произошла ошибка при регистрации. Попробуйте еще раз позже или обратитесь к администратору."
        )
        await state.clear()

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
    max_admins, admin_tokens_str = await get_admin_settings()
    existing_managers = await get_users_by_role(session, "Руководитель")
    allow_auto_role = os.getenv("ALLOW_AUTO_ROLE_ASSIGNMENT", "false").lower() == "true"

    # ПРИОРИТЕТ 1: Если есть токены админов и не достигнут лимит - ВСЕГДА показываем возможность стать админом
    if admin_tokens_str and len(existing_managers) < max_admins:
        await show_admin_token_prompt(message, state, max_admins, existing_managers)
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
            await message.answer(f"Произошла ошибка при автоматической регистрации. Попробуем зарегистрировать вас для активации рекрутером.")
    
    # Создаем пользователя без роли для последующей активации рекрутером
    user_data = await state.get_data()
    user_data['tg_id'] = message.from_user.id
    user_data['username'] = message.from_user.username
    
    try:
        await create_user_without_role(session, user_data, bot)
        
        await message.answer(
            "✅ Регистрация завершена!\n\n"
            "Ваши данные переданы рекрутеру для активации доступа к чат-боту.\n"
            "Ожидайте подтверждения. Вам придет уведомление, как только доступ будет открыт."
        )
        
        log_user_action(
            message.from_user.id, 
            message.from_user.username, 
            "registration completed (waiting activation)", 
            {"full_name": user_data['full_name'], "phone": user_data['phone_number']}
        )
        
        await state.clear()
        
    except Exception as e:
        log_user_error(message.from_user.id, message.from_user.username, "registration error", str(e))
        await message.answer(
            "❌ Произошла ошибка при регистрации. Попробуйте еще раз позже или обратитесь к администратору."
        )
        await state.clear()

@router.callback_query(RegistrationStates.waiting_for_admin_token, F.data == "admin_token:skip")
async def process_skip_admin_token(callback: CallbackQuery, state: FSMContext, session: AsyncSession, bot: Bot):
    """Обработка пропуска токена администратора"""
    # Создаем пользователя без роли для последующей активации рекрутером
    user_data = await state.get_data()
    user_data['tg_id'] = callback.from_user.id
    user_data['username'] = callback.from_user.username
    
    try:
        await create_user_without_role(session, user_data, bot)
        
        await callback.message.edit_text(
            "✅ Регистрация завершена!\n\n"
            "Ваши данные переданы рекрутеру для активации доступа к чат-боту.\n"
            "Ожидайте подтверждения. Вам придет уведомление, как только доступ будет открыт."
        )
        
        log_user_action(
            callback.from_user.id, 
            callback.from_user.username, 
            "registration completed (waiting activation, skipped admin token)", 
            {"full_name": user_data['full_name'], "phone": user_data['phone_number']}
        )
        
        await state.clear()
        
    except Exception as e:
        log_user_error(callback.from_user.id, callback.from_user.username, "registration error", str(e))
        await callback.message.edit_text(
            "❌ Произошла ошибка при регистрации. Попробуйте еще раз позже или обратитесь к администратору."
        )
        await state.clear()
    
    await callback.answer()

@router.message(RegistrationStates.waiting_for_admin_token)
async def process_admin_token(message: Message, state: FSMContext, session: AsyncSession, bot: Bot):
    """Обработка токена администратора"""
    if message.text.lower() == 'пропустить':
        # Создаем пользователя без роли для последующей активации рекрутером
        user_data = await state.get_data()
        user_data['tg_id'] = message.from_user.id
        user_data['username'] = message.from_user.username
        
        try:
            await create_user_without_role(session, user_data, bot)
            
            await message.answer(
                "✅ Регистрация завершена!\n\n"
                "Ваши данные переданы рекрутеру для активации доступа к чат-боту.\n"
                "Ожидайте подтверждения. Вам придет уведомление, как только доступ будет открыт."
            )
            
            log_user_action(
                message.from_user.id, 
                message.from_user.username, 
                "registration completed (waiting activation, skipped admin token)", 
                {"full_name": user_data['full_name'], "phone": user_data['phone_number']}
            )
            
            await state.clear()
            
        except Exception as e:
            log_user_error(message.from_user.id, message.from_user.username, "registration error", str(e))
            await message.answer(
                "❌ Произошла ошибка при регистрации. Попробуйте еще раз позже или обратитесь к администратору."
            )
            await state.clear()
        return
    
    user_data = await state.get_data()
    user_data['tg_id'] = message.from_user.id
    user_data['username'] = message.from_user.username
    
    # Проверяем токен
    from database.db import validate_admin_token
    if await validate_admin_token(session, message.text.strip()):
        # Токен верный, предлагаем выбрать роль
        await message.answer(
            "🎉 <b>Токен администратора принят!</b>\n\n"
            "Теперь выберите роль, которую вы хотите получить:",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [
                    InlineKeyboardButton(text="👑 Руководитель", callback_data="select_admin_role:Руководитель"),
                    InlineKeyboardButton(text="👨‍💼 Рекрутер", callback_data="select_admin_role:Рекрутер")
                ],
                [
                    InlineKeyboardButton(text="🚫 Отменить", callback_data="cancel_admin_role_selection")
                ]
            ])
        )
        await state.set_state(RegistrationStates.waiting_for_admin_role_selection)
        log_user_action(
            message.from_user.id,
            message.from_user.username,
            "admin_token_validated",
            {"full_name": user_data['full_name']}
        )
    else:
        # Токен неверный - создаем пользователя без роли для последующей активации рекрутером
        try:
            await create_user_without_role(session, user_data, bot)
            
            await message.answer(
                "❌ <b>Неверный токен или достигнут лимит</b>\n\n"
                "Токен инициализации неверный или достигнут лимит администраторов.\n\n"
                "✅ Регистрация завершена!\n\n"
                "Ваши данные переданы рекрутеру для активации доступа к чат-боту.\n"
                "Ожидайте подтверждения. Вам придет уведомление, как только доступ будет открыт.",
                parse_mode="HTML"
            )
            
            log_user_action(
                message.from_user.id, 
                message.from_user.username, 
                "registration completed (waiting activation, invalid admin token)", 
                {"full_name": user_data['full_name'], "phone": user_data['phone_number']}
            )
            
            await state.clear()
            
        except Exception as e:
            log_user_error(message.from_user.id, message.from_user.username, "registration error", str(e))
            await message.answer(
                "❌ Произошла ошибка при регистрации. Попробуйте еще раз позже или обратитесь к администратору."
            )
            await state.clear()

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
    max_admins, admin_tokens_str = await get_admin_settings()
    existing_managers = await get_users_by_role(session, "Руководитель")
    
    # Если есть токены, проверяем введенный текст как потенциальный токен
    if admin_tokens_str:
        user_data = await state.get_data()
        user_data['tg_id'] = message.from_user.id
        user_data['username'] = message.from_user.username

        # Проверяем токен
        from database.db import validate_admin_token
        if await validate_admin_token(session, message.text.strip()):
            # Токен верный, предлагаем выбрать роль
            await message.answer(
                "🎉 <b>Токен администратора принят!</b>\n\n"
                "Теперь выберите роль, которую вы хотите получить:",
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [
                        InlineKeyboardButton(text="👑 Руководитель", callback_data="select_admin_role:Руководитель"),
                        InlineKeyboardButton(text="👨‍💼 Рекрутер", callback_data="select_admin_role:Рекрутер")
                    ],
                    [
                        InlineKeyboardButton(text="🚫 Отменить", callback_data="cancel_admin_role_selection")
                    ]
                ])
            )
            await state.set_state(RegistrationStates.waiting_for_admin_role_selection)
            log_user_action(
                message.from_user.id,
                message.from_user.username,
                "admin_token_validated",
                {"full_name": user_data['full_name']}
            )
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


@router.callback_query(F.data.startswith("select_admin_role:"), RegistrationStates.waiting_for_admin_role_selection)
async def callback_select_admin_role(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Обработчик выбора роли администратора"""
    role_name = callback.data.split(":")[1]

    # Получаем данные пользователя
    user_data = await state.get_data()
    user_data['tg_id'] = callback.from_user.id
    user_data['username'] = callback.from_user.username

    # Создаем администратора с выбранной ролью
    from database.db import create_admin_with_role
    success = await create_admin_with_role(session, user_data, role_name)

    if success:
        role_display = "👑 Руководителем" if role_name == "Руководитель" else "👨‍💼 Рекрутером"

        await callback.message.edit_text(
            f"🎉 <b>Поздравляем!</b>\n\n"
            f"Вы успешно стали {role_display} системы.\n"
            "Используйте команду /login для входа.",
            parse_mode="HTML"
        )
        log_user_action(
            callback.from_user.id,
            callback.from_user.username,
            f"admin_created_with_role_{role_name}",
            {"full_name": user_data['full_name'], "role": role_name}
        )
        await state.clear()
    else:
        await callback.message.edit_text(
            "❌ <b>Ошибка создания администратора</b>\n\n"
            "Произошла ошибка при создании учетной записи администратора.\n"
            "Попробуйте позже или обратитесь к разработчику.",
            parse_mode="HTML"
        )

    await callback.answer()


@router.callback_query(F.data == "cancel_admin_role_selection", RegistrationStates.waiting_for_admin_role_selection)
async def callback_cancel_admin_role_selection(callback: CallbackQuery, state: FSMContext):
    """Обработчик отмены выбора роли администратора"""
    await callback.message.edit_text(
        "🚫 <b>Регистрация администратора отменена</b>\n\n"
        "Вы можете начать регистрацию заново с помощью команды /register.",
        parse_mode="HTML"
    )
    await state.clear()
    await callback.answer() 