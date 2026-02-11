from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

from app.models import FeedConfig, StyleConfig


def _as_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _as_int(value: str | None, default: int) -> int:
    if value is None or value.strip() == "":
        return default
    return int(value)


@dataclass(slots=True)
class Settings:
    openai_api_key: str | None
    openai_primary_model: str
    openai_fallback_model: str
    elevenlabs_api_key: str | None
    elevenlabs_voice_id: str | None
    elevenlabs_model: str
    elevenlabs_stability: float
    elevenlabs_similarity: float
    r2_access_key_id: str | None
    r2_secret_access_key: str | None
    r2_account_id: str
    r2_bucket: str
    r2_endpoint: str
    r2_presign_expires_seconds: int
    r2_retention_days: int
    smtp_host: str
    smtp_port: int
    smtp_user: str | None
    smtp_pass: str | None
    email_to: str | None
    email_mode: str
    always_email: bool
    max_recent_per_feed: int
    ffmpeg_bin: str
    ffprobe_bin: str
    user_agent: str
    run_summary_path: str


def load_settings(env_path: str | None = ".env") -> Settings:
    if env_path:
        load_dotenv(env_path, override=False)

    account_id = os.getenv("R2_ACCOUNT_ID", "8da6aa93ea04160c27bb21557c54e2b0")
    endpoint = os.getenv(
        "R2_ENDPOINT",
        f"https://{account_id}.r2.cloudflarestorage.com",
    )

    return Settings(
        openai_api_key=os.getenv("OPENAI_API_KEY"),
        openai_primary_model=os.getenv("OPENAI_PRIMARY_MODEL", "gpt-5-mini"),
        openai_fallback_model=os.getenv("OPENAI_FALLBACK_MODEL", "gpt-4.1-nano"),
        elevenlabs_api_key=os.getenv("ELEVENLABS_API_KEY"),
        elevenlabs_voice_id=os.getenv("ELEVENLABS_VOICE_ID"),
        elevenlabs_model=os.getenv("ELEVENLABS_MODEL", "eleven_multilingual_v2"),
        elevenlabs_stability=float(os.getenv("ELEVENLABS_STABILITY", "0.5")),
        elevenlabs_similarity=float(os.getenv("ELEVENLABS_SIMILARITY", "0.8")),
        r2_access_key_id=os.getenv("R2_ACCESS_KEY_ID"),
        r2_secret_access_key=os.getenv("R2_SECRET_ACCESS_KEY"),
        r2_account_id=account_id,
        r2_bucket=os.getenv("R2_BUCKET", "videoshorts"),
        r2_endpoint=endpoint,
        r2_presign_expires_seconds=_as_int(
            os.getenv("R2_PRESIGN_EXPIRES_SECONDS"), 604800
        ),
        r2_retention_days=_as_int(os.getenv("R2_RETENTION_DAYS"), 30),
        smtp_host=os.getenv("SMTP_HOST", "smtp.gmail.com"),
        smtp_port=_as_int(os.getenv("SMTP_PORT"), 587),
        smtp_user=os.getenv("SMTP_USER"),
        smtp_pass=os.getenv("SMTP_PASS"),
        email_to=os.getenv("EMAIL_TO"),
        email_mode=os.getenv("EMAIL_MODE", "digest").strip().lower(),
        always_email=_as_bool(os.getenv("ALWAYS_EMAIL"), default=False),
        max_recent_per_feed=_as_int(os.getenv("MAX_RECENT_PER_FEED"), 5),
        ffmpeg_bin=os.getenv("FFMPEG_BIN", "ffmpeg"),
        ffprobe_bin=os.getenv("FFPROBE_BIN", "ffprobe"),
        user_agent=os.getenv(
            "HTTP_USER_AGENT",
            "AutoSportsVideo/1.0 (+https://github.com/your/repo)",
        ),
        run_summary_path=os.getenv("RUN_SUMMARY_PATH", "run_summary.json"),
    )


def load_feeds_config(path: str = "config/feeds.json") -> list[FeedConfig]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    feeds: list[FeedConfig] = []
    for item in payload:
        name = str(item.get("name", "")).strip()
        url = str(item.get("url", "")).strip()
        if not name or not url:
            continue
        feeds.append(FeedConfig(name=name, url=url))
    return feeds


def load_style_config(path: str = "config/style.json") -> StyleConfig:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    return StyleConfig(
        min_duration_sec=int(payload.get("min_duration_sec", 10)),
        max_duration_sec=int(payload.get("max_duration_sec", 45)),
        caption_font_size=int(payload.get("caption_font_size", 46)),
        caption_margin_v=int(payload.get("caption_margin_v", 96)),
        fps=int(payload.get("fps", 30)),
        bitrate=str(payload.get("bitrate", "4M")),
        max_images_per_video=int(payload.get("max_images_per_video", 3)),
    )
