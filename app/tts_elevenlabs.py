from __future__ import annotations

import logging
import time
from pathlib import Path

import requests

LOGGER = logging.getLogger(__name__)


class ElevenLabsTTS:
    def __init__(
        self,
        api_key: str,
        voice_id: str,
        model: str = "eleven_multilingual_v2",
        stability: float = 0.5,
        similarity: float = 0.8,
        max_retries: int = 3,
    ) -> None:
        self.api_key = api_key
        self.voice_id = voice_id
        self.model = model
        self.stability = stability
        self.similarity = similarity
        self.max_retries = max_retries

    def synthesize(self, text: str, output_path: Path, timeout_sec: int = 45) -> Path:
        url = f"https://api.elevenlabs.io/v1/text-to-speech/{self.voice_id}"
        headers = {
            "Accept": "audio/mpeg",
            "Content-Type": "application/json",
            "xi-api-key": self.api_key,
        }
        payload = {
            "text": text,
            "model_id": self.model,
            "voice_settings": {
                "stability": self.stability,
                "similarity_boost": self.similarity,
            },
        }

        last_exc: Exception | None = None
        for attempt in range(1, self.max_retries + 1):
            try:
                resp = requests.post(url, headers=headers, json=payload, timeout=timeout_sec)
                if resp.status_code in {429, 500, 502, 503, 504}:
                    raise requests.HTTPError(
                        f"ElevenLabs transient status={resp.status_code}: {resp.text[:300]}"
                    )
                resp.raise_for_status()
                output_path.parent.mkdir(parents=True, exist_ok=True)
                output_path.write_bytes(resp.content)
                return output_path
            except Exception as exc:
                last_exc = exc
                if attempt >= self.max_retries:
                    break
                sleep_sec = 2 ** (attempt - 1)
                LOGGER.warning(
                    "ElevenLabs retry %s/%s in %ss due to: %s",
                    attempt,
                    self.max_retries,
                    sleep_sec,
                    exc,
                )
                time.sleep(sleep_sec)

        if last_exc is None:
            raise RuntimeError("ElevenLabs failed without explicit error")
        raise RuntimeError(f"ElevenLabs TTS failed: {last_exc}") from last_exc

