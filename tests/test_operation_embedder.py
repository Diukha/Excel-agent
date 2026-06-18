"""Тесты для модуля operation_embedder."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from operation_embedder import OperationEmbedder

EMBEDDING_MODEL_PATH = "models/paraphrase-multilingual-MiniLM-L12-v2"


def test_embedder() -> None:
    """Тестирует поиск операций с помощью эмбеддингов."""
    embedder = OperationEmbedder(model_name=EMBEDDING_MODEL_PATH)

    request1 = "Вычесть Расходы из Выручки для каждой строки, результат в столбце Прибыль"
    request2 = "Создать столбчатую диаграмму по столбцу Мероприятия"
    request3 = "Создать круговую диаграмму по столбцу Мероприятия"
    request4 = "Сделай мне бутерброд с колбасой"

    expected1 = "АРИФМЕТИКА"
    expected2 = "СТОЛБЧАТАЯ_ДИАГРАММА"
    expected3 = "КРУГОВАЯ_ДИАГРАММА"
    expected4 = "НЕ_ОПРЕДЕЛЕНО"

    result1 = embedder.find_operation(request1)
    result2 = embedder.find_operation(request2)
    result3 = embedder.find_operation(request3)
    result4 = embedder.find_operation(request4)

    tests = [
        (request1, result1, expected1),
        (request2, result2, expected2),
        (request3, result3, expected3),
        (request4, result4, expected4),
    ]

    passed = 0
    for i, (req, got, exp) in enumerate(tests, 1):
        status = "OK" if got == exp else "FAIL"
        if status == "OK":
            passed += 1
        print(f"  Test {i}: {status}")
        print(f"    Query:    {req}")
        print(f"    Expected: {exp}")
        print(f"    Got:      {got}")

    print(f"\nResults: {passed}/{len(tests)} passed")
    return passed == len(tests)


if __name__ == "__main__":
    test_embedder()
