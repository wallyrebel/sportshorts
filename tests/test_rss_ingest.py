from __future__ import annotations

from app.rss_ingest import extract_image_urls


def test_extract_image_urls_from_rss_paths() -> None:
    entry = {
        "enclosures": [
            {"href": "https://cdn.example.com/a.jpg", "type": "image/jpeg"},
            {"href": "https://cdn.example.com/not-image.mp4", "type": "video/mp4"},
        ],
        "media_content": [
            {"url": "https://cdn.example.com/b.png", "type": "image/png"},
        ],
        "media_thumbnail": [
            {"url": "https://cdn.example.com/c.webp"},
        ],
        "summary": "<p>inline <img src='https://cdn.example.com/d.gif' /></p>",
        "content": [
            {"value": "<div><img src='https://cdn.example.com/e.jpeg' /></div>"},
        ],
    }
    urls = extract_image_urls(entry, base_url="https://feed.example.com/rss")
    assert "https://cdn.example.com/a.jpg" in urls
    assert "https://cdn.example.com/b.png" in urls
    assert "https://cdn.example.com/c.webp" in urls
    assert "https://cdn.example.com/d.gif" in urls
    assert "https://cdn.example.com/e.jpeg" in urls
    assert len(urls) == 5


def test_extract_image_urls_deduplicates() -> None:
    entry = {
        "enclosures": [
            {"href": "https://cdn.example.com/a.jpg", "type": "image/jpeg"},
        ],
        "summary": "<img src='https://cdn.example.com/a.jpg'>",
    }
    urls = extract_image_urls(entry, base_url="https://feed.example.com/rss")
    assert urls == ["https://cdn.example.com/a.jpg"]

