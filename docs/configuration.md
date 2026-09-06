# Конфигурация

Бот настраивается через два слоя:

1. **`.env`** — секреты и переменные окружения (токен, уровень логирования, пути).
2. **`config.py`** — статические параметры, читаемые из `.env` при запуске.

Динамические настройки групп (код группы, время отправки, картинки) хранятся в SQLite и управляются через команду `/settings` — см. [Использование](usage.md).

## Файл `.env`

Скопируйте `.env.example` в `.env` и заполните поля:

| Переменная | Обязательно | По умолчанию | Описание |
| --- | :---: | --- | --- |
| `BOT_TOKEN` | да | — | Токен Telegram-бота от [@BotFather](https://t.me/BotFather) |
| `LOG_LEVEL` | нет | `INFO` | Уровень логирования: `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL` |
| `ADMIN_IDS` | нет | — | ID администраторов через запятую, имеют доступ к `/settings` в любом чате |
| `LOGS_DIR` | нет | `logs` | Директория для файлов логов |
| `TEACHERS_FULLNAMES_PATH` | нет | `data/teachers.json` | JSON с полными именами преподавателей |
| `IMAGES_DIR` | нет | `images` | Директория с изображениями для отправки |
| `CHECK_TIME_INTERVAL` | нет | `30` | Интервал проверки планировщика (секунды) |
| `DATABASE_PATH` | нет | `data/bot.db` | Путь к файлу SQLite |
| `ENABLE_SECURE` | нет | `true` | Ограничить команды только привязанными чатами |
| `MOODLE_BASE_URL` | нет | `https://edu.stankin.ru` | Базовый URL Moodle |
| `MOODLE_COURSE_ID` | нет | `11557` | ID курса Moodle с расписаниями |
| `SCHEDULE_CACHE_DIR` | нет | `data/cache` | Директория кэша PDF |
| `SCHEDULE_CACHE_TTL` | нет | `21600` | TTL кэша PDF в секундах (6 часов) |
| `PROXY` | нет | — | Прокси для запросов к Telegram API |
| `HTTP_PROXY` | нет | — | Альтернативная переменная прокси |

## Пример `.env`

```env
BOT_TOKEN=1234567890:AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA
LOG_LEVEL=INFO
ADMIN_IDS=123456789,987654321
LOGS_DIR=logs
TEACHERS_FULLNAMES_PATH=data/teachers.json
IMAGES_DIR=images
CHECK_TIME_INTERVAL=30
DATABASE_PATH=data/bot.db
ENABLE_SECURE=true
MOODLE_BASE_URL=https://edu.stankin.ru
MOODLE_COURSE_ID=11557
SCHEDULE_CACHE_DIR=data/cache
SCHEDULE_CACHE_TTL=21600
PROXY=
```

## Динамические настройки групп

Эти параметры хранятся в БД и настраиваются через `/settings`:

| Параметр | Описание |
| --- | --- |
| Код группы | Код учебной группы (например, `ИДБ-24-10`), по которому бот ищет PDF на Moodle |
| Время отправки | Часы и минуты ежедневной рассылки (ЧЧ:ММ) |
| Картинки | Отправлять ли случайное изображение из `IMAGES_DIR` вместе с расписанием |
| Кнопка «Завтра» | Показывать ли inline-кнопку «Расписание на завтра» под ежедневным сообщением |
| Топик | ID топика супергруппы для отправки (привязывается через `/settopic`) |

## Дефолты для новых групп

При добавлении бота в новую группу применяются значения из `config.py`:

- `DEFAULT_SEND_HOUR = 5`
- `DEFAULT_SEND_MINUTE = 5`
- `DEFAULT_ENABLE_IMAGE = True`
- `DEFAULT_ENABLE_TOMORROW_BUTTON = False`
- `DEFAULT_THREADED = True`

## Файл с именами преподавателей

`data/teachers.json` — словарь, где ключ — инициалы из расписания (`Иванов И.И.`), значение — полное имя. Если файл отсутствует, бот использует инициалы как есть.

Пример:

```json
{
  "Иванов И.И.": "Иванов Иван Иванович",
  "Петров П.П.": "Петров Пётр Петрович"
}
```
