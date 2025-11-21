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
import db

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

# Кэш для списка фото (сканируем один раз при старте)
_photos_cache = {}

def scan_profile_photos():
    """Сканирует папку с фото и создает словарь {профиль: (thumb_url, full_url)}"""
    global _photos_cache
    _photos_cache.clear()
    
    if not PROFILES_DIR.exists():
        print(f"[WARN] Папка с фото не найдена: {PROFILES_DIR}")
        return
    
    print(f"[SCAN] Сканирование фото профилей...")
    thumb_count = 0
    full_count = 0
    
    # Проходим по всем файлам в папке
    for file_path in PROFILES_DIR.glob('*'):
        if not file_path.is_file():
            continue
        
        # Проверяем расширение
        ext = file_path.suffix.lower()
        if ext not in ['.jpg', '.jpeg', '.png', '.webp', '.gif']:
            continue
        
        filename = file_path.stem  # Имя без расширения
        is_thumb = filename.endswith('-thumb')
        
        # Получаем имя профиля
        profile_name = filename[:-6] if is_thumb else filename
        
        # Нормализуем имя (lowercase для проверки)
        profile_key = profile_name.lower()
        
        # Инициализируем если еще нет
        if profile_key not in _photos_cache:
            _photos_cache[profile_key] = {'thumb': None, 'full': None, 'original_name': profile_name}
        
        # Сохраняем URL
        url = f"/static/images/{file_path.name}"
        if is_thumb:
            _photos_cache[profile_key]['thumb'] = url
            thumb_count += 1
        else:
            _photos_cache[profile_key]['full'] = url
            full_count += 1
    
    print(f"[OK] Найдено профилей с фото: {len(_photos_cache)} ({thumb_count} превью, {full_count} полных)")

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

def get_dataframe(full_dataset=False):
    """
    Читает Excel с кэшированием
    
    Args:
        full_dataset: если True - читает ВСЕ строки (для поиска фото),
                     если False - последние 100 строк (для таблицы, быстро)
    """
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
        # Возвращаем либо полный датасет, либо последние 100 строк
        df_cached = _cache['df'].copy()
        if not full_dataset and len(df_cached) > 100:
            return df_cached.tail(100)
        return df_cached
    
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
    
    # Переименовываем колонки для удобства
    df.columns = ['date', 'number', 'time', 'material_type', 'kpz_number', 
                  'client', 'profile', 'color', 'lamels_qty']
    
    # ВАЖНО: удаляем полностью пустые строки (где все ячейки пусты)
    df = df.dropna(how='all')
    
    print(f"[DEBUG] После удаления пустых: {len(df)} строк")
    
    # Сохраняем в кэш с временной меткой
    from datetime import datetime
    _cache['df'] = df
    _cache['file_mtime'] = current_mtime
    _cache['cache_time'] = datetime.now()
    
    if force_reload:
        timestamp = datetime.now().strftime('%H:%M:%S')
        print(f"[OK] [{timestamp}] Загружено {len(df)} строк в кэш")
    
    # Возвращаем либо полный датасет, либо последние 100 строк
    if not full_dataset and len(df) > 100:
        return df.tail(100).copy()
    return df.copy()

def split_profiles(profile_string):
    """
    Разбивает строку с несколькими профилями на отдельные профили
    Разделители: пробелы, +, запятые, точки с запятой
    
    Примеры:
    "юп-1625  +  юп-3233 + юп-1875" → ["юп-1625", "юп-3233", "юп-1875"]
    "корпус" → ["корпус"]
    "1515  357  381  юп-009" → ["1515", "357", "381", "юп-009"]
    """
    if not profile_string or pd.isna(profile_string):
        return []
    
    profile_str = str(profile_string).strip()
    
    # Разделители: +, запятая, точка с запятой, 2+ пробела
    import re
    # Заменяем разделители на |
    profile_str = re.sub(r'\s*[+,;]\s*|\s{2,}', '|', profile_str)
    
    # Разбиваем по |
    profiles = [p.strip() for p in profile_str.split('|') if p.strip()]
    
    # Фильтруем слишком короткие (меньше 2 символов)
    profiles = [p for p in profiles if len(p) >= 2]
    
    return profiles

def get_profile_photo(profile_name):
    """Проверяет наличие фото профиля и возвращает (thumb_url, full_url) из кэша"""
    if not profile_name or pd.isna(profile_name):
        return None, None
    
    # Очищаем имя и приводим к lowercase для поиска
    clean_name = str(profile_name).strip()
    profile_key = clean_name.lower()
    
    # Проверяем кэш
    if profile_key in _photos_cache:
        photo_info = _photos_cache[profile_key]
        return photo_info['thumb'], photo_info['full']
    
    return None, None

def check_profiles_have_photos(profile_string):
    """
    Проверяет есть ли фото хотя бы у ОДНОГО из профилей в строке
    
    Args:
        profile_string: строка с одним или несколькими профилями
        
    Returns:
        bool: True если хотя бы у одного профиля есть фото
    """
    if not profile_string or pd.isna(profile_string):
        return False
    
    # Разбиваем на отдельные профили
    profiles = split_profiles(profile_string)
    
    # Проверяем каждый профиль
    for profile in profiles:
        thumb_url, full_url = get_profile_photo(profile)
        if thumb_url or full_url:
            return True  # Хотя бы у одного есть фото
    
    return False  # Ни у одного нет фото

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

def get_recent_profiles(limit=50):
    """Возвращает последние записи с заполненным полем 'Профиль'"""
    df = get_dataframe()
    if df is None:
        return []
    
    # Фильтруем только строки с заполненным профилем
    df_with_profiles = df[pd.notna(df['profile']) & (df['profile'].astype(str).str.strip() != '')]
    
    # Сохраняем оригинальный индекс для правильной сортировки
    # Индекс = номер строки в Excel, поэтому последние строки = максимальный индекс
    df_with_profiles = df_with_profiles.sort_index(ascending=False)
    
    # Берем последние N записей
    recent = df_with_profiles.head(limit)
    
    # Формируем результат с проверкой наличия фото
    result = []
    for idx, row in recent.iterrows():
        profile_name = str(row['profile']).strip()
        # Проверяем есть ли фото хотя бы у одного из профилей в строке
        has_photo = check_profiles_have_photos(profile_name)
        
        # Получаем URL фото (для первого профиля если их несколько)
        profiles = split_profiles(profile_name)
        thumb_url, full_url = None, None
        if profiles:
            thumb_url, full_url = get_profile_photo(profiles[0])
        
        result.append({
            'profile': profile_name,
            'date': row['date'].strftime('%d.%m.%Y') if pd.notna(row['date']) else '—',
            'number': row['number'] if pd.notna(row['number']) else '—',
            'has_photo': has_photo,
            'photo_thumb': thumb_url,
            'photo_full': full_url,
            'row_number': int(idx) + 2  # +2 потому что индекс с 0 + заголовок в Excel
        })
    
    return result

def get_recent_missing_profiles(limit=20, offset=0):
    """
    Возвращает топ N уникальных профилей БЕЗ фото (по последней строке) с пагинацией
    Просматривает ВСЕ строки файла без ограничений!
    
    Args:
        limit: сколько профилей вернуть (по умолчанию 20)
        offset: сколько профилей пропустить (для пагинации, по умолчанию 0)
    
    Returns:
        dict: {'profiles': [...], 'total': N, 'has_more': bool}
    """
    # ВАЖНО: full_dataset=True чтобы читать ВСЕ строки для поиска фото!
    df = get_dataframe(full_dataset=True)
    if df is None:
        return {'profiles': [], 'total': 0, 'has_more': False}
    
    # Фильтруем только строки с заполненным профилем
    df_with_profiles = df[pd.notna(df['profile']) & (df['profile'].astype(str).str.strip() != '')]
    
    # Сортируем по индексу (последние строки сверху)
    df_with_profiles = df_with_profiles.sort_index(ascending=False)
    
    # БЕЗ ОГРАНИЧЕНИЙ - просматриваем ВСЕ строки!
    
    # Собираем ВСЕ уникальные профили без фото (для подсчета total и пагинации)
    all_missing = []
    seen_profiles = set()
    
    for idx, row in df_with_profiles.iterrows():
        profile_name = str(row['profile']).strip()
        
        # Пропускаем, если этот профиль уже был добавлен
        if profile_name in seen_profiles:
            continue
        
        # Проверяем наличие фото хотя бы у одного из профилей (быстрая проверка по кэшу)
        has_photo = check_profiles_have_photos(profile_name)
        
        # Только профили БЕЗ фото
        if not has_photo:
            all_missing.append({
                'profile': profile_name,
                'date': row['date'].strftime('%d.%m.%Y') if pd.notna(row['date']) else '—',
                'number': row['number'] if pd.notna(row['number']) else '—',
                'has_photo': False,
                'row_number': int(idx) + 2  # +2 для Excel (индекс с 0 + заголовок)
            })
            seen_profiles.add(profile_name)
    
    # Применяем пагинацию
    total = len(all_missing)
    paginated = all_missing[offset:offset + limit]
    has_more = (offset + limit) < total
    
    return {
        'profiles': paginated,
        'total': total,
        'has_more': has_more
    }

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
    """API для получения списка профилей (без фото, недавние, или недавние без фото) с пагинацией"""
    sort_by = request.args.get('sort_by', default='missing')  # missing, recent, или recent_missing
    limit = request.args.get('limit', default=20, type=int)
    offset = request.args.get('offset', default=0, type=int)
    
    if sort_by == 'recent':
        profiles = get_recent_profiles(limit=limit)
        return jsonify({
            'success': True,
            'total': len(profiles),
            'profiles': profiles,
            'sort_by': 'recent',
            'has_more': False
        })
    elif sort_by == 'recent_missing':
        # Для этого режима просматриваем ВЕСЬ файл, возвращаем с пагинацией
        result = get_recent_missing_profiles(limit=limit, offset=offset)
        return jsonify({
            'success': True,
            'total': result['total'],
            'profiles': result['profiles'],
            'has_more': result['has_more'],
            'sort_by': 'recent_missing',
            'offset': offset,
            'limit': limit
        })
    else:
        missing = get_profiles_without_photos()
        return jsonify({
            'success': True,
            'total': len(missing),
            'profiles': missing,
            'sort_by': 'missing',
            'has_more': False
        })

@app.route('/api/catalog')
def api_catalog():
    """API для получения всех профилей из справочника"""
    try:
        search = request.args.get('search', '').strip()
        
        if search:
            profiles = db.search_profiles(search)
        else:
            profiles = db.get_all_profiles(order_by='updated_at DESC')
        
        return jsonify({
            'success': True,
            'total': len(profiles),
            'profiles': profiles
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        })

@app.route('/api/catalog/<profile_name>', methods=['DELETE'])
def api_delete_profile(profile_name):
    """API для удаления профиля из справочника"""
    try:
        # Удаляем из БД
        success = db.delete_profile(profile_name)
        
        if success:
            # Удаляем файлы фото (если есть)
            thumb_path = PROFILES_DIR / f"{profile_name}-thumb.jpg"
            full_path = PROFILES_DIR / f"{profile_name}.jpg"
            
            if thumb_path.exists():
                thumb_path.unlink()
            if full_path.exists():
                full_path.unlink()
            
            # Обновляем кэш
            scan_profile_photos()
            
            return jsonify({'success': True, 'message': f'Профиль "{profile_name}" удалён'})
        else:
            return jsonify({'success': False, 'error': 'Не удалось удалить профиль'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/catalog/<profile_name>', methods=['PUT'])
def api_update_profile(profile_name):
    """API для обновления данных профиля"""
    try:
        data = request.get_json()
        
        quantity_per_hanger = data.get('quantity_per_hanger')
        length = data.get('length')
        notes = data.get('notes', '').strip()
        
        success = db.add_or_update_profile(
            name=profile_name,
            quantity_per_hanger=quantity_per_hanger,
            length=length,
            notes=notes
        )
        
        if success:
            return jsonify({'success': True, 'message': f'Профиль "{profile_name}" обновлён'})
        else:
            return jsonify({'success': False, 'error': 'Не удалось обновить профиль'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/profiles/search-duplicates')
def api_search_duplicates():
    """Поиск профилей похожих на запрос (fuzzy matching)"""
    query = request.args.get('query', '').strip().lower()
    
    if not query:
        return jsonify({
            'success': False,
            'error': 'Не указан запрос для поиска'
        })
    
    # Получаем ВСЕ строки для поиска
    df = get_dataframe(full_dataset=True)
    if df is None:
        return jsonify({
            'success': False,
            'error': 'Не удалось загрузить данные'
        })
    
    # Фильтруем только строки с заполненным профилем
    df_with_profiles = df[pd.notna(df['profile']) & (df['profile'].astype(str).str.strip() != '')]
    
    # Ищем похожие профили
    matches = []
    seen_profiles = {}  # {profile_name: (row_idx, similarity)}
    
    for idx, row in df_with_profiles.iterrows():
        profile_name = str(row['profile']).strip()
        profile_lower = profile_name.lower()
        
        # Вычисляем процент совпадения
        similarity = calculate_similarity(query, profile_lower)
        
        # Порог совпадения >= 30%
        if similarity >= 30:
            # Берем самую свежую строку для каждого профиля
            if profile_name not in seen_profiles or idx > seen_profiles[profile_name][0]:
                seen_profiles[profile_name] = (idx, similarity)
    
    # Формируем результаты
    for profile_name, (idx, similarity) in seen_profiles.items():
        row = df_with_profiles.loc[idx]
        thumb_url, full_url = get_profile_photo(profile_name)
        has_photo = bool(thumb_url or full_url)
        
        # Подсчитываем сколько раз этот профиль встречается в файле
        count = len(df_with_profiles[df_with_profiles['profile'].astype(str).str.strip() == profile_name])
        
        matches.append({
            'profile': profile_name,
            'date': row['date'].strftime('%d.%m.%Y') if pd.notna(row['date']) else '—',
            'number': row['number'] if pd.notna(row['number']) else '—',
            'has_photo': has_photo,
            'row_number': int(idx) + 2,
            'similarity': int(similarity),
            'count': count
        })
    
    # Сортируем по совпадению (от большего к меньшему), при одинаковом совпадении - по частоте
    matches.sort(key=lambda x: (x['similarity'], x['count']), reverse=True)
    
    return jsonify({
        'success': True,
        'total': len(matches),
        'profiles': matches,
        'query': query
    })

def calculate_similarity(query, text):
    """Вычисляет процент совпадения между запросом и текстом"""
    from difflib import SequenceMatcher
    
    # 1. Точное совпадение = 100%
    if query == text:
        return 100
    
    # 2. Один полностью содержит другой как подстроку
    if query in text:
        # Чем ближе длины, тем выше совпадение
        length_ratio = len(query) / len(text)
        return int(70 + length_ratio * 30)  # 70-100%
    
    if text in query:
        length_ratio = len(text) / len(query)
        return int(60 + length_ratio * 30)  # 60-90%
    
    # 3. Используем SequenceMatcher для точного сравнения последовательностей
    matcher = SequenceMatcher(None, query, text)
    sequence_similarity = matcher.ratio() * 100
    
    # 4. Разбиваем на слова/токены и ищем совпадения
    query_words = set(query.replace('-', ' ').replace('_', ' ').split())
    text_words = set(text.replace('-', ' ').replace('_', ' ').split())
    
    if query_words and text_words:
        common_words = query_words & text_words
        word_similarity = (len(common_words) / len(query_words)) * 100
    else:
        word_similarity = 0
    
    # Итоговое совпадение = максимум из двух методов
    return max(sequence_similarity, word_similarity)

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

@app.route('/catalog')
def catalog_page():
    """Страница справочника профилей с фото и параметрами"""
    return render_template('catalog.html')

@app.route('/api/profiles/upload', methods=['POST'])
def upload_profile_photo():
    """Загрузка фото профиля с кропом - сохраняет 2 файла + запись в БД"""
    try:
        data = request.get_json()
        profile_name = data.get('profile_name')
        image_data = data.get('image_data')  # base64
        crop_data = data.get('crop_data')  # {x, y, width, height}
        
        # Дополнительные параметры для БД
        quantity_per_hanger = data.get('quantity_per_hanger')
        length = data.get('length')
        notes = data.get('notes', '').strip()
        
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
        
        # === 1. ПОЛНОЕ ФОТО (оригинал БЕЗ изменений) ===
        img_full = img_original.copy()
        img_full = convert_to_rgb(img_full)
        
        full_path = PROFILES_DIR / f"{clean_name}.jpg"
        img_full.save(full_path, 'JPEG', quality=95, optimize=True)
        print(f"[UPLOAD] Полное фото сохранено: {full_path} ({img_full.width}x{img_full.height})")
        
        # === 2. ПРЕВЬЮ (кропнутая область → уменьшена до 300px) ===
        img_thumb = img_original.copy()
        
        # Применяем кроп (если указан)
        if crop_data:
            x = int(crop_data.get('x', 0))
            y = int(crop_data.get('y', 0))
            width = int(crop_data.get('width', img_thumb.width))
            height = int(crop_data.get('height', img_thumb.height))
            print(f"[UPLOAD] Кроп для превью: x={x}, y={y}, width={width}, height={height}")
            
            # Валидация координат
            if width > 0 and height > 0:
                img_thumb = img_thumb.crop((x, y, x + width, y + height))
                print(f"[UPLOAD] Кроп применён, размер после: {img_thumb.width}x{img_thumb.height}")
            else:
                print(f"[UPLOAD] WARNING: Неверные размеры кропа, используем оригинал")
        
        img_thumb = convert_to_rgb(img_thumb)
        
        # Resize до 300px (для превью) - сохраняем пропорции
        max_size_thumb = 300
        if img_thumb.width > max_size_thumb or img_thumb.height > max_size_thumb:
            img_thumb.thumbnail((max_size_thumb, max_size_thumb), Image.Resampling.LANCZOS)
        
        print(f"[UPLOAD] Превью создано: {img_thumb.width}x{img_thumb.height}")
        
        thumb_path = PROFILES_DIR / f"{clean_name}-thumb.jpg"
        img_thumb.save(thumb_path, 'JPEG', quality=85, optimize=True)
        print(f"[UPLOAD] Превью сохранено: {thumb_path}")
        
        # Сохраняем в базу данных
        url_full = f'/static/images/{clean_name}.jpg'
        url_thumb = f'/static/images/{clean_name}-thumb.jpg'
        
        db.add_or_update_profile(
            name=clean_name,
            quantity_per_hanger=quantity_per_hanger,
            length=length,
            notes=notes,
            photo_thumb=url_thumb,
            photo_full=url_full
        )
        print(f"[UPLOAD] Профиль '{clean_name}' сохранён в БД")
        
        # Обновляем кэш фото
        scan_profile_photos()
        print(f"[UPLOAD] Кэш фото обновлён")
        
        return jsonify({
            'success': True,
            'message': f'Фото для профиля "{clean_name}" успешно загружено (2 файла)',
            'url_full': url_full,
            'url_thumb': url_thumb
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

if __name__ == '__main__':
    # Загружаем настройки из .env
    port = int(os.getenv('PORT', 5000))
    debug = os.getenv('DEBUG', 'True').lower() == 'true'
    
    # Инициализируем базу данных
    db.init_database()
    
    # Сканируем фото профилей (один раз при старте)
    scan_profile_photos()
    
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
