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
