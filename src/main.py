"""Точка входа для Excel-агента.

Обрабатывает аргументы командной строки, загружает модели
и запускает пайплайн обработки Excel-файла.
"""

import argparse
import re
import sys
from pathlib import Path
from llm_operator import LLMOperator
from excel_agent import ExcelAgent

DEFAULT_MODEL_PATH = "C:\\Users\\y9798\\Downloads\\qwen3-4b-instruct-2507.Q4_K_M.gguf"


def parse_args() -> argparse.Namespace:
    """Парсит аргументы командной строки.

    Returns:
        Объект Namespace с аргументами.
    """
    parser = argparse.ArgumentParser(description="Local agent for processing Excel reports.")
    parser.add_argument(
        "query",
        nargs="?",
        default=(
            "Take data.xlsx, columns 'Revenue' and 'Expenses', calculate profit, "
            "if it is negative - highlight it in red, create a bar chart, "
            "and save the result."
        ),
        help="Task description",
    )
    parser.add_argument("--input", "-i", help="Path to the input .xlsx file")
    parser.add_argument("--output", "-o", help="Path to save the output file")
    parser.add_argument("--model", "-m", default=DEFAULT_MODEL_PATH, help="Path to the .gguf model")
    return parser.parse_args()


def find_xlsx_paths(text: str) -> list[str]:
    """Находит пути к Excel-файлам в тексте.

    Args:
        text: Текст для поиска.

    Returns:
        Список найденных путей к .xlsx файлам.
    """
    return re.findall(r"[\w\u0400-\u04FF\-]+\.xlsx", text, flags=re.IGNORECASE)


def resolve_io_paths(
    user_query: str, input_file: str | None, output_file: str | None
) -> tuple[str, str]:
    """Определяет пути к входному и выходному файлам.

    Args:
        user_query: Задача пользователя (может содержать имена файлов).
        input_file: Путь к входному файлу (если задан).
        output_file: Путь к выходному файлу (если задан).

    Returns:
        Кортеж (input_path, output_path).

    Raises:
        ValueError: Если файл не найден в запросе и не задан через --input.
        FileNotFoundError: Если входной файл не существует.
    """
    if input_file:
        resolved_input = str(Path(input_file).resolve())
    else:
        matches = find_xlsx_paths(user_query)
        if not matches:
            raise ValueError("Excel file not found. Specify --input or mention a file like report.xlsx in the query.")
        resolved_input = str(Path(matches[0]).resolve())

    if output_file:
        resolved_output = str(Path(output_file).resolve())
    else:
        matches = find_xlsx_paths(user_query)
        if len(matches) >= 2:
            resolved_output = str(Path(matches[1]).resolve())
        else:
            stem = Path(resolved_input).stem
            resolved_output = str(Path(resolved_input).with_name(f"result_{stem}.xlsx"))

    if not Path(resolved_input).exists():
        raise FileNotFoundError(f"Input file not found: {resolved_input}")

    return resolved_input, resolved_output


def main() -> None:
    """Основная функция запуска Excel-агента.

    Загружает модели, обрабатывает аргументы и запускает пайплайн.
    """
    args = parse_args()

    try:
        input_file, output_file = resolve_io_paths(args.query, args.input, args.output)
    except (ValueError, FileNotFoundError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)

    model_path = Path(args.model)
    if not model_path.exists():
        print(f"Model not found: {model_path}", file=sys.stderr)
        print("Place the .gguf file in the models/ folder and specify the path via --model", file=sys.stderr)
        sys.exit(1)

    llm_op = LLMOperator(model_path=str(model_path))

    print("--- TASK ---")
    print(args.query)
    print(f"Input:  {input_file}")
    print(f"Output: {output_file}\n")

    agent = ExcelAgent(llm_operator=llm_op)
    agent.run(user_query=args.query, input_file=input_file, output_file=output_file)


if __name__ == "__main__":
    main()
