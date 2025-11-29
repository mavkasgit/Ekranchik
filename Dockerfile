FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Системные зависимости
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Копируем requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копируем код приложения
COPY app.py db.py bot.py logging_config.py ./
COPY templates/ ./templates/
COPY static/ ./static/

# Создаем директории для данных и логов
RUN mkdir -p /app/data/images /app/data/backups /app/logs

# Точка входа: запускаем Bot и Flask через WSGI параллельно
# gunicorn не блокирует, позволяя боту запуститься
CMD ["sh", "-c", "python bot.py & gunicorn --bind 0.0.0.0:5000 --workers 1 app:app"]
