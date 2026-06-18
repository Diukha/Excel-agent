"""Генератор плана обработки Excel-файлов с помощью LLM.

Использует structured output с грамматикой для генерации
валидного JSON-плана на основе задачи пользователя и структуры таблицы.
"""

import json
from llama_cpp import LlamaGrammar
from pydantic_templates import ExcelPlan
from llm_operator import LLMOperator


def generate_excel_plan(
    llm_op: LLMOperator,
    user_query: str,
    excel_structure: str,
    existing_plan: ExcelPlan | None = None,
) -> ExcelPlan:
    """Генерирует план обработки Excel-файла с помощью LLM.

    Если передан existing_plan, LLM заполняет аргументы для уже
    существующих операций. Если existing_plan не передан, LLM
    создаёт план с нуля, выбирая операции и заполняя аргументы.

    Args:
        llm_op: Экземпляр LLMOperator для работы с моделью.
        user_query: Задача пользователя на естественном языке.
        excel_structure: JSON-строка со структурой Excel-файла.
        existing_plan: Опциональный план с пустыми аргументами операций.

    Returns:
        План ExcelPlan с заполненными аргументами операций.
    """
    schema = ExcelPlan.model_json_schema()
    grammar = LlamaGrammar.from_json_schema(json.dumps(schema))

    if existing_plan:
        existing_ops = [op.model_dump() for op in existing_plan.operations]
        prompt = f"""Структура Excel:\n{excel_structure}\n\n
                    Задача пользователя:\n{user_query}\n\n

                    У тебя уже есть план с операциями, но без заполненных аргументов:
                    {json.dumps(existing_ops, ensure_ascii=False, indent=2)}

                    Твоя задача - заполнить аргументы для каждой операции, используя данные из таблицы.
                    Не меняй типы операций, только заполни поля args.
                    Каждая операция содержит поле "operation" (тип) и поле "args" (параметры).
                    Доступные операции: СТОЛБЧАТАЯ_ДИАГРАММА, КРУГОВАЯ_ДИАГРАММА, АРИФМЕТИКА, НЕ_ОПРЕДЕЛЕНО.
                    СТОЛБЧАТАЯ_ДИАГРАММА: {{"operation":"СТОЛБЧАТАЯ_ДИАГРАММА","args":{{"title":"...","data_columns":[{{"name":"...","excel_column":"X"}},{{"name":"...","excel_column":"Y"}}],"label_column":{{"name":"...","excel_column":"Z"}},"output_sheet":"Диаграмма"}}}}
                    КРУГОВАЯ_ДИАГРАММА: {{"operation":"КРУГОВАЯ_ДИАГРАММА","args":{{"title":"...","data_column":{{"name":"...","excel_column":"X"}},"label_column":{{"name":"...","excel_column":"Y"}},"output_sheet":"Диаграмма"}}}}
                    АРИФМЕТИКА: {{"operation":"АРИФМЕТИКА","args":{{"operation_type":"СЛОЖЕНИЕ|ВЫЧИТАНИЕ|УМНОЖЕНИЕ|ДЕЛЕНИЕ","operand1":{{"name":"...","excel_column":"X"}},"operand2":{{"name":"...","excel_column":"Y"}},"result_column_name":"...","result_column_letter":"E","output_sheet":""}}}}
                    НЕ_ОПРЕДЕЛЕНО: {{"operation":"НЕ_ОПРЕДЕЛЕНО","args":{{"reason":"..."}}}}
                """
    else:
        prompt = f"""Структура Excel:\n{excel_structure}\n\n
                    Задача пользователя:\n{user_query}\n\n

                    Поле "operations" — это массив. Каждое отдельное действие из запроса пользователя — это отдельный элемент массива.
                    Если пользователь просит сделать несколько действий (например, посчитать что-то И сделать диаграмму) — верни несколько операций в массиве.
                    Не додумывай за пользователем, если он что-то не указал - его проблема.
                    От тебя требуется только выбрать нужную операцию и подставить данные из таблицы.
                    Каждая операция содержит поле "operation" (тип) и поле "args" (параметры).
                    Доступные операции: СТОЛБЧАТАЯ_ДИАГРАММА, КРУГОВАЯ_ДИАГРАММА, АРИФМЕТИКА, НЕ_ОПРЕДЕЛЕНО.
                    СТОЛБЧАТАЯ_ДИАГРАММА: {{"operation":"СТОЛБЧАТАЯ_ДИАГРАММА","args":{{"title":"...","data_columns":[{{"name":"...","excel_column":"X"}},{{"name":"...","excel_column":"Y"}}],"label_column":{{"name":"...","excel_column":"Z"}},"output_sheet":"Диаграмма"}}}}
                    КРУГОВАЯ_ДИАГРАММА: {{"operation":"КРУГОВАЯ_ДИАГРАММА","args":{{"title":"...","data_column":{{"name":"...","excel_column":"X"}},"label_column":{{"name":"...","excel_column":"Y"}},"output_sheet":"Диаграмма"}}}}
                    АРИФМЕТИКА: {{"operation":"АРИФМЕТИКА","args":{{"operation_type":"СЛОЖЕНИЕ|ВЫЧИТАНИЕ|УМНОЖЕНИЕ|ДЕЛЕНИЕ","operand1":{{"name":"...","excel_column":"X"}},"operand2":{{"name":"...","excel_column":"Y"}},"result_column_name":"...","result_column_letter":"E","output_sheet":""}}}}
                    НЕ_ОПРЕДЕЛЕНО: {{"operation":"НЕ_ОПРЕДЕЛЕНО","args":{{"reason":"..."}}}}
                """

    raw = llm_op.ask_llm(
        prompt=prompt,
        temperature=0.3,
        max_tokens=1024,
        grammar=grammar,
    )

    return ExcelPlan(**json.loads(raw))
