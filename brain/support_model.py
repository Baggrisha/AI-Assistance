import re
import ollama

from tools.promt import SYSTEM_PROMPT_SUPPORT as SYSTEM_PROMPT


class MiniCommandModel:
    def __init__(self, model: str = "qwen3:0.6b"):
        self.model = model

    def generate(self, user_text: str) -> str:
        prompt = f"{SYSTEM_PROMPT}\nПользователь: {user_text}\nJSON:"

        try:
            response = ollama.generate(
                model=self.model,
                prompt=prompt,
                options={
                    "temperature": 0.3,
                    "top_p": 0.9,
                    "num_predict": 200,
                }
            )
            raw = response["response"]
            raw = re.sub(r"```json|```", "", raw).strip()

            match = re.search(r"\[\s*\{.*?\}\s*\]", raw, re.DOTALL)
            if match:
                return match.group(0)

            return "[]"

        except Exception as e:
            print("[MiniCommandModel] Ollama error:", e)
            return "[]"
