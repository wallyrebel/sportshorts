from __future__ import annotations

import json

from app.settings import load_settings, load_style_config


def test_max_recent_per_feed_hard_capped_to_five(monkeypatch) -> None:
    monkeypatch.setenv("MAX_RECENT_PER_FEED", "99")
    settings = load_settings(env_path=None)
    assert settings.max_recent_per_feed == 5


def test_caption_font_size_is_clamped(tmp_path) -> None:
    path = tmp_path / "style.json"
    path.write_text(
        json.dumps(
            {
                "min_duration_sec": 10,
                "max_duration_sec": 45,
                "caption_font_size": 80,
                "caption_margin_v": 96,
                "fps": 30,
                "bitrate": "4M",
                "max_images_per_video": 3,
            }
        ),
        encoding="utf-8",
    )
    style = load_style_config(str(path))
    assert style.caption_font_size == 32

