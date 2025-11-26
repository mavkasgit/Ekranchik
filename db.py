#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Модуль для работы с SQLite базой данных профилей
"""

import sqlite3
from datetime import datetime
from pathlib import Path

DB_FILE = Path(__file__).parent / 'profiles.db'

# Маппинг Cyrillic → Latin lookalike characters
CYRILLIC_LATIN_MAP = {
    'А': 'A', 'а': 'a',  # А/a → A/a
    'В': 'B', 'в': 'b',  # В/в → B/b
    'Е': 'E', 'е': 'e',  # Е/е → E/e
    'К': 'K', 'к': 'k',  # К/к → K/k
    'М': 'M', 'м': 'm',  # М/м → M/m
    'Н': 'H', 'н': 'h',  # Н/н → H/h
    'О': 'O', 'о': 'o',  # О/о → O/o
    'П': 'P', 'п': 'p',  # П/п → P/p (похожа на P)
    'Р': 'P', 'р': 'p',  # Р/р → P/p
    'С': 'C', 'с': 'c',  # С/с → C/c
    'Т': 'T', 'т': 't',  # Т/т → T/t
    'У': 'Y', 'у': 'y',  # У/у → Y/y
    'Х': 'X', 'х': 'x',  # Х/х → X/x
}

def normalize_text(text):
    """
    Нормализует текст для поиска:
    - Переводит в нижний регистр
    - Заменяет похожие Cyrillic символы на Latin эквиваленты
    
    Примеры:
    'Проверка' → 'проверка' → 'проверка'
    'СЧ' → 'сч' (Cyrillic не меняется)
    'С' → 'c' (заменяется на Latin C)
    
    Args:
        text: исходный текст
    
    Returns:
        str: нормализованный текст
    """
    if not text:
        return ''
    
    text = str(text).lower()
    result = []
    for char in text:
        result.append(CYRILLIC_LATIN_MAP.get(char, char))
    
    return ''.join(result)

def get_db_connection():
    """Создает подключение к базе с автокоммитом и timeout"""
    conn = sqlite3.connect(DB_FILE, timeout=10)
    conn.row_factory = sqlite3.Row  # Возвращать строки как словари
    return conn

def init_database():
    """Инициализирует базу данных - создает таблицы если их нет"""
    conn = get_db_connection()
    
    conn.execute('''
        CREATE TABLE IF NOT EXISTS profiles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            quantity_per_hanger INTEGER,
            length REAL,
            notes TEXT,
            photo_thumb TEXT,
            photo_full TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            usage_count INTEGER DEFAULT 0
        )
    ''')
    
    # Создаем индекс для быстрого поиска по имени
    conn.execute('CREATE INDEX IF NOT EXISTS idx_profile_name ON profiles(name)')
    
    conn.commit()
    conn.close()
    print(f"[DB] База данных инициализирована: {DB_FILE}")

def add_or_update_profile(name, quantity_per_hanger=None, length=None, notes=None, 
                          photo_thumb=None, photo_full=None, usage_count=None):
    """
    Добавляет или обновляет профиль в базе
    
    Args:
        name: название профиля (обязательно)
        quantity_per_hanger: кол-во на подвес
        length: длина в мм
        notes: примечание
        photo_thumb: URL превью
        photo_full: URL полного фото
        usage_count: количество использований
    
    Returns:
        bool: True если успешно
    """
    conn = get_db_connection()
    
    try:
        # Проверяем существует ли профиль
        existing = conn.execute('SELECT * FROM profiles WHERE name = ?', (name,)).fetchone()
        
        if existing:
            # Обновляем только переданные поля
            updates = []
            params = []
            
            if quantity_per_hanger is not None:
                updates.append('quantity_per_hanger = ?')
                params.append(quantity_per_hanger)
            if length is not None:
                updates.append('length = ?')
                params.append(length)
            if notes is not None:
                updates.append('notes = ?')
                params.append(notes)
            if photo_thumb is not None:
                updates.append('photo_thumb = ?')
                params.append(photo_thumb)
            if photo_full is not None:
                updates.append('photo_full = ?')
                params.append(photo_full)
            if usage_count is not None:
                updates.append('usage_count = ?')
                params.append(usage_count)
            
            if updates:
                updates.append('updated_at = ?')
                params.append(datetime.now())
                params.append(name)
                
                query = f"UPDATE profiles SET {', '.join(updates)} WHERE name = ?"
                conn.execute(query, params)
        else:
            # Создаем новый
            conn.execute('''
                INSERT INTO profiles (name, quantity_per_hanger, length, notes, 
                                     photo_thumb, photo_full, usage_count)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (name, quantity_per_hanger, length, notes, photo_thumb, photo_full, usage_count or 0))
        
        conn.commit()
        return True
    except Exception as e:
        print(f"[DB ERROR] Ошибка при сохранении профиля '{name}': {e}")
        return False
    finally:
        conn.close()

def get_profile(name):
    """
    Получает информацию о профиле из базы
    
    Returns:
        dict или None
    """
    conn = get_db_connection()
    try:
        row = conn.execute('SELECT * FROM profiles WHERE name = ?', (name,)).fetchone()
        if row:
            return dict(row)
        return None
    finally:
        conn.close()

def get_all_profiles(order_by='updated_at DESC', limit=None):
    """
    Получает все профили из базы
    
    Args:
        order_by: сортировка (например: 'updated_at DESC', 'usage_count DESC', 'has_photos DESC')
                 'has_photos' сортирует по наличию фото (с фото сверху)
        limit: ограничение количества
    
    Returns:
        list of dict
    """
    conn = get_db_connection()
    try:
        # Поддерживаем специальную сортировку по наличию фото
        if 'has_photos' in order_by:
            # has_photos DESC = с фото в начале, has_photos ASC = без фото в начале
            direction = 'DESC' if 'DESC' in order_by else 'ASC'
            final_order = f'CASE WHEN photo_thumb IS NOT NULL OR photo_full IS NOT NULL THEN 0 ELSE 1 END {direction}, updated_at DESC'
            query = f'SELECT * FROM profiles ORDER BY {final_order}'
        else:
            query = f'SELECT * FROM profiles ORDER BY {order_by}'
        
        if limit:
            query += f' LIMIT {limit}'
        
        rows = conn.execute(query).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()

def delete_profile(name):
    """Удаляет профиль из базы"""
    conn = get_db_connection()
    try:
        conn.execute('DELETE FROM profiles WHERE name = ?', (name,))
        conn.commit()
        return True
    except Exception as e:
        print(f"[DB ERROR] Ошибка при удалении профиля '{name}': {e}")
        return False
    finally:
        conn.close()

def search_profiles(query, order_by='usage_count DESC'):
    """
    Ищет профили по частичному совпадению (case-insensitive, с нормализацией символов):
    1. Имени (наивысший приоритет)
    2. Примечаний (высокий приоритет)
    3. Количества на подвес (низкий приоритет)
    4. Длины (низкий приоритет)
    
    Нормализует Cyrillic/Latin похожие символы (С→C, Р→P и т.д.)
    
    Args:
        query: поисковый запрос (case-insensitive)
        order_by: порядок сортировки (по умолчанию usage_count DESC)
    
    Returns:
        list of dict (отсортировано по приоритету совпадения + order_by)
    """
    conn = get_db_connection()
    try:
        # Нормализуем поисковый запрос
        normalized_query = normalize_text(query)
        
        # Ищем по всем полям с приоритетом:
        # CASE WHEN определяет приоритет совпадения:
        # 1 = имя, 2 = примечания, 3 = количество/длина
        rows = conn.execute(
            f'''SELECT *, 
                   CASE 
                       WHEN LOWER(name) LIKE ? THEN 1
                       WHEN LOWER(notes) LIKE ? THEN 2
                       WHEN CAST(quantity_per_hanger AS TEXT) LIKE ? THEN 3
                       WHEN CAST(length AS TEXT) LIKE ? THEN 3
                       ELSE 4
                   END as match_priority
                FROM profiles 
                WHERE LOWER(name) LIKE ? 
                   OR LOWER(notes) LIKE ? 
                   OR CAST(quantity_per_hanger AS TEXT) LIKE ? 
                   OR CAST(length AS TEXT) LIKE ?
                ORDER BY match_priority ASC, {order_by}''',
            (f'%{normalized_query}%', f'%{normalized_query}%', f'%{normalized_query}%', f'%{normalized_query}%',
             f'%{normalized_query}%', f'%{normalized_query}%', f'%{normalized_query}%', f'%{normalized_query}%')
        ).fetchall()
        
        # Удаляем служебное поле match_priority из результатов
        result = []
        for row in rows:
            d = dict(row)
            d.pop('match_priority', None)
            result.append(d)
        
        return result
    finally:
        conn.close()

def update_usage_counts(profile_counts):
    """
    Обновляет usage_count для профилей из Excel
    
    Args:
        profile_counts: dict {profile_name: count}
    """
    conn = get_db_connection()
    try:
        for name, count in profile_counts.items():
            conn.execute(
                'UPDATE profiles SET usage_count = ? WHERE name = ?',
                (count, name)
            )
        conn.commit()
    finally:
        conn.close()

def rename_profile(old_name, new_name):
    """
    Переименовывает профиль в базе данных
    
    Args:
        old_name: старое название
        new_name: новое название
    
    Returns:
        bool: True если успешно, False если профиль не найден или ошибка
    """
    conn = get_db_connection()
    try:
        # Проверяем существует ли старый профиль
        existing = conn.execute('SELECT * FROM profiles WHERE name = ?', (old_name,)).fetchone()
        if not existing:
            print(f"[DB] Профиль '{old_name}' не найден")
            return False
        
        # Проверяем нет ли профиля с новым именем
        duplicate = conn.execute('SELECT * FROM profiles WHERE name = ?', (new_name,)).fetchone()
        if duplicate:
            print(f"[DB] Профиль с названием '{new_name}' уже существует")
            return False
        
        # Обновляем название в БД
        conn.execute(
            'UPDATE profiles SET name = ?, updated_at = ? WHERE name = ?',
            (new_name, datetime.now(), old_name)
        )
        conn.commit()
        print(f"[DB] Профиль переименован: '{old_name}' -> '{new_name}'")
        return True
    except Exception as e:
        print(f"[DB ERROR] Ошибка при переименовании профиля: {e}")
        return False
    finally:
        conn.close()

def sync_photos_from_folder(photos_folder='static/images'):
    """
    Синхронизирует фото из папки со всеми профилями в БД
    Ищет файлы типа: name.jpg, name-thumb.jpg
    
    Args:
        photos_folder: путь к папке с фото
    
    Returns:
        dict: статистика синхронизации {updated: N, found_files: N, total_profiles: N}
    """
    conn = get_db_connection()
    try:
        photos_path = Path(__file__).parent / photos_folder
        
        if not photos_path.exists():
            print(f"[DB] Папка фото не найдена: {photos_path}")
            return {'updated': 0, 'found_files': 0, 'total_profiles': 0, 'error': 'Folder not found'}
        
        # Получаем все профили
        profiles = conn.execute('SELECT name FROM profiles').fetchall()
        total = len(profiles)
        updated = 0
        found_files = 0
        
        # Для каждого профиля ищем фото
        for profile in profiles:
            name = profile['name']
            
            # Формируем имена файлов
            full_name = f"{name}.jpg"
            thumb_name = f"{name}-thumb.jpg"
            
            full_path = photos_path / full_name
            thumb_path = photos_path / thumb_name
            
            photo_full = None
            photo_thumb = None
            
            # Проверяем существуют ли файлы
            if full_path.exists():
                photo_full = f"/static/images/{full_name}"
                found_files += 1
            
            if thumb_path.exists():
                photo_thumb = f"/static/images/{thumb_name}"
                found_files += 1
            
            # Обновляем БД если нашли фото
            if photo_full or photo_thumb:
                conn.execute(
                    'UPDATE profiles SET photo_full = ?, photo_thumb = ?, updated_at = ? WHERE name = ?',
                    (photo_full, photo_thumb, datetime.now(), name)
                )
                updated += 1
        
        conn.commit()
        print(f"[DB] Синхронизация: обновлено {updated} профилей, найдено {found_files} файлов")
        
        return {
            'updated': updated,
            'found_files': found_files,
            'total_profiles': total,
            'success': True
        }
    
    except Exception as e:
        print(f"[DB ERROR] Ошибка при синхронизации фото: {e}")
        return {'success': False, 'error': str(e)}
    finally:
        conn.close()
