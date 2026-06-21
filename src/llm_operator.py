"""Обёртка над llama.cpp для работы с локальными LLM-моделями."""

from llama_cpp import Llama, LlamaGrammar


class LLMOperator:
    """Класс для взаимодействия с локальной LLM через llama.cpp."""

    def __init__(self, model_path: str) -> None:
        """Загружает LLM-модель из файла .gguf."""
        print("Loading model...")
        self.llm = Llama(
            model_path=model_path,
            n_ctx=8192,
            n_threads=6,
            n_threads_batch=6,
            n_batch=1024,
            n_gpu_layers=0,
            use_mmap=True,
            use_mlock=False,
            verbose=False,
            logits_all=False,
            embedding=False,
        )
        print("Model loaded.\n")

    def ask_llm(
        self,
        prompt: str,
        temperature: float = 0.3,
        top_p=0.9,
        top_k=50,
        max_tokens: int = 4096,
        grammar: LlamaGrammar | None = None,
    ) -> str:
        """Отправляет промпт модели и возвращает ответ."""
        kwargs: dict = {
            "messages": [{"role": "user", "content": prompt}],
            "temperature": temperature,
            "top_p": top_p,
            "top_k": top_k,
            "max_tokens": max_tokens,
            "stream": True,
        }
        if grammar is not None:
            kwargs["grammar"] = grammar
        chunks: list[str] = []
        for chunk in self.llm.create_chat_completion(**kwargs):
            delta: dict = chunk["choices"][0]["delta"]
            if "content" in delta and delta["content"]:
                print(delta["content"], end="", flush=True)
                chunks.append(delta["content"])
        print()
        return "".join(chunks)


