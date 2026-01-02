from __future__ import annotations

import io
import wave
from typing import Optional

import numpy as np
import requests
import sounddevice as sd


DEFAULT_GIGAAM_URL = "https://gigachat.devices.sberbank.ru/api/v1/speech:recognize"


class VoiceRecorder:
    """Простой рекордер через sounddevice, возвращает WAV-байты."""

    def __init__(self, sample_rate: int = 16000, channels: int = 1, dtype: str = "int16"):
        self.sample_rate = sample_rate
        self.channels = channels
        self.dtype = dtype
        self._frames: list[np.ndarray] = []
        self._stream: sd.InputStream | None = None

    @property
    def is_recording(self) -> bool:
        return self._stream is not None

    def _callback(self, indata, frames, time, status):  # noqa: ARG002
        self._frames.append(indata.copy())

    def start(self):
        if self._stream:
            return
        self._frames = []
        self._stream = sd.InputStream(
            samplerate=self.sample_rate,
            channels=self.channels,
            dtype=self.dtype,
            callback=self._callback,
        )
        self._stream.start()

    def stop(self) -> tuple[bytes, int]:
        if not self._stream:
            return b"", self.sample_rate

        self._stream.stop()
        self._stream.close()
        self._stream = None

        if not self._frames:
            return b"", self.sample_rate

        data = np.concatenate(self._frames, axis=0)
        buff = io.BytesIO()
        with wave.open(buff, "wb") as wf:
            wf.setnchannels(self.channels)
            wf.setsampwidth(2)  # int16
            wf.setframerate(self.sample_rate)
            wf.writeframes(data.tobytes())

        return buff.getvalue(), self.sample_rate


class GigaAMRecognizer:
    """HTTP-клиент для GigaAM ASR. Требует токен и endpoint."""

    def __init__(self, api_key: str, url: str = DEFAULT_GIGAAM_URL, language: str = "ru"):
        if not api_key:
            raise ValueError("GigaAM API key is required")

        self.api_key = api_key
        self.url = url
        self.language = language
        self.session = requests.Session()

    @classmethod
    def from_env(cls, env: dict[str, str]) -> Optional["GigaAMRecognizer"]:
        token = env.get("GIGAAM_TOKEN", "").strip()
        url = env.get("GIGAAM_URL", DEFAULT_GIGAAM_URL).strip()
        if not token:
            return None
        return cls(api_key=token, url=url)

    def transcribe(self, wav_bytes: bytes, sample_rate: int) -> str:
        if not wav_bytes:
            return ""

        headers = {
            "Authorization": f"Bearer {self.api_key}",
        }
        files = {
            "file": ("speech.wav", wav_bytes, "audio/wav"),
        }
        data = {"language": self.language, "sample_rate": str(sample_rate)}

        resp = self.session.post(self.url, headers=headers, data=data, files=files, timeout=60)
        resp.raise_for_status()

        try:
            payload = resp.json()
        except Exception:
            return resp.text.strip()

        for key in ("text", "result", "transcript"):
            if key in payload and payload[key]:
                return str(payload[key]).strip()
        return ""
