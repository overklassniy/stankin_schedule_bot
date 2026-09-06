"""
Планировщик ежедневной отправки расписания по группам из БД.
"""
import asyncio
import os
from datetime import datetime
from random import choice
from typing import Optional

import aiofiles.os
from aiogram import Bot
from aiogram.enums import ParseMode
from aiogram.types import FSInputFile, InlineKeyboardMarkup, InlineKeyboardButton

from config import IMAGES_DIR
from db.models import get_all_groups
from services.schedule_cache import get_cached_pdf_path, get_cached_schedule
from utils.basic import logger
from utils.parser import get_today_schedule, create_message

# Интервал проверки (секунды). Каждые 30с проверяем, не пора ли отправить.
SCHEDULER_CHECK_INTERVAL = 30

# Множество (group_id, "YYYY-MM-DD") – чтобы не отправлять одной группе дважды за день.
_sent_today: set = set()


async def get_schedule_pdf_path(group: dict = None) -> Optional[str]:
    """
    Возвращает путь к PDF расписания группы из кэша.

    Берёт код группы из group["schedule_source_value"], делегирует в
    schedule_cache.get_cached_pdf_path. PDF скачивается только при промахе кэша.

    Args:
        group: Словарь группы из БД (должен содержать schedule_source_value). Может быть None.

    Returns:
        Путь к PDF-файлу в кэше или None, если группа не задана, код пустой или загрузка не удалась.
    """
    if not group:
        logger.debug("get_schedule_pdf_path: no group")
        return None
    group_code = (group.get("schedule_source_value") or "").strip()
    if not group_code:
        logger.debug("get_schedule_pdf_path: empty group_code for group id=%s", group.get("id"))
        return None
    path = await get_cached_pdf_path(group_code)
    logger.debug("get_schedule_pdf_path: group_code=%s -> %s", group_code, path)
    return path


async def _send_schedule(bot: Bot, group: dict, message_text: str) -> None:
    """
    Отправляет готовое сообщение с расписанием в чат группы.

    Алгоритм: если у группы включены картинки и папка IMAGES_DIR существует и не пуста –
    отправляет фото со caption; при ошибке отправки фото – fallback на текстовое сообщение.
    Иначе отправляет только текст. Учитывает thread_id (топик в супергруппе). Добавляет
    inline-кнопку «Расписание на завтра», если enable_tomorrow_button включён.

    Args:
        bot: Экземпляр aiogram Bot для отправки.
        group: Словарь группы (chat_id, thread_id, enable_image, enable_tomorrow_button).
        message_text: Готовый HTML-текст расписания.

    Raises:
        Исключения aiogram при отправке (сеть, права бота и т.д.).
    """
    chat_id = group["chat_id"]
    thread_id = group.get("thread_id")
    logger.debug("_send_schedule: chat_id=%s thread_id=%s enable_image=%s", chat_id, thread_id, group.get("enable_image"))

    keyboard = None
    if group.get("enable_tomorrow_button"):
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Расписание на завтра", callback_data="tomorrow")]
        ])

    kwargs = {"parse_mode": ParseMode.HTML, "reply_markup": keyboard}
    send_kwargs = {"chat_id": chat_id, **kwargs}
    if thread_id:
        send_kwargs["message_thread_id"] = thread_id

    sent = False

    # Попытка отправить с картинкой
    if group.get("enable_image") and await aiofiles.os.path.isdir(IMAGES_DIR):
        images = [f for f in await aiofiles.os.listdir(IMAGES_DIR) if not f.startswith(".")]
        logger.debug("_send_schedule: images count=%s", len(images))
        if images:
            try:
                image = FSInputFile(os.path.join(IMAGES_DIR, choice(images)))
                await bot.send_photo(**send_kwargs, photo=image, caption=message_text)
                sent = True
                logger.debug("_send_schedule: sent as photo to chat_id=%s", chat_id)
            except Exception as e:
                logger.warning("Send photo failed for chat %s, falling back to text: %s", chat_id, e)

    # Если картинка не отправилась – текстом
    if not sent:
        await bot.send_message(**send_kwargs, text=message_text)
        logger.debug("_send_schedule: sent as text to chat_id=%s", chat_id)

    logger.info("Sent daily schedule to chat_id=%s", chat_id)


async def run_daily_scheduler(bot: Bot) -> None:
    """
    Фоновая задача: периодически проверяет время и отправляет расписание по группам.

    Алгоритм: начальная задержка 10 с, затем бесконечный цикл – вызов _scheduler_tick(bot)
    и сон SCHEDULER_CHECK_INTERVAL секунд. Исключения в тике логируются, цикл не прерывается.

    Args:
        bot: Экземпляр aiogram Bot для отправки сообщений.

    Returns:
        Не возвращает значение; корутина выполняется бесконечно.
    """
    await asyncio.sleep(10)
    logger.info("Scheduler started")

    while True:
        try:
            await _scheduler_tick(bot)
        except Exception:
            logger.exception("Scheduler tick failed")

        await asyncio.sleep(SCHEDULER_CHECK_INTERVAL)


async def _scheduler_tick(bot: Bot) -> None:
    """
    Одна итерация планировщика: проверка времени и отправка расписания подходящим группам.

    Алгоритм:
    1. Очистка _sent_today от записей не за сегодня.
    2. Загрузка списка групп из БД.
    3. Для каждой группы: если уже отправляли сегодня — skip; если час/минута не совпадают — skip;
       если код группы пустой — помечаем как «отправлено» и skip; иначе получаем расписание
       из кэша (get_cached_schedule, при промахе скачивает и парсит), формируем сообщение;
       если «Выходной» — помечаем отправку и skip; иначе отправляем и помечаем.

    Args:
        bot: Экземпляр aiogram Bot.
    """
    now = datetime.now()
    today_str = now.strftime("%Y-%m-%d")

    # Очистка _sent_today от вчерашних записей
    global _sent_today
    prev_len = len(_sent_today)
    _sent_today = {(gid, d) for gid, d in _sent_today if d == today_str}
    if prev_len != len(_sent_today):
        logger.debug("_scheduler_tick: cleaned _sent_today %s -> %s entries", prev_len, len(_sent_today))

    groups = await get_all_groups()
    logger.debug("_scheduler_tick: now=%s:%s groups=%s", now.hour, now.minute, len(groups))

    for group in groups:
        group_id = group["id"]

        # Уже отправляли сегодня?
        if (group_id, today_str) in _sent_today:
            continue

        # Совпадает ли время?
        if now.hour != group["send_hour"] or now.minute != group["send_minute"]:
            continue

        logger.debug("_scheduler_tick: processing group id=%s chat_id=%s time match", group_id, group["chat_id"])

        group_code = (group.get("schedule_source_value") or "").strip()
        if not group_code:
            logger.warning("Group %s: group code not set, skipping", group["group_key"])
            _sent_today.add((group_id, today_str))
            continue

        # Получаем расписание из кэша (скачивает и парсит при промахе)
        try:
            schedule = await get_cached_schedule(group_code)
        except Exception:
            logger.exception("Failed to get schedule for group %s", group["group_key"])
            schedule = None

        if not schedule:
            logger.warning("Group %s: schedule not available for code '%s'", group["group_key"], group_code)
            continue

        # Формируем сообщение
        try:
            today_schedule = get_today_schedule(schedule)
            message_text = create_message(today_schedule)
        except Exception:
            logger.exception("Failed to build message for group %s", group["group_key"])
            continue

        if message_text == "Выходной":
            logger.debug("_scheduler_tick: group id=%s Sunday, skip send", group_id)
            _sent_today.add((group_id, today_str))
            continue

        # Отправляем
        logger.info("_scheduler_tick: sending schedule to group id=%s chat_id=%s", group_id, group["chat_id"])
        try:
            await _send_schedule(bot, group, message_text)
            _sent_today.add((group_id, today_str))
        except Exception:
            logger.exception("Failed to send schedule to chat %s", group["chat_id"])
