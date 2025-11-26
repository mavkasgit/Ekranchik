#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Скрипт для загрузки профилей в БД
Использование: python load_profiles.py profiles.csv
"""

import sys
import csv
import io
from pathlib import Path

# Добавляем родительскую папку в путь для импорта db
parent_dir = Path(__file__).parent.parent
sys.path.insert(0, str(parent_dir))

import db

# Устанавливаем UTF-8 для вывода
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

def load_from_csv(filename):
    """Загружает профили из CSV файла"""
    db.init_database()
    
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            header = next(reader)  # пропустить заголовок
            
            count = 0
            for row in reader:
                if len(row) < 1 or not row[0].strip():
                    continue
                
                name = row[0].strip()
                qty = int(row[1]) if len(row) > 1 and row[1].strip() else None
                length = float(row[2]) if len(row) > 2 and row[2].strip() else None
                notes = row[3].strip() if len(row) > 3 else ''
                
                success = db.add_or_update_profile(
                    name=name,
                    quantity_per_hanger=qty,
                    length=length,
                    notes=notes
                )
                
                if success:
                    print(f"✓ Загружен: {name}")
                    count += 1
                else:
                    print(f"✗ Ошибка: {name}")
            
            print(f"\n✅ Всего загружено: {count} профилей")
            
    except FileNotFoundError:
        print(f"❌ Файл не найден: {filename}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        sys.exit(1)

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Использование: python load_profiles.py <filename.csv>")
        print("\nФормат CSV:")
        print("Название,Кол-во,Длина,Примечание")
        print("ЮП-1625,50,6000,Люкс")
        print("ЮП-3233,45,5500,Стандарт")
        sys.exit(1)
    
    load_from_csv(sys.argv[1])
