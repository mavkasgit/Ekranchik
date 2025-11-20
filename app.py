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
import time
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from dotenv import load_dotenv

# Загружаем переменные из .env файла
load_dotenv()

app = Flask(__name__)

# Определяем директорию где лежит app.py
BASE_DIR = Path(__file__).parent.absolute()

# Путь к Excel файлу из переменной окружения
EXCEL_FILE_PATH = os.getenv('EXCEL_FILE_PATH')
if EXCEL_FILE_PATH:
    EXCEL_FILE_PATH = Path(EXCEL_FILE_PATH)
    # Если указан конкретный файл
    if EXCEL_FILE_PATH.is_file():
        EXCEL_DIR = EXCEL_FILE_PATH.parent
        EXCEL_FILENAME = EXCEL_FILE_PATH.name
    else:
        # Если указана только директория - ищем .xlsm файлы в ней
        EXCEL_DIR = EXCEL_FILE_PATH
        EXCEL_FILENAME = None
else:
    # По умолчанию - текущая директория
    EXCEL_DIR = BASE_DIR
    EXCEL_FILENAME = None

print(f"[INFO] Excel директория: {EXCEL_DIR}")
if EXCEL_FILENAME:
    print(f"[INFO] Excel файл: {EXCEL_FILENAME}")

# Глобальный кэш для данных
_cache = {'df': None, 'file_mtime': None, 'cache_time': None, 'force_reload': True}

# Папка с фото профилей
profiles_dir = os.getenv('PROFILES_DIR', 'static/images')
PROFILES_DIR = BASE_DIR / profiles_dir if not Path(profiles_dir).is_absolute() else Path(profiles_dir)

# Watchdog для отслеживания изменений Excel файла
class ExcelFileHandler(FileSystemEventHandler):
    def __init__(self):
        self.last_modified = {}
    
    def on_modified(self, event):
        if event.is_directory:
            return
        # Отслеживаем .xlsm и временные файлы ~$
        if event.src_path.endswith('.xlsm') or '~$' in event.src_path:
            # Дебаунсинг: игнорируем события чаще чем раз в 1 секунду
            now = time.time()
            if event.src_path in self.last_modified:
                if now - self.last_modified[event.src_path] < 1.0:
                    return
            
            self.last_modified[event.src_path] = now
            timestamp = datetime.now().strftime('%H:%M:%S')
            print(f"[FILE] [{timestamp}] Файл изменен: {os.path.basename(event.src_path)}")
            _cache['force_reload'] = True
            _cache['file_changed'] = True  # Флаг для фронтенда

# Запускаем watchdog в отдельном потоке
observer = None
def start_file_watcher():
    global observer
    if observer is None:
        # Проверяем доступность директории
        if not EXCEL_DIR.exists():
            print(f"[WARN] Предупреждение: директория недоступна, мониторинг не запущен: {EXCEL_DIR}")
            return
        
        event_handler = ExcelFileHandler()
        observer = Observer()
        observer.schedule(event_handler, str(EXCEL_DIR), recursive=False)
        observer.start()
        print(f"[WATCH] Мониторинг файлов запущен: {EXCEL_DIR}")
        if EXCEL_DIR != BASE_DIR:
            print(f"   (сетевой диск - возможна задержка до 5 сек)")

def get_dataframe():
    """Читает Excel с кэшированием - последние 300 строк"""
    from datetime import datetime, timedelta
    
    # Проверяем доступность директории (для сетевых дисков)
    if not EXCEL_DIR.exists():
        print(f"[ERROR] Ошибка: директория недоступна: {EXCEL_DIR}")
        print(f"   Проверьте сетевое подключение и путь в .env файле")
        return None
    
    # Ищем Excel файл
    if EXCEL_FILENAME:
        # Конкретный файл указан
        excel_file = EXCEL_DIR / EXCEL_FILENAME
        if not excel_file.exists():
            print(f"[ERROR] Ошибка: файл не найден: {excel_file}")
            return None
    else:
        # Ищем любой .xlsm файл в директории
        files = [f for f in os.listdir(EXCEL_DIR) if f.endswith('.xlsm') and not f.startswith('~$')]
        if not files:
            print(f"[ERROR] Ошибка: .xlsm файлы не найдены в {EXCEL_DIR}")
            return None
        excel_file = EXCEL_DIR / files[0]
    current_mtime = os.path.getmtime(excel_file)
    
    # Проверяем временный файл (если Excel открыт)
    temp_file = EXCEL_DIR / f"~${excel_file.name}"
    if temp_file.exists():
        temp_mtime = os.path.getmtime(temp_file)
        current_mtime = max(current_mtime, temp_mtime)
    
    # Принудительная перезагрузка от watchdog
    force_reload = _cache.get('force_reload', False)
    
    # Проверяем кэш
    cache_valid = (
        _cache.get('df') is not None and 
        _cache.get('file_mtime') == current_mtime and
        not force_reload  # Сбрасываем кэш при изменении файла
    )
    
    if cache_valid:
        return _cache['df'].copy()
    
    # Сбрасываем флаг принудительной перезагрузки
    if force_reload:
        timestamp = datetime.now().strftime('%H:%M:%S')
        print(f"[RELOAD] [{timestamp}] Чтение Excel (файл изменен)...")
    
    _cache['force_reload'] = False
    
    # Читаем все данные (пропускаем только инструкции)
    # Строка 0-1: инструкции, Строка 2: заголовки, Строка 3+: данные
    df = pd.read_excel(excel_file, sheet_name='Подвесы', skiprows=[0, 1], 
                       usecols=[3, 4, 5, 7, 10, 11, 12, 16, 19], engine='openpyxl')
    
    print(f"[DEBUG] Прочитано всего строк: {len(df)}")
    
    # Берем последние 100 строк для скорости
    df = df.tail(100)
    
    # Переименовываем колонки для удобства
    df.columns = ['date', 'number', 'time', 'material_type', 'kpz_number', 
                  'client', 'profile', 'color', 'lamels_qty']
    
    # ВАЖНО: удаляем полностью пустые строки (где все ячейки пусты)
    df = df.dropna(how='all')
    
    print(f"[DEBUG] После tail(100) и удаления пустых: {len(df)} строк")
    
    # Сохраняем в кэш с временной меткой
    from datetime import datetime
    _cache['df'] = df
    _cache['file_mtime'] = current_mtime
    _cache['cache_time'] = datetime.now()
    
    if force_reload:
        timestamp = datetime.now().strftime('%H:%M:%S')
        print(f"[OK] [{timestamp}] Загружено {len(df)} строк")
    
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
        # Получаем данные из кэша
        df = get_dataframe()
        if df is None:
            return {'error': 'Excel файл (.xlsm) не найден', 'products': []}
        
        total_before = len(df)
        print(f"[DEBUG] Загружено строк из Excel: {total_before}")
        
        # Фильтр валидных строк: должна быть дата ИЛИ номер подвеса
        df = df[(pd.notna(df['date'])) | (pd.notna(df['number']))]
        print(f"[DEBUG] После фильтра (дата или номер): {len(df)} строк")
        
        # Фильтр по дате (последние N дней) - только для строк с датой
        if days:
            cutoff_date = datetime.now() - timedelta(days=days)
            df['date'] = pd.to_datetime(df['date'], errors='coerce')
            # Оставляем строки: (дата >= cutoff) ИЛИ (дата пустая, но есть номер)
            df = df[(df['date'] >= cutoff_date) | (pd.isna(df['date']) & pd.notna(df['number']))]
            print(f"[DEBUG] После фильтра по дате ({days} дней): {len(df)} строк")
        
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
            time_obj = row['time']
            # Если это объект time/datetime - конвертируем
            if hasattr(time_obj, 'strftime'):
                time_str = time_obj.strftime('%H:%M')
            else:
                # Если строка - парсим
                time_val = str(time_obj)
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

@app.route('/api/file/status')
def api_file_status():
    """Проверка статуса Excel файла + флаг изменения"""
    try:
        # Проверяем доступность директории
        if not EXCEL_DIR.exists():
            return jsonify({
                'success': False,
                'status': 'network_error',
                'message': 'Сетевая директория недоступна'
            })
        
        # Находим файл
        if EXCEL_FILENAME:
            excel_file = EXCEL_DIR / EXCEL_FILENAME
            if not excel_file.exists():
                return jsonify({
                    'success': False,
                    'status': 'not_found',
                    'message': f'Файл не найден: {EXCEL_FILENAME}'
                })
        else:
            files = [f for f in os.listdir(EXCEL_DIR) if f.endswith('.xlsm') and not f.startswith('~$')]
            if not files:
                return jsonify({
                    'success': False,
                    'status': 'not_found',
                    'message': 'Excel файл не найден'
                })
            excel_file = EXCEL_DIR / files[0]
        
        # Проверяем временный файл (Excel открыт?)
        temp_file = EXCEL_DIR / f"~${excel_file.name}"
        is_open = temp_file.exists()
        
        # Получаем время последнего изменения
        import datetime
        # Используем ctime (время изменения) или mtime (время модификации)
        # В Windows при сохранении в Excel обновляется mtime
        mtime = os.path.getmtime(excel_file)
        
        # Если файл открыт, также проверяем временный файл
        if is_open:
            temp_mtime = os.path.getmtime(temp_file)
            # Берем более свежее время
            mtime = max(mtime, temp_mtime)
        
        last_modified = datetime.datetime.fromtimestamp(mtime)
        
        # Размер файла
        file_size = os.path.getsize(excel_file)
        size_mb = round(file_size / (1024 * 1024), 2)
        
        # Проверяем флаг изменения и сбрасываем его
        file_changed = _cache.get('file_changed', False)
        if file_changed:
            _cache['file_changed'] = False  # Сбрасываем после считывания
        
        return jsonify({
            'success': True,
            'status': 'open' if is_open else 'closed',
            'filename': excel_file.name,
            'filepath': str(excel_file) if EXCEL_DIR != BASE_DIR else excel_file.name,
            'changed': file_changed,  # Флаг для фронтенда
            'last_modified': last_modified.strftime('%d.%m.%Y %H:%M:%S'),
            'last_modified_relative': get_relative_time(last_modified),
            'size_mb': size_mb,
            'is_open': is_open
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        })

def get_relative_time(dt):
    """Возвращает относительное время (например, '5 минут назад')"""
    from datetime import datetime, timedelta
    now = datetime.now()
    diff = now - dt
    
    if diff < timedelta(minutes=1):
        return 'только что'
    elif diff < timedelta(hours=1):
        mins = int(diff.total_seconds() / 60)
        return f'{mins} мин. назад'
    elif diff < timedelta(days=1):
        hours = int(diff.total_seconds() / 3600)
        return f'{hours} ч. назад'
    else:
        days = diff.days
        return f'{days} дн. назад'

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
    # Загружаем настройки из .env
    port = int(os.getenv('PORT', 5000))
    debug = os.getenv('DEBUG', 'True').lower() == 'true'
    
    # Запускаем файловый мониторинг
    start_file_watcher()
    
    print(f"\n[START] Запуск сервера на http://localhost:{port}")
    print(f"   Режим отладки: {debug}")
    print(f"   Excel директория: {EXCEL_DIR}")
    if EXCEL_DIR != BASE_DIR:
        print(f"   [WARN] Используется сетевой диск - проверьте доступность!")
    print()
    
    try:
        app.run(debug=debug, port=port, host='0.0.0.0')
    finally:
        # Останавливаем observer при выходе
        if observer:
            observer.stop()
            observer.join()
