import json
import ollama

from tools.promt import SYSTEM_PROMPT_SUPPORT as SYSTEM_PROMPT


class MiniCommandModel:
    def __init__(self, model: str = "qwen3:0.6b"):
        self.model = model

    def generate(self, user_text: str) -> str:
        prompt = f"{SYSTEM_PROMPT}\nЗапрос: {user_text}\nОтвет:"

        try:
            response = ollama.generate(
                model=self.model,
                prompt=prompt,
                options={
                    "temperature": 0.0,
                    "top_p": 1.0,
                }
            )
            raw = response["response"].strip()

            if "]" in raw:
                raw = raw[: raw.rfind("]") + 1].strip()
            return raw

        except Exception as e:
            print("[MiniCommandModel] Ollama error:", e)
            return "[]"

    def warmup(self):
        """
        Прогрев мини-модели, чтобы избежать задержки на первом запросе.
        """
        try:
            ollama.generate(
                model=self.model,
                prompt=f"{SYSTEM_PROMPT}\nЗапрос: ping\nОтвет:",
                stream=False,
                options={
                    "temperature": 0.0,
                    "top_p": 1.0,
                    "num_predict": 8,
                },
            )
        except Exception as e:
            print("[MiniCommandModel] Warmup error:", e)
