"""Анализатор структуры Excel-файлов.

Использует sheetwise для сжатия данных Excel в компактный текст,
оптимизированный для передачи в контекст LLM-агента.
"""

import re

from openpyxl.utils import get_column_letter
from sheetwise import SpreadsheetLLM


def analyze_excel(file_path: str, preview_rows: int = 3) -> str:
    """Анализирует Excel-файл и возвращает компактное описание для LLM."""
    try:
        sllm = SpreadsheetLLM()
        df_full = sllm.load_from_file(file_path)

        columns_lines = []
        for i, col_name in enumerate(df_full.columns):
            letter = get_column_letter(i + 1)
            columns_lines.append(f"{letter}|{col_name}")

        columns_block = "\n".join(columns_lines)

        total_rows = len(df_full)
        df_preview = df_full.head(preview_rows)

        compressed = sllm.compressor.compress(df_preview)
        compressed_text = sllm.encode_compressed_for_llm(compressed)

        if total_rows > preview_rows:
            compressed_text = re.sub(
                r"# Data \(Compressed ([\d.]+)x\)",
                rf"# Data (Compressed \1x, {total_rows} rows total, showing first {preview_rows})",
                compressed_text,
                count=1,
            )

        if "## Types:" in compressed_text:
            parts = compressed_text.split("## Types:", 1)
            return f"{parts[0]}## Types:\n{columns_block}"
        else:
            return f"{compressed_text}\n\n{columns_block}"

    except Exception as e:
        return f"Ошибка: не удалось прочитать файл: {str(e)}"


if __name__ == "__main__":
    print(analyze_excel("data.xlsx"))