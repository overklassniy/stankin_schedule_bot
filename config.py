"""
Статическая конфигурация бота.
Токен бота загружается из .env (BOT_TOKEN).
Динамические настройки групп хранятся в БД (aiosqlite).
"""

import os

# Уровень логирования: DEBUG, INFO, WARNING, ERROR (из .env: LOG_LEVEL)
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()

# Пути
LOGS_DIR = os.getenv("LOGS_DIR", "logs")
TEACHERS_FULLNAMES_PATH = os.getenv("TEACHERS_FULLNAMES_PATH", "data/teachers.json")
IMAGES_DIR = os.getenv("IMAGES_DIR", "images")

# Интервал проверки планировщика (секунды) – для совместимости, но scheduler.py использует свой
CHECK_TIME_INTERVAL = int(os.getenv("CHECK_TIME_INTERVAL", "30"))

# Ограничение команд только чатами из БД (если True – команды только в привязанных группах)
ENABLE_SECURE = os.getenv("ENABLE_SECURE", "true").lower() in ("1", "true", "yes")

# Дефолты для новых групп (при миграции или создании)
DEFAULT_SEND_HOUR = 5
DEFAULT_SEND_MINUTE = 5
DEFAULT_ENABLE_IMAGE = True
DEFAULT_ENABLE_TOMORROW_BUTTON = False
DEFAULT_THREADED = True

# Путь к БД
DATABASE_PATH = os.getenv("DATABASE_PATH", "data/bot.db")

# ID админов Telegram (через запятую), настраивают бота через /settings
ADMIN_IDS = [int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip().isdigit()]

# Moodle (гостевой доступ, токен не нужен)
MOODLE_BASE_URL = os.getenv("MOODLE_BASE_URL", "https://edu.stankin.ru")
MOODLE_COURSE_ID = int(os.getenv("MOODLE_COURSE_ID", "11557"))

# Кэш расписания: директория для хранения PDF и TTL в секундах (по умолчанию 6 часов)
SCHEDULE_CACHE_DIR = os.getenv("SCHEDULE_CACHE_DIR", "data/cache")
SCHEDULE_CACHE_TTL = int(os.getenv("SCHEDULE_CACHE_TTL", "21600"))

# Прокси для запросов бота к Telegram API (.env: PROXY или HTTP_PROXY).
PROXY = os.getenv("PROXY", "").strip() or os.getenv("HTTP_PROXY", "").strip() or None
