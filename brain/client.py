import ollama

from tools.promt import SYSTEM_PROMPT_MAIN as SYSTEM_PROMPT


class LLMClient:
    def __init__(self, model: str):
        self.model = model

    def generate(self, prompt: str):
        stream = ollama.generate(
            model=self.model,
            prompt=SYSTEM_PROMPT+prompt,
            stream=True
        )

        for chunk in stream:
            yield chunk["response"]

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
