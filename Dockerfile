# Мультистейдж Dockerfile для минимального размера образа бота.
#
# Stage 1 (builder): создаёт виртуальное окружение и устанавливает зависимости.
# Stage 2 (runtime): копирует только venv и код, без компиляторов и кеша pip.

# Stage 1: сборка зависимостей в виртуальном окружении
FROM python:3.13-slim AS builder

# Создаём изолированное venv, чтобы перенести только установленные пакеты в runtime
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

WORKDIR /app

# Обновляем pip и устанавливаем зависимости без кеша и без генерации байткода
COPY requirements.txt .
RUN pip install --no-cache-dir --no-compile --upgrade pip && \
    pip install --no-cache-dir --no-compile -r requirements.txt && \
    # Удаляем pip из venv: в runtime он не нужен
    pip uninstall -y pip && \
    # Очищаем кеш, байткод, тесты из venv для уменьшения размера
    find /opt/venv -depth -type d -name "__pycache__" -exec rm -rf {} + && \
    find /opt/venv -depth -type d -name "tests" -exec rm -rf {} + && \
    find /opt/venv -depth -type d -name "test" -exec rm -rf {} + && \
    find /opt/venv -name "*.pyc" -delete && \
    find /opt/venv -name "*.pyo" -delete && \
    rm -rf /opt/venv/share /opt/venv/man


# Stage 2: минимальный runtime-образ
FROM python:3.13-slim

WORKDIR /app

# Копируем готовое venv из builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Копируем исходный код приложения
COPY . .

# Создаём непривилегированного пользователя для безопасности
RUN useradd --create-home --uid 1000 appuser && \
    mkdir -p /app/data /app/logs /app/images && \
    chown -R appuser:appuser /app
USER appuser

CMD ["python", "bot.py"]
