from llama_cpp import Llama
from excel_analyzer import analyze_excel

MODEL_PATH = "models/model.gguf"

llm = Llama(
    model_path=MODEL_PATH,
    n_ctx=2048,
    n_threads=6,
    n_batch=256,
    use_mmap=True,
    use_mlock=False,
    verbose=False
)

def ask_llm():
    metadata = analyze_excel("data/input.xlsx")

    prompt = f"""
        Преобразуй данные в валидный JSON.

        Ответ должен содержать только JSON.

        Данные:
        {metadata}
    """

    response = llm.create_chat_completion(
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2,
        max_tokens=512
    )

    return response["choices"][0]["message"]["content"]

if __name__ == "__main__":
    result = ask_llm()
    print("\nМОДЕЛЬ ЗАГРУЖЕНА\n")
    print("\nОТВЕТ МОДЕЛИ\n", result)