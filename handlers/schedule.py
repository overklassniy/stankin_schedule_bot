from datetime import datetime, timedelta

from aiogram import Router, types, F
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.types import CallbackQuery

from db.models import resolve_group
from services.schedule_cache import get_cached_schedule
from utils.basic import logger, days_until_date
from utils.parser import get_today_schedule, create_message

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
    logger.debug("schedule command from user_id=%s chat_id=%s text=%s", message.from_user.id, message.chat.id, message.text)
    thread_id = getattr(message, "message_thread_id", None)
    logger.debug("resolve_group chat_id=%s thread_id=%s", message.chat.id, thread_id)
    group = await resolve_group(message.chat.id, thread_id)
    if not group:
        logger.info("User %s tried /schedule in unattached chat %s", message.from_user.id, message.chat.id)
        await message.answer(text="Эту команду можно использовать только в привязанной к боту группе.")
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
    logger.debug("schedule: increment_day=%s", increment_day)

    date = (datetime.today() + timedelta(increment_day)).strftime("%d.%m")
    group_code = (group.get("schedule_source_value") or "").strip()
    logger.debug("schedule: requesting schedule for group id=%s code=%s", group["id"], group_code)
    schedule = await get_cached_schedule(group_code)
    if not schedule:
        logger.warning("Schedule: no schedule for group (chat_id=%s)", message.chat.id)
        await message.answer(
            text="Источник расписания не задан или недоступен. Настройте в /settings (кнопка «Источник расписания»)."
        )
        return
    try:
        today_schedule = get_today_schedule(schedule, increment_day)
    except Exception as e:
        logger.exception("Schedule: parse failed for chat_id=%s: %s", message.chat.id, e)
        await message.answer(text=f"Ошибка загрузки расписания: {e}")
        return
    try:
        message_text = create_message(today_schedule, increment_day, scheduled=False)
    except Exception:
        logger.exception("create_message failed for schedule command")
        await message.answer(text="Не удалось сформировать расписание.")
        return
    if message_text == "Выходной":
        logger.debug("schedule: Sunday, sending holiday message")
        message_text = f"<b>{date} - Воскресенье. Занятий нет!</b>"
    await message.answer(text=message_text, parse_mode=ParseMode.HTML)
    logger.info("Sent schedule date=%s to user_id=%s chat_id=%s", date, message.from_user.id, message.chat.id)


@router.message(Command("tomorrow", "t"))
async def handle_tomorrow_command(message: types.Message) -> None:
    """
    Команды /tomorrow и /t: отправляет расписание на завтра в привязанную группу.

    Логика аналогична handle_schedule_command с increment_day=1. Требует привязанную группу и
    настроенный код группы (источник расписания).

    Args:
        message: Сообщение с командой.
    """
    logger.debug("tomorrow command from user_id=%s chat_id=%s", message.from_user.id, message.chat.id)
    thread_id = getattr(message, "message_thread_id", None)
    group = await resolve_group(message.chat.id, thread_id)
    if not group:
        logger.info("User %s tried /tomorrow in unattached chat %s", message.from_user.id, message.chat.id)
        await message.answer(text="Эту команду можно использовать только в привязанной к боту группе.")
        return

    increment_day = 1
    date = (datetime.today() + timedelta(increment_day)).strftime("%d.%m")
    group_code = (group.get("schedule_source_value") or "").strip()
    schedule = await get_cached_schedule(group_code)
    if not schedule:
        logger.warning("Tomorrow: no schedule for group (chat_id=%s)", message.chat.id)
        await message.answer(
            text="Источник расписания не задан или недоступен. Настройте в /settings."
        )
        return
    try:
        today_schedule = get_today_schedule(schedule, increment_day)
    except Exception as e:
        logger.exception("Tomorrow: parse failed for chat_id=%s: %s", message.chat.id, e)
        await message.answer(text=f"Ошибка загрузки расписания: {e}")
        return
    try:
        message_text = create_message(today_schedule, increment_day, scheduled=False)
    except Exception:
        logger.exception("create_message failed for tomorrow command")
        await message.answer(text="Не удалось сформировать расписание.")
        return
    if message_text == "Выходной":
        logger.debug("tomorrow: Sunday, sending holiday message")
        message_text = f"<b>{date} - Воскресенье. Занятий нет!</b>"
    await message.answer(text=message_text, parse_mode=ParseMode.HTML)
    logger.info("Sent tomorrow schedule date=%s to user_id=%s chat_id=%s", date, message.from_user.id, message.chat.id)


@router.callback_query(F.data == "tomorrow")
async def handle_tomorrow_query(call: CallbackQuery) -> None:
    """
    Обработка нажатия inline-кнопки «Расписание на завтра».

    Вызывается только если у группы включена кнопка (enable_tomorrow_button). Делегирует
    отправку handle_tomorrow_command(call.message).

    Args:
        call: CallbackQuery от нажатия кнопки.
    """
    logger.debug("tomorrow callback from user_id=%s chat_id=%s", call.from_user.id, call.message.chat.id)
    thread_id = getattr(call.message, "message_thread_id", None)
    group = await resolve_group(call.message.chat.id, thread_id)
    if not group:
        logger.debug("tomorrow callback: no group for chat_id=%s", call.message.chat.id)
        return
    if not group.get("enable_tomorrow_button"):
        logger.debug("tomorrow callback: button disabled for group id=%s", group["id"])
        return
    await handle_tomorrow_command(call.message)
    logger.info("Sent schedule via tomorrow button chat_id=%s user_id=%s", call.message.chat.id, call.message.from_user.id)
