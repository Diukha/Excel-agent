from llama_cpp import Llama

MODEL_PATH = "models/model.gguf"

llm = Llama(
    model_path=MODEL_PATH,
    n_ctx=2048,
    n_threads=4,
    verbose=False
)


def ask_llm(prompt: str) -> str:
    response = llm.create_chat_completion(
        messages=[
            {"role": "user", "content": prompt}
        ],
        temperature=0.7,
        max_tokens=200
    )

    return response["choices"][0]["message"]["content"]


if __name__ == "__main__":
    print(ask_llm("Скажи привет одним предложением"))