"""
Работа с группами и админами в БД.
"""
from typing import Optional, List, Any

import aiosqlite

from config import DATABASE_PATH, DEFAULT_SEND_HOUR, DEFAULT_SEND_MINUTE, DEFAULT_ENABLE_IMAGE, \
    DEFAULT_ENABLE_TOMORROW_BUTTON


def _row_to_group(row: tuple) -> dict:
    """
    Преобразует кортеж-строку из таблицы groups в словарь с именованными ключами.

    Args:
        row: Кортеж (id, group_key, name, chat_id, thread_id, schedule_source_type,
            schedule_source_value, send_hour, send_minute, enable_image, enable_tomorrow_button, created_at).

    Returns:
        Словарь с ключами id, group_key, name, chat_id, thread_id, schedule_source_type,
        schedule_source_value, send_hour, send_minute, enable_image (bool), enable_tomorrow_button (bool), created_at.
    """
    return {
        "id": row[0],
        "group_key": row[1],
        "name": row[2],
        "chat_id": row[3],
        "thread_id": row[4],
        "schedule_source_type": row[5],
        "schedule_source_value": row[6],
        "send_hour": row[7],
        "send_minute": row[8],
        "enable_image": bool(row[9]),
        "enable_tomorrow_button": bool(row[10]),
        "created_at": row[11],
    }


async def get_group_by_id(group_id: int) -> Optional[dict]:
    """
    Возвращает запись группы по первичному ключу.

    Args:
        group_id: ID группы (поле id в таблице groups).

    Returns:
        Словарь группы в формате _row_to_group или None, если запись не найдена.
    """
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM groups WHERE id = ?", (group_id,)) as cursor:
            row = await cursor.fetchone()
            if row:
                return _row_to_group(tuple(row))
    return None


async def resolve_group(chat_id: int, thread_id: Optional[int]) -> Optional[dict]:
    """
    Определяет группу по чату и опционально топику: сначала поиск по (chat_id, thread_id),
    при отсутствии – по chat_id без топика (первая подходящая запись).

    Args:
        chat_id: ID чата Telegram.
        thread_id: ID топика в супергруппе или None.

    Returns:
        Словарь группы или None.
    """
    group = await get_group_by_chat_and_thread(chat_id, thread_id)
    if group:
        return group
    return await get_group_by_chat(chat_id)


async def get_group_by_chat(chat_id: int) -> Optional[dict]:
    """
    Возвращает одну группу с данным chat_id (любой thread_id или без топика).

    Args:
        chat_id: ID чата Telegram.

    Returns:
        Словарь первой найденной группы с этим chat_id или None.
    """
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
                "SELECT * FROM groups WHERE chat_id = ? LIMIT 1",
                (chat_id,),
        ) as cursor:
            row = await cursor.fetchone()
            if row:
                return _row_to_group(tuple(row))
    return None


async def get_group_by_chat_and_thread(chat_id: int, thread_id: Optional[int]) -> Optional[dict]:
    """
    Возвращает группу по паре (chat_id, thread_id). Для thread_id=None ищет запись с NULL/0 топика.

    Args:
        chat_id: ID чата Telegram.
        thread_id: ID топика или None (без топика).

    Returns:
        Словарь группы или None.
    """
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        if thread_id is not None:
            async with db.execute(
                    "SELECT * FROM groups WHERE chat_id = ? AND thread_id = ?",
                    (chat_id, thread_id),
            ) as cursor:
                row = await cursor.fetchone()
        else:
            async with db.execute(
                    "SELECT * FROM groups WHERE chat_id = ? AND (thread_id IS NULL OR thread_id = 0)",
                    (chat_id,),
            ) as cursor:
                row = await cursor.fetchone()
        if row:
            return _row_to_group(tuple(row))
    return None


async def get_all_groups() -> List[dict]:
    """
    Возвращает все группы из БД в порядке id (для планировщика и обхода).

    Returns:
        Список словарей групп в формате _row_to_group.
    """
    async with aiosqlite.connect(DATABASE_PATH) as db:
        async with db.execute("SELECT * FROM groups ORDER BY id") as cursor:
            rows = await cursor.fetchall()
            return [_row_to_group(tuple(r)) for r in rows]


async def update_group_settings(
        group_id: int,
        *,
        thread_id: Optional[int] = None,
        send_hour: Optional[int] = None,
        send_minute: Optional[int] = None,
        enable_image: Optional[bool] = None,
        enable_tomorrow_button: Optional[bool] = None,
        schedule_source_type: Optional[str] = None,
        schedule_source_value: Optional[str] = None,
) -> None:
    """
    Обновляет настройки группы. Обновляются только переданные (не None) поля.

    Args:
        group_id: ID группы.
        thread_id: Новый ID топика (опционально).
        send_hour: Час отправки 0–23 (опционально).
        send_minute: Минута отправки 0–59 (опционально).
        enable_image: Включить картинки в рассылке (опционально).
        enable_tomorrow_button: Показывать кнопку «Завтра» (опционально).
        schedule_source_type: Тип источника, например "moodle" (опционально).
        schedule_source_value: Код группы или значение источника (опционально).

    Returns:
        None.
    """
    updates = []
    args: List[Any] = []
    if thread_id is not None:
        updates.append("thread_id = ?")
        args.append(thread_id)
    if send_hour is not None:
        updates.append("send_hour = ?")
        args.append(send_hour)
    if send_minute is not None:
        updates.append("send_minute = ?")
        args.append(send_minute)
    if enable_image is not None:
        updates.append("enable_image = ?")
        args.append(1 if enable_image else 0)
    if enable_tomorrow_button is not None:
        updates.append("enable_tomorrow_button = ?")
        args.append(1 if enable_tomorrow_button else 0)
    if schedule_source_type is not None:
        updates.append("schedule_source_type = ?")
        args.append(schedule_source_type)
    if schedule_source_value is not None:
        updates.append("schedule_source_value = ?")
        args.append(schedule_source_value)
    if not updates:
        return
    args.append(group_id)
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            f"UPDATE groups SET {', '.join(updates)} WHERE id = ?",
            args,
        )
        await db.commit()


async def is_admin(user_id: int) -> bool:
    """
    Проверяет, есть ли пользователь в таблице admins (глобальные админы бота).

    Args:
        user_id: Telegram user id.

    Returns:
        True, если запись в admins найдена, иначе False.
    """
    async with aiosqlite.connect(DATABASE_PATH) as db:
        async with db.execute(
                "SELECT 1 FROM admins WHERE user_id = ?",
                (user_id,),
        ) as cursor:
            row = await cursor.fetchone()
            return row is not None


async def add_admin(user_id: int) -> None:
    """
    Добавляет пользователя в таблицу admins. Дубликаты игнорируются (INSERT OR IGNORE).

    Args:
        user_id: Telegram user id.

    Returns:
        None.
    """
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            "INSERT OR IGNORE INTO admins (user_id) VALUES (?)",
            (user_id,),
        )
        await db.commit()


async def create_group(
        chat_id: int,
        name: str,
        thread_id: Optional[int] = None,
) -> Optional[dict]:
    """
    Создаёт новую запись группы при добавлении бота в чат.

    Алгоритм: формирование group_key (chat_{chat_id} или chat_{chat_id}_t{thread_id}),
    INSERT с дефолтами из конфига (время, картинки, кнопка «Завтра», источник local/пусто),
    получение last_insert_rowid и возврат полной записи через get_group_by_id.

    Args:
        chat_id: ID чата Telegram.
        name: Название чата (обрезается до 255 символов).
        thread_id: ID топика или None.

    Returns:
        Словарь созданной группы или None при ошибке.
    """
    group_key = f"chat_{chat_id}" if not thread_id else f"chat_{chat_id}_t{thread_id}"
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            """INSERT INTO groups (group_key, name, chat_id, thread_id,
                                   schedule_source_type, schedule_source_value,
                                   send_hour, send_minute, enable_image, enable_tomorrow_button)
               VALUES (?, ?, ?, ?, 'local', '', ?, ?, ?, ?)
            """,
            (
                group_key,
                name[:255] if name else str(chat_id),
                chat_id,
                thread_id,
                DEFAULT_SEND_HOUR,
                DEFAULT_SEND_MINUTE,
                1 if DEFAULT_ENABLE_IMAGE else 0,
                1 if DEFAULT_ENABLE_TOMORROW_BUTTON else 0,
            ),
        )
        await db.commit()
        cur = await db.execute("SELECT last_insert_rowid()")
        row_id = (await cur.fetchone())[0]
    return await get_group_by_id(row_id)


async def delete_groups_by_chat_id(chat_id: int) -> int:
    """
    Удаляет все записи групп с данным chat_id (при удалении бота из чата).

    Args:
        chat_id: ID чата Telegram.

    Returns:
        Количество удалённых строк.
    """
    async with aiosqlite.connect(DATABASE_PATH) as db:
        cur = await db.execute("DELETE FROM groups WHERE chat_id = ?", (chat_id,))
        n = cur.rowcount if cur.rowcount >= 0 else 0
        await db.commit()
        return n
