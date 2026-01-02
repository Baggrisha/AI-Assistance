# core/tts_stream.py
import re
import queue
import threading
import time

import torch
import sounddevice as sd

_END_RE = re.compile(r"[.!?…]+(\s|$)|\n+")


class SileroTTSStreamer:
    def __init__(
        self,
        speaker: str = "kseniya",
        sample_rate: int = 24000,
        min_chars: int = 25,
        debug: bool = False,
        auto_flush_sec: float = 0.8,  # быстрее начинаем говорить
    ):
        self.speaker = speaker
        self.sample_rate = sample_rate
        self.min_chars = min_chars
        self.debug = debug
        self.auto_flush_sec = auto_flush_sec

        self.model, _ = torch.hub.load(
            repo_or_dir="snakers4/silero-models",
            model="silero_tts",
            language="ru",
            speaker="v3_1_ru",
        )

        self._buf = ""
        self._last_push = time.time()

        self._q: "queue.Queue[str | None]" = queue.Queue()
        self._stop = threading.Event()
        self._muted = False
        self._shutdown = threading.Event()

        self._worker = threading.Thread(target=self._run, daemon=True)
        self._worker.start()

        self._ticker = threading.Thread(target=self._auto_flush_loop, daemon=True)
        self._ticker.start()

    def _run(self):
        while not self._shutdown.is_set():
            text = self._q.get()
            if text is None:
                self._q.task_done()
                break

            text = text.strip()
            if not text:
                self._q.task_done()
                continue

            if self._muted:
                self._q.task_done()
                continue

            audio = self.model.apply_tts(
                text=text,
                speaker=self.speaker,
                sample_rate=self.sample_rate,
            )

            sd.play(audio, self.sample_rate)
            sd.wait()
            self._q.task_done()

    def _auto_flush_loop(self):
        while not self._stop.is_set():
            time.sleep(0.2)
            if self._buf and (time.time() - self._last_push) >= self.auto_flush_sec:
                # если долго нет конца предложения — скажем что накопили
                self._flush_internal(reason="auto")

    def push(self, chunk: str):
        if not chunk or self._shutdown.is_set():
            return

        if self._muted:
            return

        self._buf += chunk
        self._last_push = time.time()
        while True:
            m = _END_RE.search(self._buf)
            if not m:
                break

            end = m.end()
            phrase = self._buf[:end]
            rest = self._buf[end:]

            normalized = " ".join(phrase.split())
            if len(normalized) >= self.min_chars:
                self._q.put(normalized)
                self._buf = rest
            else:
                # коротко — копим дальше
                break

        # избегаем озвучки по слогам: без точки ждём автофлаша

    def _flush_internal(self, reason="manual"):
        tail = " ".join(self._buf.split()).strip()
        self._buf = ""
        if tail and len(tail) >= self.min_chars:
            self._q.put(tail)

    def flush(self):
        self._flush_internal(reason="manual")

    def interrupt(self):
        """Останавливает текущую озвучку и очищает очередь."""
        try:
            sd.stop()
        except Exception:
            pass

        self._buf = ""
        while True:
            try:
                item = self._q.get_nowait()
            except queue.Empty:
                break
            finally:
                try:
                    self._q.task_done()
                except ValueError:
                    # если join не вызывался, task_done может бросить ошибку
                    pass

    def mute(self):
        self._muted = True
        self.interrupt()

    def unmute(self):
        self._muted = False

    def close(self, wait: bool = True):
        # close теперь используется как "дождаться окончания" или мгновенно оборвать
        if wait:
            self.flush()
            self._q.join()
        else:
            self.interrupt()

    def shutdown(self):
        self._shutdown.set()
        self._stop.set()
        self.flush()
        self._q.put(None)
        try:
            self._q.join()
        except Exception:
            pass
