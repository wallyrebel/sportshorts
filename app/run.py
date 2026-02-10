from __future__ import annotations

import argparse
import json
import logging
import sys
import tempfile
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from pathlib import Path

from app.captions import generate_srt
from app.email_gmail_smtp import GmailSender
from app.media_fetch import download_images
from app.models import RssItem, VideoResult
from app.r2_storage import R2Storage
from app.render_ffmpeg import probe_audio_duration, render_video
from app.rss_ingest import fetch_feed_entries
from app.script_llm import ScriptGenerator
from app.settings import Settings, load_feeds_config, load_settings, load_style_config
from app.state import is_processed, load_state, mark_processed, prune_state_by_retention, save_state
from app.tts_elevenlabs import ElevenLabsTTS
from app.utils import iso_utc, sha256_text, slugify, utcnow

LOGGER = logging.getLogger(__name__)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate short videos from RSS feed items.")
    parser.add_argument("--dry-run", action="store_true", help="No rendering/upload/email side effects.")
    parser.add_argument(
        "--max-items",
        type=int,
        default=0,
        help="Maximum number of new items to process in this run (0 means unlimited).",
    )
    return parser.parse_args(argv)


def _require(value: str | None, name: str) -> str:
    if not value:
        raise ValueError(f"Missing required environment variable: {name}")
    return value


def _setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )


def _parse_rss_datetime_utc(value: str) -> datetime | None:
    raw = (value or "").strip()
    if not raw:
        return None
    try:
        parsed = parsedate_to_datetime(raw)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=UTC)
        return parsed.astimezone(UTC)
    except Exception:
        return None


def _select_recent_items(items: list[RssItem], max_recent: int) -> list[RssItem]:
    if max_recent <= 0:
        return items
    sorted_items = sorted(
        items,
        key=lambda item: (
            _parse_rss_datetime_utc(item.published) or datetime(1970, 1, 1, tzinfo=UTC)
        ),
        reverse=True,
    )
    return sorted_items[:max_recent]


def _build_video_key(item_title: str, item_id: str, published: str) -> str:
    key_date = _parse_rss_datetime_utc(published) or datetime(1970, 1, 1, tzinfo=UTC)
    slug = slugify(item_title, max_length=70)
    suffix = sha256_text(item_id)[:10]
    return f"videos/{key_date:%Y/%m/%d}/{slug}-{suffix}.mp4"


def _write_run_summary(path: str, payload: dict) -> None:
    Path(path).write_text(json.dumps(payload, indent=2), encoding="utf-8")


def run_pipeline(settings: Settings, dry_run: bool, max_items: int) -> dict:
    feeds = load_feeds_config()
    style = load_style_config()
    stats = {
        "feeds": len(feeds),
        "entries_seen": 0,
        "skipped_no_image": 0,
        "skipped_duplicate": 0,
        "skipped_no_downloadable_image": 0,
        "processed": 0,
        "errors": 0,
        "retention_deleted_videos": 0,
        "retention_pruned_state": 0,
        "emails_sent": 0,
    }

    created: list[VideoResult] = []
    processed_count = 0

    r2: R2Storage | None = None
    script_gen: ScriptGenerator | None = None
    tts: ElevenLabsTTS | None = None
    email_sender: GmailSender | None = None
    state: dict = {"version": 1, "processed": {}}

    if not dry_run:
        r2 = R2Storage(
            access_key_id=_require(settings.r2_access_key_id, "R2_ACCESS_KEY_ID"),
            secret_access_key=_require(settings.r2_secret_access_key, "R2_SECRET_ACCESS_KEY"),
            bucket=settings.r2_bucket,
            endpoint_url=settings.r2_endpoint,
        )
        state = load_state(r2)
        script_gen = ScriptGenerator(api_key=_require(settings.openai_api_key, "OPENAI_API_KEY"))
        tts = ElevenLabsTTS(
            api_key=_require(settings.elevenlabs_api_key, "ELEVENLABS_API_KEY"),
            voice_id=_require(settings.elevenlabs_voice_id, "ELEVENLABS_VOICE_ID"),
            model=settings.elevenlabs_model,
            stability=settings.elevenlabs_stability,
            similarity=settings.elevenlabs_similarity,
        )
        email_sender = GmailSender(
            host=settings.smtp_host,
            port=settings.smtp_port,
            user=_require(settings.smtp_user, "SMTP_USER"),
            password=_require(settings.smtp_pass, "SMTP_PASS"),
            to_address=_require(settings.email_to, "EMAIL_TO"),
            mode=settings.email_mode,
        )
    else:
        LOGGER.info("Dry run enabled. No render/upload/email side effects will occur.")

    for feed in feeds:
        try:
            items = fetch_feed_entries(feed)
            items = _select_recent_items(items, settings.max_recent_per_feed)
            LOGGER.info(
                "Feed '%s' limited to %s most recent item(s) this run.",
                feed.name,
                len(items),
            )
        except Exception as exc:
            stats["errors"] += 1
            LOGGER.exception("Failed to fetch feed %s: %s", feed.url, exc)
            continue

        for item in items:
            stats["entries_seen"] += 1
            if max_items and processed_count >= max_items:
                LOGGER.info("Reached --max-items=%s, stopping early.", max_items)
                break

            if not item.image_urls:
                stats["skipped_no_image"] += 1
                LOGGER.info("skip=%s reason=skipped_no_image title=%s", item.item_id, item.title)
                continue

            if is_processed(state, item.item_id):
                stats["skipped_duplicate"] += 1
                LOGGER.info("skip=%s reason=skipped_duplicate title=%s", item.item_id, item.title)
                continue

            key = _build_video_key(item.title, item.item_id, item.published)
            if not dry_run:
                assert r2
                if r2.object_exists(key):
                    stats["skipped_duplicate"] += 1
                    mark_processed(state, item.item_id, timestamp=iso_utc())
                    LOGGER.info(
                        "skip=%s reason=skipped_duplicate_existing_object key=%s title=%s",
                        item.item_id,
                        key,
                        item.title,
                    )
                    continue

            if dry_run:
                processed_count += 1
                LOGGER.info(
                    "[DRY RUN] would_process item_id=%s feed=%s images=%s key=%s title=%s",
                    item.item_id,
                    item.feed_name,
                    len(item.image_urls),
                    key,
                    item.title,
                )
                continue

            assert r2 and script_gen and tts and email_sender
            try:
                with tempfile.TemporaryDirectory(prefix="autosports_") as tmp:
                    tmp_path = Path(tmp)
                    downloaded = download_images(
                        item.image_urls,
                        output_dir=tmp_path / "images",
                        max_images=max(1, style.max_images_per_video),
                        user_agent=settings.user_agent,
                    )
                    if not downloaded:
                        stats["skipped_no_downloadable_image"] += 1
                        LOGGER.info(
                            "skip=%s reason=skipped_no_downloadable_image title=%s",
                            item.item_id,
                            item.title,
                        )
                        continue

                    script = script_gen.create_script(item)
                    audio_path = tmp_path / "voiceover.mp3"
                    tts.synthesize(script.narration_text, output_path=audio_path)
                    audio_duration = probe_audio_duration(audio_path, ffprobe_bin=settings.ffprobe_bin)

                    duration = min(max(audio_duration, style.min_duration_sec), style.max_duration_sec)
                    srt_path = generate_srt(
                        narration_text=script.narration_text,
                        duration_sec=duration,
                        output_path=tmp_path / "captions.srt",
                    )

                    output_video = tmp_path / "clip.mp4"
                    render_video(
                        image_paths=downloaded[: style.max_images_per_video],
                        audio_path=audio_path,
                        output_path=output_video,
                        style=style,
                        ffmpeg_bin=settings.ffmpeg_bin,
                        ffprobe_bin=settings.ffprobe_bin,
                        srt_path=srt_path,
                        on_screen_hook=script.on_screen_hook,
                    )

                    r2.upload_file(output_video, key=key, content_type="video/mp4")
                    url = r2.presign_get_url(
                        key=key,
                        expires_seconds=settings.r2_presign_expires_seconds,
                    )

                    now_ts = utcnow()
                    created.append(
                        VideoResult(
                            item_id=item.item_id,
                            feed_name=item.feed_name,
                            title=item.title,
                            published=item.published,
                            source_link=item.link,
                            r2_key=key,
                            presigned_url=url,
                            model_used=script.model_used,
                            created_at=now_ts,
                        )
                    )
                    mark_processed(state, item.item_id, timestamp=iso_utc(now_ts))
                    processed_count += 1
                    stats["processed"] += 1
                    LOGGER.info("processed item_id=%s key=%s", item.item_id, key)
            except Exception as exc:
                stats["errors"] += 1
                LOGGER.exception("Failed processing item_id=%s error=%s", item.item_id, exc)
                continue
        if max_items and processed_count >= max_items:
            break

    if not dry_run:
        assert r2 and email_sender
        stats["retention_deleted_videos"] = r2.delete_videos_older_than(settings.r2_retention_days)
        stats["retention_pruned_state"] = prune_state_by_retention(
            state, retention_days=settings.r2_retention_days
        )
        save_state(r2, state)
        stats["emails_sent"] = email_sender.send(created, always_email=settings.always_email)

    summary = {
        "dry_run": dry_run,
        "timestamp_utc": iso_utc(),
        "stats": stats,
        "created_count": len(created),
        "created": [
            {
                "title": item.title,
                "feed_name": item.feed_name,
                "published": item.published,
                "source_link": item.source_link,
                "r2_key": item.r2_key,
                "presigned_url": item.presigned_url,
                "model_used": item.model_used,
            }
            for item in created
        ],
    }
    _write_run_summary(settings.run_summary_path, summary)
    return summary


def main(argv: list[str] | None = None) -> int:
    _setup_logging()
    args = parse_args(argv)
    settings = load_settings()
    summary = run_pipeline(settings=settings, dry_run=args.dry_run, max_items=args.max_items)
    LOGGER.info("Run summary: %s", json.dumps(summary["stats"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
