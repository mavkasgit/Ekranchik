# ПЛАН МИГРАЦИИ НА DOCKER С AIOGRAM БОТОМ

## ИТОГОВАЯ АРХИТЕКТУРА

```
Docker Container (один контейнер, всё внутри)
├─ Flask (порт 5000)
├─ Telegram Bot (aiogram, фоновый процесс)
├─ Логирование (оба приложения пишут логи)
└─ Утилиты (backup скрипт, синхронизация)

Volumes (на хосте сохраняются):
├─ /docker-data/app-data/
│  ├─ profiles.db (БД)
│  ├─ images/ (фото профилей)
│  └─ backups/ (резервные копии)
├─ /docker-data/logs/
│  ├─ app.log (Flask)
│  ├─ bot.log (Telegram Bot)
│  └─ backup.log
└─ /network-mount/excel/
   └─ Учет КПЗ 2025.xlsm (сетевой диск, не трогаем)
```

---

## СТРУКТУРА ПРОЕКТА

```
Ekranchik/
├─ app.py (текущий Flask - БЕЗ ИЗМЕНЕНИЙ)
├─ db.py (текущий - БЕЗ ИЗМЕНЕНИЙ)
├─ bot.py (НОВЫЙ - Telegram Bot с aiogram)
├─ backup.py (НОВЫЙ - backup скрипт)
├─ logging_config.py (НОВЫЙ - настройка логирования)
├─ requirements.txt (ОБНОВИТЬ - добавить aiogram)
├─ Dockerfile (НОВЫЙ - сборка image)
├─ docker-compose.yml (НОВЫЙ - запуск контейнера)
├─ .dockerignore (НОВЫЙ - что не копировать)
├─ templates/ (текущие - БЕЗ ИЗМЕНЕНИЙ)
├─ static/ (текущие - БЕЗ ИЗМЕНЕНИЙ)
└─ README_DOCKER.md (НОВЫЙ - инструкция запуска)
```

---

## ФАЙЛ 1: requirements.txt (ОБНОВИТЬ)

**Добавить в существующий:**
```
flask==2.3.0
pandas==2.0.0
openpyxl==3.10.0
watchdog==3.0.0
python-dotenv==1.0.0
Pillow==9.5.0
werkzeug==2.3.0

# НОВОЕ ДЛЯ DOCKER И БОТА:
aiogram==3.0.0
aiohttp==3.8.0
python-multipart==0.0.6
gunicorn==21.2.0
```

---

## ФАЙЛ 2: logging_config.py (НОВЫЙ)

```python
import logging
import logging.handlers
from pathlib import Path

def setup_logging(app_name="ekranchik"):
    """Настройка логирования для всех приложений"""
    
    logs_dir = Path("/app/logs")
    logs_dir.mkdir(exist_ok=True)
    
    # Формат логов
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Логгер
    logger = logging.getLogger(app_name)
    logger.setLevel(logging.DEBUG)
    
    # Файловый обработчик (ротация каждые 10MB)
    log_file = logs_dir / f"{app_name}.log"
    file_handler = logging.handlers.RotatingFileHandler(
        log_file,
        maxBytes=10*1024*1024,  # 10MB
        backupCount=5
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    
    # Консольный обработчик (для контейнера)
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    return logger
```

---

## ФАЙЛ 3: bot.py (НОВЫЙ)

```python
import asyncio
import logging
from pathlib import Path
import requests
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from logging_config import setup_logging

# Логирование
logger = setup_logging("bot")

# Конфиг
TELEGRAM_TOKEN = "YOUR_TOKEN_HERE"  # Переопределяется из .env
FLASK_API_URL = "http://localhost:5000"  # Внутри контейнера

# Инициализация
bot = Bot(token=TELEGRAM_TOKEN)
dp = Dispatcher()

# ===== КОМАНДЫ =====

@dp.message(Command("start"))
async def start_cmd(message: types.Message):
    """Главное меню"""
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📚 Справочник", callback_data="catalog")],
        [InlineKeyboardButton(text="🔍 Поиск профиля", callback_data="search")],
        [InlineKeyboardButton(text="ℹ️ О системе", callback_data="about")],
    ])
    await message.answer(
        "Привет! Я помощник Ekranchik справочника профилей.\n\n"
        "Выбери действие:",
        reply_markup=kb
    )

@dp.message(Command("catalog"))
async def catalog_cmd(message: types.Message):
    """Показать все профили из справочника"""
    try:
        response = requests.get(f"{FLASK_API_URL}/api/catalog?limit=100")
        data = response.json()
        
        if not data.get('success'):
            await message.answer("❌ Ошибка загрузки справочника")
            return
        
        profiles = data.get('profiles', [])
        if not profiles:
            await message.answer("📭 Справочник пуст")
            return
        
        text = "📚 *СПРАВОЧНИК ПРОФИЛЕЙ*\n\n"
        for p in profiles[:20]:  # Первые 20
            thumb = "📷" if p.get('photo_thumb') else "❌"
            text += f"{thumb} {p['name']}\n"
        
        if len(profiles) > 20:
            text += f"\n...и еще {len(profiles) - 20} профилей"
        
        await message.answer(text, parse_mode="Markdown")
        logger.info(f"User {message.from_user.id} viewed catalog")
        
    except Exception as e:
        logger.error(f"Catalog error: {e}")
        await message.answer(f"❌ Ошибка: {str(e)}")

@dp.message(Command("search"))
async def search_cmd(message: types.Message):
    """Начать поиск профиля"""
    await message.answer(
        "Введи название или часть названия профиля:\n"
        "(например: ЮП-1625 или CP-100)"
    )

@dp.message()
async def handle_search(message: types.Message):
    """Обработка текста поиска"""
    if not message.text:
        return
    
    try:
        response = requests.get(
            f"{FLASK_API_URL}/api/catalog",
            params={'search': message.text}
        )
        data = response.json()
        
        if not data.get('success'):
            await message.answer("❌ Ошибка поиска")
            return
        
        profiles = data.get('profiles', [])
        if not profiles:
            await message.answer(f"❌ Профили по запросу '{message.text}' не найдены")
            return
        
        text = f"🔍 *Результаты поиска по: {message.text}*\n\n"
        for p in profiles[:10]:
            thumb = "📷" if p.get('photo_thumb') else "❌"
            text += (
                f"{thumb} *{p['name']}*\n"
                f"   Кол-во: {p.get('quantity_per_hanger', '—')}\n"
                f"   Длина: {p.get('length', '—')} мм\n"
                f"   Примечания: {p.get('notes', '—')}\n\n"
            )
        
        await message.answer(text, parse_mode="Markdown")
        logger.info(f"User {message.from_user.id} searched: {message.text}")
        
    except Exception as e:
        logger.error(f"Search error: {e}")
        await message.answer(f"❌ Ошибка поиска: {str(e)}")

# ===== ЗАПУСК БОТА =====

async def main():
    """Главная функция бота"""
    logger.info("Bot started")
    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        await bot.session.close()
        logger.info("Bot stopped")

if __name__ == "__main__":
    asyncio.run(main())
```

---

## ФАЙЛ 4: backup.py (НОВЫЙ)

```python
import shutil
import json
from pathlib import Path
from datetime import datetime
from logging_config import setup_logging

logger = setup_logging("backup")

def create_backup():
    """Создает резервную копию БД и фото"""
    
    data_dir = Path("/app/data")
    backup_dir = data_dir / "backups"
    backup_dir.mkdir(exist_ok=True)
    
    # Создаем папку с временной меткой
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_name = f"backup_{timestamp}"
    backup_path = backup_dir / backup_name
    backup_path.mkdir(exist_ok=True)
    
    try:
        # Backup БД
        db_file = data_dir / "profiles.db"
        if db_file.exists():
            shutil.copy2(db_file, backup_path / "profiles.db")
            logger.info(f"Database backed up to {backup_path}")
        
        # Backup фото
        images_dir = data_dir / "images"
        if images_dir.exists():
            backup_images = backup_path / "images"
            shutil.copytree(images_dir, backup_images)
            logger.info(f"Images backed up to {backup_path}")
        
        # Создаем metadata файл
        metadata = {
            "timestamp": timestamp,
            "datetime": datetime.now().isoformat(),
            "db_exists": db_file.exists(),
            "images_count": len(list(images_dir.glob("*"))) if images_dir.exists() else 0
        }
        with open(backup_path / "metadata.json", "w") as f:
            json.dump(metadata, f, indent=2)
        
        logger.info(f"Backup completed: {backup_name}")
        print(f"✅ Backup created: {backup_name}")
        
    except Exception as e:
        logger.error(f"Backup failed: {e}")
        print(f"❌ Backup error: {e}")

if __name__ == "__main__":
    create_backup()
```

---

## ФАЙЛ 5: Dockerfile (НОВЫЙ)

```dockerfile
FROM python:3.11-slim

# Переменные окружения
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Установка зависимостей системы
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Копируем requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копируем код приложения
COPY app.py db.py bot.py backup.py logging_config.py ./
COPY templates/ ./templates/
COPY static/ ./static/

# Создаем директории для данных и логов
RUN mkdir -p /app/data /app/logs /app/data/backups

# Пермиссии
RUN chmod +x /app/bot.py /app/backup.py

# Точка входа: запускаем ОБА приложения
CMD ["sh", "-c", "python app.py & python bot.py"]
```

---

## ФАЙЛ 6: docker-compose.yml (НОВЫЙ)

```yaml
version: '3.8'

services:
  ekranchik:
    build: .
    container_name: ekranchik-app
    
    ports:
      - "5000:5000"
    
    volumes:
      # Данные приложения (БД, фото, backups)
      - ekranchik-data:/app/data
      
      # Логи
      - ekranchik-logs:/app/logs
      
      # Сетевой диск с Excel (ВАЖНО: измените путь!)
      - /mnt/network-share/excel:/excel:ro
    
    environment:
      # Flask
      FLASK_APP: app.py
      FLASK_HOST: 0.0.0.0
      FLASK_PORT: 5000
      FLASK_DEBUG: "false"
      
      # Excel файл
      EXCEL_FILE_PATH: /excel/Учет КПЗ 2025.xlsm
      
      # БД
      DB_PATH: /app/data/profiles.db
      
      # Фото
      PROFILES_DIR: /app/data/images
      
      # Telegram Bot
      TELEGRAM_TOKEN: ${TELEGRAM_TOKEN}
      FLASK_API_URL: http://localhost:5000
    
    restart: unless-stopped
    
    # Лог драйвер
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"

volumes:
  ekranchik-data:
    driver: local
  ekranchik-logs:
    driver: local
```

---

## ФАЙЛ 7: .env (НОВЫЙ)

```env
# Telegram Bot Token
TELEGRAM_TOKEN=YOUR_BOT_TOKEN_HERE

# Flask
FLASK_HOST=0.0.0.0
FLASK_PORT=5000

# Excel
EXCEL_FILE_PATH=/excel/Учет КПЗ 2025.xlsm

# Profiles directory (в volume)
PROFILES_DIR=/app/data/images
```

---

## ФАЙЛ 8: .dockerignore (НОВЫЙ)

```
.git
.gitignore
.factory
__pycache__
*.pyc
*.pyo
*.pyd
.pytest_cache
.venv
venv
*.db
profiles.db
.DS_Store
*.xlsx
*.xlsm
logs/
backups/
README.md
*.md
.env.example
```

---

## ИНСТРУКЦИЯ ПО ЗАПУСКУ

### Шаг 1: Подготовка на хосте

```bash
# Создать директории для volumes
mkdir -p /docker-data/app-data
mkdir -p /docker-data/logs
mkdir -p /docker-data/backups

# Монтировать сетевой диск (ПРИМЕР ДЛЯ LINUX)
sudo mkdir -p /mnt/network-share
sudo mount -t cifs //192.168.1.100/excel /mnt/network-share/excel \
  -o username=user,password=pass

# Для Windows: просто используй UNC path в docker-compose
```

### Шаг 2: Настройка .env

```bash
# В файле Ekranchik/.env установить:
TELEGRAM_TOKEN=123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11
```

### Шаг 3: Сборка и запуск

```bash
# Сборка image
docker-compose build

# Первый запуск (создаст volumes и логи)
docker-compose up -d

# Проверка логов
docker-compose logs -f

# Останавливать
docker-compose down
```

### Шаг 4: Ручной backup

```bash
# Запустить backup скрипт
docker-compose exec ekranchik python backup.py

# Или через бота: /backup (потом добавить)
```

---

## ПРОВЕРКА ПОСЛЕ ЗАПУСКА

```bash
# Проверить статус контейнера
docker-compose ps

# Проверить Flask (должна быть 200)
curl http://localhost:5000/

# Проверить API
curl http://localhost:5000/api/catalog

# Проверить логи
tail -f /docker-data/logs/app.log
tail -f /docker-data/logs/bot.log

# Проверить данные
ls -la /docker-data/app-data/
```

---

## ОСНОВНЫЕ ОТЛИЧИЯ ОТ ТЕКУЩЕЙ СИСТЕМЫ

| Параметр | Раньше | Теперь |
|---|---|---|
| Запуск | `python app.py` | `docker-compose up` |
| Flask | Локально | В контейнере |
| Бот | Не было | aiogram в контейнере |
| БД | В корне | `/app/data/profiles.db` |
| Фото | `static/images` | `/app/data/images` |
| Логи | Консоль | `/app/logs/*.log` |
| Excel | Сетевой диск | Остается на сетевом диске |
| Backup | Не было | `/app/data/backups/` |

---

## ЧТО ДАЛЬШЕ

1. Написать bot.py с функциональностью
2. Создать Dockerfile
3. Создать docker-compose.yml
4. Протестировать локально
5. Деплоить на VPS с Docker
6. Настроить backup стратегию

---

## ВАЖНЫЕ ЗАМЕЧАНИЯ

⚠️ **EXCEL НА СЕТЕВОМ ДИСКЕ** - это ОБЯЗАТЕЛЬНО! Не копировать в контейнер!

⚠️ **VOLUMES НА ХОСТЕ** - все данные хранятся на хосте, контейнер лишь использует

⚠️ **TELEGRAM_TOKEN** - не коммитить в git! Использовать .env

⚠️ **СЕТЕВОЙ ДИСК** - путь зависит от ОС и сети, адаптировать под свою систему
