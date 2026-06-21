"""Основной агент для обработки Excel-файлов."""

import json
from typing import TypedDict
from langgraph.graph import START, StateGraph
from llama_cpp import LlamaGrammar
from excel_analyzer import analyze_excel
from pydantic_templates import (
    OperationSelection,
    TemplateTaskDecomposition,
    OPERATION_CLASSES,
    OPERATION_MAP,
)
from llm_operator import LLMOperator


# ---------------------------------------------------------------------------
# Промпты
# ---------------------------------------------------------------------------

DECOMPOSE_TASK_PROMPT = (
    "Разбей задачу пользователя на отдельные действия.\n",
    "\n",
    "Правила:\n",
    "- Каждое действие — отдельный шаг\n",
    "- Формулируй кратко и конкретно: что делаем + над чем\n",
    "- Указывай имена столбцов как они есть в таблице\n",
    "- Не объединяй разные операции в один шаг\n",
    "- Действий может быть несколько\n",
    "- От тебя ждут массив действий\n",
    "- Оперируй словами, а не математическими выражениями\n",
    "- Пиши только слова, знаки препинания и цифры\n",
    "\n",
    "Примеры хорошего разбиения:\n",
    'Задача: "Посчитай прибыль и сделай диаграмму" →\n',
    '[{{"step":1,"action":"Вычесть A из B, результат в новый столбец C"}},'
    '{{"step":2,"action":"Создать столбчатую диаграмму по столбцу D"}}]\n',
    "\n",
    'Задача: "Сделай круговую диаграмму состава инвестиционного портфеля" →\n',
    '[{{"step":1,"action":"Создать круговую диаграмму: Доли акций в портфеле"}}]\n',
    "\n",
    "Задача: {user_query}\n",
    "\n",
    "Структура таблицы (сжатый формат):\n",
    "Справочник колонок: Буква Excel|Имя столбца\n",
    'compressed_text показывает значения ячеек в формате "значение|ячейка" '
    '(например, 7500|B1 означает значение 7500 в ячейке B1).\n',
    "\n",
    "{excel_structure}",
)

EXCEL_STRUCTURE_BLOCK = (
    "Структура Excel (сжатый формат):\n",
    "Справочник колонок: имя столбца → буква Excel.\n",
    'compressed_text показывает значения ячеек в формате "значение|ячейка" '
    '(например, 7500|B1 означает значение 7500 в ячейке B1).\n',
    "\n",
    "{excel_structure}\n",
)

SELECT_SINGLE_OPERATION_PROMPT = (
    "Выбери одну операцию для выполнения подзадачи.\n",
    "\n",
    "Доступные операции (формат: имя|описание|аргументы):\n",
    "{operations_text}\n",
    "\n",
    "Подзадача:\n",
    "{subtask}\n",
    "\n",
    "Структура таблицы:\n",
    "{excel_structure}\n",
    "\n",
    "Выбери подходящую операцию из списка выше.\n",
    'Верни JSON только с полем "operation" — именем операции точно как в списке.\n',
)

GENERATE_SINGLE_PLAN_PROMPT = (
    *EXCEL_STRUCTURE_BLOCK,
    "\n",
    "Задача пользователя:\n",
    "{user_query}\n",
    "\n",
    "Подзадача:\n",
    "{subtask}\n",
    "\n",
    "Тип операции: {operation_type}\n",
    "\n",
    "Заполни аргументы для этой операции, используя данные из таблицы.\n",
    'Каждая операция содержит поле "operation" (тип) и поле "args" (параметры).\n',
    "\n",
    "{use_case}\n",
)



class AgentState(TypedDict):
    """Состояние агента в пайплайне LangGraph."""

    user_query: str
    input_file: str
    output_file: str
    excel_structure: str
    subtasks: str
    subtask_list: list[str]
    execution_error: str
    success: bool


class ExcelAgent:
    """Агент для обработки Excel-файлов."""

    def __init__(self, llm_operator: LLMOperator) -> None:
        """Инициализирует агента с LLM."""
        self.llm_op = llm_operator
        self.app = self._build_graph()

    def _build_graph(self) -> StateGraph:
        """Строит граф пайплайна LangGraph."""
        workflow = StateGraph(AgentState)
        workflow.add_node("analyze_excel", self.analyze_excel)
        workflow.add_node("decompose_task", self.decompose_task)
        workflow.add_node("process_subtasks", self.process_subtasks)

        workflow.add_edge(START, "analyze_excel")
        workflow.add_edge("analyze_excel", "decompose_task")
        workflow.add_edge("decompose_task", "process_subtasks")

        return workflow.compile()

    def analyze_excel(self, state: AgentState) -> dict:
        """Анализирует структуру Excel-файла."""
        print(f"\n[AGENT] Анализирую структуру Excel: {state['input_file']}\n\n")
        structure_str = analyze_excel(state["input_file"])
        print(f"[AGENT] Структура таблицы:\n\n{structure_str}\n\n")
        return {"excel_structure": structure_str}

    def decompose_task(self, state: AgentState) -> dict:
        """Разбивает задачу пользователя на отдельные подзадачи."""
        print("\n[AGENT] Разбиваю задачу на подзадачи...\n")

        schema = TemplateTaskDecomposition.model_json_schema()
        grammar = LlamaGrammar.from_json_schema(json.dumps(schema))

        prompt = "".join(DECOMPOSE_TASK_PROMPT).format(
            user_query=state["user_query"],
            excel_structure=state["excel_structure"],
        )

        print(f"\n[AGENT] === PROMPT (decompose_task) ===\n\n{prompt}\n\n[AGENT] === END PROMPT ===\n")

        raw = self.llm_op.ask_llm(
            prompt=prompt,
            temperature=0.0,
            max_tokens=4096,
            grammar=grammar,
        )

        decomposition = TemplateTaskDecomposition(**json.loads(raw))

        steps_str = "\n".join(f"  {s.step}. {s.action}" for s in decomposition.steps)
        subtask_list = [s.action for s in decomposition.steps]
        print(f"\n[AGENT] Подзадачи:\n{steps_str}\n")
        return {"subtasks": steps_str, "subtask_list": subtask_list}

    def _build_operations_text(self) -> str:
        """Формирует текстовый список доступных операций."""
        lines = []
        for cls in OPERATION_CLASSES:
            name = cls.__name__
            desc = cls.model_fields["DESCRIPTION"].default
            args_names = ", ".join(cls.Args.model_fields.keys())
            lines.append(f"{name}|{desc}|{args_names}")
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Пошаговое исполнение: select → fill → execute → re-analyze → repeat
    # ------------------------------------------------------------------

    def select_operation_template(self, subtask: str, excel_structure: str) -> str:
        """Выбирает одну операцию для подзадачи."""
        operations_text = self._build_operations_text()

        schema = OperationSelection.model_json_schema()
        grammar = LlamaGrammar.from_json_schema(json.dumps(schema))

        prompt = "".join(SELECT_SINGLE_OPERATION_PROMPT).format(
            operations_text=operations_text,
            subtask=subtask,
            excel_structure=excel_structure,
        )

        print(f"\n[AGENT] === PROMPT (select_operation_template) ===\n\n{prompt}\n\n[AGENT] === END PROMPT ===\n")

        raw = self.llm_op.ask_llm(
            prompt=prompt,
            temperature=0.0,
            max_tokens=4096,
            grammar=grammar,
        )

        selection = OperationSelection(**json.loads(raw))
        print(f"[AGENT]   → Выбрана операция: {selection.operation}")
        return selection.operation

    def fill_operation_template(self, subtask: str, operation_type: str, excel_structure: str) -> dict:
        """Заполняет аргументы для одной операции."""
        op_cls = OPERATION_MAP.get(operation_type)
        if op_cls is None:
            raise ValueError(f"Неизвестная операция: {operation_type}")

        schema = op_cls.model_json_schema()
        grammar = LlamaGrammar.from_json_schema(json.dumps(schema))

        use_case = op_cls.model_fields["USE_CASE"].default

        prompt = "".join(GENERATE_SINGLE_PLAN_PROMPT).format(
            excel_structure=excel_structure,
            user_query="",
            subtask=subtask,
            operation_type=operation_type,
            use_case=use_case,
        )

        print(f"\n[AGENT] === PROMPT (fill_operation_template) ===\n\n{prompt}\n\n[AGENT] === END PROMPT ===\n")

        raw = self.llm_op.ask_llm(
            prompt=prompt,
            temperature=0.0,
            max_tokens=4096,
            grammar=grammar,
        )

        parsed = json.loads(raw)
        op_instance = op_cls.parse_args(parsed)
        print(f"[AGENT]   → Аргументы заполнены:\n {op_instance.model_dump_json(indent=2)[:300]}...")
        return op_instance

    def execute_operation(self, input_file: str, output_file: str, operation) -> None:
        """Выполняет одну операцию. Копирует input → output только при первом вызове."""
        import shutil
        import os

        if not os.path.exists(output_file):
            shutil.copy2(input_file, output_file)

        print(f"[AGENT] Выполняю операцию: {operation.operation}")
        operation.execute(output_file, output_file)

    def process_subtasks(self, state: AgentState) -> dict:
        """Пошагово обрабатывает каждую подзадачу: select → fill → execute → re-analyze."""
        print("\n[AGENT] Пошаговое исполнение подзадач...\n")

        subtask_list = state["subtask_list"]
        input_file = state["input_file"]
        output_file = state["output_file"]
        excel_structure = state["excel_structure"]

        for i, subtask in enumerate(subtask_list, 1):
            print(f"\n[AGENT] ===== Подзадача {i}/{len(subtask_list)}: {subtask} =====\n")

            try:
                operation_type = self.select_operation_template(subtask, excel_structure)
                operation = self.fill_operation_template(subtask, operation_type, excel_structure)
                self.execute_operation(input_file, output_file, operation)

                print(f"\n[AGENT] Подзадача {i} выполнена. Пересчитываю структуру таблицы...\n")
                excel_structure = analyze_excel(output_file)
                print(f"[AGENT] Новая структура:\n{excel_structure}\n")

            except Exception as e:
                print(f"\n[AGENT] ОШИБКА на подзадаче {i}: {e}\n")
                import traceback
                traceback.print_exc()
                return {"execution_error": str(e), "success": False}

        print("\n[AGENT] Все подзадачи выполнены успешно.\n")
        return {"success": True}

    def run(self, user_query: str, input_file: str, output_file: str) -> AgentState:
        """Запускает полный пайплайн обработки Excel-файла."""
        initial_state: AgentState = {
            "user_query": user_query,
            "input_file": input_file,
            "output_file": output_file,
            "excel_structure": "",
            "subtasks": "",
            "subtask_list": [],
            "execution_error": "",
            "success": False
        }
        return self.app.invoke(initial_state)
