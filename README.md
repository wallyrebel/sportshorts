# AutoSportsVideo

Automated Python pipeline that runs hourly, reads multiple RSS feeds, and creates vertical Shorts/Reels clips from RSS-only content.

For each **new** RSS item with at least one image:
- Generates a rewritten narration script with OpenAI (primary + fallback model), fact-checked against RSS content and not copied word-for-word
- Generates voiceover MP3 with ElevenLabs
- Renders a 1080x1920 MP4 with FFmpeg (Ken Burns image motion + optional burned captions)
- Uploads MP4 to private Cloudflare R2
- Creates a presigned GET URL (expiring link)
- Sends one Gmail digest email containing all links created in that run

Items without images are skipped by design, and article pages are never scraped.

## Core Rules Implemented
- Multiple RSS feeds from `config/feeds.json`
- Image required (`skipped_no_image` if none found in RSS payload)
- RSS-only parsing (title/summary/content/enclosures/media tags)
- Duplicate prevention via state persisted in R2 at `state/processed.json`
- Per-run feed cap: hard-capped at 5 most recent items per feed (even if env is set higher), then all candidates are processed globally newest-first regardless of feed
- Cross-feed same-story dedupe: near-duplicate title/summary items are collapsed and only the first chronological item is kept
- Retention cleanup for old videos and old processed-state entries
- Per-item error handling so one bad item does not stop the run

## Project Structure
- `app/run.py`: CLI entrypoint (`python -m app.run`)
- `app/rss_ingest.py`: feed fetch + RSS-only image extraction
- `app/script_llm.py`: OpenAI script generation with fallback/retries/timeouts
- `app/tts_elevenlabs.py`: ElevenLabs TTS with retries
- `app/captions.py`: SRT generation
- `app/render_ffmpeg.py`: FFmpeg rendering with subtitles fallback (no extra on-screen hook text, captions only)
- `app/r2_storage.py`: Cloudflare R2 upload/state/presign/retention operations
- `app/state.py`: duplicate state load/save/prune
- `app/email_gmail_smtp.py`: digest/per-clip email delivery via Gmail SMTP
- `.github/workflows/build_shorts.yml`: hourly GitHub Actions workflow
- `tests/`: pytest unit tests

## Local Setup
### 1) Install Python dependencies
```bash
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate

pip install -r requirements.txt
```

### 2) Install FFmpeg
- Windows:
  - `winget install Gyan.FFmpeg` or `choco install ffmpeg`
  - Verify: `ffmpeg -version` and `ffprobe -version`
- macOS:
  - `brew install ffmpeg`
- Linux (Debian/Ubuntu):
  - `sudo apt-get update && sudo apt-get install -y ffmpeg`

### 3) Configure environment
```bash
cp .env.example .env
```
Fill every required value in `.env`:
- OpenAI key/models
- ElevenLabs key/voice
- R2 credentials
- Gmail SMTP app-password credentials

## Running
### Dry run (no render/upload/email side effects)
```bash
python -m app.run --dry-run --max-items 5
```

### Real run
```bash
python -m app.run
```

### Optional flags
- `--dry-run`: print what would be processed without side effects
- `--max-items N`: cap newly processed items for test runs

Pipeline writes a machine-readable summary file at `run_summary.json`.
By default, clips target at least 10 seconds and can extend up to `max_duration_sec` (default `45`) based on narration audio length.
Default caption font size is reduced to `24` and runtime-clamped between `16` and `32` to avoid oversized text.

### Manual run helpers
- Local PowerShell helper:
  - `.\scripts\manual_run.ps1 -DryRun -MaxItems 5`
  - `.\scripts\manual_run.ps1 -MaxItems 10`
- GitHub Actions manual run:
  - Open **Actions -> Build Shorts -> Run workflow**
  - Choose `dry_run` and `max_items` inputs

## Cloudflare R2 Notes
- Bucket is private (public access disabled).
- Shared links are presigned GET URLs and expire (default 7 days via `R2_PRESIGN_EXPIRES_SECONDS`).
- R2 endpoint must be:
  - `https://8da6aa93ea04160c27bb21557c54e2b0.r2.cloudflarestorage.com`
- Uploaded video key format:
  - `videos/YYYY/MM/DD/<slug>-<hash>.mp4`
- Duplicate protection:
  - Primary: item IDs tracked in `state/processed.json` in R2
  - Secondary: deterministic R2 object key per item, with pre-upload existence check

### Retention policy
- `R2_RETENTION_DAYS=30` by default.
- Each run:
  - Deletes `videos/` objects older than retention
  - Prunes old `state/processed.json` entries older than retention
- If unset or `0`, retention deletion/pruning is disabled.
- Manual deletion in R2 is allowed, but old presigned links for deleted files will stop working.

## GitHub Actions (Hourly)
Workflow file: `.github/workflows/build_shorts.yml`
- Schedule: hourly (`0 * * * *`)
- Also supports manual run (`workflow_dispatch`)
- Manual runs support `dry_run` and `max_items` inputs
- Installs Python + FFmpeg
- Executes `python -m app.run`
- Appends created clip links to job summary from `run_summary.json`

### Required GitHub Secrets
Create these repo secrets:
- `OPENAI_API_KEY`
- `OPENAI_PRIMARY_MODEL` (optional; default `gpt-5-mini`)
- `OPENAI_FALLBACK_MODEL` (optional; default `gpt-4.1-nano`)
- `ELEVENLABS_API_KEY`
- `ELEVENLABS_VOICE_ID`
- `ELEVENLABS_MODEL` (optional)
- `ELEVENLABS_STABILITY` (optional)
- `ELEVENLABS_SIMILARITY` (optional)
- `R2_ACCESS_KEY_ID`
- `R2_SECRET_ACCESS_KEY`
- `R2_ACCOUNT_ID` (set to `8da6aa93ea04160c27bb21557c54e2b0`)
- `R2_BUCKET` (set to `videoshorts`)
- `R2_ENDPOINT` (set to `https://8da6aa93ea04160c27bb21557c54e2b0.r2.cloudflarestorage.com`)
- `R2_PRESIGN_EXPIRES_SECONDS` (optional, default `604800`)
- `R2_RETENTION_DAYS` (optional, default `30`)
- `SMTP_HOST` (default `smtp.gmail.com`)
- `SMTP_PORT` (default `587`)
- `SMTP_USER`
- `SMTP_PASS` (Gmail App Password)
- `EMAIL_TO`
- `EMAIL_MODE` (`digest` or `per_clip`)
- `ALWAYS_EMAIL` (`true` or `false`)
- `MAX_RECENT_PER_FEED` (optional, default `5`)

## Troubleshooting
### Subtitles/font failures
- FFmpeg `subtitles` filter can fail if subtitle/font stack is unavailable.
- Renderer automatically retries without burned captions on failure.
- Fix by installing additional fonts or libass-enabled FFmpeg.

### RSS items skipped without images
- Intended behavior.
- Only images in RSS payload are considered:
  - `enclosure` (image/*)
  - `media:content`
  - `media:thumbnail`
  - `<img src>` inside RSS summary/content
- Linked article pages are never scraped.

### ElevenLabs rate limits/transient errors
- TTS client retries with exponential backoff.
- Persistent API failures are logged and item processing continues to next item.

### OpenAI fallback behavior
- Script generation first uses `OPENAI_PRIMARY_MODEL` (default `gpt-5-mini`) with hard timeout.
- On timeout/429/5xx, it falls back to `OPENAI_FALLBACK_MODEL` (default `gpt-4.1-nano`).
- Logs include which model was used for each processed item.
- Narration is forced to be a factual rewrite/paraphrase of RSS content (not verbatim copy), with an automatic rewrite pass if similarity is too high.

## Testing
Run unit tests:
```bash
pytest -q
```

Covered tests include:
- Item ID generation
- RSS image extraction paths
- Slugify
- State load/save (mocked)
- Retention pruning logic (mocked)
- Presigned URL generation (mocked)
