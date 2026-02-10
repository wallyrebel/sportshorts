from __future__ import annotations

import hashlib
import re
import unicodedata
from datetime import UTC, datetime
from urllib.parse import urlparse


def utcnow() -> datetime:
    return datetime.now(tz=UTC)


def iso_utc(dt: datetime | None = None) -> str:
    value = dt or utcnow()
    return value.astimezone(UTC).replace(microsecond=0).isoformat()


def parse_iso_utc(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def slugify(text: str, max_length: int = 80) -> str:
    normalized = unicodedata.normalize("NFKD", text)
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii")
    lowered = ascii_text.lower()
    cleaned = re.sub(r"[^a-z0-9]+", "-", lowered).strip("-")
    if not cleaned:
        cleaned = "clip"
    return cleaned[:max_length].strip("-")


def sanitize_for_ffmpeg_text(text: str) -> str:
    return (
        text.replace("\\", "\\\\")
        .replace(":", "\\:")
        .replace("'", "\\'")
        .replace("%", "\\%")
        .replace(",", "\\,")
    )


def accepted_image_extension(url: str) -> bool:
    parsed = urlparse(url)
    path = parsed.path.lower()
    return path.endswith((".jpg", ".jpeg", ".png", ".webp", ".gif"))


def compute_item_id(entry: dict) -> str:
    guid = str(entry.get("id") or entry.get("guid") or "").strip()
    if guid:
        return f"guid:{guid}"

    link = str(entry.get("link") or "").strip()
    if link:
        return f"link:{link}"

    title = str(entry.get("title") or "").strip()
    pub_date = str(entry.get("published") or entry.get("updated") or "").strip()
    return "hash:" + sha256_text(f"{title}|{pub_date}")


def word_count(text: str) -> int:
    return len([w for w in re.split(r"\s+", text.strip()) if w])

