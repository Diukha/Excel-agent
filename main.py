import argparse
import json
import re
import sys
from pathlib import Path
from typing import Literal, TypedDict

from langgraph.graph import END, START, StateGraph
from llama_cpp import Llama

from code_executor import execute_code, extract_python_code
from excel_analyzer import analyze_excel
from output_validator import validate_excel_output
import prompt_storage


MAX_RETRIES = 3
DEFAULT_MODEL_PATH = "models/model.gguf"


class AgentState(TypedDict):
    user_query: str
    input_file: str
    output_file: str
    json_data: str
    prompt_text: str
    generated_code: str
    execution_stdout: str
    execution_error: str
    success: bool
    retry_count: int


class ExcelAgent:
    def __init__(self, llm_model: Llama, max_retries: int = MAX_RETRIES):
        self.llm = llm_model
        self.max_retries = max_retries
        self.app = self._build_graph()

    def _build_graph(self):
        workflow = StateGraph(AgentState)

        workflow.add_node("analyze_excel", self.analyze_excel_node)
        workflow.add_node("prepare_prompt", self.prepare_prompt)
        workflow.add_node("generate_code", self.generate_code)
        workflow.add_node("execute_code", self.execute_code_node)
        workflow.add_node("evaluate", self.evaluate)

        workflow.add_edge(START, "analyze_excel")
        workflow.add_edge("analyze_excel", "prepare_prompt")
        workflow.add_edge("prepare_prompt", "generate_code")
        workflow.add_edge("generate_code", "execute_code")
        workflow.add_edge("execute_code", "evaluate")
        workflow.add_conditional_edges(
            "evaluate",
            self._route_after_evaluate,
            {"retry": "prepare_prompt", "finish": END},
        )

        return workflow.compile()

    def ask_llm(self, prompt: str) -> str:
        print("[LLM] Запрос к модели...")
        response = self.llm.create_chat_completion(
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
            max_tokens=4096,
        )
        return response["choices"][0]["message"]["content"]

    def analyze_excel_node(self, state: AgentState):
        print(f"[1/5] Анализ Excel: {state['input_file']}")
        analysis = analyze_excel(state["input_file"])
        json_data = json.dumps(analysis, ensure_ascii=False, indent=2)
        return {"json_data": json_data}

    def prepare_prompt(self, state: AgentState):
        print("[2/5] Подготовка промпта...")

        if state["retry_count"] > 0 and state.get("generated_code") and state.get("execution_error"):
            combined_prompt = (
                prompt_storage.PROMPT_CODE_FIX.format(
                    error=state["execution_error"],
                    previous_code=extract_python_code(state["generated_code"]),
                )
                + f"\n\nСтруктура Excel (JSON):\n{state['json_data']}\n\n"
                f"Запрос пользователя: {state['user_query']}\n\n"
                f"INPUT_FILE = {state['input_file']!r}\n"
                f"OUTPUT_FILE = {state['output_file']!r}\n"
            )
        else:
            combined_prompt = (
                f"{prompt_storage.PROMPT_CODE_WRITER}\n\n"
                f"Структура Excel (JSON):\n{state['json_data']}\n\n"
                f"Запрос пользователя: {state['user_query']}\n\n"
                f"INPUT_FILE = {state['input_file']!r}\n"
                f"OUTPUT_FILE = {state['output_file']!r}\n\n"
                f"Напиши код:"
            )

        return {"prompt_text": combined_prompt}

    def generate_code(self, state: AgentState):
        attempt = state["retry_count"] + 1
        print(f"[3/5] Генерация кода (попытка {attempt})...")
        raw_code = self.ask_llm(state["prompt_text"])
        return {"generated_code": raw_code}

    def execute_code_node(self, state: AgentState):
        print("[4/5] Выполнение кода в песочнице...")
        result = execute_code(
            code=state["generated_code"],
            input_file=state["input_file"],
            output_file=state["output_file"],
        )

        if result.success:
            validation_issues = validate_excel_output(
                state["output_file"],
                state["user_query"],
            )
            if validation_issues:
                combined_error = "\n".join(f"- {issue}" for issue in validation_issues)
                print(f"[4/5] Результат не прошёл проверку:\n{combined_error}")
                return {
                    "execution_stdout": result.stdout,
                    "execution_error": combined_error,
                    "success": False,
                }

        return {
            "execution_stdout": result.stdout,
            "execution_error": result.error,
            "success": result.success,
        }

    def evaluate(self, state: AgentState):
        if state["success"]:
            print(f"[5/5] Успех. Результат: {state['output_file']}")
            return {}

        new_retry = state["retry_count"] + 1
        print(f"[5/5] Ошибка (попытка {new_retry}/{self.max_retries}): {state['execution_error']}")
        return {"retry_count": new_retry}

    def _route_after_evaluate(self, state: AgentState) -> Literal["retry", "finish"]:
        if state["success"]:
            return "finish"
        if state["retry_count"] >= self.max_retries:
            print("Достигнут лимит попыток.")
            return "finish"
        return "retry"

    def run(self, user_query: str, input_file: str, output_file: str) -> AgentState:
        initial_state: AgentState = {
            "user_query": user_query,
            "input_file": input_file,
            "output_file": output_file,
            "json_data": "",
            "prompt_text": "",
            "generated_code": "",
            "execution_stdout": "",
            "execution_error": "",
            "success": False,
            "retry_count": 0,
        }

        return self.app.invoke(initial_state)


def parse_args():
    parser = argparse.ArgumentParser(
        description="Локальный агент для обработки Excel-отчётов на русском языке.",
    )
    parser.add_argument(
        "query",
        nargs="?",
        default=(
            "Возьми data.xlsx, столбцы 'Выручка' и 'Расходы', посчитай прибыль, "
            "если она отрицательная — выдели красным, сделай столбчатую диаграмму, "
            "сохрани результат."
        ),
        help="Задача на русском языке",
    )
    parser.add_argument("--input", "-i", help="Путь к исходному .xlsx")
    parser.add_argument("--output", "-o", help="Путь для сохранения результата")
    parser.add_argument("--model", "-m", default=DEFAULT_MODEL_PATH, help="Путь к .gguf модели")
    parser.add_argument("--retries", type=int, default=MAX_RETRIES, help="Макс. число попыток")
    return parser.parse_args()


def find_xlsx_paths(text: str) -> list[str]:
    """Ищет упоминания .xlsx в тексте запроса."""
    return re.findall(r"[\w\u0400-\u04FF\-]+\.xlsx", text, flags=re.IGNORECASE)


def resolve_io_paths(user_query: str, input_file: str | None, output_file: str | None) -> tuple[str, str]:
    """Определяет входной и выходной файлы из аргументов или текста запроса."""
    if input_file:
        resolved_input = str(Path(input_file).resolve())
    else:
        matches = find_xlsx_paths(user_query)
        if not matches:
            raise ValueError(
                "Не найден Excel-файл. Укажите --input или упомяните файл вида report.xlsx в запросе."
            )
        resolved_input = str(Path(matches[0]).resolve())

    if output_file:
        resolved_output = str(Path(output_file).resolve())
    else:
        matches = find_xlsx_paths(user_query)
        if len(matches) >= 2:
            resolved_output = str(Path(matches[1]).resolve())
        else:
            stem = Path(resolved_input).stem
            resolved_output = str(Path(resolved_input).with_name(f"итог_{stem}.xlsx"))

    if not Path(resolved_input).exists():
        raise FileNotFoundError(f"Входной файл не найден: {resolved_input}")

    return resolved_input, resolved_output


def main():
    args = parse_args()

    try:
        input_file, output_file = resolve_io_paths(args.query, args.input, args.output)
    except (ValueError, FileNotFoundError) as exc:
        print(f"Ошибка: {exc}", file=sys.stderr)
        sys.exit(1)

    model_path = Path(args.model)
    if not model_path.exists():
        print(f"Модель не найдена: {model_path}", file=sys.stderr)
        print("Положите .gguf файл в папку models/ и укажите путь через --model", file=sys.stderr)
        sys.exit(1)

    print("Загрузка модели...")
    llm = Llama(
        model_path=str(model_path),
        n_ctx=8192,
        n_threads=6,
        n_batch=512,
        use_mmap=True,
        use_mlock=False,
        verbose=False,
    )
    print("Модель загружена.\n")

    print("--- ЗАДАЧА ---")
    print(args.query)
    print(f"Вход:  {input_file}")
    print(f"Выход: {output_file}\n")

    agent = ExcelAgent(llm_model=llm, max_retries=args.retries)
    result = agent.run(user_query=args.query, input_file=input_file, output_file=output_file)

    print("\n--- СГЕНЕРИРОВАННЫЙ КОД ---")
    print(result["generated_code"])

    if result["success"]:
        print(f"\nГотово: {output_file}")
        if result["execution_stdout"]:
            print(result["execution_stdout"])
        sys.exit(0)

    print(f"\nНе удалось выполнить задачу: {result['execution_error']}", file=sys.stderr)
    sys.exit(1)


if __name__ == "__main__":
    main()
