from flask import Flask, render_template, jsonify, request
import pandas as pd
from datetime import datetime, timedelta
import os
from pathlib import Path
import openpyxl

app = Flask(__name__)

# Определяем директорию где лежит app.py
BASE_DIR = Path(__file__).parent.absolute()

# Глобальный кэш для данных
_cache = {'df': None, 'file_mtime': None}

def get_dataframe():
    """Читает Excel с кэшированием - только последние 1500 строк"""
    files = [f for f in os.listdir(BASE_DIR) if f.endswith('.xlsm') and not f.startswith('~$')]
    if not files:
        return None
    
    excel_file = BASE_DIR / files[0]
    current_mtime = os.path.getmtime(excel_file)
    
    # Если файл не менялся - возвращаем из кэша
    if _cache['df'] is not None and _cache['file_mtime'] == current_mtime:
        return _cache['df'].copy()
    
    # Быстро узнаем количество строк
    wb = openpyxl.load_workbook(excel_file, read_only=True)
    ws = wb['Подвесы']
    total_rows = ws.max_row
    wb.close()
    
    # Читаем только последние 1500 строк (этого хватит на несколько месяцев)
    rows_to_read = min(1500, total_rows - 2)
    skip_rows = list(range(2, total_rows - rows_to_read))
    
    df = pd.read_excel(excel_file, sheet_name='Подвесы', skiprows=skip_rows, engine='openpyxl')
    
    # Переименовываем колонки
    df.columns = [
        'old_num', 'datetime', 'comment', 'date', 'number', 'time', 'shift',
        'material_type', 'quality', 'manager', 'kpz_number', 'client', 'profile',
        'suspension_type', 'processing_type', 'thickness', 'color', 'suspensions_qty',
        'conditional_qty', 'lamels_qty', 'unknown1', 'meterage', 'area', 'weight', 'on_suspension'
    ]
    
    # Сохраняем в кэш
    _cache['df'] = df
    _cache['file_mtime'] = current_mtime
    
    return df.copy()

def get_products(limit=None, days=2, no_time_filter=False, unload_filter=False, loading_limit=None, unloading_limit=None):
    """Читает Excel с фильтрами"""
    
    try:
        # Получаем данные из кэша (быстро!)
        df = get_dataframe()
        if df is None:
            return {'error': 'Excel файл (.xlsm) не найден', 'products': []}
        
        total_before = len(df)
        
        # Фильтр по дате (последние N дней)
        if days:
            cutoff_date = datetime.now() - timedelta(days=days)
            df['date'] = pd.to_datetime(df['date'], errors='coerce')
            df = df[df['date'] >= cutoff_date]
        
        loading_products = []
        unloading_products = []
        
        # Если включены оба фильтра
        if no_time_filter and unload_filter:
            # Загрузка: БЕЗ времени, С профилем
            df_loading = df[pd.isna(df['time']) & pd.notna(df['profile'])]
            load_limit = loading_limit if loading_limit else 10
            df_loading = df_loading.head(load_limit)
            loading_products = process_dataframe(df_loading)
            
            # Выгрузка: последние N строк С временем
            df_unloading = df[pd.notna(df['time'])]
            unload_limit = unloading_limit if unloading_limit else 10
            df_unloading = df_unloading.tail(unload_limit)
            unloading_products = process_dataframe(df_unloading)
            
            return {
                'success': True,
                'products': loading_products,
                'unloading_products': unloading_products,
                'total': len(loading_products) + len(unloading_products),
                'total_all': total_before,
                'days_filter': days,
                'dual_mode': True
            }
        
        # Фильтр: только Загрузка
        elif no_time_filter:
            df = df[pd.isna(df['time']) & pd.notna(df['profile'])]
            load_limit = loading_limit if loading_limit else (limit if limit else 10)
            df = df.head(load_limit)
        
        # Фильтр: только Выгрузка
        elif unload_filter:
            df = df[pd.notna(df['time'])]
            unload_limit = unloading_limit if unloading_limit else 10
            df = df.tail(unload_limit)
        
        # Обычный режим
        else:
            if limit:
                df = df.tail(limit)
            df = df.iloc[::-1]
        
        products = process_dataframe(df)
        
        return {
            'success': True,
            'products': products,
            'total': len(products),
            'total_all': total_before,
            'days_filter': days
        }
        
    except Exception as e:
        return {'error': str(e), 'products': []}

def process_dataframe(df):
    """Обрабатывает DataFrame и возвращает список продуктов"""
    products = []
    for _, row in df.iterrows():
        # Обработка ламелей (может быть "30+30" или число)
        lamels = row['lamels_qty']
        if pd.notna(lamels):
            try:
                # Если число - конвертим в int
                lamels_display = int(float(lamels))
            except:
                # Если строка типа "30+30" - оставляем как есть
                lamels_display = str(lamels)
        else:
            lamels_display = 0
        
        # Форматирование времени (убираем секунды)
        time_str = '—'
        if pd.notna(row['time']):
            time_val = str(row['time'])
            # Формат может быть "HH:MM:SS" или просто время
            if ':' in time_val:
                parts = time_val.split(':')
                time_str = f"{parts[0]}:{parts[1]}"
            else:
                time_str = time_val
        
        products.append({
            'number': row['number'] if pd.notna(row['number']) else '—',
            'date': row['date'].strftime('%d.%m.%y') if pd.notna(row['date']) else '—',
            'time': time_str,
            'client': row['client'] if pd.notna(row['client']) else '—',
            'profile': row['profile'] if pd.notna(row['profile']) else '—',
            'color': row['color'] if pd.notna(row['color']) else '—',
            'lamels_qty': lamels_display,
            'kpz_number': row['kpz_number'] if pd.notna(row['kpz_number']) else '—',
            'material_type': row['material_type'] if pd.notna(row['material_type']) else '—',
        })
    
    return products

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/products')
def api_products():
    limit = request.args.get('limit', type=int)
    days = request.args.get('days', default=2, type=int)
    no_time_filter = request.args.get('no_time_filter', default='false') == 'true'
    unload_filter = request.args.get('unload_filter', default='false') == 'true'
    loading_limit = request.args.get('loading_limit', type=int)
    unloading_limit = request.args.get('unloading_limit', type=int)
    
    data = get_products(limit, days, no_time_filter, unload_filter, loading_limit, unloading_limit)
    return jsonify(data)

if __name__ == '__main__':
    app.run(debug=True, port=5000)
