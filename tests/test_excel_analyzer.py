"""Тесты для модуля excel_analyzer."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from excel_analyzer import analyze_excel


def test_excel_analyze() -> None:
    """Тестирует анализ структуры Excel-файла."""
    result = analyze_excel("result.xlsx")
    print(result)


if __name__ == "__main__":
    test_excel_analyze()
