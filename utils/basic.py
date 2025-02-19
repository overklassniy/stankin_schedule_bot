# Подгрузка конфигураций из config.json
import json
import logging
import os
from datetime import datetime
from typing import Union


# Подгрузка конфигураций из config.json
def load_config() -> dict:
    """
    Загружает конфигурационные данные из файла config.json.

    Возвращает:
        dict: Словарь с конфигурационными данными.
    """
    with open('config.json', 'r', encoding='UTF-8') as config_file:
        return json.load(config_file)


config = load_config()


# Настройка логирования
def setup_logger() -> logging.Logger:
    """
    Настраивает логирование для вывода в файл и консоль.

    Возвращает:
        logging.Logger: Объект логгера для записи логов.
    """
    logger_obj = logging.getLogger()
    # Если обработчики уже добавлены, не настраиваем логгер заново
    if not logger_obj.handlers:
        os.makedirs(config['LOGS_DIR'], exist_ok=True)
        current_time = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
        log_file_name = f"{config['LOGS_DIR']}/{current_time}.log"
        logger_obj.setLevel(logging.INFO)

        # Логирование в файл с явным указанием кодировки UTF-8
        file_handler = logging.FileHandler(log_file_name, encoding="utf-8")

        # Логирование в консоль с поддержкой UTF-8
        console_handler = logging.StreamHandler()
        console_handler.stream.reconfigure(encoding="utf-8")

        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        file_handler.setFormatter(formatter)
        console_handler.setFormatter(formatter)

        logger_obj.addHandler(file_handler)
        logger_obj.addHandler(console_handler)

        logger_obj.info("Логгер успешно настроен. Логи записываются в файл: %s", log_file_name)
    else:
        logger_obj.info("Логгер уже настроен ранее.")

    return logger_obj


logger = setup_logger()


# Функции для работы с файлами JSON
def load_json_file(file_path: str, default_value: Union[dict, list]) -> Union[dict, list]:
    """
    Загружает данные из JSON файла. Если файл не существует, возвращает значение по умолчанию.

    Аргументы:
        file_path (str): Путь к JSON файлу.
        default_value (dict | list): Значение по умолчанию, если файл не найден.

    Возвращает:
        dict | list: Данные, загруженные из JSON файла, или значение по умолчанию.
    """
    if os.path.exists(file_path):
        with open(file_path, 'r') as f:
            return json.load(f)
    return default_value


def save_json_file(file_path: str, data: Union[dict, list]) -> None:
    """
    Сохраняет данные в JSON файл.

    Аргументы:
        file_path (str): Путь к JSON файлу.
        data (dict | list): Данные для сохранения.
    """
    # Получаем директорию из пути к файлу
    directory = os.path.dirname(file_path)

    # Проверяем, существует ли директория, и создаем её, если нет
    if not os.path.exists(directory):
        os.makedirs(directory)

    # Сохраняем данные в JSON файл
    with open(file_path, 'w') as f:
        json.dump(data, f)


def days_until_date(date_str: str) -> int:
    """
    Вычисляет количество дней до указанной даты в формате 'день.месяц.год' или 'день.месяц'.

    Если дата указывается в формате 'день.месяц', используется текущий год.
    Если указанная дата уже прошла в текущем году, возвращается количество дней до этой даты в следующем году.

    Аргументы:
        date_str (str): Дата в строковом формате 'день.месяц.год' или 'день.месяц'.

    Возвращает:
        int: Количество дней до указанной даты.

    Вызывает:
        ValueError: Если строка даты не соответствует ожидаемому формату 'день.месяц' или 'день.месяц.год'.
    """
    # Получаем текущую дату
    today = datetime.now().date()

    # Парсим входную строку. Если год не указан, используем текущий год.
    try:
        # Если строка имеет формат 'день.месяц.год'
        parsed_date = datetime.strptime(date_str, "%d.%m.%Y").date()
    except ValueError:
        # Если строка имеет формат 'день.месяц', добавляем текущий год
        current_year = today.year
        parsed_date = datetime.strptime(f"{date_str}.{current_year}", "%d.%m.%Y").date()

    # Если дата уже прошла в этом году, добавляем год
    if parsed_date < today:
        parsed_date = parsed_date.replace(year=today.year + 1)

    # Вычисляем количество дней до этой даты
    days_left = (parsed_date - today).days

    return days_left
