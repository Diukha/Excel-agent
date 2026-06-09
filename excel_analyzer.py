import pandas as pd
import json

def analyze_excel(file_path):
    """
    Проводит глубокий анализ структуры Excel файла для подготовки контекста ИИ-агенту.
    """
    analysis_results = {
        "sheets": {}
    }
    
    try:
        # Читаем все листы сразу
        excel_file = pd.ExcelFile(file_path)
        
        for sheet_name in excel_file.sheet_names:
            df = pd.read_excel(file_path, sheet_name=sheet_name)
            
            # Если лист пустой, пропускаем
            if df.empty:
                analysis_results["sheets"][sheet_name] = "Лист пуст"
                continue
            
            sheet_info = {
                "total_rows": len(df),
                "columns": [],
                "sample_data": df.head(3).to_dict(orient='records')  # Первые 3 строки
            }
            
            for column in df.columns:
                # Анализируем каждую колонку
                col_data = df[column]
                
                col_info = {
                    "name": str(column),
                    "type": str(col_data.dtype),
                    "non_null_count": int(col_data.count()),
                    "null_count": int(col_data.isnull().sum()),
                }
                
                # Если в колонке мало уникальных значений, это "категория" (например, Статус)
                # Передаем их модели, чтобы она знала, по каким фильтрам можно группировать
                unique_vals = col_data.dropna().unique()
                if len(unique_vals) < 15:
                    col_info["unique_values"] = [str(v) for v in unique_vals]
                else:
                    # Если данных много, даем только диапазон (для чисел)
                    if pd.api.types.is_numeric_dtype(col_data):
                        col_info["min"] = float(col_data.min()) if not pd.isna(col_data.min()) else None
                        col_info["max"] = float(col_data.max()) if not pd.isna(col_data.max()) else None
                
                sheet_info["columns"].append(col_info)
            
            analysis_results["sheets"][sheet_name] = sheet_info
            
        return analysis_results

    except Exception as e:
        return {"error": f"Не удалось прочитать файл: {str(e)}"}

# Пример использования для отладки:
if __name__ == "__main__":
    report = analyze_excel("data.xlsx")
    print(json.dumps(report, indent=2, ensure_ascii=False))