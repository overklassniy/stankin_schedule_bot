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
    github_link = "https://github.com/overklassniy/stankin_schedule_bot/"
    try:
        await message.answer(f"Исходный код бота доступен на GitHub: {github_link}")
        logger.info(f"Sent GitHub link to {message.chat.id}")
    except Exception as e:
        logger.error(f"Error sending GitHub link to {message.chat.id}: {e}")
