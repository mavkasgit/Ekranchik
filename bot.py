#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Telegram бот для справочника профилей"""

import asyncio
import logging
import os
from pathlib import Path
import requests
import json
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, BufferedInputFile, ReplyKeyboardMarkup, KeyboardButton
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from dotenv import load_dotenv
from logging_config import setup_logging

load_dotenv()
logger = setup_logging("bot")

TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN', 'YOUR_TOKEN_HERE')
BOT_PASSWORD = os.getenv('BOT_PASSWORD', '1122')
FLASK_API_URL = os.getenv('FLASK_API_URL', 'http://localhost:5000')
AUTH_FILE = 'authorized_users.json'

logger.info(f"[INIT] Token: {TELEGRAM_TOKEN[:20]}...")
logger.info(f"[INIT] Password: {BOT_PASSWORD}")

if TELEGRAM_TOKEN.startswith('YOUR_'):
    logger.error("TELEGRAM_TOKEN не установлен!")
    exit(1)

def load_authorized_users():
    """Загружает авторизованных пользователей"""
    if not os.path.exists(AUTH_FILE):
        return set()
    try:
        with open(AUTH_FILE, 'r') as f:
            return set(json.load(f))
    except:
        return set()

def save_authorized_users():
    """Сохраняет авторизованных пользователей"""
    try:
        with open(AUTH_FILE, 'w') as f:
            json.dump(list(authorized_users), f)
    except Exception as e:
        logger.error(f"Ошибка сохранения пользователей: {e}")

authorized_users = load_authorized_users()
user_search_cache = {}

logger.info(f"[INIT] Загружено {len(authorized_users)} авторизованных пользователей")

bot = Bot(
    token=TELEGRAM_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN)
)
dp = Dispatcher()

logger.info("[INIT] Bot initialized")

@dp.message(Command("start"))
async def start_cmd(message: types.Message):
    """Команда /start"""
    try:
        user_id = message.from_user.id
        logger.info(f"[START] User {user_id} called /start")
        
        if user_id not in authorized_users:
            await message.answer("Привет! Введи пароль для доступа:")
            logger.info(f"[START] User {user_id} запросил пароль")
            return
        
        kb = ReplyKeyboardMarkup(keyboard=[
            [KeyboardButton(text="🔍 Поиск")],
            [KeyboardButton(text="ℹ️ О системе")]
        ], resize_keyboard=True)
        
        await message.answer(
            f"Добро пожаловать, {message.from_user.first_name}!",
            reply_markup=kb
        )
        logger.info(f"[START] User {user_id} авторизован")
    except Exception as e:
        logger.error(f"[START] Ошибка: {e}", exc_info=True)
        await message.answer("Ошибка")

@dp.message(Command("search"))
async def search_cmd(message: types.Message):
    """Команда /search"""
    try:
        await message.answer("Введи название профиля:")
    except Exception as e:
        logger.error(f"[SEARCH] Ошибка: {e}")

@dp.message(F.text == "🔍 Поиск")
async def search_button(message: types.Message):
    """Кнопка поиска"""
    try:
        await message.answer("Введи название профиля:")
    except Exception as e:
        logger.error(f"[SEARCH_BTN] Ошибка: {e}")

@dp.message(F.text == "ℹ️ О системе")
async def about_button(message: types.Message):
    """Кнопка О системе"""
    try:
        await message.answer("Справочник профилей Ekranchik")
    except Exception as e:
        logger.error(f"[ABOUT_BTN] Ошибка: {e}")

async def show_profile(message: types.Message, profile: dict):
    """Показывает профиль"""
    try:
        name = profile.get('name', 'Unknown')
        length = profile.get('length', '-')
        qty = profile.get('quantity_per_hanger', '-')
        notes = profile.get('notes', '-') or 'нет'
        
        caption = f"*{name}*\nКол-во: {qty}\nДлина: {length} мм\nПримечания: {notes}"
        
        photo_url = profile.get('photo_full') or profile.get('photo_thumb')
        if photo_url:
            try:
                photo_response = requests.get(
                    f"{FLASK_API_URL}{photo_url}",
                    timeout=10
                )
                photo_response.raise_for_status()
                photo_file = BufferedInputFile(photo_response.content, filename=f"{name}.jpg")
                await message.answer_photo(photo=photo_file, caption=caption, parse_mode=ParseMode.MARKDOWN)
            except Exception as e:
                logger.error(f"Ошибка загрузки фото: {e}")
                await message.answer(caption, parse_mode=ParseMode.MARKDOWN)
        else:
            await message.answer(caption, parse_mode=ParseMode.MARKDOWN)
    except Exception as e:
        logger.error(f"[SHOW_PROFILE] Ошибка: {e}", exc_info=True)
        await message.answer("Ошибка")

@dp.callback_query(lambda c: c.data.startswith("view_"))
async def view_profile(callback: types.CallbackQuery):
    """Просмотр профиля из кнопки"""
    try:
        user_id = callback.from_user.id
        index = int(callback.data.split("_")[1])
        
        if user_id not in user_search_cache or index >= len(user_search_cache[user_id]):
            await callback.answer("Результаты устарели", show_alert=True)
            return
        
        profile = user_search_cache[user_id][index]
        await show_profile(callback.message, profile)
        await callback.answer()
        logger.info(f"[CALLBACK] User {user_id} просмотрел профиль")
    except Exception as e:
        logger.error(f"[CALLBACK] Ошибка: {e}", exc_info=True)
        await callback.answer("Ошибка", show_alert=True)

@dp.message()
async def handle_text(message: types.Message):
    """Обработка всех текстовых сообщений"""
    try:
        user_id = message.from_user.id
        text = message.text or "[NO TEXT]"
        
        logger.info(f"[MESSAGE] User {user_id}: {text[:100]}")
        
        if not message.text or message.text.startswith('/'):
            logger.debug(f"[SKIP] Пропускаем команду: {text}")
            return
        
        if message.text in ("🔍 Поиск", "ℹ️ О системе"):
            logger.debug(f"[SKIP] Пропускаем кнопку: {text}")
            return
        
        # Проверка пароля
        if user_id not in authorized_users:
            logger.info(f"[AUTH] User {user_id} проверка пароля")
            if message.text.strip() == BOT_PASSWORD:
                authorized_users.add(user_id)
                save_authorized_users()
                logger.info(f"[AUTH] User {user_id} успешно авторизован")
                
                kb = ReplyKeyboardMarkup(keyboard=[
                    [KeyboardButton(text="🔍 Поиск")],
                    [KeyboardButton(text="ℹ️ О системе")]
                ], resize_keyboard=True)
                
                await message.answer(
                    f"Доступ разрешен, {message.from_user.first_name}!",
                    reply_markup=kb
                )
            else:
                logger.warning(f"[AUTH] User {user_id} неверный пароль")
                await message.answer("Неверный пароль")
            return
        
        # Поиск профиля
        logger.info(f"[SEARCH] User {user_id} ищет: {text}")
        
        try:
            response = requests.get(
                f"{FLASK_API_URL}/api/catalog",
                params={'search': text},
                timeout=10
            )
            response.raise_for_status()
            data = response.json()
        except requests.exceptions.Timeout:
            logger.error(f"[SEARCH] Timeout для user {user_id}")
            await message.answer("Сервер не отвечает")
            return
        except requests.exceptions.ConnectionError:
            logger.error(f"[SEARCH] Нет соединения для user {user_id}")
            await message.answer("Сервер недоступен")
            return
        except Exception as e:
            logger.error(f"[SEARCH] Ошибка API: {e}")
            await message.answer("Ошибка соединения")
            return
        
        if not data.get('success'):
            logger.error(f"[SEARCH] API error: {data}")
            await message.answer("Ошибка сервера")
            return
        
        profiles = data.get('profiles', [])
        logger.info(f"[SEARCH] Найдено {len(profiles)} профилей для user {user_id}")
        
        if not profiles:
            await message.answer(f"Профили не найдены: '{text}'")
            return
        
        if len(profiles) == 1:
            await show_profile(message, profiles[0])
        elif len(profiles) <= 5:
            user_search_cache[user_id] = profiles
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text=p['name'], callback_data=f"view_{i}")]
                for i, p in enumerate(profiles)
            ])
            await message.answer(f"Найдено {len(profiles)} профилей:", reply_markup=kb)
        else:
            names = "\n".join([f"• {p['name']}" for p in profiles[:20]])
            await message.answer(f"Найдено {len(profiles)} профилей:\n\n{names}\n\nОпишите точнее")
    
    except Exception as e:
        logger.error(f"[MESSAGE] Критическая ошибка: {e}", exc_info=True)
        try:
            await message.answer("Непредвиденная ошибка")
        except:
            pass

async def main():
    """Главная функция"""
    logger.info("[BOT] Запуск бота...")
    try:
        logger.info("[BOT] Начинаю polling...")
        await dp.start_polling(bot)
    except Exception as e:
        logger.error(f"[BOT] Ошибка: {e}", exc_info=True)
    finally:
        await bot.session.close()
        logger.info("[BOT] Бот остановлен")

if __name__ == "__main__":
    try:
        logger.info("[MAIN] Начинаю asyncio.run(main())")
        asyncio.run(main())
    except Exception as e:
        logger.error(f"[MAIN] Критическая ошибка: {e}", exc_info=True)
    logger.info("[MAIN] Завершение программы")
