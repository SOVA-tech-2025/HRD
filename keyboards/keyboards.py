from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton


def get_contact_keyboard() -> ReplyKeyboardMarkup:
    keyboard = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="Отправить контакт", request_contact=True)]],
        resize_keyboard=True,
        one_time_keyboard=True
    )
    return keyboard


def get_role_selection_keyboard() -> InlineKeyboardMarkup:
    import os
    allow_auto_role = os.getenv("ALLOW_AUTO_ROLE_ASSIGNMENT", "false").lower() == "true"
    default_role = os.getenv("DEFAULT_ROLE", "Стажер")
    
    # Базовые роли
    all_roles = [
        ("Стажёр", "Стажер"),
        ("Сотрудник", "Сотрудник"), 
        ("Рекрутер", "Рекрутер")
    ]
    
    keyboard_buttons = []
    
    # Если включено автоназначение, добавляем рекомендуемую роль вверху
    if allow_auto_role:
        keyboard_buttons.append([InlineKeyboardButton(
            text=f"🚀 {default_role} (рекомендуемая роль)", 
            callback_data=f"role:{default_role}"
        )])
    
    # Добавляем остальные роли, исключая дублирование с рекомендуемой
    for display_name, role_name in all_roles:
        if not (allow_auto_role and role_name == default_role):
            keyboard_buttons.append([InlineKeyboardButton(text=display_name, callback_data=f"role:{role_name}")])
    
    keyboard_buttons.append([InlineKeyboardButton(text="Отмена", callback_data="cancel_registration")])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
    return keyboard


def get_trainee_keyboard() -> ReplyKeyboardMarkup:
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Мой профиль")],
            [KeyboardButton(text="Доступные тесты")],
            [KeyboardButton(text="Посмотреть баллы")],
            [KeyboardButton(text="Мой наставник")],
            [KeyboardButton(text="Помощь")]
        ],
        resize_keyboard=True
    )
    return keyboard


def get_recruiter_keyboard() -> ReplyKeyboardMarkup:
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Мой профиль")],
            [KeyboardButton(text="Создать тест"), KeyboardButton(text="Открыть список тестов")],
            [KeyboardButton(text="Назначить наставника")],
            [KeyboardButton(text="Список Наставников")],
            [KeyboardButton(text="Список Стажеров")],
            [KeyboardButton(text="Список новых пользователей")],
            [KeyboardButton(text="Помощь")]
        ],
        resize_keyboard=True
    )
    return keyboard


def get_employee_keyboard() -> ReplyKeyboardMarkup:
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Мой профиль")],
            [KeyboardButton(text="Мои стажеры")],
            [KeyboardButton(text="Открыть список тестов")],
            [KeyboardButton(text="Помощь")]
        ],
        resize_keyboard=True
    )
    return keyboard


def get_manager_keyboard() -> ReplyKeyboardMarkup:
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Мой профиль")],
            [KeyboardButton(text="Управление пользователями")],
            [KeyboardButton(text="Список Стажеров")],
            [KeyboardButton(text="Управление правами ролей")],
            [KeyboardButton(text="Помощь")]
        ],
        resize_keyboard=True
    )
    return keyboard


def get_user_selection_keyboard(users: list) -> InlineKeyboardMarkup:
    """Создает инлайн-клавиатуру со списком пользователей"""

    keyboard = []
    
    for user in users:
        button = InlineKeyboardButton(
            text=f"{user.full_name} ({user.username or 'нет юзернейма'})",
            callback_data=f"user:{user.id}"
        )
        keyboard.append([button])
    
    keyboard.append([InlineKeyboardButton(text="Отмена", callback_data="cancel")])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_user_action_keyboard(user_id: int) -> InlineKeyboardMarkup:
    """Создает инлайн-клавиатуру с действиями для пользователя"""

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Изменить роль", callback_data=f"change_role:{user_id}")],
            [InlineKeyboardButton(text="Назад к списку", callback_data="back_to_users")]
        ]
    )
    return keyboard


def get_role_change_keyboard(user_id: int, roles: list) -> InlineKeyboardMarkup:
    """Создает инлайн-клавиатуру для выбора новой роли пользователя"""

    keyboard = []
    
    for role in roles:
        button = InlineKeyboardButton(
            text=role.name,
            callback_data=f"set_role:{user_id}:{role.name}"
        )
        keyboard.append([button])
    
    keyboard.append([InlineKeyboardButton(text="Отмена", callback_data=f"cancel_role_change:{user_id}")])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_confirmation_keyboard(user_id: int, role_name: str, action: str) -> InlineKeyboardMarkup:
    """Создает инлайн-клавиатуру для подтверждения изменения роли"""

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ Подтвердить", callback_data=f"confirm:{action}:{user_id}:{role_name}")],
            [InlineKeyboardButton(text="❌ Отменить", callback_data=f"cancel_role_change:{user_id}")]
        ]
    )
    return keyboard


def get_keyboard_by_role(role_name: str) -> ReplyKeyboardMarkup:
    if role_name == "Стажер":
        return get_trainee_keyboard()
    elif role_name == "Рекрутер":
        return get_recruiter_keyboard()
    elif role_name == "Сотрудник":
        return get_employee_keyboard()
    elif role_name == "Управляющий":
        return get_manager_keyboard()
    else:
        return ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text="Мой профиль"), KeyboardButton(text="Помощь")]],
            resize_keyboard=True
        )


def get_role_management_keyboard(roles: list) -> InlineKeyboardMarkup:
    """Создает инлайн-клавиатуру для выбора роли, чьи права будут изменяться"""

    keyboard = []
    
    for role in roles:
        button = InlineKeyboardButton(
            text=role.name,
            callback_data=f"manage_role_permissions:{role.id}"
        )
        keyboard.append([button])
    
    keyboard.append([InlineKeyboardButton(text="Отмена", callback_data="cancel")])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_permission_action_keyboard(role_id: int) -> InlineKeyboardMarkup:
    """Создает инлайн-клавиатуру с действиями для управления правами роли """

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Расширить возможности роли", callback_data=f"add_permission:{role_id}")],
            [InlineKeyboardButton(text="Ограничить возможности роли", callback_data=f"remove_permission:{role_id}")],
            [InlineKeyboardButton(text="Назад к списку ролей", callback_data="back_to_roles")]
        ]
    )
    return keyboard


def get_permission_selection_keyboard(permissions: list, role_id: int, action: str) -> InlineKeyboardMarkup:
    """Создает инлайн-клавиатуру для выбора права """

    keyboard = []
    
    for permission in permissions:
        button = InlineKeyboardButton(
            text=f"{permission.description}",
            callback_data=f"select_permission:{action}:{role_id}:{permission.name}"
        )
        keyboard.append([button])
    
    keyboard.append([InlineKeyboardButton(text="Отмена", callback_data=f"cancel_permission_selection:{role_id}")])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_permission_confirmation_keyboard(role_id: int, permission_name: str, action: str) -> InlineKeyboardMarkup:
    """Создает инлайн-клавиатуру для подтверждения изменения прав"""
    
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ Подтвердить", callback_data=f"confirm_permission:{action}:{role_id}:{permission_name}")],
            [InlineKeyboardButton(text="❌ Отменить", callback_data=f"cancel_permission_confirmation:{role_id}:{permission_name}")]
        ]
    )
    return keyboard


# =================================
# КЛАВИАТУРЫ ДЛЯ РАБОТЫ С ТЕСТАМИ
# =================================

def get_yes_no_keyboard(prefix: str) -> InlineKeyboardMarkup:
    """Создает инлайн-клавиатуру с кнопками Да/Нет"""
    keyboard_buttons = [
        [InlineKeyboardButton(text="✅ Да", callback_data=f"{prefix}:yes")],
        [InlineKeyboardButton(text="❌ Нет", callback_data=f"{prefix}:no")]
    ]
    
    # Добавляем кнопку отмены для этапов создания теста
    if prefix in ["more_questions", "materials"]:
        keyboard_buttons.append([InlineKeyboardButton(text="🚫 Отменить создание теста", callback_data="cancel")])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
    return keyboard


def get_question_type_keyboard(is_creating_test: bool = True) -> InlineKeyboardMarkup:
    """Клавиатура для выбора типа вопроса"""
    keyboard_buttons = [
        [InlineKeyboardButton(text="Свободный ответ (текст)", callback_data="q_type:text")],
        [InlineKeyboardButton(text="Выбор одного правильного ответа", callback_data="q_type:single_choice")],
        [InlineKeyboardButton(text="Выбор нескольких правильных ответов", callback_data="q_type:multiple_choice")],
        [InlineKeyboardButton(text="Ответ 'Да' или 'Нет'", callback_data="q_type:yes_no")]
    ]
    
    # Разные кнопки отмены в зависимости от контекста
    if is_creating_test:
        keyboard_buttons.append([InlineKeyboardButton(text="🚫 Отменить создание теста", callback_data="cancel")])
    else:
        keyboard_buttons.append([InlineKeyboardButton(text="❌ Отменить добавление вопроса", callback_data="cancel_question")])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
    return keyboard


def get_test_edit_menu(test_id: int) -> InlineKeyboardMarkup:
    """Клавиатура для главного меню редактирования теста"""
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✏️ Название/Описание", callback_data=f"edit_test_meta:{test_id}"),
                InlineKeyboardButton(text="🔗 Материалы", callback_data=f"edit_test_materials:{test_id}")
            ],
            [
                InlineKeyboardButton(text="❓ Управление вопросами", callback_data=f"edit_test_questions:{test_id}"),
                InlineKeyboardButton(text="⚙️ Настройки", callback_data=f"edit_test_settings:{test_id}")
            ],
            [InlineKeyboardButton(text="👁️ Предпросмотр", callback_data=f"preview_test:{test_id}")],
            [InlineKeyboardButton(text="⬅️ Назад к тесту", callback_data=f"test:{test_id}")]
        ]
    )
    return keyboard


def get_test_filter_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для выбора фильтра тестов для рекрутера"""
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🗂️ Мои тесты", callback_data="test_filter:my"),
                InlineKeyboardButton(text="📚 Все тесты", callback_data="test_filter:all")
            ],
            [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")]
        ]
    )
    return keyboard


def get_test_selection_keyboard(tests: list) -> InlineKeyboardMarkup:
    """Создает инлайн-клавиатуру со списком тестов"""
    keyboard = []
    
    for test in tests:
        button = InlineKeyboardButton(
            text=f"{test.name} (макс. {test.max_score} баллов)",
            callback_data=f"test:{test.id}"
        )
        keyboard.append([button])
    
    keyboard.append([InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_question_edit_keyboard(question_id: int) -> InlineKeyboardMarkup:
    """Создает инлайн-клавиатуру для редактирования вопроса"""
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✏️ Изменить текст вопроса", callback_data=f"edit_question_text:{question_id}")],
            [InlineKeyboardButton(text="✏️ Изменить ответ", callback_data=f"edit_question_answer:{question_id}")],
            [InlineKeyboardButton(text="✏️ Изменить баллы", callback_data=f"edit_question_points:{question_id}")],
            [InlineKeyboardButton(text="🗑️ Удалить вопрос", callback_data=f"delete_question:{question_id}")],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_questions")]
        ]
    )
    return keyboard


def get_stage_selection_keyboard(stages: list) -> InlineKeyboardMarkup:
    """Создает инлайн-клавиатуру для выбора этапа стажировки"""
    keyboard = []
    
    for stage in stages:
        button = InlineKeyboardButton(
            text=f"{stage.order_number}. {stage.name}",
            callback_data=f"stage:{stage.id}"
        )
        keyboard.append([button])
    
    keyboard.append([InlineKeyboardButton(text="🔓 Тест без этапа", callback_data="stage:none")])
    keyboard.append([InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_test_actions_keyboard(test_id: int, user_role: str = "creator") -> InlineKeyboardMarkup:
    """Создает инлайн-клавиатуру с действиями для теста"""
    keyboard = []
    
    if user_role == "creator":
        # Кнопки для создателя теста (рекрутера)
        keyboard.extend([
            [InlineKeyboardButton(text="✏️ Редактировать", callback_data=f"edit_test:{test_id}")],
            [InlineKeyboardButton(text="📚 Материалы", callback_data=f"view_materials:{test_id}")],
            [InlineKeyboardButton(text="📊 Результаты", callback_data=f"test_results:{test_id}")],
            [InlineKeyboardButton(text="🗑️ Удалить", callback_data=f"delete_test:{test_id}")]
        ])
    else:
        # Кнопки для наставника
        keyboard.extend([
            [InlineKeyboardButton(text="🔐 Предоставить доступ стажерам", callback_data=f"grant_access_to_test:{test_id}")],
            [InlineKeyboardButton(text="📚 Материалы", callback_data=f"view_materials:{test_id}")],
            [InlineKeyboardButton(text="📊 Результаты", callback_data=f"test_results:{test_id}")]
        ])
    
    keyboard.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_tests")])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_question_selection_keyboard(questions: list) -> InlineKeyboardMarkup:
    """Создает инлайн-клавиатуру для выбора вопроса"""
    keyboard = []
    
    for question in questions:
        button = InlineKeyboardButton(
            text=f"Вопрос {question.question_number}",
            callback_data=f"question:{question.id}"
        )
        keyboard.append([button])
    
    keyboard.append([InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


# =================================
# КЛАВИАТУРЫ ДЛЯ НАСТАВНИЧЕСТВА
# =================================

def get_trainee_selection_keyboard(trainees: list) -> InlineKeyboardMarkup:
    """Создает инлайн-клавиатуру со списком стажеров"""
    keyboard = []
    
    for trainee in trainees:
        button = InlineKeyboardButton(
            text=f"{trainee.full_name}",
            callback_data=f"trainee:{trainee.id}"
        )
        keyboard.append([button])
    
    keyboard.append([InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_mentor_selection_keyboard(mentors: list) -> InlineKeyboardMarkup:
    """Создает инлайн-клавиатуру со списком наставников"""
    keyboard = []
    
    for mentor in mentors:
        button = InlineKeyboardButton(
            text=f"{mentor.full_name}",
            callback_data=f"mentor:{mentor.id}"
        )
        keyboard.append([button])
    
    keyboard.append([InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_assignment_confirmation_keyboard(mentor_id: int, trainee_id: int) -> InlineKeyboardMarkup:
    """Создает инлайн-клавиатуру для подтверждения назначения наставника"""
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ Подтвердить", callback_data=f"confirm_assignment:{mentor_id}:{trainee_id}")],
            [InlineKeyboardButton(text="❌ Отменить", callback_data="cancel_assignment")]
        ]
    )
    return keyboard


def get_trainee_actions_keyboard(trainee_id: int) -> InlineKeyboardMarkup:
    """Создает инлайн-клавиатуру с действиями для стажера"""
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📋 Добавить тест", callback_data=f"add_test_access:{trainee_id}")],
            [InlineKeyboardButton(text="📊 Результаты тестов", callback_data=f"trainee_results:{trainee_id}")],
            [InlineKeyboardButton(text="👤 Профиль", callback_data=f"trainee_profile:{trainee_id}")],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_trainees")]
        ]
    )
    return keyboard


def get_test_access_keyboard(tests: list, trainee_id: int) -> InlineKeyboardMarkup:
    """Создает инлайн-клавиатуру для предоставления доступа к тестам"""
    keyboard = []
    
    for test in tests:
        button = InlineKeyboardButton(
            text=f"{test.name}",
            callback_data=f"grant_access:{trainee_id}:{test.id}"
        )
        keyboard.append([button])
    
    keyboard.append([InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


# =================================
# КЛАВИАТУРЫ ДЛЯ ПРОХОЖДЕНИЯ ТЕСТОВ
# =================================

# Функция удалена - используется get_test_start_keyboard с расширенным функционалом

def get_test_navigation_keyboard(current_question: int, total_questions: int, test_id: int) -> InlineKeyboardMarkup:
    """Создает инлайн-клавиатуру для навигации по тесту"""
    keyboard = []
    
    # Навигация
    nav_row = []
    if current_question > 1:
        nav_row.append(InlineKeyboardButton(text="⬅️ Предыдущий", callback_data=f"prev_question:{test_id}"))
    if current_question < total_questions:
        nav_row.append(InlineKeyboardButton(text="Следующий ➡️", callback_data=f"next_question:{test_id}"))
    
    if nav_row:
        keyboard.append(nav_row)
    
    # Завершение теста
    if current_question == total_questions:
        keyboard.append([InlineKeyboardButton(text="✅ Завершить тест", callback_data=f"finish_test:{test_id}")])
    
    keyboard.append([InlineKeyboardButton(text="❌ Прервать тест", callback_data=f"cancel_test:{test_id}")])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


# =================================
# КЛАВИАТУРЫ ДЛЯ УПРАВЛЕНИЯ ПОЛЬЗОВАТЕЛЯМИ
# =================================

def get_unassigned_trainees_keyboard(trainees: list) -> InlineKeyboardMarkup:
    """Создает инлайн-клавиатуру со списком стажеров без наставника"""
    keyboard = []
    
    for trainee in trainees:
        button = InlineKeyboardButton(
            text=f"{trainee.full_name}",
            callback_data=f"unassigned_trainee:{trainee.id}"
        )
        keyboard.append([button])
    
    if not trainees:
        keyboard.append([InlineKeyboardButton(text="ℹ️ Нет неназначенных стажеров", callback_data="info")])
    
    keyboard.append([InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_test_start_keyboard(test_id: int, has_previous_result: bool = False) -> InlineKeyboardMarkup:
    """Создает инлайн-клавиатуру для начала теста с дополнительными опциями"""
    keyboard = []
    
    # Кнопка начала теста
    start_text = "🔄 Пройти повторно" if has_previous_result else "🚀 Начать тест"
    keyboard.append([InlineKeyboardButton(text=start_text, callback_data=f"start_test:{test_id}")])
    
    # Кнопка просмотра материалов
    keyboard.append([InlineKeyboardButton(text="📚 Материалы", callback_data=f"view_materials:{test_id}")])
    
    # Кнопки навигации
    navigation_row = [
        InlineKeyboardButton(text="📋 К списку тестов", callback_data="back_to_test_list")
    ]
    keyboard.append(navigation_row)
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_test_selection_for_taking_keyboard(tests: list) -> InlineKeyboardMarkup:
    """Создает инлайн-клавиатуру со списком тестов для прохождения"""
    keyboard = []
    
    for test in tests:
        button = InlineKeyboardButton(
            text=f"📋 {test.name}",
            callback_data=f"test:{test.id}"
        )
        keyboard.append([button])
    
    keyboard.append([InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_question_management_keyboard(question_id: int, is_first: bool, is_last: bool) -> InlineKeyboardMarkup:
    """Клавиатура для управления конкретным вопросом"""
    nav_buttons = []
    if not is_first:
        nav_buttons.append(InlineKeyboardButton(text="⬆️", callback_data=f"move_q_up:{question_id}"))
    if not is_last:
        nav_buttons.append(InlineKeyboardButton(text="⬇️", callback_data=f"move_q_down:{question_id}"))

    keyboard = [
        [InlineKeyboardButton(text="✏️ Изменить текст", callback_data=f"edit_q_text:{question_id}")],
        [InlineKeyboardButton(text="🔄 Изменить ответ", callback_data=f"edit_q_answer:{question_id}")],
        [InlineKeyboardButton(text="🔢 Изменить баллы", callback_data=f"edit_q_points:{question_id}")],
        [InlineKeyboardButton(text="📊 Статистика", callback_data=f"q_stats:{question_id}")],
        nav_buttons,
        [InlineKeyboardButton(text="🗑️ Удалить вопрос", callback_data=f"delete_q:{question_id}")],
        [InlineKeyboardButton(text="⬅️ Назад к вопросам", callback_data="back_to_q_list")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_test_settings_keyboard(test_id: int, shuffle: bool, attempts: int) -> InlineKeyboardMarkup:
    """Клавиатура настроек теста"""
    shuffle_text = "✅ Перемешивать вопросы" if shuffle else "☑️ Не перемешивать вопросы"
    
    if attempts == 0:
        attempts_text = "♾️ Попытки: бесконечно"
    else:
        attempts_text = f"🔢 Попытки: {attempts}"

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=shuffle_text, callback_data=f"toggle_shuffle:{test_id}")],
            [InlineKeyboardButton(text=attempts_text, callback_data=f"edit_attempts:{test_id}")],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data=f"edit_test:{test_id}")]
        ]
    )
    return keyboard


def get_finish_options_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для завершения добавления вариантов ответа"""
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ Завершить добавление вариантов", callback_data="finish_options")],
            [InlineKeyboardButton(text="❌ Отменить создание вопроса", callback_data="cancel_current_question")]
        ]
    )
    return keyboard


def format_help_message(role_name: str) -> str:
    """Форматирует справочное сообщение для роли"""
    base_text = "🤖 <b>Справочная система HRD-бота</b>\n\n"
    
    role_specific_help = {
        "Стажер": """🎓 <b>Вы — стажер.</b>
Ваша основная задача — проходить тесты, которые назначает ваш наставник.

<b>Доступные команды:</b>
• <code>/my_tests</code> — посмотреть назначенные вам тесты.
• <code>/my_results</code> — увидеть ваши баллы за пройденные тесты.
• <code>/my_mentor</code> — получить информацию о вашем наставнике.
""",
        "Сотрудник": """👨‍🏫 <b>Вы — наставник.</b>
Ваша задача — курировать стажеров и предоставлять им доступ к тестам.

<b>Доступные команды:</b>
• <code>/my_trainees</code> — посмотреть список ваших стажеров и управлять ими.
• <code>/all_tests</code> — просмотреть все тесты в системе, чтобы назначить их стажерам.
""",
        "Рекрутер": """👔 <b>Вы — рекрутер.</b>
Ваша задача — создавать контент для обучения (тесты) и управлять процессом наставничества.

<b>Доступные команды:</b>
• <code>/create_test</code> — запустить мастер создания нового теста.
• <code>/manage_tests</code> — управлять всеми тестами в системе (редактировать, удалять, смотреть статистику).
• <code>/assign_mentor</code> — назначить наставника новому стажеру.
""",
        "Управляющий": """🔧 <b>Вы — управляющий.</b>
Вам доступен полный функционал системы, включая управление ролями и правами других пользователей.
""",
        "Неавторизованный": """👋 <b>Добро пожаловать!</b>
Вы еще не вошли в систему.

<b>Доступные команды:</b>
• <code>/register</code> — пройти регистрацию, чтобы получить доступ к функциям бота.
• <code>/login</code> — войти в систему, если вы уже зарегистрированы.
"""
    }
    
    base_text += role_specific_help.get(role_name, "Для вашей роли нет специальной справки.")
    base_text += "\n\n• <code>/profile</code> — посмотреть ваш профиль.\n• <code>/help</code> — вызвать эту справку."
    
    return base_text 

def get_tests_for_access_keyboard(tests: list) -> InlineKeyboardMarkup:
    """Создает инлайн-клавиатуру для выбора тестов для предоставления доступа из уведомлений"""
    keyboard = []
    
    for test in tests:
        button = InlineKeyboardButton(
            text=f"📋 {test.name}",
            callback_data=f"grant_access_to_test:{test.id}"
        )
        keyboard.append([button])
    
    keyboard.append([InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard) 