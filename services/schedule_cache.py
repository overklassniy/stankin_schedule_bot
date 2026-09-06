"""
Гибридный кэш расписания: PDF на диске с TTL и распарсенный результат в памяти.

PDF-файлы сохраняются в SCHEDULE_CACHE_DIR и переиспользуются, пока не истечёт TTL.
Распарсенное расписание хранится в памяти и инвалидируется при изменении PDF-файла
на диске (по mtime и размеру). Это исключает повторные сетевые запросы к Moodle
и повторный парсинг PDF при частых командах /schedule.
"""
import asyncio
import os
from typing import Optional

import aiofiles.os

from config import SCHEDULE_CACHE_DIR, SCHEDULE_CACHE_TTL
from services.moodle_client import download_schedule_pdf
from utils.basic import logger
from utils.parser import parse_pdf


# Кэш распарсенного расписания в памяти.
# Ключ — (group_code, mtime, size), значение — словарь расписания.
# Инвалидация происходит при изменении PDF-файла на диске.
_schedule_cache: dict = {}

# Метаданные скачанных PDF: group_code -> (download_time, file_path).
# Используется для проверки TTL дискового кэша.
_pdf_meta: dict = {}

# Блокировки для предотвращения параллельного скачивания одного и того же PDF.
# Ключ — group_code, значение — asyncio.Lock.
_download_locks: dict = {}


def _safe_filename(group_code: str) -> str:
    """
    Преобразует код группы в безопасное имя файла.

    Args:
        group_code: Код группы (например «ИДБ-24-10»).

    Returns:
        Имя файла с расширением .pdf, безопасное для файловой системы.
    """
    # Заменяем символы, недопустимые в именах файлов на Windows и Linux
    safe = group_code.strip().replace("/", "_").replace("\\", "_").replace(":", "_")
    safe = safe.replace("*", "_").replace("?", "_").replace('"', "_").replace("<", "_").replace(">", "_").replace("|", "_")
    return f"{safe}.pdf"


def _get_pdf_path(group_code: str) -> str:
    """
    Возвращает путь к PDF-файлу группы в кэше на диске.

    Args:
        group_code: Код группы.

    Returns:
        Абсолютный путь к файлу в SCHEDULE_CACHE_DIR.
    """
    return os.path.join(SCHEDULE_CACHE_DIR, _safe_filename(group_code))


async def _file_signature(path: str) -> Optional[tuple]:
    """
    Асинхронно возвращает сигнатуру файла (mtime, size) для проверки изменений.

    Args:
        path: Путь к файлу.

    Returns:
        Кортеж (mtime, size) или None, если файл не существует.
    """
    try:
        st = await aiofiles.os.stat(path)
        return (st.st_mtime, st.st_size)
    except OSError:
        return None


async def get_cached_pdf_path(group_code: str) -> Optional[str]:
    """
    Возвращает путь к актуальному PDF расписания группы.

    Если PDF уже есть в дисковом кэше и TTL не истёк — возвращает путь к нему.
    Иначе скачивает PDF с Moodle в SCHEDULE_CACHE_DIR и обновляет метаданные.
    Параллельные запросы для одного group_code ожидают завершения скачивания
    через блокировку, чтобы не дублировать сетевые запросы.

    Args:
        group_code: Код группы (например «ИДБ-24-10»).

    Returns:
        Путь к PDF-файлу или None, если group_code пустой или скачивание не удалось.
    """
    if not group_code:
        return None

    code = group_code.strip()
    if not code:
        return None

    # Блокировка на group_code, чтобы не скачивать один файл параллельно
    lock = _download_locks.setdefault(code, asyncio.Lock())
    async with lock:
        pdf_path = _get_pdf_path(code)
        meta = _pdf_meta.get(code)

        # Проверяем дисковый кэш: файл существует и TTL не истёк
        if meta and await _file_signature(pdf_path):
            download_time, _ = meta
            age = asyncio.get_event_loop().time() - download_time
            if age < SCHEDULE_CACHE_TTL:
                logger.debug("schedule_cache: PDF cache hit group_code=%s age=%.0fs", code, age)
                return pdf_path
            logger.debug("schedule_cache: PDF cache expired group_code=%s age=%.0fs", code, age)

        # Промах кэша — скачиваем
        logger.debug("schedule_cache: downloading PDF for group_code=%s", code)
        await aiofiles.os.makedirs(SCHEDULE_CACHE_DIR, exist_ok=True)
        path = await download_schedule_pdf(code, save_dir=SCHEDULE_CACHE_DIR)
        if not path:
            logger.warning("schedule_cache: download failed for group_code=%s", code)
            return None

        # download_schedule_pdf сохраняет под именем из Moodle; переименовываем в каноничное
        if os.path.abspath(path) != os.path.abspath(pdf_path):
            try:
                await aiofiles.os.replace(path, pdf_path)
            except OSError as e:
                # Если переименование не удалось — используем оригинальный путь
                logger.debug("schedule_cache: rename failed, using original path %s: %s", path, e)
                pdf_path = path

        _pdf_meta[code] = (asyncio.get_event_loop().time(), pdf_path)
        logger.info("schedule_cache: PDF cached group_code=%s -> %s", code, pdf_path)
        return pdf_path


async def get_cached_schedule(group_code: str) -> Optional[dict]:
    """
    Возвращает распарсенное расписание группы из кэша.

    Сначала получает актуальный PDF через get_cached_pdf_path, затем проверяет
    кэш распарсенного расписания в памяти по сигнатуре файла (mtime, size).
    При промахе парсит PDF в executor (не блокируя event loop) и сохраняет
    результат в кэш.

    Args:
        group_code: Код группы (например «ИДБ-24-10»).

    Returns:
        Словарь расписания (день недели -> список занятий) или None при ошибке.
    """
    pdf_path = await get_cached_pdf_path(group_code)
    if not pdf_path:
        return None

    code = group_code.strip()
    sig = await _file_signature(pdf_path)
    if not sig:
        logger.warning("schedule_cache: PDF disappeared after download group_code=%s", code)
        return None

    cache_key = (code, sig)
    cached = _schedule_cache.get(cache_key)
    if cached is not None:
        logger.debug("schedule_cache: schedule cache hit group_code=%s", code)
        return cached

    # Парсим в executor, чтобы не блокировать event loop
    logger.debug("schedule_cache: parsing PDF for group_code=%s", code)
    loop = asyncio.get_running_loop()
    try:
        result = await loop.run_in_executor(None, parse_pdf, pdf_path)
    except Exception as e:
        logger.exception("schedule_cache: parse failed for group_code=%s: %s", code, e)
        return None

    # Очищаем устаревшие записи для этого group_code (другие сигнатуры файла)
    stale_keys = [k for k in _schedule_cache if k[0] == code and k != cache_key]
    for k in stale_keys:
        _schedule_cache.pop(k, None)

    _schedule_cache[cache_key] = result
    logger.info("schedule_cache: schedule cached group_code=%s days=%s", code, len(result))
    return result


async def invalidate_cache(group_code: str) -> None:
    """
    Инвалидирует кэш расписания для группы.

    Удаляет записи из кэша памяти и метаданные PDF, чтобы следующий запрос
    скачал свежий PDF и распарсил его заново. Используется кнопкой
    «Проверить загрузку» в настройках.

    Args:
        group_code: Код группы.
    """
    if not group_code:
        return
    code = group_code.strip()
    stale_keys = [k for k in _schedule_cache if k[0] == code]
    for k in stale_keys:
        _schedule_cache.pop(k, None)
    _pdf_meta.pop(code, None)
    logger.info("schedule_cache: invalidated cache for group_code=%s", code)
