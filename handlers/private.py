from aiogram import Router, types, F
from aiogram.enums import ChatType
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from utils.basic import logger

router = Router()

WELCOME_LS = """Привет!

Я бот расписания для групп. В группе, куда меня добавят, я буду привязан автоматически.

• /schedule или /s – расписание на сегодня (в привязанной группе)
• /tomorrow или /t – на завтра
• /settings – настройки (админы): группа, время, топик, картинки, кнопка «Завтра»

Добавьте меня в группу, в настройках укажите код группы (например ИДБ-24-10).

Исходный код: /code"""


@router.message(F.chat.func(lambda chat: chat.type == ChatType.PRIVATE))
async def handle_private_message(message: types.Message) -> None:
    """
    Обрабатывает любое сообщение в личном чате: отправляет приветствие и ссылку на GitHub.

    Args:
        message: Входящее сообщение (чат – личный).

    Returns:
        None.
    """
    logger.debug("Private message from user_id=%s chat_id=%s", message.from_user.id, message.chat.id)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Исходный код на GitHub",
                              url="https://github.com/overklassniy/stankin_schedule_bot/")],
    ])
    try:
        await message.answer(WELCOME_LS, reply_markup=kb)
        logger.info("Sent private message to %s", message.chat.id)
    except Exception as e:
        logger.error("Error sending private message to %s: %s", message.chat.id, e)
