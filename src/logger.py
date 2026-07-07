"""Логгер для перенаправления вывода программы в файлы."""

import os
import sys
from datetime import datetime


class Logger:
    """Перехватывает весь stdout/stderr и пишет в файл в папке logs/."""

    def __init__(self, input_file: str) -> None:
        """
        Args:
            input_file: Путь к входному файлу. Имя файла используется в имени лога.
        """
        base_name = os.path.splitext(os.path.basename(input_file))[0]
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        log_name = f"{base_name}_{timestamp}.txt"

        logs_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "logs")
        os.makedirs(logs_dir, exist_ok=True)

        self.log_path = os.path.join(logs_dir, log_name)
        self._log_file = open(self.log_path, "w", encoding="utf-8")
        self._original_stdout = sys.stdout
        self._original_stderr = sys.stderr

    def start(self) -> None:
        """Начинает перехват вывода."""
        sys.stdout = self
        sys.stderr = self

    def stop(self) -> None:
        """Останавливает перехват и восстанавливает оригинальный вывод."""
        sys.stdout = self._original_stdout
        sys.stderr = self._original_stderr
        self._log_file.close()

    def write(self, text: str) -> None:
        """Пишет текст и в файл, и в оригинальный stdout."""
        self._log_file.write(text)
        self._log_file.flush()
        self._original_stdout.write(text)

    def flush(self) -> None:
        self._log_file.flush()
