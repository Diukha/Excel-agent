"""Основной агент для обработки Excel-файлов."""

import json
from typing import NotRequired, TypedDict
from langgraph.graph import START, StateGraph
from llama_cpp import LlamaGrammar
from excel_analyzer import analyze_excel
from plan_executor import execute_plan
from pydantic_templates import (
    ExcelPlan,
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

OPERATIONS_EXAMPLES = (
    "Доступные операции:\n",
    'СТОЛБЧАТАЯ_ДИАГРАММА: {{"operation":"СТОЛБЧАТАЯ_ДИАГРАММА","args":{{"title":"...","data_columns":[{{"name":"...","excel_column":"X"}},{{"name":"...","excel_column":"Y"}}],"label_column":{{"name":"...","excel_column":"Z"}},"output_sheet":"Диаграмма"}}}}\n',
    'КРУГОВАЯ_ДИАГРАММА: {{"operation":"КРУГОВАЯ_ДИАГРАММА","args":{{"title":"...","data_column":{{"name":"...","excel_column":"X"}},"label_column":{{"name":"...","excel_column":"Y"}},"output_sheet":"Диаграмма"}}}}\n',
    'АРИФМЕТИКА: {{"operation":"АРИФМЕТИКА","args":{{"operation_type":"СЛОЖЕНИЕ|ВЫЧИТАНИЕ|УМНОЖЕНИЕ|ДЕЛЕНИЕ","operand1":{{"name":"...","excel_column":"X"}},"operand2":{{"name":"...","excel_column":"Y"}},"result_column_name":"...","result_column_letter":"E","output_sheet":""}}}}\n',
    'УСЛОВНОЕ_ФОРМАТИРОВАНИЕ: {{"operation":"УСЛОВНОЕ_ФОРМАТИРОВАНИЕ","args":{{"target_column":{{"name":"...","excel_column":"X"}},"operator":"БОЛЬШЕ|МЕНЬШЕ|РАВНО|НЕ_РАВНО|БОЛЬШЕ_ИЛИ_РАВНО|МЕНЬШЕ_ИЛИ_РАВНО","value":100,"fill_color":"00FF00","font_color":"FFFFFF"}}}}\n',
    'НЕ_ОПРЕДЕЛЕНО: {{"operation":"НЕ_ОПРЕДЕЛЕНО","args":{{"reason":"..."}}}}\n',
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
    *OPERATIONS_EXAMPLES,
)



class AgentState(TypedDict):
    """Состояние агента в пайплайне LangGraph."""

    user_query: str
    input_file: str
    output_file: str
    excel_structure: str
    subtasks: str
    subtask_list: list[str]
    selected_operations: NotRequired[list[dict]]
    generated_plan: NotRequired[ExcelPlan]
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
        workflow.add_node("select_operations", self.select_operations)
        workflow.add_node("generate_plan", self.generate_plan)
        workflow.add_node("execute_plan", self.execute_plan_node)

        workflow.add_edge(START, "analyze_excel")
        workflow.add_edge("analyze_excel", "decompose_task")
        workflow.add_edge("decompose_task", "select_operations")
        workflow.add_edge("select_operations", "generate_plan")
        workflow.add_edge("generate_plan", "execute_plan")

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

    def select_operations(self, state: AgentState) -> dict:
        """Выбирает операции для подзадач — по одной операции за вызов LLM."""
        print("\n[AGENT] Выбираю операции для каждой подзадачи (пошагово)...\n")

        operations_text = self._build_operations_text()
        subtask_list = state["subtask_list"]

        schema = OperationSelection.model_json_schema()
        grammar = LlamaGrammar.from_json_schema(json.dumps(schema))

        selected_ops: list[dict] = []

        for i, subtask in enumerate(subtask_list, 1):
            print(f"[AGENT] --- Подзадача {i}/{len(subtask_list)}: {subtask}")

            prompt = "".join(SELECT_SINGLE_OPERATION_PROMPT).format(
                operations_text=operations_text,
                subtask=subtask,
                excel_structure=state["excel_structure"],
            )

            print(f"\n[AGENT] === PROMPT (select_operation step {i}) ===\n\n{prompt}\n\n[AGENT] === END PROMPT ===\n")

            raw = self.llm_op.ask_llm(
                prompt=prompt,
                temperature=0.0,
                max_tokens=4096,
                grammar=grammar,
            )

            selection = OperationSelection(**json.loads(raw))
            print(f"[AGENT]   → Выбрана операция: {selection.operation}")
            selected_ops.append({
                "subtask": subtask,
                "operation": selection.operation,
            })

        print(f"\n[AGENT] Все операции выбраны: {[o['operation'] for o in selected_ops]}\n")
        return {"selected_operations": selected_ops}

    def generate_plan(self, state: AgentState) -> dict:
        """Генерирует план — заполняет аргументы для каждой операции по отдельности."""
        print("\n[AGENT] Заполняю аргументы операций (пошагово)...\n")
        try:
            selected_ops = state["selected_operations"]
            filled_operations = []

            for i, op_info in enumerate(selected_ops, 1):
                op_name = op_info["operation"]
                subtask = op_info["subtask"]
                print(f"[AGENT] --- Операция {i}/{len(selected_ops)}: {op_name} для подзадачи: {subtask}")

                op_cls = OPERATION_MAP.get(op_name)
                if op_cls is None:
                    print(f"[AGENT]   → Неизвестная операция '{op_name}', пропускаю")
                    continue

                schema = op_cls.model_json_schema()
                grammar = LlamaGrammar.from_json_schema(json.dumps(schema))

                prompt = "".join(GENERATE_SINGLE_PLAN_PROMPT).format(
                    excel_structure=state["excel_structure"],
                    user_query=state["user_query"],
                    subtask=subtask,
                    operation_type=op_name,
                )

                print(f"\n[AGENT] === PROMPT (generate_plan step {i}) ===\n\n{prompt}\n\n[AGENT] === END PROMPT ===\n")

                raw = self.llm_op.ask_llm(
                    prompt=prompt,
                    temperature=0.0,
                    max_tokens=4096,
                    grammar=grammar,
                )

                parsed = json.loads(raw)
                op_instance = op_cls.parse_args(parsed)
                filled_operations.append(op_instance)
                print(f"[AGENT]   → Аргументы заполнены:\n {op_instance.model_dump_json(indent=2)[:200]}...")

            plan = ExcelPlan(operations=filled_operations, summary="План сформирован пошагово")
            plan_json = plan.model_dump_json(indent=2)
            print(f"\n[AGENT] Сгенерированный план (JSON):\n{plan_json}\n")

            return {"generated_plan": plan, "success": True}
        except Exception as e:
            return {"execution_error": str(e), "success": False}

    def execute_plan_node(self, state: AgentState) -> dict:
        """Выполняет сгенерированный план."""
        if not state.get("success"):
            print(f"\n[AGENT] Выполнение прервано. Причина: {state.get('execution_error')}\n")
            return state

        print("\n[AGENT] Передаю план в детерминированный исполнитель...\n")
        print(f"[AGENT] Файл ввода: {state['input_file']}")
        print(f"[AGENT] Файл вывода: {state['output_file']}")
        try:
            execute_plan(state["input_file"], state["output_file"], state["generated_plan"])
            print("\n[AGENT] Исполнение завершено успешно.\n")
            return {"success": True}
        except Exception as e:
            print(f"\n[AGENT] ОШИБКА при исполнении: {e}\n")
            import traceback
            traceback.print_exc()
            return {"execution_error": str(e), "success": False}

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
