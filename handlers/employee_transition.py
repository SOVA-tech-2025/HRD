"""
Обработчики для перехода стажера в сотрудника (Task 7).
Включает переход из роли стажера в роль сотрудника после успешной аттестации.
"""

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession

from database.db import (
    get_user_by_tg_id, change_trainee_to_employee, check_user_permission,
    get_employee_tests_from_recruiter, get_user_test_result
)
from handlers.auth import check_auth
from keyboards.keyboards import get_keyboard_by_role
from utils.logger import log_user_action, log_user_error

router = Router()


# ===============================
# Обработчики для Task 7: Переход стажера в сотрудника
# ===============================

@router.callback_query(F.data == "become_employee")
async def callback_become_employee(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Обработчик кнопки 'Стать сотрудником' после успешной аттестации (ТЗ шаг 12-5)"""
    try:
        await callback.answer()
        
        # Получаем пользователя
        user = await get_user_by_tg_id(session, callback.from_user.id)
        if not user:
            await callback.message.edit_text("❌ Вы не зарегистрированы в системе.")
            return
            
        # Проверяем что пользователь - стажер
        user_roles = [role.name for role in user.roles]
        if "Стажер" not in user_roles:
            await callback.message.edit_text("❌ Только стажеры могут стать сотрудниками.")
            return
            
        # Меняем роль стажера на сотрудника
        success = await change_trainee_to_employee(session, user.id, None)  # attestation_result_id не нужен в данном контексте
        
        if not success:
            await callback.message.edit_text(
                "❌ Произошла ошибка при смене роли.\n"
                "Обратитесь к администратору."
            )
            return
            
        await session.commit()
        
        # Показываем ЛК сотрудника согласно ТЗ (шаг 12-8)
        await show_employee_profile(callback, session, show_congratulation=True)
        
        log_user_action(callback.from_user.id, "became_employee", f"Пользователь {user.full_name} стал сотрудником")
        
    except Exception as e:
        await callback.message.edit_text("Произошла ошибка при переходе в сотрудника")
        log_user_error(callback.from_user.id, "become_employee_error", str(e))


async def show_employee_profile(callback: CallbackQuery, session: AsyncSession, show_congratulation: bool = False):
    """Показ профиля сотрудника согласно ТЗ (шаг 12-8)
    show_congratulation - показывать ли поздравительное сообщение (только при первом переходе)"""
    try:
        # Получаем обновленные данные пользователя
        user = await get_user_by_tg_id(session, callback.from_user.id)
        if not user:
            await callback.message.edit_text("❌ Ошибка получения данных пользователя")
            return
            
        # Формируем сообщение согласно ТЗ
        profile_text = (
            "<b>Ваши данные:</b>\n\n"
            f"🧑 <b>ФИО:</b> {user.full_name}\n"
            f"📞 <b>Телефон:</b> {user.phone_number}\n"
            f"🆔 <b>Telegram ID:</b> {user.tg_id}\n"
            f"👤 <b>Username:</b> @{user.username or 'не указан'}\n"
            f"📅 <b>Дата регистрации:</b> {user.registration_date.strftime('%d.%m.%Y %H:%M')}\n"
            f"👑 <b>Роли:</b> {', '.join([role.name for role in user.roles])}\n"
            f"🗂️<b>Группа:</b> {', '.join([group.name for group in user.groups]) if user.groups else 'Не указана'}\n"
            f"📍<b>2️⃣Объект работы:</b> {user.work_object.name if user.work_object else 'Не указан'}\n"
            f"🎱<b>Номер пользователя:</b> {user.id}"
        )
        
        # Клавиатура для ЛК сотрудника согласно ТЗ
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📚База знаний", callback_data="knowledge_base")]
        ])
        
        await callback.message.edit_text(
            profile_text,
            parse_mode="HTML",
            reply_markup=keyboard
        )

        # Показываем поздравительное сообщение только при первом переходе в сотрудника
        if show_congratulation:
            # Обновляем reply клавиатуру на роль сотрудника
            employee_keyboard = get_keyboard_by_role(["Сотрудник"])

            await callback.message.answer(
                "🎉 <b>Поздравляем!</b> Вы успешно стали сотрудником!",
                parse_mode="HTML",
                reply_markup=employee_keyboard
            )
        
        log_user_action(callback.from_user.id, "employee_profile_shown", "Показан профиль сотрудника")
        
    except Exception as e:
        await callback.message.edit_text("Произошла ошибка при показе профиля сотрудника")
        log_user_error(callback.from_user.id, "show_employee_profile_error", str(e))


# УДАЛЕНО: Заглушка для базы знаний заменена на реальную функциональность в handlers/knowledge_base.py


@router.callback_query(F.data == "back_to_employee_profile")
async def callback_back_to_employee_profile(callback: CallbackQuery, session: AsyncSession):
    """Возврат к профилю сотрудника"""
    try:
        await show_employee_profile(callback, session, show_congratulation=False)

    except Exception as e:
        await callback.message.edit_text("Произошла ошибка при возврате к профилю")
        log_user_error(callback.from_user.id, "back_to_profile_error", str(e))


@router.message(F.text == "Мои данные")
async def cmd_employee_profile(message: Message, state: FSMContext, session: AsyncSession):
    """Обработчик команды 'Мои данные' для сотрудника"""
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

        # Проверяем что пользователь - сотрудник
        user_roles = [role.name for role in user.roles]
        if "Сотрудник" not in user_roles:
            await message.answer("❌ Команда доступна только сотрудникам.")
            return

        # Используем общую функцию формирования профиля
        profile_text = (
            "<b>Ваши данные:</b>\n\n"
            f"🧑 <b>ФИО:</b> {user.full_name}\n"
            f"📞 <b>Телефон:</b> {user.phone_number}\n"
            f"🆔 <b>Telegram ID:</b> {user.tg_id}\n"
            f"👤 <b>Username:</b> @{user.username or 'не указан'}\n"
            f"📅 <b>Дата регистрации:</b> {user.registration_date.strftime('%d.%m.%Y %H:%M')}\n"
            f"👑 <b>Роли:</b> {', '.join([role.name for role in user.roles])}\n"
            f"🗂️<b>Группа:</b> {', '.join([group.name for group in user.groups]) if user.groups else 'Не указана'}\n"
            f"📍<b>2️⃣Объект работы:</b> {user.work_object.name if user.work_object else 'Не указан'}\n"
            f"🎱<b>Номер пользователя:</b> {user.id}"
        )

        # Клавиатура для ЛК сотрудника согласно ТЗ
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📚База знаний", callback_data="knowledge_base")]
        ])

        await message.answer(
            profile_text,
            parse_mode="HTML",
            reply_markup=keyboard
        )

        log_user_action(user.tg_id, "employee_data_viewed", "Просмотр данных сотрудника")

    except Exception as e:
        await message.answer("Произошла ошибка при получении данных")
        log_user_error(message.from_user.id, "employee_profile_error", str(e))


@router.message(F.text == "Мои тесты")
async def cmd_employee_tests(message: Message, state: FSMContext, session: AsyncSession):
    """Обработчик команды 'Мои тесты' для сотрудника"""
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

        # Проверяем что пользователь - сотрудник
        has_permission = await check_user_permission(session, user.id, "take_tests")
        if not has_permission:
            await message.answer("❌ У вас нет прав для прохождения тестов.")
            return
            
        # Получаем тесты для сотрудника ТОЛЬКО от рекрутера (включая пройденные для пересдачи)
        # Сотрудники проходят тесты, которые назначает рекрутер ПОСЛЕ перехода в сотрудники
        # С бесконечными попытками показываем все тесты для возможности пересдачи
        available_tests = await get_employee_tests_from_recruiter(session, user.id, exclude_completed=False)
        
        if not available_tests:
            await message.answer(
                "📋 <b>Мои тесты</b>\n\n"
                "❌ У вас пока нет новых тестов от рекрутера.\n\n"
                "📝 <b>Как получить тесты:</b>\n"
                "• Рекрутер назначает тесты через массовую рассылку\n"
                "• Тесты от времен стажировки не отображаются\n"
                "• Отображаются только непройденные тесты от рекрутера\n\n"
                "Ожидайте назначения новых тестов от рекрутера.",
                parse_mode="HTML"
            )
            return
            
        # Формируем список доступных тестов (включая пройденные для пересдачи)
        tests_list = []
        for i, test in enumerate(available_tests, 1):
            # Получаем результат последнего прохождения
            test_result = await get_user_test_result(session, user.id, test.id)
            if test_result and test_result.is_passed:
                status = f"✅ Пройден ({test_result.score}/{test_result.max_possible_score} баллов)"
                action_text = "Пересдать для улучшения результата"
            else:
                status = "📋 Доступен для прохождения"
                action_text = "Пройти тест"
            
            tests_list.append(
                f"<b>{i}. {test.name}</b>\n"
                f"   🎯 Порог: {test.threshold_score}/{test.max_score} баллов\n"
                f"   📊 Статус: {status}\n"
                f"   📝 {test.description or 'Описание не указано'}"
            )
        
        tests_display = "\n\n".join(tests_list)
        
        # Создаем клавиатуру для прохождения тестов (включая пересдачу)
        keyboard = InlineKeyboardMarkup(inline_keyboard=[])
        
        for test in available_tests:
            # Определяем текст кнопки в зависимости от статуса
            test_result = await get_user_test_result(session, user.id, test.id)
            if test_result and test_result.is_passed:
                button_text = f"🔄 Пересдать: {test.name}"
            else:
                button_text = f"🚀 Пройти: {test.name}"
            
            keyboard.inline_keyboard.append([
                InlineKeyboardButton(
                    text=button_text,
                    callback_data=f"take_test:{test.id}"
                )
            ])
        
        await message.answer(
            f"📋 <b>Мои тесты</b>\n\n"
            f"👤 <b>Сотрудник:</b> {user.full_name}\n"
            f"📊 <b>Всего тестов:</b> {len(available_tests)}\n\n"
            f"{tests_display}\n\n"
            "Выберите тест для прохождения:",
            reply_markup=keyboard,
            parse_mode="HTML"
        )
        
        log_user_action(user.tg_id, "employee_tests_viewed", f"Сотрудник просмотрел доступные тесты: {len(available_tests)}")

    except Exception as e:
        await message.answer("Произошла ошибка при получении списка тестов")
        log_user_error(message.from_user.id, "employee_tests_error", str(e))
