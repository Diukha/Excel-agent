"""Исполнение плана обработки Excel-файлов.

Последовательно выполняет операции из плана, передавая результат
каждой операции как вход для следующей.
"""

from pydantic_templates import ExcelPlan, UndefinedOperation


def execute_plan(input_file: str, output_file: str, plan: ExcelPlan) -> None:
    """Выполняет план операций над Excel-файлом.

    Args:
        input_file: Путь к входному Excel-файлу.
        output_file: Путь для сохранения результата.
        plan: План операций для выполнения.
    """
    print(f"\n[EXECUTOR] План: {plan.summary}")
    print(f"[EXECUTOR] Операций: {len(plan.operations)}")

    current_file: str = input_file
    for i, op in enumerate(plan.operations):
        name: str = op.operation
        print(f"[EXECUTOR] Операция {i + 1}/{len(plan.operations)}: {name}")

        if isinstance(op, UndefinedOperation):
            op.execute(current_file, output_file)
            continue

        op.execute(current_file, output_file)
        current_file = output_file

    print(f"[EXECUTOR] Готово: {output_file}")
