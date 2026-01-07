import queue
import re
import subprocess
import threading
import time

import sounddevice as sd
import torch

_END_RE = re.compile(r"[.!?…]+(\s|$)|\n+")


def _get_output_volume() -> int | None:
    try:
        out = subprocess.check_output(
            ["osascript", "-e", "output volume of (get volume settings)"],
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
        return int(float(out))
    except Exception:
        return None


def _set_output_volume(vol: int) -> None:
    try:
        vol = max(0, min(int(vol), 100))
        subprocess.run(
            ["osascript", "-e", f"set volume output volume {vol}"],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except Exception:
        pass


class VolumeDucker:
    """Best-effort системный дакинг: опускаем громкость macOS и восстанавливаем после."""

    def __init__(self, target_volume: int = 20):
        self.target_volume = max(0, min(int(target_volume), 100))
        self._original: int | None = None
        self._lock = threading.Lock()

    def duck(self):
        with self._lock:
            if self._original is not None:
                return
            cur = _get_output_volume()
            if cur is None:
                return
            if cur <= self.target_volume:
                self._original = cur
                return
            self._original = cur
            _set_output_volume(self.target_volume)

    def restore(self):
        with self._lock:
            if self._original is None:
                return
            _set_output_volume(self._original)
            self._original = None


class SileroTTSStreamer:
    def __init__(
            self,
            speaker: str = "kseniya",
            sample_rate: int = 48000,
            min_chars: int = 10,
            debug: bool = False,
            auto_flush_sec: float = 1.5,
            block_output: bool = True,
            duck_other_audio: bool = True,
            duck_volume: int = 20,
    ):
        self.speaker = speaker
        self.sample_rate = sample_rate
        self.min_chars = min_chars
        self.debug = debug
        self.auto_flush_sec = auto_flush_sec
        self.block_output = block_output
        self._duck = VolumeDucker(target_volume=duck_volume) if duck_other_audio else None
        self._ducked = False

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

            if self._duck and not self._ducked:
                self._duck.duck()
                self._ducked = True

            audio = self.model.apply_tts(
                text=text,
                speaker=self.speaker,
                sample_rate=self.sample_rate,
            )

            sd.play(audio, self.sample_rate)
            if self.block_output:
                sd.wait()
            self._q.task_done()

    def _auto_flush_loop(self):
        while not self._stop.is_set():
            time.sleep(0.2)
            if self._buf and (time.time() - self._last_push) >= self.auto_flush_sec:
                self._flush_internal()

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
                break

    def _flush_internal(self):
        tail = " ".join(self._buf.split()).strip()
        self._buf = ""
        if tail and len(tail) >= self.min_chars:
            self._q.put(tail)

    def flush(self):
        self._flush_internal()

    def interrupt(self):
        try:
            sd.stop()
        except Exception:
            pass

        self._buf = ""
        while True:
            try:
                self._q.get_nowait()
            except queue.Empty:
                break
            finally:
                try:
                    self._q.task_done()
                except ValueError:
                    pass
        if self._ducked and self._duck:
            self._duck.restore()
            self._ducked = False

    def mute(self):
        self._muted = True
        self.interrupt()

    def unmute(self):
        self._muted = False

    def close(self, wait: bool = True):
        if wait:
            self.flush()
            self._q.join()
        else:
            self.interrupt()
        if self._ducked and self._duck:
            self._duck.restore()
            self._ducked = False

    def shutdown(self):
        self._shutdown.set()
        self._stop.set()
        self.flush()
        self._q.put(None)
        try:
            self._q.join()
        except Exception:
            pass
        if self._ducked and self._duck:
            self._duck.restore()
            self._ducked = False
