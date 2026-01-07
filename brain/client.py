import threading

import ollama

from tools.promt import SYSTEM_PROMPT_MAIN as SYSTEM_PROMPT


class LLMClient:
    def __init__(self, model: str):
        self.model = model
        self._lock = threading.Lock()
        self._current_stream = None

    def generate(self, prompt: str, stop_event: threading.Event | None = None):
        stream = ollama.generate(
            model=self.model,
            prompt=SYSTEM_PROMPT + prompt,
            stream=True
        )

        with self._lock:
            self._current_stream = stream

        try:
            for chunk in stream:
                if stop_event and stop_event.is_set():
                    break
                yield chunk["response"]
        finally:
            try:
                stream.close()
            except Exception:
                pass
            with self._lock:
                if self._current_stream is stream:
                    self._current_stream = None

    def cancel(self):
        with self._lock:
            stream = self._current_stream
        if stream is None:
            return
        try:
            stream.close()
        except Exception:
            pass

    def warmup(self):
        """
        Короткий запрос к Ollama, чтобы прогреть модель и соединение перед первым использованием.
        """
        try:
            ollama.generate(
                model=self.model,
                prompt=SYSTEM_PROMPT + "Проверка связи.",
                stream=False,
                options={
                    "temperature": 0.0,
                    "top_p": 1.0,
                    "num_predict": 8,
                },
            )
        except Exception as e:
            print("[LLMClient] Warmup error:", e)
