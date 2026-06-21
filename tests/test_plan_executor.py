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
        "operation_type": "ВЫЧИТАНИЕ",
        "operand1": {
          "name": "Выручка",
          "excel_column": "B"
        },
        "operand2": {
          "name": "Расходы",
          "excel_column": "C"
        },
        "result_column_name": "Прибыль",
        "result_column_letter": "E",
        "output_sheet": ""
      },
      "operation": "АРИФМЕТИКА"
    },
    {
      "args": {
        "target_column": {
          "name": "C1:C3",
          "excel_column": "C"
        },
        "operator": "МЕНЬШЕ",
        "value": 0.0,
        "fill_color": "FF0000",
        "font_color": "FFFFFF"
      },
      "operation": "УСЛОВНОЕ_ФОРМАТИРОВАНИЕ"
    },
    {
      "args": {
        "title": "Сравнение выручки и расходов",
        "data_columns": [
          {
            "name": "Выручка",
            "excel_column": "B"
          },
          {
            "name": "Расходы",
            "excel_column": "C"
          }
        ],
        "label_column": {
          "name": "Дата",
          "excel_column": "A"
        },
        "output_sheet": "Диаграмма1"
      },
      "operation": "СТОЛБЧАТАЯ_ДИАГРАММА"
    },
    {
      "args": {
        "title": "Количество мероприятий",
        "data_column": {
          "name": "Количество",
          "excel_column": "D"
        },
        "label_column": {
          "name": "Ячейка",
          "excel_column": "D"
        },
        "output_sheet": "Диаграмма_Мероприятия"
      },
      "operation": "КРУГОВАЯ_ДИАГРАММА"
    }
  ],
  "summary": "План сформирован пошагово"
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
