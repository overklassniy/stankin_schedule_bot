"""
Привязка и отвязка чата при добавлении/удалении бота в группу.
"""
from aiogram import Router, F
from aiogram.types import ChatMemberUpdated

from db.models import create_group, delete_groups_by_chat_id, get_group_by_chat
from utils.basic import logger

router = Router()


@router.my_chat_member(F.chat.func(lambda c: c.type != "private"))
async def on_my_chat_member(event: ChatMemberUpdated) -> None:
    """
    Обработка события изменения статуса бота в чате (добавление/удаление из группы).

    Алгоритм: обрабатываются только события, где изменённый участник – сам бот (new.user.id == bot.id).
    При переходе в member/administrator из left/kicked: если группы для chat_id ещё нет – create_group,
    отправка сообщения «Чат привязан…». При переходе в left/kicked – delete_groups_by_chat_id.

    Args:
        event: ChatMemberUpdated (my_chat_member) для неприватного чата.
    """
    old = event.old_chat_member
    new = event.new_chat_member
    logger.debug("my_chat_member: chat_id=%s old=%s new=%s bot_id=%s", event.chat.id, old.status, new.status, event.bot.id)
    if new.user.id != event.bot.id:
        logger.debug("my_chat_member: not bot, skip")
        return
    chat_id = event.chat.id
    chat_title = event.chat.title or str(chat_id)

    if new.status in ("member", "administrator"):
        if old.status in ("left", "kicked"):
            logger.info("Bot added to chat_id=%s title=%s", chat_id, chat_title)
            existing = await get_group_by_chat(chat_id)
            if existing:
                logger.debug("Bot added: group already exists id=%s", existing["id"])
                return
            group = await create_group(chat_id=chat_id, name=chat_title)
            if group:
                logger.info("Bot added to chat %s (%s), group created id=%s", chat_id, chat_title, group["id"])
                await event.bot.send_message(
                    event.chat.id,
                    f"Чат «{chat_title}» привязан к боту. Настройте расписание: /settings (только для админов).",
                )
            else:
                logger.warning("Bot added: create_group returned None for chat_id=%s", chat_id)
            return
        logger.debug("my_chat_member: bot already in chat, no action")
        return
    if new.status in ("left", "kicked"):
        logger.info("Bot removed from chat_id=%s", chat_id)
        n = await delete_groups_by_chat_id(chat_id)
        if n:
            logger.info("Bot removed from chat %s, %s group(s) deleted", chat_id, n)
        else:
            logger.debug("Bot removed: no groups to delete for chat_id=%s", chat_id)
