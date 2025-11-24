#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Модуль для работы с SQLite базой данных профилей
"""

import sqlite3
from datetime import datetime
from pathlib import Path

DB_FILE = Path(__file__).parent / 'profiles.db'

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
        order_by: сортировка (например: 'updated_at DESC', 'usage_count DESC')
        limit: ограничение количества
    
    Returns:
        list of dict
    """
    conn = get_db_connection()
    try:
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
    Ищет профили по частичному совпадению:
    1. Имени (наивысший приоритет)
    2. Примечаний (высокий приоритет)
    3. Количества на подвес (низкий приоритет)
    4. Длины (низкий приоритет)
    
    Args:
        query: поисковый запрос
        order_by: порядок сортировки (по умолчанию usage_count DESC)
    
    Returns:
        list of dict (отсортировано по приоритету совпадения + order_by)
    """
    conn = get_db_connection()
    try:
        # Ищем по всем полям с приоритетом:
        # CASE WHEN определяет приоритет совпадения:
        # 1 = имя, 2 = примечания, 3 = количество/длина
        rows = conn.execute(
            f'''SELECT *, 
                   CASE 
                       WHEN name LIKE ? THEN 1
                       WHEN notes LIKE ? THEN 2
                       WHEN CAST(quantity_per_hanger AS TEXT) LIKE ? THEN 3
                       WHEN CAST(length AS TEXT) LIKE ? THEN 3
                       ELSE 4
                   END as match_priority
                FROM profiles 
                WHERE name LIKE ? 
                   OR notes LIKE ? 
                   OR CAST(quantity_per_hanger AS TEXT) LIKE ? 
                   OR CAST(length AS TEXT) LIKE ?
                ORDER BY match_priority ASC, {order_by}''',
            (f'%{query}%', f'%{query}%', f'%{query}%', f'%{query}%',
             f'%{query}%', f'%{query}%', f'%{query}%', f'%{query}%')
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
