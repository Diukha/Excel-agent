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
from output_validator import OutputValidator
import prompt_storage


MAX_RETRIES = 3
# DEFAULT_MODEL_PATH = "C:\\Users\\y9798\\Downloads\\gemma-4-E4B-it-UD-IQ3_XXS.gguf"
DEFAULT_MODEL_PATH = "models/model.gguf"

class AgentState(TypedDict):
    user_query: str
    input_file: str
    output_file: str
    json_data: str          
    refined_query: str      
    pseudocode: str         
    generated_code: str     
    execution_error: str    
    success: bool           
    retry_count: int        


class ExcelAgent:
    def __init__(self, llm_model: Llama, max_retries: int = MAX_RETRIES):
        self.llm = llm_model
        self.max_retries = max_retries
        self.validator = OutputValidator(llm_model)
        self.app = self._build_graph()

    def _build_graph(self):
        workflow = StateGraph(AgentState)

        workflow.add_node("analyze_excel", self.analyze_excel_node)
        workflow.add_node("prepare_prompt", self.prepare_prompt_node)
        workflow.add_node("generate_pseudocode", self.generate_pseudocode_node)
        workflow.add_node("generate_code", self.generate_code_node)
        workflow.add_node("execute_code", self.execute_code_node)
        workflow.add_node("fix_code", self.fix_code_node)

        workflow.add_edge(START, "analyze_excel")
        workflow.add_edge("analyze_excel", "prepare_prompt")
        workflow.add_edge("prepare_prompt", "generate_pseudocode")
        workflow.add_edge("generate_pseudocode", "generate_code")
        workflow.add_edge("generate_code", "execute_code")
        
        workflow.add_conditional_edges(
            "execute_code",
            self._route_after_execute,
            {"retry": "fix_code", "finish": END},
        )
        workflow.add_edge("fix_code", "execute_code")

        return workflow.compile()

    def ask_llm(self, prompt: str) -> str:
        print("[LLM] Streaming response in real-time:")
        response_chunks = self.llm.create_chat_completion(
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
            max_tokens=4096,
            stream=True,
        )
        
        full_response = []
        for chunk in response_chunks:
            delta = chunk["choices"][0]["delta"]
            if "content" in delta:
                token = delta["content"]
                print(token, end="", flush=True)
                full_response.append(token)
                
        print("\n[LLM] Generation finished.\n")
        return "".join(full_response)

    def analyze_excel_node(self, state: AgentState):
        print(f"[1/6] Analyzing Excel structure (Script): {state['input_file']}")
        analysis = analyze_excel(state["input_file"])
        json_data = json.dumps(analysis, ensure_ascii=False, indent=2)
        print(f"```json\n{json_data}\n```\n")
        return {"json_data": json_data}

    def prepare_prompt_node(self, state: AgentState):
        print("[2/6] Refining user requirements (Model)...")
        prompt = (
            f"{prompt_storage.PROMPT_PREPARE_QUERY}\n\n"
            f"Excel Structure (JSON):\n{state['json_data']}\n\n"
            f"User Query: {state['user_query']}"
        )
        refined_query = self.ask_llm(prompt)
        return {"refined_query": refined_query}

    def generate_pseudocode_node(self, state: AgentState):
        print("[3/6] Creating openpyxl architectural pseudocode (Model)...")
        prompt = (
            f"{prompt_storage.PROMPT_PSEUDOCODE_GENERATION}\n\n"
            f"Excel Structure (JSON):\n{state['json_data']}\n\n"
            f"Requirements:\n{state['refined_query']}"
        )
        pseudocode = self.ask_llm(prompt)
        return {"pseudocode": pseudocode}

    def generate_code_node(self, state: AgentState):
        print("[4/6] Initial code generation based on Requirements and Pseudocode (Model)...")
        prompt = (
            f"{prompt_storage.PROMPT_CODE_GENERATION}\n\n"
            f"EXCEL STRUCTURE (JSON):\n{state['json_data']}\n\n"
            f"TECHNICAL SPECIFICATION:\n{state['refined_query']}\n\n"
            f"ALGORITHM LOGIC (PSEUDOCODE):\n{state['pseudocode']}\n\n"
            f"INPUT_FILE = {state['input_file']!r}\n"
            f"OUTPUT_FILE = {state['output_file']!r}\n"
        )
        raw_code = self.ask_llm(prompt)
        return {"generated_code": raw_code}

    def execute_code_node(self, state: AgentState):
        attempt = state["retry_count"] + 1
        print(f"[5/6] Executing code in sandbox (Attempt {attempt})...")
        
        pure_code = extract_python_code(state["generated_code"])
        result = execute_code(
            code=pure_code,
            input_file=state["input_file"],
            output_file=state["output_file"],
        )
        
        if not result.success:
            print(f"[5/6] Code execution failed with an error.")
            state["execution_error"] = result.error
            print(state["execution_error"], "\n")
            return {"execution_error": result.error, "success": False}

        if not Path(state["output_file"]).exists():
            print("[5/6] Error: Code executed successfully, but the output file was not created.")
            return {"execution_error": "The output file was not physically created on disk.", "success": False}

        issues = self.validator.validate_output(
            state["output_file"], state["refined_query"]
        )
        if issues:
            issues_text = "\n".join(f"- {issue}" for issue in issues)
            print(f"[5/6] Execution result does not match requirements:\n{issues_text}")
            return {"execution_error": f"Output file created, but there are issues:\n{issues_text}", "success": False}

        print(f"[5/6] Execution successful! File saved.")
        return {"success": True, "execution_error": ""}

    def fix_code_node(self, state: AgentState):
        print(f"[6/6] Fixing code based on error (Model)...")
        pure_code = extract_python_code(state["generated_code"])
        
        prompt = (
            f"{prompt_storage.PROMPT_CODE_FIX}\n\n"
            f"REQUIREMENTS (TS):\n{state['refined_query']}\n\n"
            f"FILE PATHS:\n"
            f"INPUT_FILE = {state['input_file']!r}\n"
            f"OUTPUT_FILE = {state['output_file']!r}\n\n"
            f"PREVIOUS GENERATED CODE:\n```python\n{pure_code}\n```\n\n"
            f"EXECUTION RESULT (ERROR OR FAILURE):\n{state['execution_error']}\n\n"
            f"INSTRUCTION:\n"
            f"Fix the error in the code. Do not use constructs that cause failures like len(wb). "
            f"Output ONLY the fixed working code inside a ```python block without any extra text."
        )
        
        fixed_code = self.ask_llm(prompt)
        return {
            "generated_code": fixed_code,
            "retry_count": state["retry_count"] + 1
        }

    def _route_after_execute(self, state: AgentState) -> Literal["retry", "finish"]:
        if state["success"]:
            return "finish"
        if state["retry_count"] >= self.max_retries:
            print("Maximum code fix retries reached.")
            return "finish"
        return "retry"

    def run(self, user_query: str, input_file: str, output_file: str) -> AgentState:
        initial_state: AgentState = {
            "user_query": user_query,
            "input_file": input_file,
            "output_file": output_file,
            "json_data": "",
            "refined_query": "",
            "pseudocode": "", 
            "generated_code": "",
            "execution_error": "",
            "success": False,
            "retry_count": 0,
        }
        return self.app.invoke(initial_state)


def parse_args():
    parser = argparse.ArgumentParser(
        description="Local agent for processing Excel reports.",
    )
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
    parser.add_argument("--retries", type=int, default=MAX_RETRIES, help="Maximum number of retries")
    return parser.parse_args()


def find_xlsx_paths(text: str) -> list[str]:
    return re.findall(r"[\w\u0400-\u04FF\-]+\.xlsx", text, flags=re.IGNORECASE)


def resolve_io_paths(user_query: str, input_file: str | None, output_file: str | None) -> tuple[str, str]:
    if input_file:
        resolved_input = str(Path(input_file).resolve())
    else:
        matches = find_xlsx_paths(user_query)
        if not matches:
            raise ValueError(
                "Excel file not found. Specify --input or mention a file like report.xlsx in the query."
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
            resolved_output = str(Path(resolved_input).with_name(f"result_{stem}.xlsx"))

    if not Path(resolved_input).exists():
        raise FileNotFoundError(f"Input file not found: {resolved_input}")

    return resolved_input, resolved_output


def main():
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

    print("Loading model...")
    llm = Llama(
        model_path=str(model_path),
        n_ctx=8192,
        n_threads=6,
        n_batch=512,
        use_mmap=True,
        use_mlock=False,
        verbose=False,
    )
    print("Model loaded.\n")

    print("--- TASK ---")
    print(args.query)
    print(f"Input:  {input_file}")
    print(f"Output: {output_file}\n")

    agent = ExcelAgent(llm_model=llm, max_retries=args.retries)
    result = agent.run(user_query=args.query, input_file=input_file, output_file=output_file)

    print("\n--- GENERATED CODE ---")
    print(result["generated_code"])

    if result["success"]:
        print(f"\nDone: {output_file}")
        sys.exit(0)

    print(f"\nFailed to complete the task. Last error:\n{result['execution_error']}", file=sys.stderr)
    sys.exit(1)


if __name__ == "__main__":
    main()