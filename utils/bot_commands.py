from aiogram import Bot
from aiogram.types import BotCommand

async def set_bot_commands(bot: Bot, role: str = None):
    """Устанавливает команды в зависимости от роли пользователя"""
    commands = [
        BotCommand(command="start", description="Запуск/перезапуск бота"),
        BotCommand(command="help", description="Получить справку")
    ]
    
    if role == "Управляющий":
        commands.extend([
            BotCommand(command="profile", description="Мой профиль"),
            BotCommand(command="manage_users", description="Управление пользователями"),
            BotCommand(command="manage_permissions", description="Управление правами ролей"),
            BotCommand(command="trainees", description="Список Стажеров"),
            BotCommand(command="logout", description="Выйти из системы")
        ])
    elif role == "Рекрутер":
        commands.extend([
            BotCommand(command="profile", description="Мой профиль"),
            BotCommand(command="create_test", description="Создать новый тест"),
            BotCommand(command="manage_tests", description="Управление тестами"),
            BotCommand(command="assign_mentor", description="Назначить наставника"),
            BotCommand(command="trainees", description="Список Стажеров"),
            BotCommand(command="logout", description="Выйти из системы")
        ])
    elif role == "Сотрудник":
        commands.extend([
            BotCommand(command="profile", description="Мой профиль"),
            BotCommand(command="my_trainees", description="Мои стажеры"),
            BotCommand(command="all_tests", description="Просмотр всех тестов"),
            BotCommand(command="logout", description="Выйти из системы")
        ])
    elif role == "Стажер":
        commands.extend([
            BotCommand(command="profile", description="Мой профиль"),
            BotCommand(command="my_tests", description="Мои доступные тесты"),
            BotCommand(command="my_mentor", description="Мой наставник"),
            BotCommand(command="logout", description="Выйти из системы")
        ])
    else: # Неавторизованный пользователь
        commands.extend([
            BotCommand(command="register", description="Регистрация"),
            BotCommand(command="login", description="Войти в систему")
        ])

    await bot.set_my_commands(commands) 