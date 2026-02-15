from datetime import datetime, timedelta

from aiogram import Router, types, F
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.types import CallbackQuery

from db.models import resolve_group
from services.scheduler import get_schedule_pdf_path
from utils.basic import logger, days_until_date
from utils.parser import parse_pdf, get_today_schedule, create_message

router = Router()


@router.message(Command("schedule", "s"))
async def handle_schedule_command(message: types.Message) -> None:
    """
    Команды /schedule и /s: отправляет расписание на день в привязанную группу.

    Алгоритм: resolve_group по chat_id и thread_id; при отсутствии группы – сообщение об ошибке;
    из текста сообщения извлекается аргумент (дата дд.мм или число дней); загрузка PDF, парс,
    get_today_schedule и create_message; отправка HTML. Воскресенье – отдельное сообщение.

    Args:
        message: Сообщение с командой (может содержать аргумент, например /s 1 или /s 25.12).
    """
    thread_id = getattr(message, "message_thread_id", None)
    group = await resolve_group(message.chat.id, thread_id)
    if not group:
        await message.answer(text="Эту команду можно использовать только в привязанной к боту группе.")
        logger.info(f"{message.from_user.id} tried to use {message.text} in {message.chat.id}")
        return
    args = message.text.split()
    try:
        arg = args[-1]
        if "." in arg:
            increment_day = days_until_date(arg)
        else:
            increment_day = int(args[-1])
    except Exception:
        increment_day = 0

    date = (datetime.today() + timedelta(increment_day)).strftime("%d.%m")
    pdf_path = await get_schedule_pdf_path(group)
    if not pdf_path:
        await message.answer(
            text="Источник расписания не задан или недоступен. Настройте в /settings (кнопка «Источник расписания»)."
        )
        return
    try:
        today_schedule = get_today_schedule(parse_pdf(pdf_path), increment_day)
    except Exception as e:
        await message.answer(text=f"Ошибка загрузки расписания: {e}")
        return
    try:
        message_text = create_message(today_schedule, increment_day, scheduled=False)
    except Exception:
        logger.exception("create_message failed for schedule command")
        await message.answer(text="Не удалось сформировать расписание.")
        return
    if message_text == "Выходной":
        message_text = f"<b>{date} - Воскресенье. Занятий нет!</b>"
    await message.answer(text=message_text, parse_mode=ParseMode.HTML)
    logger.info(f"Sent schedule for {date} to {message.from_user.id}")


@router.message(Command("tomorrow", "t"))
async def handle_tomorrow_command(message: types.Message) -> None:
    """
    Команды /tomorrow и /t: отправляет расписание на завтра в привязанную группу.

    Логика аналогична handle_schedule_command с increment_day=1. Требует привязанную группу и
    настроенный код группы (источник расписания).

    Args:
        message: Сообщение с командой.
    """
    thread_id = getattr(message, "message_thread_id", None)
    group = await resolve_group(message.chat.id, thread_id)
    if not group:
        await message.answer(text="Эту команду можно использовать только в привязанной к боту группе.")
        logger.info(f"{message.from_user.id} tried to use {message.text} in {message.chat.id}")
        return

    increment_day = 1
    date = (datetime.today() + timedelta(increment_day)).strftime("%d.%m")
    pdf_path = await get_schedule_pdf_path(group)
    if not pdf_path:
        await message.answer(
            text="Источник расписания не задан или недоступен. Настройте в /settings."
        )
        return
    try:
        today_schedule = get_today_schedule(parse_pdf(pdf_path), increment_day)
    except Exception as e:
        await message.answer(text=f"Ошибка загрузки расписания: {e}")
        return
    try:
        message_text = create_message(today_schedule, increment_day, scheduled=False)
    except Exception:
        logger.exception("create_message failed for tomorrow command")
        await message.answer(text="Не удалось сформировать расписание.")
        return
    if message_text == "Выходной":
        message_text = f"<b>{date} - Воскресенье. Занятий нет!</b>"
    await message.answer(text=message_text, parse_mode=ParseMode.HTML)
    logger.info(f"Sent schedule for {date} to {message.from_user.id}")


@router.callback_query(F.data == "tomorrow")
async def handle_tomorrow_query(call: CallbackQuery) -> None:
    """
    Обработка нажатия inline-кнопки «Расписание на завтра».

    Вызывается только если у группы включена кнопка (enable_tomorrow_button). Делегирует
    отправку handle_tomorrow_command(call.message).

    Args:
        call: CallbackQuery от нажатия кнопки.
    """
    thread_id = getattr(call.message, "message_thread_id", None)
    group = await resolve_group(call.message.chat.id, thread_id)
    if group and group.get("enable_tomorrow_button"):
        await handle_tomorrow_command(call.message)
        logger.info(f"Sent schedule for {call.message.chat.id} to {call.message.from_user.id} via inline button")
