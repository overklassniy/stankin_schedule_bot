import json
from datetime import datetime, timedelta
from random import choice
from typing import List, Union

import camelot
import numpy as np
import pandas as pd

from config import TEACHERS_FULLNAMES_PATH
from utils.basic import logger


def fix_labs(df: pd.DataFrame) -> pd.DataFrame:
    """
    Объединяет строки таблицы расписания для корректного отображения лабораторных.

    Алгоритм: копия DataFrame; пустые строки заменяются на NaN; для строк с пустой первой
    ячейкой значения из остальных столбцов конкатенируются с предыдущей строкой (через \\n),
    текущая строка обнуляется; строки, полностью NaN, удаляются; NaN обратно в пустую строку.

    Args:
        df: Исходный DataFrame (таблица из PDF, например первая таблица camelot).

    Returns:
        Новый DataFrame с объединёнными лабораторными и без полностью пустых строк.
    """
    df_copy = df.copy()
    df_copy.replace('', np.nan, inplace=True)

    for i in range(1, len(df_copy)):
        if pd.isna(df_copy.iloc[i, 0]):
            for j in range(1, len(df_copy.columns)):
                if pd.notna(df_copy.iloc[i, j]):
                    prev_val = df_copy.iloc[i - 1, j]
                    curr_val = df_copy.iloc[i, j]
                    if pd.isna(prev_val):
                        df_copy.iloc[i - 1, j] = str(curr_val)
                    else:
                        df_copy.iloc[i - 1, j] = str(prev_val) + '\n' + str(curr_val)
            df_copy.iloc[i] = np.nan

    df_copy = df_copy.dropna(how='all')
    df_copy.replace(np.nan, '', inplace=True)
    return df_copy


def parse_pdf(file_path: str) -> dict:
    """
    Парсит PDF с расписанием (camelot) в словарь по дням недели.

    Алгоритм: извлечение всех таблиц camelot.read_pdf(pages='all'), взятие первой таблицы,
    fix_labs; из строк 1:8 формируется плоский список ячеек; по ячейкам строится словарь:
    ключ – день недели (Понедельник … Суббота), значение – список занятий (строки или списки
    подзанятий с датами в квадратных скобках).

    Args:
        file_path: Путь к PDF-файлу на диске.

    Returns:
        Словарь: ключи – названия дней недели (рус.), значения – списки элементов расписания
        (строка или список строк с датами в конце).

    Raises:
        FileNotFoundError, IOError при ошибках чтения; исключения camelot при невалидном PDF.
    """
    logger.debug("Parsing PDF: %s", file_path)
    # Извлечение таблиц из PDF файла, обработка всех страниц
    tables = camelot.read_pdf(file_path, pages='all')

    # Выбор первой таблицы
    table = fix_labs(tables[0].df)

    # Инициализация списка расписания
    schedule_ = table.iloc[1:8].stack().tolist()

    # Инициализация словаря для хранения расписания
    schedule = {}
    days_of_week = ['Понедельник', 'Вторник', 'Среда', 'Четверг', 'Пятница', 'Суббота']
    current_day = None

    # Обработка списка расписания
    for item in schedule_:
        if item in days_of_week:
            current_day = item
            schedule[current_day] = []
        elif current_day:
            if not item:
                schedule[current_day].append(item)
                continue
            item_ = item.replace('\n', ' ').strip().rstrip().replace('. ', '\n')
            if item_.count(']') > 1:
                item__ = []
                for x in item_.split(']'):
                    tmp = (x + ']\n').strip()
                    if tmp != ']':
                        item__.append(tmp)
            else:
                item__ = item_.replace('] ', ']\n').strip()
            schedule[current_day].append(item__)

    logger.debug("Parsed PDF: %s days", len(schedule))
    return schedule


def parse_date_range(date_range: str, increment_day: int = 0) -> list:
    """
    Проверяет, попадает ли «текущая» дата (сегодня + increment_day) в указанные периоды.

    Алгоритм: date_range разбивается по ", "; для частей с "-" обрабатываются периоды
    (поддержка "к.н." и "ч.н." для двухнедельных); для точечных дат "дд.мм" проверяется
    совпадение с днём/месяцем. Возвращается список подходящих подстрок периода/даты.

    Args:
        date_range: Строка с периодами и датами, например "01.09-30.12 к.н.", "15.10".
        increment_day: Смещение от текущей даты в днях (0 = сегодня).

    Returns:
        Список строк (подстрок из date_range), в которые попадает целевая дата; может быть пустым.
    """
    today = datetime.today() + timedelta(increment_day)
    today = today.replace(hour=0, minute=0, second=0, microsecond=0)  # Обнуляем часы, минуты, секунды и микросекунды
    day, month = today.day, today.month

    def is_within_period(start: str, end: str, after_week: bool = False) -> bool:
        """
        Проверяет, входит ли today в отрезок [start, end] (формат дд.мм).
        Если after_week=True, дополнительно проверяется чётность недели (каждые 14 дней от start).

        Args:
            start: Начало периода "дд.мм".
            end: Конец периода "дд.мм" (если end < start, год конца +1).
            after_week: Учёт двухнедельной сетки от start.

        Returns:
            True, если дата в периоде (и при after_week на нужной неделе).
        """
        start_day, start_month = map(int, start.split('.'))
        end_day, end_month = map(int, end.split('.'))

        start_date = datetime(today.year, start_month, start_day)
        end_date = datetime(today.year, end_month, end_day)
        if end_date < start_date:
            end_date = datetime(today.year + 1, end_month, end_day)  # Если период охватывает конец года

        if after_week:
            if start_date <= today <= end_date:
                return (today - start_date).days % 14 == 0
        else:
            return start_date <= today <= end_date

    date_parts = date_range.split(', ')
    valid_dates = []

    for part in date_parts:
        if '-' in part:
            if 'к.н.' in part:
                part = part.replace(' к.н.', '')
                start_date, end_date = part.split('-')
                if is_within_period(start_date, end_date):
                    valid_dates.append(part)
            elif 'ч.н.' in part:
                part = part.replace(' ч.н.', '')
                start_date, end_date = part.split('-')
                if is_within_period(start_date, end_date, after_week=True):
                    valid_dates.append(part)
        else:
            if '.' in part:
                d, m = map(int, part.split('.'))
                if d == day and m == month:
                    valid_dates.append(part)

    return valid_dates


def get_today_schedule(schedule: dict, increment_day: int = 0) -> list:
    """
    Извлекает расписание на один день (сегодня + increment_day) с учётом дат в ячейках.

    Алгоритм: определение дня недели по целевой дате; взятие из schedule списка занятий
    для этого дня; для каждого занятия из последней строки извлекается дата/период и
    проверяется через parse_date_range – если дата не подходит, в список подставляется
    "Окно"; для списков подзанятий (лабы по подгруппам) обрабатывается каждый элемент.

    Args:
        schedule: Словарь расписания (результат parse_pdf): день недели -> список занятий.
        increment_day: Смещение в днях от текущей даты (0 = сегодня, 1 = завтра).

    Returns:
        Список занятий на день: строки с \\n или списки строк; "Окно" для пропусков.
    """
    today = (datetime.today() + timedelta(increment_day)).strftime('%A')
    day_map = {
        'Monday': 'Понедельник',
        'Tuesday': 'Вторник',
        'Wednesday': 'Среда',
        'Thursday': 'Четверг',
        'Friday': 'Пятница',
        'Saturday': 'Суббота',
        'Sunday': 'Воскресенье'
    }

    today_rus = day_map[today]
    logger.debug("get_today_schedule: day=%s increment_day=%s", today_rus, increment_day)

    # Инициализация расписания на сегодняшний день как пустого
    today_schedule = []

    if today_rus in schedule:
        day_schedule = schedule[today_rus]

        # Проверка каждого элемента расписания
        for lesson in day_schedule:
            if isinstance(lesson, list):
                found_valid = []
                for sublesson in lesson:
                    lines = sublesson.split('\n')
                    dates_line = lines[-1].strip('[]')
                    if parse_date_range(dates_line, increment_day):
                        found_valid.append(sublesson)
                if not found_valid:
                    today_schedule.append("Окно")  # Для сохранения структуры
                else:
                    if len(found_valid) == 1:
                        today_schedule.append(found_valid[0])
                    else:
                        today_schedule.append(found_valid)
            else:
                lines = lesson.split('\n')
                dates_line = lines[-1].strip('[]')
                if parse_date_range(dates_line, increment_day):
                    today_schedule.append(lesson)
                else:
                    today_schedule.append("Окно")  # Для сохранения структуры

    logger.debug("get_today_schedule: lessons count=%s", len([x for x in today_schedule if x != "Окно"]))
    return today_schedule


def get_teachers_name(initials: str) -> str:
    """
    Возвращает полное имя преподавателя по инициалам из JSON-словаря.

    Загружает TEACHERS_FULLNAMES_PATH (JSON), ищет ключ initials. При KeyError или
    FileNotFoundError возвращает исходные initials.

    Args:
        initials: Инициалы, например "Иванов И.И." (точка в конце допустима).

    Returns:
        Полное имя из файла или initials при отсутствии записи/файла.
    """
    try:
        # Загружаем словарь с полными именами преподавателей из файла
        with open(TEACHERS_FULLNAMES_PATH, 'r', encoding='utf-8') as file:
            teachers_names = json.load(file)

        # Ищем полное имя по инициалам
        full_name = teachers_names[initials]
        logger.debug("get_teachers_name: found %s -> %s", initials, full_name[:30] + "..." if len(full_name) > 30 else full_name)
    except (KeyError, FileNotFoundError):
        # Возвращаем инициалы, если полное имя не найдено или файл отсутствует
        full_name = initials
        logger.debug("get_teachers_name: not found or no file, using initials %s", initials)

    return full_name


def format_lesson(lesson_info: List[str], times: List[str], time_counter: int) -> str:
    """
    Форматирует одну пару (название, тип/преподаватель, кабинет, даты) в HTML blockquote.

    Алгоритм: lesson_info – строки, полученные split('\\n') из ячейки расписания (название,
    тип/преподаватель, вид, кабинет, период); определение типа (лекция/семинар/лаб) или
    подстановка полного имени преподавателя из get_teachers_name; для лаб – учёт подгруппы
    и сдвоенного времени; сборка строк с эмодзи и обёртка в <blockquote>.

    Args:
        lesson_info: Список строк полей пары (минимум: название, тип, кабинет, период).
        times: Список временных интервалов пар по порядку.
        time_counter: Индекс интервала для этой пары (0..len(times)-1).

    Returns:
        Строка HTML (blockquote) с названием, преподавателем, типом, кабинетом, датами, временем.
    """
    name = '📚 ' + lesson_info[0]

    TYPE_MAP = {
        "лекция": "Лекция",
        "семинар": "Семинар",
        "лабораторная": "Лабораторная работа",
        "лабораторные занятия": "Лабораторная работа"
    }

    raw_type = lesson_info[1].lower()

    if raw_type not in TYPE_MAP:
        teacher_initials = f'{lesson_info[1]}.'
        teacher_fullname = f'👤 {get_teachers_name(teacher_initials)}'
        lesson_type = f'⚙️ {lesson_info[2]}'
    else:
        teacher_fullname = None
        lesson_type = '⚙️ ' + TYPE_MAP[raw_type]

    try:
        location_number = int(lesson_info[-2])
        location = f'📍 Каб. {lesson_info[-2]}'
    except ValueError:
        location_ = lesson_info[-2]
        if location_ == '':
            location = '💻 Онлайн'
        else:
            location = f'📍 {location_}'

    duration = f'🗓 {lesson_info[-1].replace("[", "").replace("]", "").replace("-", " - ")}'
    # Защита от выхода за границы: в расписании может быть больше слотов, чем в times
    time_idx = min(time_counter, len(times) - 1)
    time = f'⏰ {times[time_idx]}'

    if 'лабораторные занятия' in lesson_type.lower() or 'лабораторная' in lesson_info[2].lower():
        subgroup = f'🗂 Группа: {lesson_info[-3].replace(")", "").replace("(", "")}'
        time_end_idx = min(time_counter + 1, len(times) - 1)
        time = f'⏰ {times[time_idx].split(" - ")[0]} - {times[time_end_idx].split(" - ")[-1]}'
    else:
        subgroup = None

    lesson_type = lesson_type[:3] + lesson_type[3].upper() + lesson_type[4:]

    args = [name, teacher_fullname, lesson_type, subgroup, location, duration, time]
    return f'<blockquote>{chr(10).join(arg for arg in args if arg)}</blockquote>'


def create_message(today_schedule: List[Union[str, List[str]]], increment_day: int = 0, scheduled: bool = True) -> str:
    """
    Собирает итоговое HTML-сообщение с расписанием на один день.

    Алгоритм: дата = сегодня + increment_day; воскресенье -> "Выходной"; иначе заголовок
    (утренний при scheduled, иначе "Расписание на … (дата)"); обход today_schedule с
    увеличением time_counter на "Окно" и на каждое занятие; каждое занятие форматируется
    через format_lesson; при пустом списке занятий – случайное сообщение "без пар" или
    "пар нет" в зависимости от scheduled.

    Args:
        today_schedule: Список занятий на день (результат get_today_schedule): строки или
            списки строк, "Окно" для пропусков.
        increment_day: Смещение даты в днях (0 = сегодня).
        scheduled: True для утренней рассылки ("Доброе утро…"), False для ответа на команду.

    Returns:
        Строка "Выходной" или HTML-текст сообщения с расписанием.
    """
    date_ = datetime.today() + timedelta(increment_day)
    today = date_.strftime('%A')
    logger.debug("create_message: date=%s increment_day=%s scheduled=%s", date_.strftime("%d.%m.%Y"), increment_day, scheduled)

    if today == 'Sunday':
        return 'Выходной'

    date = date_.strftime('%d.%m.%Y')
    day_map = {
        'Monday': 'Понедельник',
        'Tuesday': 'Вторник',
        'Wednesday': 'Среда',
        'Thursday': 'Четверг',
        'Friday': 'Пятница',
        'Saturday': 'Суббота',
        'Sunday': 'Воскресенье'
    }

    times = ['8:30 - 10:10', '10:20 - 12:00', '12:20 - 14:00', '14:10 - 15:50',
             '16:00 - 17:40', '18:00 - 19:30', '19:40 - 21:10', '21:20 - 22:50']

    today_rus = day_map[today]

    lessons = []
    time_counter = 0

    for lesson in today_schedule:
        if lesson == 'Окно':
            time_counter += 1
            continue

        if isinstance(lesson, list):
            for sublesson in lesson:
                if sublesson == 'Окно':
                    continue
                lessons.append(format_lesson(sublesson.split('\n'), times, time_counter))
            time_counter += 1
            continue

        lessons.append(format_lesson(lesson.split('\n'), times, time_counter))
        time_counter += 1

    if scheduled:
        message = f'<b>Доброе утро, сегодня {today_rus.lower()}. Расписание на сегодня:</b>\n'
    else:
        today_rus_modified = today_rus[:-1] + 'у' if today_rus.endswith('а') else today_rus
        message = f'<b>Расписание на {today_rus_modified.lower()} ({date}):</b>\n'

    if not lessons:
        if scheduled:
            messages = [
                f'<b>Доброе утро, сегодня {today_rus.lower()}, по совместительству – выходной!</b>\n',
                f'<b>Доброе утро, сегодня {today_rus.lower()}. К счастью, без пар!</b>\n',
                f'<b>Доброе утро, сегодня {today_rus.lower()}. Сегодня без пар. Отдыхаем!</b>\n',
                f'<b>Доброе утро, сегодня {today_rus.lower()}. Сегодня без пар. Продолжаем спать...</b>\n'
            ]
            message = choice(messages)
        else:
            today_rus_modified = today_rus[:-1] + 'у' if today_rus.endswith('а') else today_rus
            message = f'<b>В {today_rus_modified.lower()} ({date}) пар нет.</b>\n'

    else:
        message += '\n'.join(lessons)

    logger.debug("create_message: lessons=%s", len(lessons))
    return message
