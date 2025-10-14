"""
Обработчики для массовой рассылки тестов по группам (Task 8).
Включает выбор теста, выбор групп и отправку уведомлений.
"""

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession

from database.db import (
    get_user_by_tg_id, check_user_permission, get_all_active_tests,
    get_test_by_id, get_all_groups, get_group_by_id, broadcast_test_to_groups,
    get_employees_in_group
)
from handlers.auth import check_auth
from states.states import BroadcastStates
from keyboards.keyboards import (
    get_broadcast_test_selection_keyboard, get_broadcast_groups_selection_keyboard,
    get_broadcast_success_keyboard, get_main_menu_keyboard, get_keyboard_by_role
)
from utils.logger import log_user_action, log_user_error

router = Router()


# ===============================
# Обработчики для Task 8: Массовая рассылка тестов
# ===============================

@router.message(F.text.in_(["Рассылка ✈️", "Рассылка"]))
async def cmd_broadcast(message: Message, state: FSMContext, session: AsyncSession):
    """Обработчик кнопки 'Рассылка ✈️' в главном меню рекрутера"""
    try:
        # Получаем пользователя и проверяем права (точно как в старом обработчике)
        user = await get_user_by_tg_id(session, message.from_user.id)
        if not user:
            await message.answer("❌ Ты не зарегистрирован в системе.")
            return
        
        # Проверяем права на создание тестов (только рекрутеры)
        has_permission = await check_user_permission(session, user.id, "create_tests")
        if not has_permission:
            await message.answer(
                "❌ <b>Недостаточно прав</b>\n\n"
                "У тебя нет прав для массовой рассылки тестов.\n"
                "Обратись к администратору.",
                parse_mode="HTML"
            )
            return
        
        # Получаем все активные тесты
        tests = await get_all_active_tests(session)
        
        if not tests:
            await message.answer(
                "✉️<b>РЕДАКТОР РАССЫЛКИ</b>✉️\n\n"
                "❌ <b>Нет доступных тестов</b>\n\n"
                "В системе пока нет созданных тестов для рассылки.\n"
                "Сначала создай тесты.",
                parse_mode="HTML",
                reply_markup=get_main_menu_keyboard()
            )
            return
        
        # Шаг 4 ТЗ: Показываем список тестов для выбора (точно как в старом обработчике)
        await message.answer(
            "✉️<b>РЕДАКТОР РАССЫЛКИ</b>✉️\n\n"
            "🟡<b>Какой тест ты хочешь отправить пользователям?</b>\n\n"
            "📝 <b>Рассылка будет отправлена сотрудникам, стажерам и наставникам</b>\n\n"
            "Выбери тест из списка👇",
            parse_mode="HTML",
            reply_markup=get_broadcast_test_selection_keyboard(tests)
        )
        
        await state.set_state(BroadcastStates.selecting_test)
        log_user_action(user.tg_id, "broadcast_started", "Начата массовая рассылка тестов")
        
    except Exception as e:
        await message.answer("Произошла ошибка при запуске рассылки")
        log_user_error(message.from_user.id, "broadcast_start_error", str(e))


@router.callback_query(F.data == "test_filter:broadcast")
async def callback_start_broadcast(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Шаг 3 ТЗ: Начало процесса рассылки"""
    try:
        await callback.answer()
        
        # Получаем пользователя и проверяем права
        user = await get_user_by_tg_id(session, callback.from_user.id)
        if not user:
            await callback.message.edit_text("❌ Ты не зарегистрирован в системе.")
            return
        
        # Проверяем права на создание тестов (только рекрутеры)
        has_permission = await check_user_permission(session, user.id, "create_tests")
        if not has_permission:
            await callback.message.edit_text(
                "❌ <b>Недостаточно прав</b>\n\n"
                "У тебя нет прав для массовой рассылки тестов.\n"
                "Обратись к администратору.",
                parse_mode="HTML"
            )
            return
        
        # Получаем все активные тесты
        tests = await get_all_active_tests(session)
        
        if not tests:
            await callback.message.edit_text(
                "✉️<b>РЕДАКТОР РАССЫЛКИ</b>✉️\n\n"
                "❌ <b>Нет доступных тестов</b>\n\n"
                "В системе пока нет созданных тестов для рассылки.\n"
                "Сначала создай тесты.",
                parse_mode="HTML",
                reply_markup=get_main_menu_keyboard()
            )
            return
        
        # Шаг 4 ТЗ: Показываем список тестов для выбора
        await callback.message.edit_text(
            "✉️<b>РЕДАКТОР РАССЫЛКИ</b>✉️\n\n"
            "🟡<b>Какой тест ты хочешь отправить пользователям?</b>\n\n"
            "📝 <b>Рассылка будет отправлена сотрудникам, стажерам и наставникам</b>\n\n"
            "Выбери тест из списка👇",
            parse_mode="HTML",
            reply_markup=get_broadcast_test_selection_keyboard(tests)
        )
        
        await state.set_state(BroadcastStates.selecting_test)
        log_user_action(user.tg_id, "broadcast_started", "Начата массовая рассылка тестов")
        
    except Exception as e:
        await callback.message.edit_text("Произошла ошибка при запуске рассылки")
        log_user_error(callback.from_user.id, "broadcast_start_error", str(e))


@router.callback_query(F.data.startswith("broadcast_test:"), BroadcastStates.selecting_test)
async def callback_select_broadcast_test(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Шаг 5-6 ТЗ: Выбор теста и переход к выбору групп"""
    try:
        await callback.answer()
        
        test_id = int(callback.data.split(":")[1])
        
        # Получаем информацию о тесте
        test = await get_test_by_id(session, test_id)
        if not test:
            await callback.answer("Тест не найден", show_alert=True)
            return
        
        # Сохраняем выбранный тест
        await state.update_data(selected_test_id=test_id, selected_groups=[])
        
        # Получаем все группы
        groups = await get_all_groups(session)
        
        if not groups:
            await callback.message.edit_text(
                "✉️<b>РЕДАКТОР РАССЫЛКИ</b>✉️\n\n"
                f"🟢<b>Тест для отправки:</b> {test.name}\n\n"
                "❌ <b>Нет доступных групп</b>\n\n"
                "В системе пока нет созданных групп.\n"
                "Сначала создай группы пользователей.",
                parse_mode="HTML",
                reply_markup=get_main_menu_keyboard()
            )
            return
        
        # Шаг 6 ТЗ: Показываем выбор групп
        await callback.message.edit_text(
            "✉️<b>РЕДАКТОР РАССЫЛКИ</b>✉️\n\n"
            f"🟢<b>Тест для отправки:</b>  {test.name}\n"
            "🟡<b>Выбери группы, которым нужно отправить тест👇</b>",
            parse_mode="HTML",
            reply_markup=get_broadcast_groups_selection_keyboard(groups, [])
        )
        
        await state.set_state(BroadcastStates.selecting_groups)
        log_user_action(callback.from_user.id, "broadcast_test_selected", f"Выбран тест для рассылки: {test.name}")
        
    except Exception as e:
        await callback.message.edit_text("Произошла ошибка при выборе теста")
        log_user_error(callback.from_user.id, "broadcast_test_select_error", str(e))


@router.callback_query(F.data.startswith("broadcast_group:"), BroadcastStates.selecting_groups)
async def callback_toggle_broadcast_group(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Шаг 7-10 ТЗ: Выбор/отмена групп для рассылки"""
    try:
        await callback.answer()
        
        group_id = int(callback.data.split(":")[1])
        
        # Получаем текущие данные
        data = await state.get_data()
        selected_test_id = data.get("selected_test_id")
        selected_groups = data.get("selected_groups", [])
        
        # Получаем информацию о тесте и группе
        test = await get_test_by_id(session, selected_test_id)
        group = await get_group_by_id(session, group_id)
        
        if not test or not group:
            await callback.answer("Данные не найдены", show_alert=True)
            return
        
        # Переключаем выбор группы
        if group_id in selected_groups:
            selected_groups.remove(group_id)
        else:
            selected_groups.append(group_id)
        
        await state.update_data(selected_groups=selected_groups)
        
        # Получаем названия выбранных групп
        selected_group_names = []
        for gid in selected_groups:
            g = await get_group_by_id(session, gid)
            if g:
                selected_group_names.append(g.name)
        
        # Формируем сообщение согласно ТЗ
        groups_text = "; ".join(selected_group_names) if selected_group_names else ""
        
        # Получаем все группы для отображения
        all_groups = await get_all_groups(session)
        
        if selected_group_names:
            # Шаги 8-10 ТЗ: Сообщение с выбранными группами
            message_text = (
                "✉️<b>РЕДАКТОР РАССЫЛКИ</b>✉️\n\n"
                f"🟢<b>Тест для отправки:</b>  {test.name}\n"
                f"🟢<b>Группы для отправки:</b> {groups_text}\n\n"
                "🟡<b>Добавить ещё группу к данной папке?</b>\n"
                "Выбери группу на клавиатуре👇"
            )
        else:
            # Шаг 6 ТЗ: Первый выбор группы
            message_text = (
                "✉️<b>РЕДАКТОР РАССЫЛКИ</b>✉️\n\n"
                f"🟢<b>Тест для отправки:</b>  {test.name}\n"
                "🟡<b>Выберите группы, которым нужно отправить тест👇</b>"
            )
        
        await callback.message.edit_text(
            message_text,
            parse_mode="HTML",
            reply_markup=get_broadcast_groups_selection_keyboard(all_groups, selected_groups)
        )
        
        log_user_action(callback.from_user.id, "broadcast_group_toggled", 
                       f"Группа {group.name} {'добавлена' if group_id in selected_groups else 'убрана'}")
        
    except Exception as e:
        await callback.message.edit_text("Произошла ошибка при выборе группы")
        log_user_error(callback.from_user.id, "broadcast_group_toggle_error", str(e))


@router.callback_query(F.data == "broadcast_send", BroadcastStates.selecting_groups)
async def callback_send_broadcast(callback: CallbackQuery, state: FSMContext, session: AsyncSession, bot):
    """Шаг 11-13 ТЗ: Отправка рассылки и показ результата"""
    try:
        await callback.answer()
        
        # Получаем данные рассылки
        data = await state.get_data()
        selected_test_id = data.get("selected_test_id")
        selected_groups = data.get("selected_groups", [])
        
        if not selected_test_id or not selected_groups:
            await callback.answer("Не выбран тест или группы", show_alert=True)
            return
        
        # Получаем пользователя
        user = await get_user_by_tg_id(session, callback.from_user.id)
        if not user:
            await callback.message.edit_text("❌ Пользователь не найден")
            return
        
        # Шаг 12 ТЗ: Выполняем массовую рассылку
        result = await broadcast_test_to_groups(
            session, selected_test_id, selected_groups, user.id, bot
        )
        
        if not result["success"]:
            await callback.message.edit_text(
                "❌ <b>Ошибка рассылки</b>\n\n"
                f"Произошла ошибка: {result.get('error', 'Неизвестная ошибка')}",
                parse_mode="HTML",
                reply_markup=get_main_menu_keyboard()
            )
            return
        
        # Получаем информацию о тесте для отображения
        test = await get_test_by_id(session, selected_test_id)
        groups_text = "; ".join(result["group_names"])
        
        # Шаг 13 ТЗ: Показываем результат успешной рассылки
        success_message = (
            "✉️<b>РЕДАКТОР РАССЫЛКИ</b>✉️\n\n"
            f"🟢<b>Тест для отправки:</b>  {test.name}\n"
            f"🟢<b>Группы для отправки:</b> {groups_text}\n\n"
            "✅<b>Ты успешно отправил рассылку</b>\n\n"
            f"📊 <b>Статистика:</b>\n"
            f"• Сотрудников в группах: {result['total_users']}\n"
            f"• Уведомлений отправлено: {result['total_sent']}\n"
            f"• Ошибок отправки: {result['failed_sends']}"
        )
        
        await callback.message.edit_text(
            success_message,
            parse_mode="HTML",
            reply_markup=get_broadcast_success_keyboard()
        )
        
        # Очищаем состояние
        await state.clear()
        
        log_user_action(callback.from_user.id, "broadcast_completed", 
                       f"Рассылка завершена: тест {test.name}, группы {groups_text}, отправлено {result['total_sent']}")
        
    except Exception as e:
        await callback.message.edit_text("Произошла ошибка при отправке рассылки")
        log_user_error(callback.from_user.id, "broadcast_send_error", str(e))


