# Базовые утилиты и логирование
import json
import logging
import os
from datetime import datetime
from typing import Union

# Статическая конфигурация из config.py (в корне проекта)
try:
    from config import LOGS_DIR
except ImportError:
    LOGS_DIR = "logs"


# Настройка логирования
def setup_logger() -> logging.Logger:
    """
    Настраивает корневой логгер: файл в LOGS_DIR (с именем по текущей дате/времени) и консоль.

    Алгоритм: если у корневого логгера ещё нет handlers – создаётся директория LOGS_DIR,
    добавляются FileHandler (UTF-8) и StreamHandler с форматом времени/уровня/сообщения;
    при повторном вызове handlers уже есть – только пишется сообщение в лог.

    Returns:
        logging.Logger: корневой логгер с уровнем INFO.

    Raises:
        OSError при невозможности создать директорию или файл лога.
    """
    logger_obj = logging.getLogger()
    if not logger_obj.handlers:
        os.makedirs(LOGS_DIR, exist_ok=True)
        current_time = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
        log_file_name = f"{LOGS_DIR}/{current_time}.log"
        logger_obj.setLevel(logging.INFO)

        file_handler = logging.FileHandler(log_file_name, encoding="utf-8")
        console_handler = logging.StreamHandler()
        if hasattr(console_handler.stream, "reconfigure"):
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


def load_json_file(file_path: str, default_value: Union[dict, list]) -> Union[dict, list]:
    """
    Загружает JSON из файла; при отсутствии файла возвращает default_value.

    Args:
        file_path: Путь к .json файлу.
        default_value: Значение, возвращаемое, если файл не существует.

    Returns:
        Распарсенный dict или list из файла либо default_value.

    Raises:
        json.JSONDecodeError при невалидном JSON в файле.
    """
    if os.path.exists(file_path):
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return default_value


def save_json_file(file_path: str, data: Union[dict, list]) -> None:
    """
    Сохраняет dict или list в JSON-файл (ensure_ascii=False, с созданием директории при необходимости).

    Args:
        file_path: Путь к целевому файлу.
        data: Объект для сериализации (dict или list).

    Returns:
        None.

    Raises:
        OSError при ошибке создания директории или записи; TypeError при неподдерживаемом типе в data.
    """
    directory = os.path.dirname(file_path)
    if not os.path.exists(directory):
        os.makedirs(directory)
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False)


def days_until_date(date_str: str) -> int:
    """
    Вычисляет количество дней от сегодня до указанной даты.

    Алгоритм: парсинг date_str как "дд.мм.гггг" или "дд.мм" (год – текущий);
    если дата в прошлом, год сдвигается на следующий; возврат разницы в днях.

    Args:
        date_str: Дата в формате "дд.мм.гггг" или "дд.мм".

    Returns:
        Неотрицательное число дней до даты.

    Raises:
        ValueError при неверном формате строки.
    """
    today = datetime.now().date()
    try:
        parsed_date = datetime.strptime(date_str, "%d.%m.%Y").date()
    except ValueError:
        current_year = today.year
        parsed_date = datetime.strptime(f"{date_str}.{current_year}", "%d.%m.%Y").date()

    if parsed_date < today:
        parsed_date = parsed_date.replace(year=today.year + 1)

    return (parsed_date - today).days
