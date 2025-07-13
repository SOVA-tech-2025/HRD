import asyncio
import logging
import sys
from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.client.default import DefaultBotProperties

from config import BOT_TOKEN, LOG_LEVEL
from database.db import init_db
from handlers import auth, registration, common, admin, role_permissions, tests, mentorship, test_taking, fallback
from middlewares.db_middleware import DatabaseMiddleware
from middlewares.role_middleware import RoleMiddleware
from utils.errors import router as error_router
from utils.config_validator import validate_env_vars
from utils.logger import logger
from utils.bot_commands import set_bot_commands

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
    stream=sys.stdout
)

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

dp.include_router(error_router)
dp.include_router(auth.router)
dp.include_router(registration.router)
dp.include_router(admin.router)
dp.include_router(role_permissions.router)
dp.include_router(tests.router)
dp.include_router(mentorship.router)
dp.include_router(test_taking.router)
dp.include_router(common.router)
# Fallback роутер должен быть в конце!
dp.include_router(fallback.router)

dp.update.middleware(DatabaseMiddleware())
dp.update.middleware(RoleMiddleware())

async def main():
    if not validate_env_vars():
        logger.critical("Ошибка проверки переменных окружения. Выход...")
        return
    
    try:
        # Инициализация базы данных
        logger.info("Инициализация базы данных...")
        await init_db()
        
        # Установка команд бота
        logger.info("Настройка команд бота...")
        await set_bot_commands(bot)
        
        # Запуск бота
        logger.info("Запуск бота...")
        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(bot)
    except Exception as e:
        logger.error(f"Ошибка запуска: {e}")
    finally:
        # Корректное завершение работы бота
        logger.info("Завершение работы...")
        await bot.session.close()
        logger.info("Бот остановлен")



if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Бот остановлен по прерыванию с клавиатуры")
    except Exception as e:
        logger.critical(f"Непредвиденная ошибка: {e}")
        sys.exit(1) 