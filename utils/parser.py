import json
from datetime import datetime, timedelta
from random import choice
from typing import List, Union

import camelot
import numpy as np
import pandas as pd

from utils.basic import config


def fix_labs(df: pd.DataFrame) -> pd.DataFrame:
    """
    Исправляет формат лабораторных в таблице, объединяя строки, которые должны быть объединены.

    Args:
        df (pd.DataFrame): Исходный DataFrame с данными.

    Returns:
        pd.DataFrame: DataFrame с исправленными лабораторными.
    """
    # Создаём копию DataFrame, чтобы не изменять оригинал
    df_copy = df.copy()

    # Заменяем пустые строки на NaN
    df_copy.replace('', np.nan, inplace=True)

    # Итерируем по строкам DataFrame
    for i in range(1, len(df_copy)):
        # Проверяем, что первая ячейка в текущей строке пуста
        if pd.isna(df_copy.iloc[i, 0]):
            # Объединяем не пустые ячейки текущей строки с предыдущей строкой
            for j in range(1, len(df_copy.columns)):
                if pd.notna(df_copy.iloc[i, j]):
                    df_copy.iloc[i - 1, j] = df_copy.iloc[i - 1, j] + '\n' + df_copy.iloc[i, j]
            # Заполняем текущую строку NaN
            df_copy.iloc[i] = np.nan

    # Удаляем строки, которые стали полностью пустыми
    df_copy = df_copy.dropna(how='all')

    # Заменяем оставшиеся NaN обратно на пустые строки
    df_copy.replace(np.nan, '', inplace=True)

    return df_copy


def parse_pdf(file_path: str) -> dict:
    """
    Парсит PDF-файл с расписанием, возвращая структурированные данные.

    Args:
        file_path (str): Путь к PDF-файлу.

    Returns:
        dict: Структурированные данные расписания, где ключи - это дни недели, а значения - списки занятий.
    """
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

    return schedule


def parse_date_range(date_range: str, increment_day: int = 0) -> list:
    """
    Парсит строку с датами и возвращает список валидных дат.

    Args:
        date_range (str): Строка с датами.
        increment_day (int, optional): Число дней для смещения даты (по умолчанию 0).

    Returns:
        list: Список валидных дат.
    """
    today = datetime.today() + timedelta(increment_day)
    today = today.replace(hour=0, minute=0, second=0, microsecond=0)  # Обнуляем часы, минуты, секунды и микросекунды
    day, month = today.day, today.month

    def is_within_period(start: str, end: str, after_week: bool = False) -> bool:
        """
        Проверяет, находится ли текущая дата в пределах периода.

        Args:
            start (str): Начальная дата в формате 'дд.мм'.
            end (str): Конечная дата в формате 'дд.мм'.
            after_week (bool): Флаг для двухнедельных периодов (чётная/нечётная недели).

        Returns:
            bool: True, если текущая дата попадает в период.
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
    Возвращает расписание на день.

    Args:
        schedule (dict): Расписание всех дней.
        increment_day (int, optional): Число дней для смещения даты (по умолчанию 0).

    Returns:
        list: Список занятий на текущий день.
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

    return today_schedule


def get_teachers_name(initials: str) -> str:
    """
    Возвращает полное имя преподавателя по его инициалам.

    Args:
        initials (str): Инициалы преподавателя (например, 'Иванов И.И.').

    Returns:
        str: Полное имя преподавателя, если оно найдено в файле, или сами инициалы, если запись не найдена или файл отсутствует.
    """
    try:
        # Загружаем словарь с полными именами преподавателей из файла
        with open(config['TEACHERS_FULLNAMES_PATH'], 'r', encoding='utf-8') as file:
            teachers_names = json.load(file)

        # Ищем полное имя по инициалам
        full_name = teachers_names[initials]
    except (KeyError, FileNotFoundError):
        # Возвращаем инициалы, если полное имя не найдено или файл отсутствует
        full_name = initials

    return full_name


def format_lesson(lesson_info: List[str], times: List[str], time_counter: int) -> str:
    """
    Форматирует информацию о паре в блок для сообщения.

    Args:
        lesson_info (List[str]): Список строк с деталями о паре.
        times (List[str]): Список временных интервалов пар.
        time_counter (int): Индекс текущего временного интервала.

    Returns:
        str: Отформатированная информация о паре.
    """
    name = '📚 ' + lesson_info[0]
    if lesson_info[1] not in ['лекции', 'семинар', 'лабораторные занятия']:
        teacher_initials = f'{lesson_info[1]}.'
        teacher_fullname = f'👤 {get_teachers_name(teacher_initials)}'
        lesson_type = f'⚙️ {lesson_info[2]}'
    else:
        teacher_fullname = None
        lesson_type = '⚙️ ' + lesson_info[1]
    lesson_type = lesson_type.replace('лекции', 'лекция')

    try:
        location_number = int(lesson_info[-2])
        location = f'📍 Каб. {lesson_info[-2]}'
    except ValueError:
        location = f'📍 {lesson_info[-2]}'

    duration = f'🗓 {lesson_info[-1].replace("[", "").replace("]", "").replace("-", " - ")}'
    time = f'⏰ {times[time_counter]}'

    if 'лабораторные занятия' in lesson_type:
        subgroup = f'🗂 Группа: {lesson_info[-3].replace(")", "").replace("(", "")}'
        time = f'⏰ {times[time_counter].split(" - ")[0]} - {times[time_counter + 1].split(" - ")[-1]}'
    else:
        subgroup = None

    args = [name, teacher_fullname, lesson_type, subgroup, location, duration, time]
    return f'<blockquote>{chr(10).join(arg.capitalize() for arg in args if arg)}</blockquote>'


def create_message(today_schedule: List[Union[str, List[str]]], increment_day: int = 0, scheduled: bool = True) -> str:
    """
    Формирует сообщение с расписанием на день.

    Args:
        today_schedule (List[Union[str, List[str]]]): Расписание на день.
        increment_day (int, optional): Смещение даты (по умолчанию 0).
        scheduled (bool, optional): Флаг, указывающий на тип формирования сообщения (по умолчанию True).

    Returns:
        str: Готовое сообщение с расписанием.
    """
    date_ = datetime.today() + timedelta(increment_day)
    today = date_.strftime('%A')

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

    return message
