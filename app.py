from flask import Flask, render_template, jsonify, request, send_from_directory
import pandas as pd
from datetime import datetime, timedelta
import os
from pathlib import Path
import openpyxl
from werkzeug.utils import secure_filename
import base64
from PIL import Image
import io

app = Flask(__name__)

# Определяем директорию где лежит app.py
BASE_DIR = Path(__file__).parent.absolute()

# Глобальный кэш для данных
_cache = {'df': None, 'file_mtime': None}

# Папка с фото профилей
PROFILES_DIR = BASE_DIR / 'static' / 'images'

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

def get_profile_photo(profile_name):
    """Проверяет наличие фото профиля и возвращает (thumb_url, full_url)"""
    if not profile_name or pd.isna(profile_name):
        return None, None
    
    # Очищаем имя от пробелов и лишних символов
    clean_name = str(profile_name).strip()
    
    # Поддерживаемые форматы
    extensions = ['.jpg', '.jpeg', '.png', '.webp', '.gif']
    
    thumb_url = None
    full_url = None
    
    for ext in extensions:
        # Проверяем превью (-thumb)
        if not thumb_url:
            thumb_variants = [
                PROFILES_DIR / f"{clean_name}-thumb{ext}",
                PROFILES_DIR / f"{clean_name.lower()}-thumb{ext}",
                PROFILES_DIR / f"{clean_name.upper()}-thumb{ext}",
            ]
            for path in thumb_variants:
                if path.exists():
                    thumb_url = f"/static/images/{path.name}"
                    break
        
        # Проверяем полное фото
        if not full_url:
            full_variants = [
                PROFILES_DIR / f"{clean_name}{ext}",
                PROFILES_DIR / f"{clean_name.lower()}{ext}",
                PROFILES_DIR / f"{clean_name.upper()}{ext}",
            ]
            for path in full_variants:
                if path.exists():
                    full_url = f"/static/images/{path.name}"
                    break
        
        if thumb_url and full_url:
            break
    
    return thumb_url, full_url

def get_profiles_without_photos():
    """Возвращает список уникальных профилей без фото"""
    df = get_dataframe()
    if df is None:
        return []
    
    # Получаем все уникальные профили
    profiles = df['profile'].dropna().unique()
    profiles = sorted([str(p).strip() for p in profiles if str(p).strip()])
    
    # Фильтруем те, у которых нет фото
    missing = []
    for profile in profiles:
        thumb_url, full_url = get_profile_photo(profile)
        if not thumb_url and not full_url:
            # Считаем сколько раз используется
            count = len(df[df['profile'] == profile])
            missing.append({'profile': profile, 'count': count})
    
    return sorted(missing, key=lambda x: x['count'], reverse=True)

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
        
        profile_name = row['profile'] if pd.notna(row['profile']) else '—'
        profile_thumb, profile_full = get_profile_photo(profile_name) if profile_name != '—' else (None, None)
        
        products.append({
            'number': row['number'] if pd.notna(row['number']) else '—',
            'date': row['date'].strftime('%d.%m.%y') if pd.notna(row['date']) else '—',
            'time': time_str,
            'client': row['client'] if pd.notna(row['client']) else '—',
            'profile': profile_name,
            'profile_photo_thumb': profile_thumb,
            'profile_photo_full': profile_full,
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

@app.route('/api/profiles/missing')
def api_missing_profiles():
    """API для получения списка профилей без фото"""
    missing = get_profiles_without_photos()
    return jsonify({
        'success': True,
        'total': len(missing),
        'profiles': missing
    })

@app.route('/profiles')
def profiles_page():
    """Страница со списком профилей без фото"""
    return render_template('profiles.html')

@app.route('/api/profiles/upload', methods=['POST'])
def upload_profile_photo():
    """Загрузка фото профиля с кропом - сохраняет 2 файла"""
    try:
        data = request.get_json()
        profile_name = data.get('profile_name')
        image_data = data.get('image_data')  # base64
        crop_data = data.get('crop_data')  # {x, y, width, height}
        
        if not profile_name or not image_data:
            return jsonify({'success': False, 'error': 'Не указано имя профиля или изображение'})
        
        # Декодируем base64
        if ',' in image_data:
            image_data = image_data.split(',')[1]
        
        img_bytes = base64.b64decode(image_data)
        img_original = Image.open(io.BytesIO(img_bytes))
        
        # Конвертируем в RGB если нужно (для PNG с прозрачностью)
        def convert_to_rgb(image):
            if image.mode in ('RGBA', 'LA', 'P'):
                background = Image.new('RGB', image.size, (255, 255, 255))
                if image.mode == 'P':
                    image = image.convert('RGBA')
                background.paste(image, mask=image.split()[-1] if image.mode == 'RGBA' else None)
                return background
            return image
        
        clean_name = profile_name.strip()
        
        # === 1. ПОЛНОЕ ФОТО (оригинал, без кропа) ===
        img_full = img_original.copy()
        img_full = convert_to_rgb(img_full)
        
        # Resize до 800px (сохраняем пропорции)
        max_size_full = 800
        if img_full.width > max_size_full or img_full.height > max_size_full:
            img_full.thumbnail((max_size_full, max_size_full), Image.Resampling.LANCZOS)
        
        full_path = PROFILES_DIR / f"{clean_name}.jpg"
        img_full.save(full_path, 'JPEG', quality=90, optimize=True)
        
        # === 2. ПРЕВЬЮ (с кропом) ===
        img_thumb = img_original.copy()
        
        # Применяем кроп
        if crop_data:
            x = int(crop_data.get('x', 0))
            y = int(crop_data.get('y', 0))
            width = int(crop_data.get('width', img_thumb.width))
            height = int(crop_data.get('height', img_thumb.height))
            img_thumb = img_thumb.crop((x, y, x + width, y + height))
        
        img_thumb = convert_to_rgb(img_thumb)
        
        # Resize до 300px (для превью)
        max_size_thumb = 300
        if img_thumb.width > max_size_thumb or img_thumb.height > max_size_thumb:
            img_thumb.thumbnail((max_size_thumb, max_size_thumb), Image.Resampling.LANCZOS)
        
        thumb_path = PROFILES_DIR / f"{clean_name}-thumb.jpg"
        img_thumb.save(thumb_path, 'JPEG', quality=85, optimize=True)
        
        return jsonify({
            'success': True,
            'message': f'Фото для профиля "{clean_name}" успешно загружено (2 файла)',
            'url_full': f'/static/images/{clean_name}.jpg',
            'url_thumb': f'/static/images/{clean_name}-thumb.jpg'
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

if __name__ == '__main__':
    app.run(debug=True, port=5000)
