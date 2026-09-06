# Установка

## Системные требования

- Python 3.13+
- Ghostscript (для парсинга PDF через camelot)
- Git

## Установка из исходников

1. **Клонируйте репозиторий**
   ```bash
   git clone https://github.com/overklassniy/stankin_schedule_bot.git
   cd stankin_schedule_bot
   ```

2. **Создайте виртуальное окружение** (рекомендуется)
   ```bash
   python -m venv .venv
   # Windows
   .venv\Scripts\activate
   # Linux/macOS
   source .venv/bin/activate
   ```

3. **Установите Python-зависимости**
   ```bash
   pip install -r requirements.txt
   ```

4. **Установите Ghostscript**

   camelot использует Ghostscript для обработки PDF.

   - **Windows**: скачайте установщик с [официального сайта](https://ghostscript.com/releases/gsdnld.html) и добавьте путь к `gswin64c.exe` в `PATH`.
   - **Linux (Debian/Ubuntu)**:
     ```bash
     sudo apt-get install ghostscript
     ```
   - **macOS**:
     ```bash
     brew install ghostscript
     ```

   Подробнее — в [документации camelot](https://camelot-py.readthedocs.io/en/master/user/install-deps.html#install-deps).

5. **Создайте файл `.env`**
   ```bash
   cp .env.example .env
   ```
   Укажите `BOT_TOKEN` и при необходимости другие параметры. Подробнее — в [Конфигурации](configuration.md).

## Docker

В репозитории есть `Dockerfile` (мультистейдж, минимальный образ) и `docker-compose.yml`.

### Запуск через docker compose

1. Создайте `.env` с токеном бота (как в шаге 5 выше).

2. Запустите контейнер:
   ```bash
   docker compose up -d
   ```

3. Логи:
   ```bash
   docker compose logs -f
   ```

### Сборка собственного образа

```bash
docker build -t stankin-schedule-bot .
docker run -d --env-file .env -v ./data:/app/data -v ./images:/app/images -v ./logs:/app/logs stankin-schedule-bot
```

### Образ на GitHub Container Registry

При пуше в ветку `master` GitHub Actions собирает и публикует dev-образ:

```
ghcr.io/overklassniy/stankin_schedule_bot:dev
```

Этот образ используется в `docker-compose.yml` по умолчанию.

## Проверка установки

После установки зависимостей и настройки `.env` запустите бота:

```bash
python bot.py
```

В логах должно появиться `Starting bot...` и `Bot initialized, ID: <id>`. Добавьте бота в тестовую группу — он пришлёт сообщение о привязке.
