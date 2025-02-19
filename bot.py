import asyncio
import os
import sys
from datetime import datetime, timedelta
from random import choice

from aiogram import Bot, Dispatcher, types, F
from aiogram.enums import ChatType, ParseMode
from aiogram.filters import Command
from aiogram.types import BotCommand, FSInputFile, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from dotenv import load_dotenv

sys.path.append("utils")
from basic import logger, config, days_until_date
from parser import parse_pdf, get_today_schedule, create_message

# Загрузка переменных окружения
load_dotenv()
TOKEN = os.getenv('BOT_TOKEN')

# Инициализация диспетчера событий
dp = Dispatcher()

# Идентификатор бота
bot_id = None


# Обработчик команды /code
@dp.message(Command(BotCommand(command='code', description='Получить ссылку на GitHub репозиторий бота')))
async def handle_code_command(message: types.Message) -> None:
    """
    Обрабатывает команду /code и отправляет ссылку на GitHub репозиторий.

    Args:
        message (types.Message): Сообщение, содержащее команду /code.
    """
    github_link = "https://github.com/overklassniy/stankin_schedule_bot/"
    try:
        # Пробуем отправить пользователю ссылку на репозиторий
        await message.answer(f"Исходный код бота доступен на GitHub: {github_link}")
        logger.info(f"Sent GitHub link to {message.chat.id}")
    except Exception as e:
        logger.error(f"Error sending GitHub link to {message.chat.id}: {e}")


# Обработчик команды /schedule
@dp.message(Command(BotCommand(command='schedule', description='Получить расписание на день')))
async def handle_schedule_command(message: types.Message) -> None:
    """
    Обрабатывает команду /schedule и отправляет расписание на день.

    Args:
        message (types.Message): Сообщение, содержащее команду /schedule.
    """
    if config['ENABLE_SECURE'] and message.chat.id != config['GROUP_ID']:
        await message.answer(text='Эту команду можно использовать только в указанной группе.')
        logger.info(f"{message.from_user.id} tried to use {message.text} in {message.chat.id}")
        return None
    # Получаем аргументы из текста сообщения (например, если указано смещение по дате)
    args = message.text.split()
    try:
        # Пробуем извлечь число, чтобы учесть смещение по дням
        arg = args[-1]
        if '.' in arg:
            increment_day = days_until_date(arg)
        else:
            increment_day = int(args[-1])
    except Exception as e:
        increment_day = 0

    # Формируем дату с учётом смещения
    date = (datetime.today() + timedelta(increment_day)).strftime('%d.%m')

    # Получаем расписание на нужный день
    today_schedule = get_today_schedule(parse_pdf(config['PDF_PATH']), increment_day)
    message_text = create_message(today_schedule, increment_day, scheduled=False)
    # Проверяем, если это выходной (воскресенье)
    if message_text == 'Выходной':
        message_text = f'<b>{date} - Воскресенье. Занятий нет!</b>'
    # Отправляем сообщение с расписанием пользователю
    await message.answer(text=message_text, parse_mode=ParseMode.HTML)

    logger.info(f"Sent schedule for {date} to {message.from_user.id}")


# Обработчик команды /tomorrow
@dp.message(Command(BotCommand(command='tomorrow', description='Получить расписание на завтра')))
async def handle_tomorrow_command(message: types.Message) -> None:
    """
    Обрабатывает команду /tomorrow и отправляет расписание на завтра.

    Args:
        message (types.Message): Сообщение, содержащее команду /tomorrow.
    """
    if config['ENABLE_SECURE'] and message.chat.id != config['GROUP_ID']:
        await message.answer(text='Эту команду можно использовать только в указанной группе.')
        logger.info(f"{message.from_user.id} tried to use {message.text} in {message.chat.id}")
        return None

    increment_day = 1

    # Формируем дату с учётом смещения
    date = (datetime.today() + timedelta(increment_day)).strftime('%d.%m')

    # Получаем расписание на нужный день
    today_schedule = get_today_schedule(parse_pdf(config['PDF_PATH']), increment_day)
    message_text = create_message(today_schedule, increment_day, scheduled=False)
    # Проверяем, если это выходной (воскресенье)
    if message_text == 'Выходной':
        message_text = f'<b>{date} - Воскресенье. Занятий нет!</b>'
    # Отправляем сообщение с расписанием пользователю
    await message.answer(text=message_text, parse_mode=ParseMode.HTML)

    logger.info(f"Sent schedule for {date} to {message.from_user.id}")


# Обработчик нажатия на кнопку с данными 'tomorrow' в inline-кнопке
@dp.callback_query(F.data == 'tomorrow')
async def handle_tomorrow_query(call: CallbackQuery) -> None:
    """
    Обрабатывает нажатие на inline кнопку с данными 'tomorrow'.

    Args:
        call (CallbackQuery): Объект CallbackQuery, содержащий информацию о нажатии на кнопку.
    """
    if config["ENABLE_TOMORROW_BUTTON"]:
        await handle_tomorrow_command(call.message)
        logger.info(f"Sent schedule for {call.message.chat.id} to {call.message.from_user.id} via inline button")


# Обработчик личных сообщений
@dp.message(F.chat.func(lambda chat: chat.type == ChatType.PRIVATE))
async def handle_private_message(message: types.Message) -> None:
    """
    Обрабатывает личные сообщения пользователей.

    Args:
        message (types.Message): Сообщение, полученное ботом.
    """
    # Ответ пользователю, когда бот получает личное сообщение
    response_text = f"Привет, это эксклюзивный бот для отправки расписания {config['GROUP']} и пока у меня нет функционала в личных сообщениях. Если Вы заинтересованы в настройке этого бота для получения своего расписания, то воспользуйтесь моим исходным кодом (/code)."
    try:
        await message.answer(response_text)
        logger.info(f"Sent private message to {message.chat.id}")
    except Exception as e:
        logger.error(f"Error sending private message to {message.chat.id}: {e}")


# Функция для отправки ежедневного сообщения с расписанием
async def send_daily_message(bot: Bot) -> None:
    """
    Периодически отправляет расписание группы в чат.

    Args:
        bot (Bot): Экземпляр бота для отправки сообщений.
    """
    # Небольшая задержка перед началом отправки сообщений
    await asyncio.sleep(10)
    chat_id = config['GROUP_ID']

    while True:
        now = datetime.now()
        # Проверяем время отправки расписания (в час HOUR и в минуты, заданные в MINUTES диапазоне)
        if now.hour == config['HOUR'] and now.minute in range(config['MINUTES']):
            # Получаем расписание на текущий день
            today_schedule = get_today_schedule(parse_pdf(config['PDF_PATH']))
            message_text = create_message(today_schedule)
            if message_text != 'Выходной':
                keyboard = None

                # Проверяем, включена ли кнопка "Расписание на завтра"
                if config["ENABLE_TOMORROW_BUTTON"]:
                    inline_kb_list = [
                        [InlineKeyboardButton(text="Расписание на завтра", callback_data='tomorrow')]
                    ]
                    keyboard = InlineKeyboardMarkup(inline_keyboard=inline_kb_list)

                # Если включен режим отправки изображения
                if config["ENABLE_IMAGE"]:
                    images_dir = config['IMAGES_DIR']
                    image = FSInputFile(f'{images_dir}/{choice(os.listdir(images_dir))}')
                    # Если включен режим отправки в тему супергруппы
                    if config['THREADED']:
                        await bot.send_photo(chat_id=chat_id, message_thread_id=config['THREAD_NUMBER'], photo=image, caption=message_text,
                                             parse_mode=ParseMode.HTML, reply_markup=keyboard if keyboard else None)
                    else:
                        await bot.send_photo(chat_id=chat_id, photo=image, caption=message_text, parse_mode=ParseMode.HTML, reply_markup=keyboard if keyboard else None)
                else:
                    # Отправка только текста расписания
                    if config['THREADED']:
                        await bot.send_message(chat_id=chat_id, message_thread_id=config['THREAD_NUMBER'], text=message_text,
                                               parse_mode=ParseMode.HTML, reply_markup=keyboard if keyboard else None)
                    else:
                        await bot.send_message(chat_id=chat_id, text=message_text, parse_mode=ParseMode.HTML, reply_markup=keyboard if keyboard else None)
                logger.info(f"Sent daily schedule to {chat_id}")
            # После отправки сообщения, бот "засыпает" на SLEEP_TIME секунд
            await asyncio.sleep(config['SLEEP_TIME'])
        else:
            # Проверка каждые CHECK_TIME_INTERVAL секунд
            await asyncio.sleep(config['CHECK_TIME_INTERVAL'])


async def main() -> None:
    """
    Запускает бота и инициализирует отправку ежедневных сообщений.
    """
    global bot_id
    bot = Bot(token=TOKEN)
    bot_id = bot.id

    # Создаём асинхронную задачу для ежедневной отправки расписания
    asyncio.create_task(send_daily_message(bot))

    # Запускаем диспетчер событий с поллингом (с периодом 30 секунд)
    await dp.start_polling(bot, polling_timeout=30)


# Запуск бота
if __name__ == '__main__':
    asyncio.run(main())
