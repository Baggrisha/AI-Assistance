"""Simple client for GigaAM speech-to-text API."""

from __future__ import annotations

import os
from typing import Any

import requests


class GigaAMSpeechToText:
    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        language: str = "ru",
        timeout: int = 30,
    ) -> None:
        self.api_key = api_key or os.getenv("GIGAAM_API_KEY")
        self.base_url = base_url or os.getenv("GIGAAM_API_URL", "https://api.gigaam.ru/v1/stt")
        self.language = language
        self.timeout = timeout

    def transcribe(self, wav_bytes: bytes) -> str:
        if not self.api_key:
            raise RuntimeError("GIGAAM_API_KEY не задан. Укажи токен доступа.")

        files = {
            "file": ("speech.wav", wav_bytes, "audio/wav"),
        }
        data = {"language": self.language}
        headers = {"Authorization": f"Bearer {self.api_key}"}

        resp = requests.post(
            self.base_url,
            files=files,
            data=data,
            headers=headers,
            timeout=self.timeout,
        )
        resp.raise_for_status()
        payload: Any = resp.json()

        text = payload.get("text") or payload.get("result") or payload.get("data")
        if not text:
            raise RuntimeError("GigaAM не вернул текст распознавания")
        return str(text).strip()
