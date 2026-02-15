"""
Подключение к SQLite и создание таблиц.
"""
import os

import aiosqlite

from config import DATABASE_PATH
from utils.basic import logger

SCHEMA_GROUPS = """
                CREATE TABLE IF NOT EXISTS groups
                (
                    id
                    INTEGER
                    PRIMARY
                    KEY
                    AUTOINCREMENT,
                    group_key
                    TEXT
                    NOT
                    NULL
                    UNIQUE,
                    name
                    TEXT
                    NOT
                    NULL,
                    chat_id
                    INTEGER
                    NOT
                    NULL,
                    thread_id
                    INTEGER,
                    schedule_source_type
                    TEXT
                    NOT
                    NULL
                    DEFAULT
                    'local',
                    schedule_source_value
                    TEXT
                    NOT
                    NULL,
                    send_hour
                    INTEGER
                    NOT
                    NULL
                    DEFAULT
                    5,
                    send_minute
                    INTEGER
                    NOT
                    NULL
                    DEFAULT
                    5,
                    enable_image
                    INTEGER
                    NOT
                    NULL
                    DEFAULT
                    1,
                    enable_tomorrow_button
                    INTEGER
                    NOT
                    NULL
                    DEFAULT
                    0,
                    created_at
                    TEXT
                    NOT
                    NULL
                    DEFAULT (
                    datetime
                (
                    'now'
                ))
                    ); \
                """

SCHEMA_ADMINS = """
                CREATE TABLE IF NOT EXISTS admins
                (
                    user_id
                    INTEGER
                    NOT
                    NULL
                    PRIMARY
                    KEY
                ); \
                """


async def init_db() -> None:
    """
    Инициализирует БД: создаёт директорию для файла БД и таблицы groups и admins.

    Алгоритм: создание родительской директории DATABASE_PATH при необходимости,
    подключение к SQLite, выполнение SCHEMA_GROUPS и SCHEMA_ADMINS (CREATE TABLE IF NOT EXISTS), commit.

    Returns:
        None.

    Raises:
        OSError при невозможности создать директорию; aiosqlite.Error при ошибках SQL.
    """
    dirpath = os.path.dirname(DATABASE_PATH)
    if dirpath:
        os.makedirs(dirpath, exist_ok=True)
    logger.debug("Initializing database at %s", DATABASE_PATH)
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(SCHEMA_GROUPS)
        logger.debug("Database: table groups created/checked")
        await db.execute(SCHEMA_ADMINS)
        logger.debug("Database: table admins created/checked")
        await db.commit()
    logger.info("Database initialized: %s", DATABASE_PATH)


def get_connection():
    """
    Возвращает контекстный менеджер подключения к SQLite (async with).

    Returns:
        Контекстный менеджер aiosqlite.connect(DATABASE_PATH). Использование:
        async with get_connection() as db: ...
    """
    return aiosqlite.connect(DATABASE_PATH)
