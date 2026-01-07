import json
import logging
import threading
from typing import Callable

from core.actions import execute_actions
from core.intent_router import detect_intents_llm
from core.tts import SileroTTSStreamer
from tools.utilits import normalize_execution_results

logger = logging.getLogger(__name__)


class Agent:
    def __init__(
            self,
            mini_model=None,
            llm=None,
            tts: SileroTTSStreamer | None = None,
            tts_factory: Callable[[], SileroTTSStreamer] | None = None,
    ):
        self.mini_model = mini_model
        self.llm = llm
        self.tts = tts
        self._tts_factory = tts_factory

        self.tts_enabled = True
        self.history: list[tuple[str, str]] = []
        self._history_limit = 10

    def enable_tts(self):
        self.tts_enabled = True
        self._ensure_tts()
        if self.tts:
            self.tts.unmute()

    def disable_tts(self):
        self.tts_enabled = False
        if self.tts:
            self.tts.mute()

    def stop_tts(self):
        if self.tts:
            self.tts.close(wait=False)

    def cancel_generation(self):
        """Запрос на отмену текущего запроса: глушим TTS и просим LLM остановиться."""
        self.stop_tts()
        for llm_obj in (self.llm, self.mini_model):
            cancel = getattr(llm_obj, "cancel", None)
            if callable(cancel):
                try:
                    cancel()
                except Exception as e:
                    logger.warning("Cancel request failed: %s", e)

    def handle_stream(self, user_input: str, cancel_event: threading.Event | None = None):
        intents = detect_intents_llm(user_input, llm=self.mini_model, cancel_event=cancel_event)
        if cancel_event and cancel_event.is_set():
            self.stop_tts()
            return

        speak = getattr(self, "tts_enabled", True)
        if speak:
            self._ensure_tts()
        speak = bool(self.tts and speak)
        if speak:
            self.tts.unmute()
        else:
            self.stop_tts()

        response_buf: list[str] = []
        if intents:
            execution_results = execute_actions(intents)
            extra = (
                "Ответь как Вика: живо и по делу.\n"
                "Не повторяй строки/абзацы. Не используй '1) 2) 3)' и 'Основной результат'.\n"
                "Если есть get_events — выведи 'Ваши планы на неделю: ...' и список по датам.\n"
                "Если есть add_remind — подтвердить: что именно и на какую дату/время.\n"
                "Юмор — максимум одна короткая фраза в конце, по желанию.\n"
                "Результаты (JSON):\n"
                "```json\n"
                f"{json.dumps(normalize_execution_results(execution_results), ensure_ascii=False, indent=2)}\n"
                "```\n"
            )
            prompt = self._build_prompt(
                user_input,
                extra=extra,
            )

            for chunk in self.llm.generate(prompt, stop_event=cancel_event):
                if cancel_event and cancel_event.is_set():
                    break
                if speak:
                    self.tts.push(chunk)
                response_buf.append(chunk)
                yield chunk

        else:
            prompt = self._build_prompt(user_input)
            for chunk in self.llm.generate(prompt, stop_event=cancel_event):
                if cancel_event and cancel_event.is_set():
                    break
                if speak:
                    self.tts.push(chunk)
                response_buf.append(chunk)
                yield chunk

        if self.tts:
            should_wait = speak and not (cancel_event and cancel_event.is_set())
            self.tts.close(wait=should_wait)

        if response_buf and not (cancel_event and cancel_event.is_set()):
            assistant_reply = "".join(response_buf).strip()
            if assistant_reply:
                self.history.append((user_input, assistant_reply))
                if len(self.history) > self._history_limit:
                    self.history = self.history[-self._history_limit:]

    def _build_prompt(self, user_input: str, extra: str | None = None) -> str:
        history_parts = []
        for u, a in self.history[-self._history_limit:]:
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

    def _ensure_tts(self):
        if self.tts or not self._tts_factory:
            return
        try:
            self.tts = self._tts_factory()
        except Exception as e:
            logger.error("Failed to initialize TTS: %s", e)

    def reset_history(self):
        self.history.clear()
