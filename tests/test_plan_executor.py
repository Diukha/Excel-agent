"""Тесты для модуля plan_executor."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from pydantic_templates import ExcelPlan, ArithmeticOperation
from plan_executor import execute_plan


def test_plan_executor() -> None:
    """Тестирует исполнение плана с арифметической операцией."""
    input_file = "data.xlsx"
    output_file = "result.xlsx"

    op = ArithmeticOperation(
        operation="АРИФМЕТИКА",
        args={
            "operation_type": "ВЫЧИТАНИЕ",
            "operand1": {"name": "Выручка", "excel_column": "B"},
            "operand2": {"name": "Расходы", "excel_column": "C"},
            "result_column_name": "Прибыль",
            "result_column_letter": "E",
            "output_sheet": "Лист1"
        }
    )

    plan = ExcelPlan(operations=[op], summary="Тест исполнителя")

    print(f"Input:  {input_file}")
    print(f"Output: {output_file}")

    execute_plan(input_file, output_file, plan)
    print("test_plan_executor completed")


if __name__ == "__main__":
    test_plan_executor()
