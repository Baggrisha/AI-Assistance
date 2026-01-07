from __future__ import annotations

import io
import os
import tempfile
import time
import wave
from typing import Optional

import numpy as np
import sounddevice as sd
import torch
from transformers import AutoConfig, AutoModel, AutoModelForSpeechSeq2Seq, AutoProcessor, pipeline
from transformers.utils import cached_file


class VoiceRecorder:
    """Простой рекордер через sounddevice, возвращает WAV-байты."""

    def __init__(
            self,
            sample_rate: int = 16000,
            channels: int = 1,
            dtype: str = "int16",
            silence_threshold: int = 800,
    ):
        self.sample_rate = sample_rate
        self.channels = channels
        self.dtype = dtype
        self.silence_threshold = silence_threshold
        self._frames: list[np.ndarray] = []
        self._stream: sd.InputStream | None = None
        self._last_sound_ts = time.time()

    @property
    def is_recording(self) -> bool:
        return self._stream is not None

    def _callback(self, indata, frames, _time, status):  # noqa: ARG002
        if np.abs(indata).max() >= self.silence_threshold:
            self._last_sound_ts = time.time()
        self._frames.append(indata.copy())

    def start(self):
        if self._stream:
            return
        self._frames = []
        self._last_sound_ts = time.time()
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
            wf.setsampwidth(2)
            wf.setframerate(self.sample_rate)
            wf.writeframes(data.tobytes())

        return buff.getvalue(), self.sample_rate

    def silence_for(self) -> float:
        return max(0.0, time.time() - self._last_sound_ts)


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

        self.dtype = torch.float16 if torch.cuda.is_available() and device != "cpu" else torch.float32

        def _from_pretrained(loader, *args, **kwargs):
            try:
                return loader(*args, local_files_only=True, **kwargs)
            except OSError:
                return loader(*args, local_files_only=False, **kwargs)

        self.config = _from_pretrained(AutoConfig.from_pretrained, self.model_id, trust_remote_code=True)
        self.is_gigaam = getattr(self.config, "model_type", None) == "gigaam"

        if self.is_gigaam:
            self.processor = None
            try:
                weights_path = cached_file(self.model_id, "pytorch_model.bin", local_files_only=True)
            except OSError:
                weights_path = cached_file(self.model_id, "pytorch_model.bin", local_files_only=False)

            self.model = AutoModel.from_config(self.config, trust_remote_code=True)
            state = torch.load(weights_path, map_location=device)
            self.model.load_state_dict(state)
            self.model = self.model.to(device=device, dtype=self.dtype)
            self.model.eval()
            self.pipe = None
            return

        self.processor = _from_pretrained(AutoProcessor.from_pretrained, self.model_id, trust_remote_code=True)
        self.model = _from_pretrained(
            AutoModelForSpeechSeq2Seq.from_pretrained,
            self.model_id,
            trust_remote_code=True,
            torch_dtype=self.dtype,
            use_safetensors=False,
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
            dtype=self.dtype,
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

        if self.is_gigaam:
            tmp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".wav")
            try:
                tmp_file.write(wav_bytes)
                tmp_file.flush()
                tmp_file.close()

                result = self.model.transcribe(tmp_file.name)
                return result.strip() if isinstance(result, str) else ""
            finally:
                try:
                    os.unlink(tmp_file.name)
                except FileNotFoundError:
                    pass

        audio = {"array": np.frombuffer(wav_bytes, dtype=np.int16).astype(np.float32) / 32768.0,
                 "sampling_rate": sample_rate}
        result = self.pipe(audio, generate_kwargs={"language": self.language})
        text = result.get("text") if isinstance(result, dict) else None
        return text.strip() if text else ""
