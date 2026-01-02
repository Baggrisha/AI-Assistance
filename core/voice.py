from __future__ import annotations

import io
import wave
from typing import Optional

import numpy as np
import sounddevice as sd
import torch
from transformers import AutoModelForSpeechSeq2Seq, AutoProcessor, pipeline


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


class HFWhisperRecognizer:
    """ASR через Hugging Face pipeline (модели Hugging Face)."""

    def __init__(
        self,
        model_id: str = "ai-sage/GigaAM-v3",
        device: str = "cpu",
        language: str = "ru",
    ):
        self.model_id = model_id
        self.device = device
        self.language = language

        dtype = torch.float16 if torch.cuda.is_available() and device != "cpu" else torch.float32

        self.processor = AutoProcessor.from_pretrained(self.model_id, trust_remote_code=True)
        self.model = AutoModelForSpeechSeq2Seq.from_pretrained(
            self.model_id,
            trust_remote_code=True,
            torch_dtype=dtype,
        )

        if device != "cpu":
            self.model = self.model.to(device)

        self.pipe = pipeline(
            "automatic-speech-recognition",
            model=self.model,
            tokenizer=getattr(self.processor, "tokenizer", self.processor),
            feature_extractor=getattr(self.processor, "feature_extractor", self.processor),
            chunk_length_s=30,
            device=self.device,
            dtype=dtype,
            trust_remote_code=True,
        )

    @classmethod
    def from_env(cls, env: dict[str, str]) -> Optional["HFWhisperRecognizer"]:
        model = env.get("HF_ASR_MODEL", "").strip() or "ai-sage/GigaAM-v3"
        device = env.get("HF_ASR_DEVICE", "").strip() or ("cuda" if torch.cuda.is_available() else "cpu")
        return cls(model_id=model, device=device)

    def transcribe(self, wav_bytes: bytes, sample_rate: int) -> str:
        if not wav_bytes:
            return ""

        audio = {"array": np.frombuffer(wav_bytes, dtype=np.int16).astype(np.float32) / 32768.0, "sampling_rate": sample_rate}
        result = self.pipe(audio, generate_kwargs={"language": self.language})
        text = result.get("text") if isinstance(result, dict) else None
        return text.strip() if text else ""
