from aiogram import Router, types
from aiogram.filters import Command
from aiogram.types import BotCommand

from utils.basic import logger

router = Router()


@router.message(Command(BotCommand(command="code", description="Получить ссылку на GitHub репозиторий бота")))
async def handle_code_command(message: types.Message) -> None:
    """
    Команда /code: отправляет в чат ссылку на репозиторий бота на GitHub.

    Args:
        message: Входящее сообщение с командой.
    """
    logger.debug("code command from user_id=%s chat_id=%s", message.from_user.id, message.chat.id)
    github_link = "https://github.com/overklassniy/stankin_schedule_bot/"
    try:
        await message.answer(f"Исходный код бота доступен на GitHub: {github_link}")
        logger.info("Sent GitHub link to chat_id=%s", message.chat.id)
    except Exception as e:
        logger.error("Error sending GitHub link to chat_id=%s: %s", message.chat.id, e)
