from flask import Flask, render_template, jsonify, request
import pandas as pd
from pathlib import Path
import os

app = Flask(__name__)

def get_products(limit=None, category=None, min_price=None, max_price=None):
    """Читает Excel с фильтрами"""
    
    excel_file = 'data.xlsx'
    images_dir = Path('static/images')
    
    if not os.path.exists(excel_file):
        return {'error': 'Excel файл не найден', 'products': []}
    
    try:
        df = pd.read_excel(excel_file, engine='openpyxl')
        
        total_before = len(df)
        
        # Фильтры
        if category:
            df = df[df['category'].str.contains(category, case=False, na=False)]
        
        if min_price is not None:
            df = df[df['price'] >= min_price]
        
        if max_price is not None:
            df = df[df['price'] <= max_price]
        
        # Сортировка (свежие сверху)
        df = df.sort_values('id', ascending=False)
        
        # Лимит
        if limit:
            df = df.head(limit)
        
        products = df.to_dict('records')
        
        # Проверка картинок
        for product in products:
            for key, value in product.items():
                if pd.isna(value):
                    product[key] = None
            
            img = product.get('image_filename')
            if img:
                product['image_exists'] = (images_dir / str(img)).exists()
            else:
                product['image_exists'] = False
        
        return {
            'success': True,
            'products': products,
            'total': len(products),
            'total_all': total_before
        }
        
    except Exception as e:
        return {'error': str(e), 'products': []}

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/products')
def api_products():
    limit = request.args.get('limit', type=int)
    category = request.args.get('category', type=str)
    min_price = request.args.get('min_price', type=float)
    max_price = request.args.get('max_price', type=float)
    
    data = get_products(limit, category, min_price, max_price)
    return jsonify(data)

if __name__ == '__main__':
    app.run(debug=True, port=5000)
