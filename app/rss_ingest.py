from __future__ import annotations

import html
import logging
import re
from html.parser import HTMLParser
from typing import Any
from urllib.parse import urljoin

import feedparser
import requests

from app.models import FeedConfig, RssItem
from app.utils import accepted_image_extension, compute_item_id

LOGGER = logging.getLogger(__name__)


class _ImgSrcParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.sources: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() != "img":
            return
        attr_map = {k.lower(): v for k, v in attrs}
        src = attr_map.get("src")
        if src:
            self.sources.append(src.strip())


def _normalize_image_url(url: str, base_url: str) -> str:
    return urljoin(base_url, html.unescape(url.strip()))


def _extract_from_html(raw_html: str, base_url: str) -> list[str]:
    parser = _ImgSrcParser()
    parser.feed(raw_html or "")
    urls = [_normalize_image_url(src, base_url) for src in parser.sources]
    return [u for u in urls if accepted_image_extension(u)]


def extract_image_urls(entry: Any, base_url: str) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []

    def add(url: str) -> None:
        normalized = _normalize_image_url(url, base_url)
        if not normalized or normalized in seen:
            return
        if accepted_image_extension(normalized):
            seen.add(normalized)
            out.append(normalized)

    for enclosure in entry.get("enclosures", []) or []:
        url = str(enclosure.get("href") or enclosure.get("url") or "").strip()
        typ = str(enclosure.get("type") or "").lower()
        if url and typ.startswith("image/"):
            add(url)

    for media_entry in entry.get("media_content", []) or []:
        url = str(media_entry.get("url") or "").strip()
        typ = str(media_entry.get("type") or "").lower()
        if url and (typ.startswith("image/") or accepted_image_extension(url)):
            add(url)

    for media_entry in entry.get("media_thumbnail", []) or []:
        url = str(media_entry.get("url") or "").strip()
        if url:
            add(url)

    html_blobs: list[str] = []
    if entry.get("summary"):
        html_blobs.append(str(entry.get("summary")))
    if entry.get("description"):
        html_blobs.append(str(entry.get("description")))

    for content in entry.get("content", []) or []:
        value = content.get("value")
        if value:
            html_blobs.append(str(value))

    for blob in html_blobs:
        for url in _extract_from_html(blob, base_url):
            add(url)

    # Some feeds expose one image directly.
    if entry.get("image", {}).get("href"):
        add(str(entry["image"]["href"]))
    if entry.get("media_url"):
        add(str(entry.get("media_url")))

    return out


def _clean_summary(entry: Any) -> str:
    summary = str(entry.get("summary") or entry.get("description") or "").strip()
    summary = re.sub(r"<[^>]+>", " ", summary)
    summary = re.sub(r"\s+", " ", summary)
    return html.unescape(summary).strip()


def fetch_feed_entries(feed: FeedConfig, timeout_sec: int = 20) -> list[RssItem]:
    headers = {"User-Agent": "AutoSportsVideo/1.0"}
    resp = requests.get(feed.url, headers=headers, timeout=timeout_sec)
    resp.raise_for_status()
    parsed = feedparser.parse(resp.content)
    items: list[RssItem] = []

    for entry in parsed.entries or []:
        entry_dict: dict[str, Any] = dict(entry)
        item_id = compute_item_id(entry_dict)
        images = extract_image_urls(entry_dict, base_url=feed.url)
        item = RssItem(
            feed_name=feed.name,
            feed_url=feed.url,
            item_id=item_id,
            title=str(entry_dict.get("title") or "Untitled").strip(),
            summary=_clean_summary(entry_dict),
            link=str(entry_dict.get("link") or "").strip(),
            published=str(entry_dict.get("published") or entry_dict.get("updated") or ""),
            image_urls=images,
        )
        items.append(item)

    LOGGER.info("Parsed feed '%s': %s entries", feed.name, len(items))
    return items

