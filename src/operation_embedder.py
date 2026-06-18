"""Эмбеддинговый поиск операций для обработки Excel-файлов.

Использует FAISS и sentence-transformers для семантического поиска
наиболее подходящей операции по текстовому описанию.
"""

import numpy as np
import faiss
from sentence_transformers import SentenceTransformer
from operations_storage import OPERATIONS


class OperationEmbedder:
    """Класс для поиска операций с помощью эмбеддингов.

    Загружает модель sentence-transformers, строит FAISS-индекс
    по описаниям операций и находит наиболее подходящую операцию
    для заданного текстового запроса.
    """

    def __init__(self, model_name: str) -> None:
        """Инициализирует эмбеддер и строит индекс операций.

        Args:
            model_name: Путь или имя модели sentence-transformers.
        """
        self.model = SentenceTransformer(model_name)
        self.names: list[str] = list(OPERATIONS.keys())
        self.descriptions: list[str] = list(OPERATIONS.values())
        self.index: faiss.IndexFlatIP = self._build_index()

    def _build_index(self) -> faiss.IndexFlatIP:
        """Строит FAISS-индекс по эмбеддингам описаний операций.

        Returns:
            Индекс FAISS с косинусным сходством.
        """
        embeddings = self.model.encode(self.descriptions, normalize_embeddings=True)
        dim: int = embeddings.shape[1]
        index: faiss.IndexFlatIP = faiss.IndexFlatIP(dim)
        index.add(embeddings.astype(np.float32))
        return index

    def find_operation(self, query: str) -> str:
        """Находит наиболее подходящую операцию для запроса.

        Args:
            query: Текстовое описание задачи пользователя.

        Returns:
            Имя найденной операции (например, "АРИФМЕТИКА").
        """
        q_emb = self.model.encode([query], normalize_embeddings=True).astype(np.float32)
        _, idx = self.index.search(q_emb, 1)
        return self.names[idx[0][0]]
