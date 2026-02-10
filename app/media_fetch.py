from __future__ import annotations

import logging
from pathlib import Path
from urllib.parse import urlparse

import requests

LOGGER = logging.getLogger(__name__)

_ALLOWED_BY_CONTENT_TYPE = {
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "image/gif": ".gif",
}


def _suffix_from_url(url: str) -> str:
    path = urlparse(url).path.lower()
    for suffix in (".jpg", ".jpeg", ".png", ".webp", ".gif"):
        if path.endswith(suffix):
            return suffix if suffix != ".jpeg" else ".jpg"
    return ".jpg"


def download_images(
    image_urls: list[str],
    output_dir: Path,
    max_images: int,
    timeout_sec: int = 20,
    user_agent: str = "AutoSportsVideo/1.0",
) -> list[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    downloaded: list[Path] = []
    headers = {"User-Agent": user_agent}

    for index, url in enumerate(image_urls):
        if len(downloaded) >= max_images:
            break
        try:
            resp = requests.get(url, headers=headers, timeout=timeout_sec)
            resp.raise_for_status()
            content_type = resp.headers.get("Content-Type", "").split(";")[0].strip().lower()
            suffix = _ALLOWED_BY_CONTENT_TYPE.get(content_type, _suffix_from_url(url))
            path = output_dir / f"image_{index:02d}{suffix}"
            path.write_bytes(resp.content)
            downloaded.append(path)
        except Exception as exc:
            LOGGER.warning("Failed to download image %s: %s", url, exc)

    return downloaded

