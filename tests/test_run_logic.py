from __future__ import annotations

from app.models import RssItem
from app.run import _build_video_key, _select_recent_items


def _item(item_id: str, published: str) -> RssItem:
    return RssItem(
        feed_name="Feed",
        feed_url="https://example.com/rss",
        item_id=item_id,
        title=f"Title {item_id}",
        summary="summary",
        link="https://example.com/item",
        published=published,
        image_urls=["https://example.com/a.jpg"],
    )


def test_select_recent_items_limits_to_five() -> None:
    items = [
        _item("1", "Mon, 01 Jan 2024 10:00:00 GMT"),
        _item("2", "Tue, 02 Jan 2024 10:00:00 GMT"),
        _item("3", "Wed, 03 Jan 2024 10:00:00 GMT"),
        _item("4", "Thu, 04 Jan 2024 10:00:00 GMT"),
        _item("5", "Fri, 05 Jan 2024 10:00:00 GMT"),
        _item("6", "Sat, 06 Jan 2024 10:00:00 GMT"),
    ]
    selected = _select_recent_items(items, max_recent=5)
    assert len(selected) == 5
    assert [item.item_id for item in selected] == ["6", "5", "4", "3", "2"]


def test_build_video_key_is_deterministic_for_same_item() -> None:
    key_1 = _build_video_key("Big Win", "guid:abc", "Tue, 09 Jan 2024 22:00:00 GMT")
    key_2 = _build_video_key("Big Win", "guid:abc", "Tue, 09 Jan 2024 22:00:00 GMT")
    assert key_1 == key_2
    assert key_1.startswith("videos/2024/01/09/")

