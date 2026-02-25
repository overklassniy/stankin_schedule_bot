# Базовые утилиты и логирование
import json
import logging
import os
from datetime import datetime
from typing import Union

# Статическая конфигурация из config.py (в корне проекта)
try:
    from config import LOGS_DIR, LOG_LEVEL
except ImportError:
    LOGS_DIR = "logs"
    LOG_LEVEL = "INFO"

_LEVEL_MAP = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
    "CRITICAL": logging.CRITICAL,
}


# Настройка логирования
def setup_logger() -> logging.Logger:
    """
    Настраивает корневой логгер: файл в LOGS_DIR (с именем по текущей дате/времени) и консоль.

    Алгоритм: если у корневого логгера ещё нет handlers – создаётся директория LOGS_DIR,
    добавляются FileHandler (UTF-8) и StreamHandler с форматом времени/уровня/сообщения;
    уровень берётся из LOG_LEVEL (.env). При повторном вызове handlers уже есть – только пишется сообщение в лог.

    Returns:
        logging.Logger: корневой логгер.

    Raises:
        OSError при невозможности создать директорию или файл лога.
    """
    logger_obj = logging.getLogger()
    if not logger_obj.handlers:
        os.makedirs(LOGS_DIR, exist_ok=True)
        current_time = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
        log_file_name = f"{LOGS_DIR}/{current_time}.log"
        level = _LEVEL_MAP.get(LOG_LEVEL, logging.INFO)
        logger_obj.setLevel(level)

        file_handler = logging.FileHandler(log_file_name, encoding="utf-8")
        console_handler = logging.StreamHandler()
        if hasattr(console_handler.stream, "reconfigure"):
            console_handler.stream.reconfigure(encoding="utf-8")

        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        file_handler.setFormatter(formatter)
        console_handler.setFormatter(formatter)

        logger_obj.addHandler(file_handler)
        logger_obj.addHandler(console_handler)

        logger_obj.info("Логгер настроен. Уровень: %s, файл: %s", LOG_LEVEL, log_file_name)
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
            data = json.load(f)
        logger.debug("load_json_file: loaded %s keys/items", len(data) if isinstance(data, (dict, list)) else "?")
        return data
    logger.debug("load_json_file: not found %s, using default", file_path)
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
        logger.debug("save_json_file: created dir %s", directory)
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False)
    logger.debug("save_json_file: saved %s", file_path)


def days_until_date(date_str: str) -> int:
    """
    Вычисляет количество дней от сегодня до указанной даты.

    Алгоритм: парсинг date_str как "дд.мм.гггг" или "дд.мм".
    Для формата без года используется текущий год, и возвращается разница в днях
    (может быть отрицательной для прошедших дат).

    Args:
        date_str: Дата в формате "дд.мм.гггг" или "дд.мм".

    Returns:
        Число дней до даты (может быть отрицательным).

    Raises:
        ValueError при неверном формате строки.
    """
    today = datetime.now().date()
    try:
        parsed_date = datetime.strptime(date_str, "%d.%m.%Y").date()
    except ValueError:
        current_year = today.year
        parsed_date = datetime.strptime(f"{date_str}.{current_year}", "%d.%m.%Y").date()

    days = (parsed_date - today).days
    logger.debug("days_until_date: date_str=%s -> %s days", date_str, days)
    return days
