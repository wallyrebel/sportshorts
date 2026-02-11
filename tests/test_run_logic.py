from __future__ import annotations

from app.models import RssItem
from app.run import (
    _build_video_key,
    _select_first_chronological_unique_stories,
    _select_recent_items,
    _sort_items_newest_first,
)


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


def test_sort_items_newest_first_across_feeds() -> None:
    items = [
        _item("feed1-old", "Mon, 01 Jan 2024 10:00:00 GMT"),
        _item("feed2-new", "Fri, 05 Jan 2024 10:00:00 GMT"),
        _item("feed3-mid", "Wed, 03 Jan 2024 10:00:00 GMT"),
    ]
    sorted_items = _sort_items_newest_first(items)
    assert [item.item_id for item in sorted_items] == ["feed2-new", "feed3-mid", "feed1-old"]


def test_same_story_dedupe_keeps_first_chronological() -> None:
    older = RssItem(
        feed_name="Feed 1",
        feed_url="https://example.com/1",
        item_id="older",
        title="Big upset in state final",
        summary="Team Alpha beat Team Beta by one point to win the state championship.",
        link="https://example.com/a",
        published="Mon, 01 Jan 2024 10:00:00 GMT",
        image_urls=["https://example.com/1.jpg"],
    )
    newer_similar = RssItem(
        feed_name="Feed 2",
        feed_url="https://example.com/2",
        item_id="newer",
        title="Big upset in state final as Team Alpha beats Team Beta",
        summary="Team Alpha beat Team Beta by one point to win the state championship game.",
        link="https://example.com/b",
        published="Tue, 02 Jan 2024 10:00:00 GMT",
        image_urls=["https://example.com/2.jpg"],
    )
    distinct = RssItem(
        feed_name="Feed 3",
        feed_url="https://example.com/3",
        item_id="distinct",
        title="Coach signs long-term extension",
        summary="The head coach signs a multi-year extension through 2029.",
        link="https://example.com/c",
        published="Wed, 03 Jan 2024 10:00:00 GMT",
        image_urls=["https://example.com/3.jpg"],
    )

    kept, skipped = _select_first_chronological_unique_stories([newer_similar, older, distinct])
    assert [item.item_id for item in kept] == ["older", "distinct"]
    assert skipped["newer"] == "older"
