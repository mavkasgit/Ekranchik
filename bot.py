#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Telegram бот для справочника профилей (aiogram)"""

import asyncio
import logging
import os
from pathlib import Path
import requests
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, BufferedInputFile
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from dotenv import load_dotenv

from logging_config import setup_logging

load_dotenv()
logger = setup_logging("bot")

# Конфиг
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN', 'YOUR_TOKEN_HERE')
BOT_PASSWORD = os.getenv('BOT_PASSWORD', '1122')
FLASK_API_URL = os.getenv('FLASK_API_URL', 'http://localhost:5000')

# Хранилище авторизованных пользователей (в памяти)
authorized_users = set()

# Проверка токена
if TELEGRAM_TOKEN.startswith('YOUR_') or not TELEGRAM_TOKEN:
    logger.error("ОШИБКА: TELEGRAM_TOKEN не установлен или некорректен!")
    logger.error("Обновите .env файл с реальным токеном от @BotFather")
    print("\n❌ Telegram Bot отключен: TELEGRAM_TOKEN не установлен")
    print("Обновите .env и перезагрузите контейнер\n")
    # Завершаем приложение
    import sys
    sys.exit(0)

# Инициализация
bot = Bot(
    token=TELEGRAM_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN)
)
dp = Dispatcher()

# ===== КОМАНДЫ =====

@dp.message(Command("start"))
async def start_cmd(message: types.Message):
    """Главное меню - с проверкой авторизации"""
    user_id = message.from_user.id
    
    # Проверяем авторизацию
    if user_id not in authorized_users:
        await message.answer(
            f"Привет, {message.from_user.first_name}!\n\n"
            "Для доступа к боту введите пароль:"
        )
        return
    
    # Авторизован - показываем меню
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📚 Справочник", callback_data="catalog")],
        [InlineKeyboardButton(text="🔍 Поиск профиля", callback_data="search")],
        [InlineKeyboardButton(text="ℹ️ О системе", callback_data="about")],
    ])
    await message.answer(
        "Привет! Я помощник справочника профилей Ekranchik.\n\n"
        "Выбери действие:",
        reply_markup=kb
    )
    logger.info(f"User {message.from_user.id} started bot")

@dp.message(Command("catalog"))
async def catalog_cmd(message: types.Message):
    """Показать все профили из справочника"""
    try:
        response = requests.get(f"{FLASK_API_URL}/api/catalog?limit=100", timeout=5)
        response.raise_for_status()
        data = response.json()
        
        if not data.get('success'):
            await message.answer("❌ Ошибка загрузки справочника")
            return
        
        profiles = data.get('profiles', [])
        if not profiles:
            await message.answer("📭 Справочник пуст")
            return
        
        text = "*📚 СПРАВОЧНИК ПРОФИЛЕЙ*\n\n"
        for p in profiles[:20]:
            thumb = "📷" if p.get('photo_thumb') else "❌"
            text += f"{thumb} {p['name']}\n"
        
        if len(profiles) > 20:
            text += f"\n_(и ещё {len(profiles) - 20} профилей)_"
        
        await message.answer(text)
        logger.info(f"User {message.from_user.id} viewed catalog")
        
    except requests.exceptions.RequestException as e:
        logger.error(f"API error: {e}")
        await message.answer(f"❌ Ошибка соединения: {str(e)}")
    except Exception as e:
        logger.error(f"Catalog error: {e}")
        await message.answer(f"❌ Ошибка: {str(e)}")

@dp.message(Command("search"))
async def search_cmd(message: types.Message):
    """Начать поиск профиля"""
    await message.answer(
        "Введи название или часть названия профиля:\n"
        "_(например: ЮП-1625 или CP-100)_",
        parse_mode=ParseMode.MARKDOWN
    )

@dp.message(Command("about"))
async def about_cmd(message: types.Message):
    """Информация о системе"""
    await message.answer(
        "*ℹ️ О СИСТЕМЕ*\n\n"
        "Это справочник профилей Ekranchik.\n\n"
        "Команды:\n"
        "/start - главное меню\n"
        "/catalog - все профили\n"
        "/search - поиск по названию\n"
        "/about - информация",
        parse_mode=ParseMode.MARKDOWN
    )

@dp.message(Command("testimg"))
async def testimg_cmd(message: types.Message):
    """Тест отправки изображения"""
    try:
        from PIL import Image, ImageDraw, ImageFont
        import io
        
        # Создаем простое тестовое изображение
        img = Image.new('RGB', (400, 300), color='blue')
        draw = ImageDraw.Draw(img)
        draw.text((100, 120), "TEST IMAGE", fill='white')
        
        # Сохраняем в байты
        bio = io.BytesIO()
        img.save(bio, 'JPEG')
        bio.seek(0)
        
        photo = BufferedInputFile(bio.getvalue(), filename="test.jpg")
        await message.answer_photo(
            photo=photo,
            caption="Test image from bot"
        )
        await message.answer("Image sent OK!")
        logger.info("TESTIMG: Image sent successfully")
        
    except Exception as e:
        logger.error(f"TESTIMG ERROR: {str(e)}")
        await message.answer("Image error - check logs")

@dp.message(Command("test"))
async def test_cmd(message: types.Message):
    """Тестовая отправка фото из API"""
    try:
        response = requests.get(
            f"{FLASK_API_URL}/api/catalog?limit=1",
            timeout=5
        )
        response.raise_for_status()
        data = response.json()
        
        profiles = data.get('profiles', [])
        if not profiles:
            await message.answer("No profiles")
            return
        
        p = profiles[0]
        photo_url = p.get('photo_full') or p.get('photo_thumb')
        if photo_url:
            try:
                photo_response = requests.get(
                    f"{FLASK_API_URL}{photo_url}",
                    timeout=10
                )
                photo_response.raise_for_status()
                
                # Отправляем фото БЕЗ текста - чистый тест
                photo_file = BufferedInputFile(photo_response.content, filename="profile.jpg")
                await message.answer_photo(
                    photo=photo_file
                )
                logger.info(f"TEST OK: Photo sent")
                await message.answer("Photo test OK!")
            except Exception as e:
                logger.error(f"TEST ERROR: {str(e)}")
                await message.answer("Photo error - check logs")
        else:
            await message.answer("No photo")
        
    except Exception as e:
        logger.error(f"TEST ERROR: {str(e)}")
        await message.answer("Test error - check logs")

@dp.message()
async def handle_search(message: types.Message):
    """Обработка текста: проверка пароля или поиск профиля"""
    if not message.text or message.text.startswith('/'):
        return
    
    user_id = message.from_user.id
    
    # Если не авторизован - проверяем пароль
    if user_id not in authorized_users:
        if message.text.strip() == BOT_PASSWORD:
            authorized_users.add(user_id)
            await message.answer(
                f"Доступ разрешен!\n\n"
                f"Привет, {message.from_user.first_name}! Отправь /start для начала работы."
            )
            logger.info(f"User {user_id} authorized")
        else:
            await message.answer("Неверный пароль. Попробуйте еще раз:")
            logger.warning(f"User {user_id} failed password attempt")
        return
    
    # Авторизован - выполняем поиск
    try:
        response = requests.get(
            f"{FLASK_API_URL}/api/catalog",
            params={'search': message.text},
            timeout=5
        )
        response.raise_for_status()
        data = response.json()
        
        if not data.get('success'):
            await message.answer("Ошибка поиска")
            return
        
        profiles = data.get('profiles', [])
        if not profiles:
            await message.answer(f"Профили по запросу '{message.text}' не найдены")
            return
        
        # Если найден РОВНО 1 профиль - отправляем сразу с фото
        if len(profiles) == 1:
            p = profiles[0]
            name = p['name']
            length = p.get('length', '-')
            qty = p.get('quantity_per_hanger', '-')
            notes = p.get('notes', '-') or "нет"
            
            caption = f"{name}\nКол-во: {qty}\nДлина: {length} мм\nПримечания: {notes}"
            
            photo_url = p.get('photo_full') or p.get('photo_thumb')
            if photo_url:
                try:
                    photo_response = requests.get(
                        f"{FLASK_API_URL}{photo_url}",
                        timeout=10
                    )
                    photo_response.raise_for_status()
                    
                    photo_file = BufferedInputFile(photo_response.content, filename=f"{name}.jpg")
                    await message.answer_photo(
                        photo=photo_file,
                        caption=caption
                    )
                except Exception as e:
                    logger.error(f"Could not send photo for {name}: {str(e)}")
                    await message.answer(caption)
            else:
                await message.answer(caption)
        
        # Если найдено НЕСКОЛЬКО - показываем полный список текстом
        else:
            await message.answer(
                f"Найдено {len(profiles)} профилей:\n\n" + 
                "\n".join([f"• {p['name']}" for p in profiles]) +
                "\n\nОтправьте точное название профиля для просмотра"
            )
        
        logger.info(f"User {message.from_user.id} searched: {message.text}")
        
    except requests.exceptions.RequestException as e:
        logger.error(f"API error during search: {e}")
        await message.answer("Ошибка соединения")
    except Exception as e:
        logger.error(f"Search error: {e}")
        await message.answer("Ошибка поиска")

# ===== CALLBACK ОБРАБОТЧИКИ =====

@dp.callback_query(F.data == "catalog")
async def cb_catalog(query: types.CallbackQuery):
    """Callback для кнопки каталога"""
    await query.answer()
    await catalog_cmd(query.message)

@dp.callback_query(F.data == "search")
async def cb_search(query: types.CallbackQuery):
    """Callback для кнопки поиска"""
    await query.answer()
    await search_cmd(query.message)

@dp.callback_query(F.data == "about")
async def cb_about(query: types.CallbackQuery):
    """Callback для кнопки информации"""
    await query.answer()
    await about_cmd(query.message)

# ===== ЗАПУСК БОТА =====

async def main():
    """Главная функция бота"""
    logger.info(f"Starting bot with token: {TELEGRAM_TOKEN[:10]}...")
    logger.info(f"Flask API URL: {FLASK_API_URL}")
    
    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    except Exception as e:
        logger.error(f"Bot error: {e}")
    finally:
        await bot.session.close()
        logger.info("Bot stopped")

if __name__ == "__main__":
    asyncio.run(main())
