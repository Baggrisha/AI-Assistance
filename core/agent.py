from core.intent_router import detect_intents_llm
from core.actions import execute_actions
from core.tts import SileroTTSStreamer


class Agent:
    def __init__(self, mini_model=None, llm=None, tts: SileroTTSStreamer | None = None):
        self.mini_model = mini_model
        self.llm = llm
        self.tts = tts

        # озвучка по умолчанию включена, но управляется GUI через tts_enabled
        self.tts_enabled = True

    def enable_tts(self):
        self.tts_enabled = True
        if self.tts:
            self.tts.unmute()

    def disable_tts(self):
        self.tts_enabled = False
        if self.tts:
            self.tts.mute()

    def stop_tts(self):
        if self.tts:
            self.tts.close(wait=False)

    def handle_stream(self, user_input: str):
        intents = detect_intents_llm(user_input, llm=self.mini_model)

        speak = bool(self.tts and getattr(self, "tts_enabled", True))
        if speak:
            self.tts.unmute()
        else:
            self.stop_tts()

        if intents:
            execution_results = execute_actions(intents)
            prompt = (
                f"Ты выполнил комманду(-ы), теперь придумай ответ, "
                f"вот резульататы её выполнения {execution_results}."
                f"Кратко напиши что ты сделал или  какой результат получил и добавь пару коментариев"
            )

            for chunk in self.llm.generate(prompt):
                if speak:
                    self.tts.push(chunk)
                yield chunk

        else:
            for chunk in self.llm.generate(user_input):
                if speak:
                    self.tts.push(chunk)
                yield chunk

        if self.tts:
            self.tts.close(wait=speak)
