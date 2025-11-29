import pandas as pd
import os

def process_anod_data_and_sort():
    excel_file_path = r'D:\KTM\Ekranchik\archive\excel\КПЗ____28.11.xlsm'
    csv_file_path = r'D:\KTM\Ekranchik\archive\manual_import\profiles_anod.csv'

    print(f"--- Начало обработки файла: {excel_file_path} ---")

    if not os.path.exists(excel_file_path):
        print(f"!!! ОШИБКА: Excel-файл не найден по пути: {excel_file_path}")
        return

    try:
        # --- Шаг 1: Извлечение уникальных данных из Excel ---
        xls = pd.ExcelFile(excel_file_path)
        anod_sheet_names = [sheet for sheet in xls.sheet_names if 'АНОД' in sheet.upper()]

        if not anod_sheet_names:
            print("--- Внимание: Листы со словом 'АНОД' не найдены. ---")
            return

        print(f"Найдены листы для обработки: {anod_sheet_names}")

        all_data = []
        for sheet_name in anod_sheet_names:
            print(f"  > Чтение листа: {sheet_name}...")
            df = pd.read_excel(xls, sheet_name=sheet_name, usecols=[6, 18, 20], header=None)
            df.columns = ['profile', 'length_m', 'quantity']
            df.dropna(subset=['profile'], inplace=True)
            if not df.empty:
                all_data.append(df)

        if not all_data:
            print("--- Внимание: Не найдено данных для обработки во всех 'АНОД' листах. ---")
            return

        combined_df = pd.concat(all_data, ignore_index=True)
        
        combined_df = combined_df[pd.to_numeric(combined_df['length_m'], errors='coerce').notna()]
        combined_df = combined_df[pd.to_numeric(combined_df['quantity'], errors='coerce').notna()]
        
        combined_df['length_m'] = combined_df['length_m'].astype(float)
        combined_df['quantity'] = combined_df['quantity'].astype(int)
        combined_df['length_mm'] = (combined_df['length_m'] * 1000).astype(int)

        unique_from_excel = combined_df[['profile', 'length_mm', 'quantity']].drop_duplicates()
        unique_from_excel['profile'] = unique_from_excel['profile'].astype(str).str.strip()
        
        print(f"Найдено {len(unique_from_excel)} уникальных сочетаний в Excel.")

        # --- Шаг 2: Чтение существующих данных из CSV ---
        existing_df = pd.DataFrame()
        if os.path.exists(csv_file_path):
            print(f"\n--- Чтение существующего файла: {csv_file_path} ---")
            try:
                existing_df = pd.read_csv(csv_file_path, header=None, names=['profile', 'length_mm', 'quantity'])
                existing_df['profile'] = existing_df['profile'].astype(str).str.strip()
                print(f"Найдено {len(existing_df)} существующих записей в CSV.")
            except pd.errors.EmptyDataError:
                print("CSV файл пуст, будет создан новый.")
        else:
            print("CSV файл не найден, будет создан новый.")

        # --- Шаг 3: Объединение и поиск действительно новых строк ---
        if not existing_df.empty:
            # Используем merge для поиска строк, которые есть в Excel, но нет в CSV
            merged = pd.merge(unique_from_excel, existing_df, how='left', indicator=True)
            truly_new_rows = merged[merged['_merge'] == 'left_only'].drop(columns=['_merge'])
        else:
            truly_new_rows = unique_from_excel
        
        print(f"Найдено {len(truly_new_rows)} действительно новых строк для добавления.")
        
        # --- Шаг 4: Добавление только новых строк ---
        if not truly_new_rows.empty:
            print(f"\n--- Дозапись {len(truly_new_rows)} новых строк в {csv_file_path} ---")
            truly_new_rows.to_csv(csv_file_path, mode='a', header=False, index=False, encoding='utf-8')
            print("✅ Новые строки успешно добавлены.")
        else:
            print("--- Новых уникальных строк для добавления не найдено. ---")

        # --- Шаг 5: Сортировка всего файла ---
        print(f"\n--- Сортировка всего файла {csv_file_path} ---")
        final_df = pd.read_csv(csv_file_path, header=None, names=['profile', 'length_mm', 'quantity'])
        
        # Сортируем по названию профиля (сначала цифры, потом буквы, без учета регистра)
        final_df_sorted = final_df.sort_values(by='profile', key=lambda col: col.str.lower())
        
        # Перезаписываем файл с отсортированными данными и заголовком
        final_df_sorted.to_csv(csv_file_path, mode='w', header=True, index=False, encoding='utf-8')
        print(f"✅ Файл успешно отсортирован и перезаписан с {len(final_df_sorted)} строками.")

    except Exception as e:
        print(f"!!! ПРОИЗОШЛА ОШИБКА: {e}")

if __name__ == '__main__':
    process_anod_data_and_sort()