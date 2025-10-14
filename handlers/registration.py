from aiogram import Router, F
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
            "Если ты сюда попал случайно, просто вернись назад ⬅️\n"
            "Этот шаг нужен только тем, кому рекрутер выдал специальный код\n\n"
            "Если есть код, введи его ниже\n\n"
            "Если кода нет, но хочешь зарегистрироваться - нажми ⏭️ Пропустить",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="⏭️ Пропустить", callback_data="admin_token:skip")],
                [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_welcome")]
            ])
        )
    else:
        # Есть админы, но можно добавить еще
        await message.answer(
            "Если ты сюда попал случайно, просто вернись назад ⬅️\n"
            "Этот шаг нужен только тем, кому рекрутер выдал специальный код\n\n"
            "Если есть код, введи его ниже\n\n"
            "Если кода нет, но хочешь зарегистрироваться - нажми ⏭️ Пропустить",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="⏭️ Пропустить", callback_data="admin_token:skip")],
                [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_welcome")]
            ])
        )
    await state.set_state(RegistrationStates.waiting_for_admin_token)

@router.message(Command("register"))
async def cmd_register(message: Message, state: FSMContext, session: AsyncSession):
    user = await get_user_by_tg_id(session, message.from_user.id)
    
    if user:
        await message.answer("Ты уже зарегистрирован в системе. Используй команду /login для входа.")
        log_user_action(message.from_user.id, message.from_user.username, "attempted to register again")
        return
    
    await message.answer("Начинаем регистрацию 🚩\nПожалуйста, введи свою фамилию и имя\n\nПример: Иванов Иван")
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
        "Спасибо!\nТеперь отправь свой номер: можешь просто нажать кнопку Отправить контакт или написать вручную в формате +7XXXXXXXXXX",
        reply_markup=get_contact_keyboard()
    )
    await state.set_state(RegistrationStates.waiting_for_phone)

@router.message(RegistrationStates.waiting_for_phone, F.contact)
async def process_contact(message: Message, state: FSMContext, session: AsyncSession, bot):
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

    # Проверяем, пришел ли пользователь через сценарий "У меня есть код"
    user_data = await state.get_data()
    
    if user_data.get('registration_flow') == 'code_first':
        # Пользователь из сценария "code_first"
        user_data['tg_id'] = message.from_user.id
        user_data['username'] = message.from_user.username
        
        try:
            if user_data.get('selected_admin_role'):
                # Роль администратора уже выбрана - создаем администратора
                from database.db import create_admin_with_role
                success = await create_admin_with_role(session, user_data, user_data['selected_admin_role'])
                
                if success:
                    role_display = "👑 Руководителем" if user_data['selected_admin_role'] == "Руководитель" else "👨‍💼 Рекрутером"
                    
                    await message.answer(
                        f"🎉 <b>Поздравляем!</b>\n\n"
                        f"Ты успешно стал {role_display} системы.\n"
                        "Используй команду /login для входа.",
                        parse_mode="HTML"
                    )
                    
                    log_user_action(
                        message.from_user.id,
                        message.from_user.username,
                        f"admin_created_with_role_{user_data['selected_admin_role']}_from_code_first",
                        {"full_name": user_data['full_name'], "phone": user_data['phone_number'], "role": user_data['selected_admin_role']}
                    )
                    await state.clear()
                    return
                else:
                    await message.answer("❌ Произошла ошибка при создании администратора. Попробуй еще раз позже.")
                    await state.clear()
                    return
            else:
                # Роль не выбрана (токен был неверный) - создаем пользователя без роли
                await create_user_without_role(session, user_data, bot)
                
                await message.answer(
                    "✅Регистрация завершена!\n\n"
                    "Данные отправлены рекрутеру на проверку. Тебе придет уведомление, как только доступ активируют, и дальше сразу можно будет пользоваться ботом"
                )
                
                log_user_action(message.from_user.id, message.from_user.username, "registration completed from code_first flow", {"full_name": user_data['full_name'], "phone": user_data['phone_number']})
                await state.clear()
                return
                
        except Exception as e:
            log_user_error(message.from_user.id, message.from_user.username, "registration error from code_first flow", str(e))
            await message.answer("❌ Произошла ошибка при регистрации. Попробуй еще раз позже или обратись к администратору.")
            await state.clear()
            return

    # Проверяем настройки для показа опции токена администратора (только для обычной регистрации)
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
                    f"Ты автоматически зарегистрирован как <b>{default_role}</b>.\n"
                    f"Ты можешь сразу начать работу - авторизация произойдет автоматически.\n\n"
                    f"При необходимости администратор может изменить твою роль.",
                    parse_mode="HTML"
                )
            else:
                await message.answer(
                    f"🎉 <b>Добро пожаловать!</b>\n\n"
                    f"Ты автоматически зарегистрирован как <b>{default_role}</b>.\n"
                    f"Используйте команду /login для входа.\n\n"
                    f"При необходимости администратор может изменить твою роль.",
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
            await message.answer(f"Произошла ошибка при автоматической регистрации. Попробуем зарегистрировать тебя для активации рекрутером.")
    
    # Создаем пользователя без роли для последующей активации рекрутером
    user_data = await state.get_data()
    user_data['tg_id'] = message.from_user.id
    user_data['username'] = message.from_user.username
    
    try:
        await create_user_without_role(session, user_data, bot)
        
        await message.answer(
            "✅Регистрация завершена!\n\n"
            "Данные отправлены рекрутеру на проверку. Тебе придет уведомление, как только доступ активируют, и дальше сразу можно будет пользоваться ботом"
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
            "❌ Произошла ошибка при регистрации. Попробуй еще раз позже или обратись к администратору."
        )
        await state.clear()

@router.message(RegistrationStates.waiting_for_phone)
async def process_phone_manually(message: Message, state: FSMContext, session: AsyncSession, bot):
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

    # Проверяем, пришел ли пользователь через сценарий "У меня есть код"
    user_data = await state.get_data()
    
    if user_data.get('registration_flow') == 'code_first':
        # Пользователь из сценария "code_first"
        user_data['tg_id'] = message.from_user.id
        user_data['username'] = message.from_user.username
        
        try:
            if user_data.get('selected_admin_role'):
                # Роль администратора уже выбрана - создаем администратора
                from database.db import create_admin_with_role
                success = await create_admin_with_role(session, user_data, user_data['selected_admin_role'])
                
                if success:
                    role_display = "👑 Руководителем" if user_data['selected_admin_role'] == "Руководитель" else "👨‍💼 Рекрутером"
                    
                    await message.answer(
                        f"🎉 <b>Поздравляем!</b>\n\n"
                        f"Ты успешно стал {role_display} системы.\n"
                        "Используй команду /login для входа.",
                        parse_mode="HTML"
                    )
                    
                    log_user_action(
                        message.from_user.id,
                        message.from_user.username,
                        f"admin_created_with_role_{user_data['selected_admin_role']}_from_code_first",
                        {"full_name": user_data['full_name'], "phone": user_data['phone_number'], "role": user_data['selected_admin_role']}
                    )
                    await state.clear()
                    return
                else:
                    await message.answer("❌ Произошла ошибка при создании администратора. Попробуй еще раз позже.")
                    await state.clear()
                    return
            else:
                # Роль не выбрана (токен был неверный) - создаем пользователя без роли
                await create_user_without_role(session, user_data, bot)
                
                await message.answer(
                    "✅Регистрация завершена!\n\n"
                    "Данные отправлены рекрутеру на проверку. Тебе придет уведомление, как только доступ активируют, и дальше сразу можно будет пользоваться ботом"
                )
                
                log_user_action(message.from_user.id, message.from_user.username, "registration completed from code_first flow", {"full_name": user_data['full_name'], "phone": user_data['phone_number']})
                await state.clear()
                return
                
        except Exception as e:
            log_user_error(message.from_user.id, message.from_user.username, "registration error from code_first flow", str(e))
            await message.answer("❌ Произошла ошибка при регистрации. Попробуй еще раз позже или обратись к администратору.")
            await state.clear()
            return

    # Проверяем настройки для показа опции токена администратора (только для обычной регистрации)
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
                    f"Ты автоматически зарегистрирован как <b>{default_role}</b>.\n"
                    f"Ты можешь сразу начать работу - авторизация произойдет автоматически.\n\n"
                    f"При необходимости администратор может изменить твою роль.",
                    parse_mode="HTML"
                )
            else:
                await message.answer(
                    f"🎉 <b>Добро пожаловать!</b>\n\n"
                    f"Ты автоматически зарегистрирован как <b>{default_role}</b>.\n"
                    f"Используйте команду /login для входа.\n\n"
                    f"При необходимости администратор может изменить твою роль.",
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
            await message.answer(f"Произошла ошибка при автоматической регистрации. Попробуем зарегистрировать тебя для активации рекрутером.")
    
    # Создаем пользователя без роли для последующей активации рекрутером
    user_data = await state.get_data()
    user_data['tg_id'] = message.from_user.id
    user_data['username'] = message.from_user.username
    
    try:
        await create_user_without_role(session, user_data, bot)
        
        await message.answer(
            "✅Регистрация завершена!\n\n"
            "Данные отправлены рекрутеру на проверку. Тебе придет уведомление, как только доступ активируют, и дальше сразу можно будет пользоваться ботом"
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
            "❌ Произошла ошибка при регистрации. Попробуй еще раз позже или обратись к администратору."
        )
        await state.clear()

@router.callback_query(RegistrationStates.waiting_for_admin_token, F.data == "admin_token:skip")
async def process_skip_admin_token(callback: CallbackQuery, state: FSMContext, session: AsyncSession, bot):
    """Обработка пропуска токена администратора (только для обычной регистрации)"""
    user_data = await state.get_data()
    
    # Этот обработчик только для обычной регистрации
    # В сценарии "code_first" кнопки "Пропустить" нет
    user_data['tg_id'] = callback.from_user.id
    user_data['username'] = callback.from_user.username
    
    try:
        await create_user_without_role(session, user_data, bot)
        
        await callback.message.edit_text(
            "✅Регистрация завершена!\n\n"
            "Данные отправлены рекрутеру на проверку. Тебе придет уведомление, как только доступ активируют, и дальше сразу можно будет пользоваться ботом"
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
            "❌ Произошла ошибка при регистрации. Попробуй еще раз позже или обратись к администратору."
        )
        await state.clear()
    
    await callback.answer()

@router.message(RegistrationStates.waiting_for_admin_token)
async def process_admin_token(message: Message, state: FSMContext, session: AsyncSession, bot):
    """Обработка токена администратора"""
    user_data = await state.get_data()
    
    if message.text.lower() == 'пропустить':
        # Команда "пропустить" только для обычной регистрации
        # В сценарии "code_first" такой возможности нет
        if user_data.get('registration_flow') == 'code_first':
            await message.answer(
                "❌ В этом режиме регистрации нужно ввести токен или вернуться назад.\n"
                "Используй кнопку \"⬅️ Назад\" для возврата к выбору типа регистрации."
            )
            return
        else:
            # Обычная регистрация - создаем пользователя без роли
            user_data['tg_id'] = message.from_user.id
            user_data['username'] = message.from_user.username
            
            try:
                await create_user_without_role(session, user_data, bot)
                
                await message.answer(
                    "✅Регистрация завершена!\n\n"
                    "Данные отправлены рекрутеру на проверку. Тебе придет уведомление, как только доступ активируют, и дальше сразу можно будет пользоваться ботом"
                )
                
                log_user_action(
                    message.from_user.id, 
                    message.from_user.username, 
                    "registration completed (waiting activation, skipped admin token)", 
                    {"full_name": user_data['full_name'], "phone": user_data['phone_number']}
                )
                
                await state.clear()
                return
                
            except Exception as e:
                log_user_error(message.from_user.id, message.from_user.username, "registration error", str(e))
                await message.answer(
                    "❌ Произошла ошибка при регистрации. Попробуй еще раз позже или обратись к администратору."
                )
                await state.clear()
                return
    
    user_data['tg_id'] = message.from_user.id
    user_data['username'] = message.from_user.username
    
    # Проверяем токен
    from database.db import validate_admin_token
    if await validate_admin_token(session, message.text.strip()):
        # Токен верный
        if user_data.get('registration_flow') == 'code_first':
            # Регистрация с кода - предлагаем выбрать роль администратора
            await message.answer(
                "🎉 <b>Токен администратора принят!</b>\n\n"
                    "Теперь выбери роль, которую ты хочешь получить:",
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
            log_user_action(message.from_user.id, message.from_user.username, "admin_token_validated in code_first flow, selecting admin role")
        else:
            # Обычная регистрация - предлагаем выбрать роль администратора
            await message.answer(
                "🎉 <b>Токен администратора принят!</b>\n\n"
                    "Теперь выбери роль, которую ты хочешь получить:",
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
                "admin_token_validated in normal flow",
                {"full_name": user_data['full_name']}
            )
    else:
        # Токен неверный
        if user_data.get('registration_flow') == 'code_first':
            # Регистрация с кода - показываем ошибку и предлагаем попробовать снова или вернуться
            await message.answer(
                "❌ <b>Неверный токен</b>\n\n"
                "Токен инициализации неверный или недействительный.\n"
                "Попробуй ввести токен еще раз или используй кнопку \"⬅️ Назад\" для возврата к выбору типа регистрации.",
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_welcome")]
                ])
            )
            
            log_user_action(message.from_user.id, message.from_user.username, "invalid admin token in code_first flow")
        else:
            # Обычная регистрация - показываем ошибку и предлагаем попробовать снова, пропустить или вернуться
            await message.answer(
                "❌ <b>Неверный токен</b>\n\n"
                "Токен инициализации неверный или недействительный.\n"
                "Попробуй ввести токен еще раз или используй кнопку \"⬅️ Назад\" для возврата к выбору типа регистрации.\n\n"
                "Если кода нет, но хочешь зарегистрироваться - нажми ⏭️ Пропустить",
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="⏭️ Пропустить", callback_data="admin_token:skip")],
                    [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_welcome")]
                ])
            )
            
            log_user_action(message.from_user.id, message.from_user.username, "invalid admin token in normal flow")

@router.callback_query(RegistrationStates.waiting_for_role, F.data.startswith("role:"))
async def process_role_selection(callback: CallbackQuery, state: FSMContext, session: AsyncSession, bot):
    selected_role = callback.data.split(':')[1]
    
    user_data = await state.get_data()
    
    user_data['tg_id'] = callback.from_user.id
    user_data['username'] = callback.from_user.username
    
    try:
        await create_user(session, user_data, selected_role, bot)
        
        auto_auth_allowed = os.getenv("ALLOW_AUTO_AUTH", "true").lower() == "true"
        if auto_auth_allowed:
            await callback.message.answer(f"🎉 Поздравляем! Ты успешно зарегистрирован как {selected_role}.\n\nТы можешь сразу начать работу - авторизация произойдет автоматически.")
        else:
            await callback.message.answer(f"🎉 Поздравляем! Ты успешно зарегистрирован как {selected_role}.\n\nИспользуй команду /login для входа.")
        
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
        await callback.message.answer(f"Произошла ошибка при регистрации. Пожалуйста, попробуй позже или обратись к рекрутеру.")
    
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
                    "Теперь выбери роль, которую ты хочешь получить:",
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
        "Пожалуйста, отправь свой номер телефона через кнопку 'Отправить контакт' или введи номер в формате +7XXXXXXXXXX.",
        reply_markup=get_contact_keyboard()
    )

@router.message(RegistrationStates.waiting_for_full_name)
async def full_name_error(message: Message):
    await message.answer("Пожалуйста, введи свою фамилию и имя, используя только буквы, пробелы и дефисы.\n\nПример: Иванов Иван")


@router.callback_query(F.data.startswith("select_admin_role:"), RegistrationStates.waiting_for_admin_role_selection)
async def callback_select_admin_role(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Обработчик выбора роли администратора"""
    role_name = callback.data.split(":")[1]

    # Получаем данные пользователя
    user_data = await state.get_data()
    
    # Проверяем тип регистрации
    if user_data.get('registration_flow') == 'code_first':
        # Регистрация с кода - сохраняем роль и переходим к ФИО
        await state.update_data(selected_admin_role=role_name)
        
        role_display = "👑 Руководителя" if role_name == "Руководитель" else "👨‍💼 Рекрутера"
        
        await callback.message.edit_text(
            f"✅ Выбрана роль {role_display}\n\n"
            "Начинаем регистрацию 🚩\nПожалуйста, введи свою фамилию и имя\n\nПример: Иванов Иван"
        )
        await state.set_state(RegistrationStates.waiting_for_full_name)
        
        log_user_action(callback.from_user.id, callback.from_user.username, f"selected_admin_role_{role_name}_in_code_first_flow")
        await callback.answer()
    else:
        # Обычная регистрация - создаем администратора сразу
        user_data['tg_id'] = callback.from_user.id
        user_data['username'] = callback.from_user.username

        # Создаем администратора с выбранной ролью
        from database.db import create_admin_with_role
        success = await create_admin_with_role(session, user_data, role_name)

        if success:
            role_display = "👑 Руководителем" if role_name == "Руководитель" else "👨‍💼 Рекрутером"

            await callback.message.edit_text(
                f"🎉 <b>Поздравляем!</b>\n\n"
                f"Ты успешно стал {role_display} системы.\n"
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
        "Ты можешь начать регистрацию заново с помощью команды /register.",
        parse_mode="HTML"
    )
    await state.clear()
    await callback.answer() 