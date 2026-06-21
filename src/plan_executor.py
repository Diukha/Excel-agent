"""Исполнение плана обработки Excel-файлов."""

import shutil

from pydantic_templates import ExcelPlan


def execute_plan(input_file: str, output_file: str, plan: ExcelPlan) -> None:
    """Выполняет план операций над Excel-файлом."""
    print(f"\n[EXECUTOR] План: {plan.summary}")
    print(f"[EXECUTOR] Операций: {len(plan.operations)}")

    shutil.copy2(input_file, output_file)

    for i, op in enumerate(plan.operations):
        print(f"[EXECUTOR] Операция {i + 1}/{len(plan.operations)}: {op.operation}")
        op.execute(output_file, output_file)

    print(f"[EXECUTOR] Готово: {output_file}")
