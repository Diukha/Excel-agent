"""Основной агент для обработки Excel-файлов.

Использует LangGraph для построения пайплайна из пяти шагов:
1. Анализ структуры Excel
2. Декомпозиция задачи на подзадачи
3. Поиск операций с помощью эмбеддингов
4. Генерация плана с аргументами через LLM
5. Исполнение плана
"""

import json
from typing import NotRequired, TypedDict
from langgraph.graph import START, StateGraph
from llama_cpp import LlamaGrammar
from excel_analyzer import analyze_excel
from result_excel_plan_generator import generate_excel_plan
from plan_executor import execute_plan
from operation_embedder import OperationEmbedder
from pydantic_templates import ExcelPlan, TemplateTaskDecomposition
from llm_operator import LLMOperator


class AgentState(TypedDict):
    """Состояние агента в пайплайне LangGraph."""

    user_query: str
    input_file: str
    output_file: str
    excel_structure: str
    subtasks: str
    generated_plan: NotRequired[ExcelPlan]
    execution_error: str
    success: bool


class ExcelAgent:
    """Основной агент для обработки Excel-файлов.

    Управляет пайплайном из пяти шагов, используя LangGraph
    для координации между ними.
    """

    def __init__(self, llm_operator: LLMOperator, embedder: OperationEmbedder) -> None:
        """Инициализирует агента с LLM и эмбеддером.

        Args:
            llm_operator: Экземпляр LLMOperator для работы с моделью.
            embedder: Экземпляр OperationEmbedder для поиска операций.
        """
        self.llm_op = llm_operator
        self.embedder = embedder
        self.app = self._build_graph()

    def resolve_operation(self, text: str) -> str:
        """Находит операцию для заданного текста с помощью эмбеддингов.

        Args:
            text: Текстовое описание задачи.

        Returns:
            Имя найденной операции.
        """
        return self.embedder.find_operation(text)

    def _build_graph(self) -> StateGraph:
        """Строит граф пайплайна LangGraph.

        Returns:
            Скомпилированный граф с пятью шагами обработки.
        """
        workflow = StateGraph(AgentState)
        workflow.add_node("analyze_excel", self.analyze_excel)
        workflow.add_node("decompose_task", self.decompose_task)
        workflow.add_node("find_operations", self.find_operations)
        workflow.add_node("generate_plan", self.generate_plan)
        workflow.add_node("execute_plan", self.execute_plan_node)

        workflow.add_edge(START, "analyze_excel")
        workflow.add_edge("analyze_excel", "decompose_task")
        workflow.add_edge("decompose_task", "find_operations")
        workflow.add_edge("find_operations", "generate_plan")
        workflow.add_edge("generate_plan", "execute_plan")

        return workflow.compile()

    def analyze_excel(self, state: AgentState) -> dict:
        """Анализирует структуру Excel-файла.

        Args:
            state: Текущее состояние агента.

        Returns:
            Словарь с обновлённым полем excel_structure.
        """
        print(f"\n[AGENT] Анализирую структуру Excel: {state['input_file']}")
        analysis = analyze_excel(state["input_file"])
        structure_str = json.dumps(analysis, ensure_ascii=False, indent=2)
        print(f"[AGENT] Структура таблицы:\n{structure_str}")
        return {"excel_structure": structure_str}

    def decompose_task(self, state: AgentState) -> dict:
        """Разбивает задачу пользователя на отдельные подзадачи.

        Args:
            state: Текущее состояние агента.

        Returns:
            Словарь с обновлённым полем subtasks.
        """
        print("\n[AGENT] Разбиваю задачу на подзадачи...")

        schema = TemplateTaskDecomposition.model_json_schema()
        grammar = LlamaGrammar.from_json_schema(json.dumps(schema))

        prompt = f"""Разбей задачу пользователя на отдельные действия.

                    Правила:
                    - Каждое действие — отдельный шаг
                    - Формулируй кратко и конкретно: что делаем + над чем
                    - Указывай имена столбцов как они есть в таблице
                    - Не объединяй разные операции в один шаг
                    - Действий может быть несколько
                    - От тебя ждут массив действий
                    - Оперируй словами, а не математическими выражениями
                    - Пиши только слова, знаки препинания и цифры

                    Примеры хорошего разбиения:
                    Задача: "Посчитай прибыль и сделай диаграмму" →
                    [{{"step":1,"action":"Вычесть A из B, результат в новый столбец C"}},{{"step":2,"action":"Создать столбчатую диаграмму по столбцу D"}}]

                    Задача: "Сделай круговую диаграмму состава инвестиционного портфеля" →
                    [{{"step":1,"action":"Создать круговую диаграмму: Доли акций в портфеле"}}]

                    Задача: {state['user_query']}

                    Структура таблицы: {state['excel_structure']}"""

        raw = self.llm_op.ask_llm(
            prompt=prompt,
            temperature=0.0,
            max_tokens=8192,
            grammar=grammar,
        )

        decomposition = TemplateTaskDecomposition(**json.loads(raw))

        steps_str = "\n".join(f"  {s.step}. {s.action}" for s in decomposition.steps)
        print(f"[AGENT] Подзадачи:\n{steps_str}")
        return {"subtasks": steps_str}

    def find_operations(self, state: AgentState) -> dict:
        """Ищет операции для каждой подзадачи с помощью эмбеддингов.

        Args:
            state: Текущее состояние агента.

        Returns:
            Словарь с обновлённым полем generated_plan (пустые аргументы).
        """
        print("\n[AGENT] Ищу операции для каждой подзадачи...")
        from pydantic_templates import (
            BarChartOperation,
            PieChartOperation,
            ArithmeticOperation,
            UndefinedOperation,
        )

        subtasks = state["subtasks"]
        operations = []

        for line in subtasks.strip().split("\n"):
            line = line.strip()
            if not line:
                continue

            action_text = line.split(".", 1)[-1].strip() if "." in line else line
            op_name = self.resolve_operation(action_text)
            print(f"[AGENT] Подзадача: '{action_text}' → операция: {op_name}")

            if op_name == "СТОЛБЧАТАЯ_ДИАГРАММА":
                op = BarChartOperation(operation="СТОЛБЧАТАЯ_ДИАГРАММА", args={"title": "", "data_columns": [], "label_column": {"name": "", "excel_column": ""}, "output_sheet": "Диаграмма"})
            elif op_name == "КРУГОВАЯ_ДИАГРАММА":
                op = PieChartOperation(operation="КРУГОВАЯ_ДИАГРАММА", args={"title": "", "data_column": {"name": "", "excel_column": ""}, "label_column": {"name": "", "excel_column": ""}, "output_sheet": "Диаграмма"})
            elif op_name == "АРИФМЕТИКА":
                op = ArithmeticOperation(operation="АРИФМЕТИКА", args={"operation_type": "СЛОЖЕНИЕ", "operand1": {"name": "", "excel_column": ""}, "operand2": {"name": "", "excel_column": ""}, "result_column_name": "", "result_column_letter": "", "output_sheet": ""})
            else:
                op = UndefinedOperation(operation="НЕ_ОПРЕДЕЛЕНО", args={"reason": "Операция не определена"})

            operations.append(op)

        plan = ExcelPlan(operations=operations, summary="")
        print(f"[AGENT] Найдено операций: {len(operations)}")
        return {"generated_plan": plan}

    def generate_plan(self, state: AgentState) -> dict:
        """Генерирует план с заполненными аргументами операций через LLM.

        Args:
            state: Текущее состояние агента.

        Returns:
            Словарь с обновлённым полем generated_plan или execution_error.
        """
        print("\n[AGENT] Генерирую план действий через LLM (Structured Output)...")
        try:
            plan = generate_excel_plan(self.llm_op, state["subtasks"], state["excel_structure"], state["generated_plan"])
            plan_json = plan.model_dump_json(indent=2)
            print(f"[AGENT] Сгенерированный план (JSON):\n{plan_json}")
            print(f"[AGENT] План: {plan.summary}")

            if any(op.operation == "НЕ_ОПРЕДЕЛЕНО" for op in plan.operations):
                undefined_op = next(op for op in plan.operations if op.operation == "НЕ_ОПРЕДЕЛЕНО")
                return {
                    "execution_error": f"ОШИБКА: {undefined_op.reason}",
                    "success": False
                }

            return {"generated_plan": plan, "success": True}
        except Exception as e:
            return {"execution_error": str(e), "success": False}

    def execute_plan_node(self, state: AgentState) -> dict:
        """Выполняет сгенерированный план.

        Args:
            state: Текущее состояние агента.

        Returns:
            Словарь с результатом выполнения (success или execution_error).
        """
        if not state.get("success"):
            print(f"[AGENT] Выполнение прервано. Причина: {state.get('execution_error')}")
            return state

        print("\n[AGENT] Передаю план в детерминированный исполнитель...")
        print(f"[AGENT] Файл ввода: {state['input_file']}")
        print(f"[AGENT] Файл вывода: {state['output_file']}")
        try:
            execute_plan(state["input_file"], state["output_file"], state["generated_plan"])
            print("[AGENT] Исполнение завершено успешно.")
            return {"success": True}
        except Exception as e:
            print(f"[AGENT] ОШИБКА при исполнении: {e}")
            import traceback
            traceback.print_exc()
            return {"execution_error": str(e), "success": False}

    def run(self, user_query: str, input_file: str, output_file: str) -> AgentState:
        """Запускает полный пайплайн обработки Excel-файла.

        Args:
            user_query: Задача пользователя на естественном языке.
            input_file: Путь к входному Excel-файлу.
            output_file: Путь для сохранения результата.

        Returns:
            Финальное состояние агента после выполнения пайплайна.
        """
        initial_state: AgentState = {
            "user_query": user_query,
            "input_file": input_file,
            "output_file": output_file,
            "excel_structure": "",
            "subtasks": "",
            "execution_error": "",
            "success": False
        }
        return self.app.invoke(initial_state)
