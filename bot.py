import asyncio
import os
import sys

from aiogram import Bot
from aiogram.fsm.storage.memory import MemoryStorage
from dotenv import load_dotenv

load_dotenv()
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from aiogram import Dispatcher
from aiogram.client.session.aiohttp import AiohttpSession

from config import ADMIN_IDS, PROXY
from db.database import init_db
from db.models import add_admin
from handlers import router as handlers_router
from services.scheduler import run_daily_scheduler
from utils.basic import logger

TOKEN = os.getenv("BOT_TOKEN")
dp = Dispatcher(storage=MemoryStorage())
dp.include_router(handlers_router)

bot_id = None


async def main() -> None:
    """
    Точка входа: инициализация БД, добавление админов из конфига, запуск бота и планировщика.

    Алгоритм: init_db(); добавление в таблицу admins всех ADMIN_IDS; создание Bot (с прокси
    из PROXY при наличии); запуск run_daily_scheduler в фоне; старт long polling диспетчера.

    Returns:
        None (корутина выполняется до остановки polling).

    Raises:
        Исключения при отсутствии BOT_TOKEN, ошибках БД или сети.
    """
    global bot_id
    await init_db()
    for aid in ADMIN_IDS:
        await add_admin(aid)

    if PROXY:
        logger.info("Using proxy: %s", PROXY)
        session = AiohttpSession(proxy=PROXY)
        bot = Bot(token=TOKEN, session=session)
    else:
        logger.info("Bot started without proxy")
        bot = Bot(token=TOKEN)
    bot_id = bot.id
    logger.info("Bot initialized, ID: %s", bot_id)

    asyncio.create_task(run_daily_scheduler(bot))

    await dp.start_polling(bot, polling_timeout=30)


if __name__ == "__main__":
    asyncio.run(main())
