from __future__ import annotations

from app.utils import compute_item_id, slugify


def test_compute_item_id_prefers_guid() -> None:
    entry = {"id": "abc-123", "link": "https://example.com/x", "title": "t"}
    assert compute_item_id(entry) == "guid:abc-123"


def test_compute_item_id_uses_link_if_no_guid() -> None:
    entry = {"link": "https://example.com/a"}
    assert compute_item_id(entry) == "link:https://example.com/a"


def test_compute_item_id_hash_fallback() -> None:
    entry = {"title": "Hello", "published": "Tue, 01 Jan 2024 00:00:00 GMT"}
    result = compute_item_id(entry)
    assert result.startswith("hash:")
    assert len(result) > 10


def test_slugify_basic() -> None:
    assert slugify("F1: Big Win!!!") == "f1-big-win"


def test_slugify_handles_unicode() -> None:
    assert slugify("Caf\u00e9 r\u00e9sum\u00e9 -- na\u00efve") == "cafe-resume-naive"

