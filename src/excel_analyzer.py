"""Анализатор структуры Excel-файлов.

Использует sheetwise для сжатия данных Excel в компактный текст,
оптимизированный для передачи в контекст LLM-агента.
"""

from openpyxl.utils import get_column_letter
from sheetwise import SpreadsheetLLM


def analyze_excel(file_path: str) -> str:
    """Анализирует Excel-файл и возвращает сжатое описание для LLM.

    Формат вывода (sheetwise compressed + колонки под Types):
        # Data (Compressed Nx)
        ## Values:
        значение|ячейка
        ...
        ## Types:
        A|Имя столбца
        B|Имя столбца

    Args:
        file_path: Путь к Excel-файлу (.xlsx).

    Returns:
        Строка с описанием структуры и данных файла.
    """
    try:
        sllm = SpreadsheetLLM()
        df = sllm.load_from_file(file_path)

        compressed_text = sllm.compress_and_encode_for_llm(df)

        columns_lines = []
        for i, col_name in enumerate(df.columns):
            letter = get_column_letter(i + 1)
            columns_lines.append(f"{letter}|{col_name}")

        columns_block = "\n".join(columns_lines)

        if "## Types:" in compressed_text:
            parts = compressed_text.split("## Types:", 1)
            return f"{parts[0]}## Types:\n{columns_block}"
        else:
            return f"{compressed_text}\n\n{columns_block}"

    except Exception as e:
        return f"Ошибка: не удалось прочитать файл: {str(e)}"


if __name__ == "__main__":
    print(analyze_excel("data.xlsx"))