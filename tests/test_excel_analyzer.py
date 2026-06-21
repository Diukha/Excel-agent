"""Тесты для модуля excel_analyzer."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from excel_analyzer import analyze_excel


def test_excel_analyze() -> None:
    """Тестирует анализ структуры Excel-файла."""
    result = analyze_excel("result.xlsx")
    print(result, "\n\n")

    assert isinstance(result, str), "Результат должен быть строкой"
    assert len(result) > 0, "Результат не должен быть пустым"
    assert "# Data (Compressed" in result, "Должен содержать заголовок sheetwise"
    assert "## Types:" in result, "Должна секция Types"
    assert "## Values:" in result, "Должна секция Values"

    types_idx = result.index("## Types:")
    types_section = result[types_idx:]

    column_lines = [line for line in types_section.split("\n") if "|" in line and len(line) <= 50]
    assert len(column_lines) > 0, "Должны быть строки с колонками в формате A|Имя"

    for col_line in column_lines:
        parts = col_line.split("|", 1)
        assert len(parts) == 2, f"Строка колонки должна быть в формате A|Имя: {col_line}"
        letter, name = parts
        assert len(letter) == 1 and letter.isalpha(), f"Первая часть должна быть буквой: {letter}"

    print("test_excel_analyze passed")


def test_excel_analyze_data() -> None:
    """Тестирует анализ data.xlsx и проверяет формат вывода."""
    result = analyze_excel("data.xlsx")

    assert isinstance(result, str)

    types_idx = result.index("## Types:")
    types_section = result[types_idx:]

    column_lines = [line for line in types_section.split("\n") if "|" in line and len(line) <= 50]
    col_letters = [c.split("|")[0] for c in column_lines]
    assert "A" in col_letters, "Первая колонка должна быть A"
    assert len(column_lines) >= 3, "В data.xlsx минимум 3 колонки"

    assert "|A1" in result or "|B1" in result, "Compressed text должен содержать ссылки на ячейки"

    print("test_excel_analyze_data passed")


if __name__ == "__main__":
    test_excel_analyze()
    test_excel_analyze_data()
