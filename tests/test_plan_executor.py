"""Тесты для модуля plan_executor."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from pydantic_templates import ExcelPlan
from plan_executor import execute_plan

PLAN_JSON = """{
  "operations": [
    {
      "args": {
        "title": "Круговая диаграмма",
        "data_column": {
          "name": "B",
          "excel_column": "B"
        },
        "label_column": {
          "name": "A",
          "excel_column": "A"
        },
        "output_sheet": "Sheet1"
      },
      "operation": "КРУГОВАЯ_ДИАГРАММА"
    },
    {
      "args": {
        "operation_type": "СЛОЖЕНИЕ",
        "operand1": {
          "name": "B",
          "excel_column": "B"
        },
        "operand2": {
          "name": "C",
          "excel_column": "C"
        },
        "result_column_name": "D",
        "result_column_letter": "D",
        "output_sheet": "Sheet1"
      },
      "operation": "АРИФМЕТИКА"
    },
    {
      "args": {
        "title": "Круговая диаграмма",
        "data_column": {
          "name": "D",
          "excel_column": "D"
        },
        "label_column": {
          "name": "A",
          "excel_column": "A"
        },
        "output_sheet": "Sheet1"
      },
      "operation": "КРУГОВАЯ_ДИАГРАММА"
    }
  ],
  "summary": "Создание круговой диаграммы по столбцу B"
}"""


def test_plan_executor() -> None:
    input_file = "data.xlsx"
    output_file = "result.xlsx"

    plan = ExcelPlan(**json.loads(PLAN_JSON))

    print(f"Input:  {input_file}")
    print(f"Output: {output_file}")

    execute_plan(input_file, output_file, plan)
    print("test_plan_executor completed")


if __name__ == "__main__":
    test_plan_executor()
