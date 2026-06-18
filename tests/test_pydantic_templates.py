"""Тесты для модуля pydantic_templates."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from pydantic_templates import BarChartOperation, ExcelPlan
from plan_executor import execute_plan


def test_barchart() -> None:
    """Тестирует создание столбчатой диаграммы."""
    input_file = "data.xlsx"
    output_file = "result.xlsx"

    op_json = {
        "args": {
            "title": "Прибыль по мероприятиям",
            "data_columns": [
                {"name": "Прибыль", "excel_column": "E"},
                {"name": "Мероприятия", "excel_column": "D"}
            ],
            "label_column": {"name": "Мероприятия", "excel_column": "D"},
            "output_sheet": "Диаграмма"
        },
        "operation": "СТОЛБЧАТАЯ_ДИАГРАММА"
    }

    op = BarChartOperation.parse_args(op_json)
    plan = ExcelPlan(operations=[op], summary="Тест столбчатой диаграммы")

    print(f"Input:  {input_file}")
    print(f"Output: {output_file}")
    print(f"Operation: {op.operation}")
    print(f"Title: {op.args.title}")

    execute_plan(input_file, output_file, plan)
    print("test_barchart completed")

if __name__ == "__main__":
    test_barchart()