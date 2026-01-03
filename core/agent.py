from core.intent_router import detect_intents_llm
from core.actions import execute_actions
from core.tts import SileroTTSStreamer


class Agent:
    def __init__(self, mini_model=None, llm=None, tts: SileroTTSStreamer | None = None):
        self.mini_model = mini_model
        self.llm = llm
        self.tts = tts

        self.tts_enabled = True
        self.history: list[tuple[str, str]] = []
        self._history_limit = 10

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

        response_buf: list[str] = []
        if intents:
            execution_results = execute_actions(intents)
            prompt = self._build_prompt(
                user_input,
                extra=f"Ты выполнила команды, вот результаты: {execution_results}. Кратко опиши, что сделала и что получилось.",
            )

            for chunk in self.llm.generate(prompt):
                if speak:
                    self.tts.push(chunk)
                response_buf.append(chunk)
                yield chunk

        else:
            prompt = self._build_prompt(user_input)
            for chunk in self.llm.generate(prompt):
                if speak:
                    self.tts.push(chunk)
                response_buf.append(chunk)
                yield chunk

        if self.tts:
            self.tts.close(wait=speak)

        if response_buf:
            assistant_reply = "".join(response_buf).strip()
            if assistant_reply:
                self.history.append((user_input, assistant_reply))
                if len(self.history) > self._history_limit:
                    self.history = self.history[-self._history_limit :]

    def _build_prompt(self, user_input: str, extra: str | None = None) -> str:
        history_parts = []
        for u, a in self.history[-self._history_limit :]:
            history_parts.append(f"Пользователь: {u}\nВика: {a}")
        history_block = "\n\n".join(history_parts)

        parts = []
        if history_block:
            parts.append(f"История диалога:\n{history_block}")
        parts.append(f"Текущий запрос: {user_input}")
        if extra:
            parts.append(extra)
        parts.append("Ответ:")
        return "\n\n".join(parts)
