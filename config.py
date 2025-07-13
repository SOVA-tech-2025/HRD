import os
import sys
from dotenv import load_dotenv
from utils.logger import logger

load_dotenv()

def get_required_env(name: str) -> str:
    """Получает обязательную переменную окружения или завершает программу при её отсутствии"""

    value = os.getenv(name)
    if value is None:
        logger.critical(f"Обязательная переменная окружения {name} не задана")
        sys.exit(1)
    return value

BOT_TOKEN = get_required_env("BOT_TOKEN")

DB_USER = get_required_env("POSTGRES_USER")
DB_PASS = os.getenv("POSTGRES_PASSWORD", "")
DB_NAME = get_required_env("POSTGRES_DB")
DB_HOST = get_required_env("POSTGRES_HOST")
DB_PORT = get_required_env("POSTGRES_PORT")

DATABASE_URL = f"postgresql+asyncpg://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

# Получаем ID управляющих из переменных окружения
MANAGER_IDS_STR = os.getenv("MANAGER_IDS", "")
MANAGER_IDS = [int(id.strip()) for id in MANAGER_IDS_STR.split(",") if id.strip().isdigit()] if MANAGER_IDS_STR else []

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

# Роль по умолчанию для новых пользователей
DEFAULT_ROLE = os.getenv("DEFAULT_ROLE", "Стажер") 