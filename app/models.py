from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass(slots=True)
class FeedConfig:
    name: str
    url: str


@dataclass(slots=True)
class StyleConfig:
    min_duration_sec: int = 10
    max_duration_sec: int = 15
    caption_font_size: int = 46
    caption_margin_v: int = 96
    fps: int = 30
    bitrate: str = "4M"
    max_images_per_video: int = 3


@dataclass(slots=True)
class RssItem:
    feed_name: str
    feed_url: str
    item_id: str
    title: str
    summary: str
    link: str
    published: str
    image_urls: list[str] = field(default_factory=list)


@dataclass(slots=True)
class ScriptResult:
    narration_text: str
    on_screen_hook: str
    model_used: str


@dataclass(slots=True)
class VideoResult:
    item_id: str
    feed_name: str
    title: str
    published: str
    source_link: str
    r2_key: str
    presigned_url: str
    model_used: str
    created_at: datetime

