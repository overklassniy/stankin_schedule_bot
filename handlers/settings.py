from aiogram import Bot, types, F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery

from db.models import resolve_group, get_group_by_id, get_group_by_chat, update_group_settings, is_admin
from services.scheduler import get_schedule_pdf_path
from utils.basic import logger
from utils.parser import parse_pdf, get_today_schedule

router = Router()


async def can_manage_settings(bot: Bot, user_id: int, chat_id: int, chat_type: str) -> bool:
    """
    Проверяет, может ли пользователь управлять настройками (команды /settings, /settopic и т.д.).

    Алгоритм: если user_id есть в таблице admins – True; иначе для group/supergroup запрос
    get_chat_member и проверка status in (creator, administrator); для остальных типов чата – False.
    Исключения при запросе к API – False.

    Args:
        bot: Экземпляр Bot для get_chat_member.
        user_id: Telegram user id.
        chat_id: ID чата.
        chat_type: Тип чата ("private", "group", "supergroup" и т.д.).

    Returns:
        True, если пользователь – глобальный админ или владелец/админ данного чата.
    """
    if await is_admin(user_id):
        return True
    if chat_type not in ("group", "supergroup"):
        return False
    try:
        member = await bot.get_chat_member(chat_id, user_id)
        return member.status in ("creator", "administrator")
    except Exception:
        return False


class SettingsStates(StatesGroup):
    wait_time = State()
    wait_group_code = State()


def _settings_inline_keyboard(group: dict) -> InlineKeyboardMarkup:
    """
    Строит inline-клавиатуру с текущими значениями настроек группы (код группы, время, картинки, завтра, проверка).

    Args:
        group: Словарь группы из БД.

    Returns:
        InlineKeyboardMarkup с кнопками и callback_data settings_*.
    """
    code = group.get("schedule_source_value") or "не задана"
    img = "Выкл" if not group.get("enable_image") else "Вкл"
    tomorrow = "Выкл" if not group.get("enable_tomorrow_button") else "Вкл"
    h = group.get("send_hour", 0)
    m = group.get("send_minute", 0) or 0
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"Группа: {code}", callback_data="settings_group_code")],
        [InlineKeyboardButton(text=f"Время: {h}:{m:02d}", callback_data="settings_time")],
        [InlineKeyboardButton(text=f"Картинки: {img}", callback_data="settings_image")],
        [InlineKeyboardButton(text=f"Кнопка «Завтра»: {tomorrow}", callback_data="settings_tomorrow")],
        [InlineKeyboardButton(text="Проверить загрузку", callback_data="settings_test_load")],
    ])


# /settings
@router.message(Command("settings"))
async def handle_settings_command(message: types.Message, state: FSMContext, bot: Bot) -> None:
    """
    Команда /settings: открывает настройки группы (сообщение с inline-кнопками под ним).
    Доступ только при can_manage_settings; группа должна быть привязана (resolve_group).
    """
    await state.clear()
    if not await can_manage_settings(bot, message.from_user.id, message.chat.id, message.chat.type):
        # await message.answer("Настройки доступны только администраторам чата.")
        return
    thread_id = getattr(message, "message_thread_id", None)
    group = await resolve_group(message.chat.id, thread_id)
    if not group:
        await message.answer("Сначала добавьте бота в группу – настройки работают только в привязанных группах.")
        return
    await message.answer(
        f"⚙️ Настройки группы «{group['name']}»\n\nВыберите пункт кнопкой ниже:",
        reply_markup=_settings_inline_keyboard(group),
    )


# /settopic
@router.message(Command("settopic"))
async def handle_settopic_command(message: types.Message, state: FSMContext, bot: Bot) -> None:
    """
    Команда /settopic: привязывает к группе топик, в котором выполнена команда.
    Расписание будет отправляться в этот топик. Если команда в общем чате (не в топике) – привязка к топику снимается.
    """
    await state.clear()
    if not await can_manage_settings(bot, message.from_user.id, message.chat.id, message.chat.type):
        # await message.answer("Команда доступна только администраторам чата.")
        return
    group = await get_group_by_chat(message.chat.id)
    if not group:
        await message.answer("Сначала добавьте бота в группу.")
        return
    thread_id = getattr(message, "message_thread_id", None)
    await update_group_settings(group["id"], thread_id=thread_id)
    if thread_id is not None:
        await message.answer(f"Топик привязан. Расписание будет отправляться в этот топик (ID: {thread_id}).")
    else:
        await message.answer(
            "Расписание будет отправляться в общий чат. Чтобы привязать к топику, выполните /settopic в нужном топике.")


# FSM: приём времени HH:MM
@router.message(SettingsStates.wait_time, F.text)
async def settings_receive_time(message: types.Message, state: FSMContext) -> None:
    """Принимает время в формате ЧЧ:ММ (или ЧЧ.ММ), валидирует, сохраняет send_hour/send_minute и выводит клавиатуру."""
    data = await state.get_data()
    gid = data.get("settings_group_id")
    if not gid:
        await state.clear()
        return
    raw = (message.text or "").strip()
    # Поддерживаем HH:MM, H:MM, HH.MM
    parts = None
    for sep in (":", "."):
        if sep in raw:
            parts = raw.split(sep, 1)
            break
    if not parts or len(parts) != 2:
        await message.answer("Введите время в формате ЧЧ:ММ, например 07:30.")
        return
    try:
        hour = int(parts[0])
        minute = int(parts[1])
    except ValueError:
        await message.answer("Введите время в формате ЧЧ:ММ, например 07:30.")
        return
    if not (0 <= hour <= 23) or not (0 <= minute <= 59):
        await message.answer("Часы – от 0 до 23, минуты – от 0 до 59.")
        return
    await state.clear()
    await update_group_settings(gid, send_hour=hour, send_minute=minute)
    await message.answer(f"Время отправки сохранено: {hour}:{minute:02d}.")
    group = await get_group_by_id(gid)
    if group:
        await message.answer("Текущие настройки:", reply_markup=_settings_inline_keyboard(group))


# FSM: приём кода группы
@router.message(SettingsStates.wait_group_code, F.text)
async def settings_receive_group_code(message: types.Message, state: FSMContext) -> None:
    """Принимает код группы (например ИДБ-24-10), сохраняет в schedule_source_value и выводит текущие настройки."""
    data = await state.get_data()
    gid = data.get("settings_group_id")
    if not gid:
        await state.clear()
        return
    raw = (message.text or "").strip()
    if not raw:
        await message.answer("Введите код группы, например: ИДБ-24-10")
        return
    await state.clear()
    await update_group_settings(gid, schedule_source_type="moodle", schedule_source_value=raw)
    await message.answer(f"Группа установлена: {raw}")
    group = await get_group_by_id(gid)
    if group:
        await message.answer("Текущие настройки:", reply_markup=_settings_inline_keyboard(group))


# Inline-кнопки
@router.callback_query(F.data == "settings_group_code")
async def settings_callback_group_code(call: CallbackQuery, state: FSMContext) -> None:
    """Inline-кнопка «Группа»: запрашивает ввод кода группы (FSM wait_group_code)."""
    if not await can_manage_settings(call.bot, call.from_user.id, call.message.chat.id, call.message.chat.type):
        await call.answer("Недостаточно прав.", show_alert=True)
        return
    thread_id = getattr(call.message, "message_thread_id", None)
    group = await resolve_group(call.message.chat.id, thread_id)
    if not group:
        await call.answer("Группа не найдена.", show_alert=True)
        return
    current = group.get("schedule_source_value") or "не задана"
    await state.set_state(SettingsStates.wait_group_code)
    await state.update_data(settings_group_id=group["id"])
    await call.message.answer(f"Сейчас: {current}\nВведите код группы, например: ИДБ-24-10")
    await call.answer()


@router.callback_query(F.data == "settings_time")
async def settings_callback_time(call: CallbackQuery, state: FSMContext) -> None:
    """Inline-кнопка «Время»: запрашивает ввод времени в формате ЧЧ:ММ (FSM wait_time)."""
    if not await can_manage_settings(call.bot, call.from_user.id, call.message.chat.id, call.message.chat.type):
        await call.answer("Недостаточно прав.", show_alert=True)
        return
    thread_id = getattr(call.message, "message_thread_id", None)
    group = await resolve_group(call.message.chat.id, thread_id)
    if not group:
        await call.answer("Группа не найдена.", show_alert=True)
        return
    await state.set_state(SettingsStates.wait_time)
    await state.update_data(settings_group_id=group["id"])
    h = group.get("send_hour", 0)
    m = group.get("send_minute", 0) or 0
    await call.message.answer(f"Сейчас: {h}:{m:02d}\nВведите новое время в формате ЧЧ:ММ, например 07:30.")
    await call.answer()


@router.callback_query(F.data == "settings_image")
async def settings_callback_image(call: CallbackQuery) -> None:
    """Inline-кнопка «Картинки»: переключает enable_image и обновляет клавиатуру сообщения."""
    if not await can_manage_settings(call.bot, call.from_user.id, call.message.chat.id, call.message.chat.type):
        await call.answer("Недостаточно прав.", show_alert=True)
        return
    thread_id = getattr(call.message, "message_thread_id", None)
    group = await resolve_group(call.message.chat.id, thread_id)
    if not group:
        await call.answer("Группа не найдена.", show_alert=True)
        return
    new_val = not group.get("enable_image")
    await update_group_settings(group["id"], enable_image=new_val)
    group["enable_image"] = new_val
    await call.message.edit_reply_markup(reply_markup=_settings_inline_keyboard(group))
    await call.answer("Картинки: " + ("включены" if new_val else "выключены"))


@router.callback_query(F.data == "settings_tomorrow")
async def settings_callback_tomorrow(call: CallbackQuery) -> None:
    """Inline-кнопка «Кнопка Завтра»: переключает enable_tomorrow_button и обновляет клавиатуру."""
    if not await can_manage_settings(call.bot, call.from_user.id, call.message.chat.id, call.message.chat.type):
        await call.answer("Недостаточно прав.", show_alert=True)
        return
    thread_id = getattr(call.message, "message_thread_id", None)
    group = await resolve_group(call.message.chat.id, thread_id)
    if not group:
        await call.answer("Группа не найдена.", show_alert=True)
        return
    new_val = not group.get("enable_tomorrow_button")
    await update_group_settings(group["id"], enable_tomorrow_button=new_val)
    group["enable_tomorrow_button"] = new_val
    await call.message.edit_reply_markup(reply_markup=_settings_inline_keyboard(group))
    await call.answer("Кнопка «Завтра»: " + ("включена" if new_val else "выключена"))


@router.callback_query(F.data == "settings_test_load")
async def settings_callback_test_load(call: CallbackQuery) -> None:
    """Inline-кнопка «Проверить загрузку»: скачивает PDF по коду группы, парсит и сообщает результат (число пар)."""
    if not await can_manage_settings(call.bot, call.from_user.id, call.message.chat.id, call.message.chat.type):
        await call.answer("Недостаточно прав.", show_alert=True)
        return
    thread_id = getattr(call.message, "message_thread_id", None)
    group = await resolve_group(call.message.chat.id, thread_id)
    if not group:
        await call.answer("Группа не найдена.", show_alert=True)
        return
    group_code = (group.get("schedule_source_value") or "").strip()
    if not group_code:
        await call.answer()
        await call.message.answer("Сначала задайте код группы в настройках (кнопка «Группа»).")
        return
    await call.answer("Проверяю…")
    try:
        pdf_path = await get_schedule_pdf_path(group)
        if not pdf_path:
            await call.message.answer(
                f"Расписание для «{group_code}» не найдено на Moodle.\n"
                "Проверьте правильность кода группы."
            )
            return
        schedule = parse_pdf(pdf_path)
        today = get_today_schedule(schedule)
        pairs = len([x for x in today if x != "Окно"])
        await call.message.answer(f"Всё в порядке. Расписание для {group_code} загружено, сегодня пар: {pairs}.")
    except Exception:
        logger.exception("Test load failed")
        await call.message.answer("При проверке произошла ошибка. Попробуйте позже.")
