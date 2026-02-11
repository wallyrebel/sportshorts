from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import dataclass

from openai import APIStatusError, APITimeoutError, OpenAI, RateLimitError

from app.models import RssItem, ScriptResult
from app.utils import word_count

LOGGER = logging.getLogger(__name__)
MIN_WORDS = 35
MAX_WORDS = 95


@dataclass(slots=True)
class ModelConfig:
    primary_model: str = "gpt-5-mini"
    fallback_model: str = "gpt-4.1-nano"
    primary_timeout_sec: int = 20
    fallback_timeout_sec: int = 15
    max_retries: int = 3


class ScriptGenerator:
    def __init__(self, api_key: str, config: ModelConfig | None = None) -> None:
        self._client = OpenAI(api_key=api_key)
        self._cfg = config or ModelConfig()

    def create_script(self, item: RssItem) -> ScriptResult:
        prompt = self._build_prompt(item)
        primary_err: Exception | None = None

        try:
            return self._run_model_with_retry(
                model=self._cfg.primary_model,
                timeout_sec=self._cfg.primary_timeout_sec,
                prompt=prompt,
            )
        except Exception as exc:
            if _is_fallback_worthy(exc):
                primary_err = exc
                LOGGER.warning(
                    "Primary model failed for item %s; falling back to %s. error=%s",
                    item.item_id,
                    self._cfg.fallback_model,
                    exc,
                )
            else:
                raise

        if primary_err is not None:
            return self._run_model_with_retry(
                model=self._cfg.fallback_model,
                timeout_sec=self._cfg.fallback_timeout_sec,
                prompt=prompt,
            )
        raise RuntimeError("Unexpected script generation state")

    def _run_model_with_retry(
        self, model: str, timeout_sec: int, prompt: str
    ) -> ScriptResult:
        last_error: Exception | None = None
        for attempt in range(1, self._cfg.max_retries + 1):
            try:
                response = self._client.responses.create(
                    model=model,
                    input=prompt,
                    timeout=timeout_sec,
                )
                text = (response.output_text or "").strip()
                result = _parse_model_json(text)
                result = _normalize_script(result, model=model)
                LOGGER.info("Script model used: %s", model)
                return result
            except Exception as exc:
                last_error = exc
                if attempt >= self._cfg.max_retries or not _is_retryable(exc):
                    break
                backoff_sec = 2 ** (attempt - 1)
                LOGGER.warning(
                    "Retrying model=%s attempt=%s/%s in %ss because: %s",
                    model,
                    attempt,
                    self._cfg.max_retries,
                    backoff_sec,
                    exc,
                )
                time.sleep(backoff_sec)

        if last_error is None:
            raise RuntimeError(f"Model {model} failed without explicit error")
        raise last_error

    @staticmethod
    def _build_prompt(item: RssItem) -> str:
        title = item.title[:350]
        summary = item.summary[:1600]
        return f"""
You are writing short voiceover scripts for vertical sports videos.
You MUST use only facts present in the RSS fields below. Do not invent details.
If details are limited, keep wording general and clearly avoid specifics not present.

Output strict JSON with this exact shape:
{{
  "narration_text": "35-95 words, spoken style, no hashtags, no emojis, no weird symbols",
  "on_screen_hook": "optional, max 8 words"
}}

RSS title:
{title}

RSS summary:
{summary}
"""


def _parse_model_json(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.DOTALL)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, flags=re.DOTALL)
        if not match:
            raise
        return json.loads(match.group(0))


def _normalize_script(payload: dict, model: str) -> ScriptResult:
    narration = re.sub(r"\s+", " ", str(payload.get("narration_text", "")).strip())
    hook = ""

    narration = narration.replace("#", "")

    words = narration.split()
    if len(words) > MAX_WORDS:
        narration = " ".join(words[:MAX_WORDS]).rstrip(".,;:!?") + "."
    elif len(words) < MIN_WORDS:
        pad = " This update is based on the RSS item details currently available."
        narration = (narration + pad).strip()
        words = narration.split()
        if len(words) > MAX_WORDS:
            narration = " ".join(words[:MAX_WORDS]).rstrip(".,;:!?") + "."

    final_count = word_count(narration)
    if final_count < MIN_WORDS:
        raise ValueError("Narration too short after normalization")

    return ScriptResult(narration_text=narration, on_screen_hook=hook, model_used=model)


def _is_retryable(exc: Exception) -> bool:
    if isinstance(exc, (APITimeoutError, RateLimitError)):
        return True
    if isinstance(exc, APIStatusError):
        return exc.status_code >= 500 or exc.status_code == 429
    return False


def _is_fallback_worthy(exc: Exception) -> bool:
    return _is_retryable(exc)
