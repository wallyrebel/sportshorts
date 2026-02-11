from __future__ import annotations

import logging
import math
import subprocess
from pathlib import Path

from app.models import StyleConfig

LOGGER = logging.getLogger(__name__)


def probe_audio_duration(audio_path: Path, ffprobe_bin: str = "ffprobe") -> float:
    cmd = [
        ffprobe_bin,
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "default=noprint_wrappers=1:nokey=1",
        str(audio_path),
    ]
    result = subprocess.run(cmd, check=True, capture_output=True, text=True)
    return max(float(result.stdout.strip()), 0.1)


def _escape_subtitles_path(path: Path) -> str:
    # Subtitles filter parser expects forward slashes and escaped colon.
    raw = str(path.resolve()).replace("\\", "/")
    raw = raw.replace(":", "\\:")
    raw = raw.replace("'", "\\'")
    return raw


def _build_filter_complex(
    image_count: int,
    segment_sec: float,
    fps: int,
    srt_path: Path | None,
    style: StyleConfig,
) -> tuple[str, str]:
    parts: list[str] = []
    frames_per_segment = max(1, int(math.ceil(segment_sec * fps)))
    for idx in range(image_count):
        parts.append(
            f"[{idx}:v]"
            "scale=1080:1920:force_original_aspect_ratio=increase,"
            "crop=1080:1920,"
            f"zoompan=z='min(zoom+0.0008,1.15)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={frames_per_segment}:s=1080x1920:fps={fps},"
            f"trim=duration={segment_sec:.3f},setpts=PTS-STARTPTS,format=yuv420p[v{idx}]"
        )

    concat_inputs = "".join(f"[v{i}]" for i in range(image_count))
    parts.append(f"{concat_inputs}concat=n={image_count}:v=1:a=0[vcat]")
    last_stream = "vcat"

    if srt_path:
        escaped_srt = _escape_subtitles_path(srt_path)
        parts.append(
            f"[{last_stream}]subtitles='{escaped_srt}':force_style='Fontsize={style.caption_font_size},MarginV={style.caption_margin_v}'[vout]"
        )
        last_stream = "vout"
    return ";".join(parts), last_stream


def render_video(
    image_paths: list[Path],
    audio_path: Path,
    output_path: Path,
    style: StyleConfig,
    ffmpeg_bin: str = "ffmpeg",
    ffprobe_bin: str = "ffprobe",
    srt_path: Path | None = None,
) -> Path:
    if not image_paths:
        raise ValueError("At least one image is required for rendering")

    audio_duration = probe_audio_duration(audio_path, ffprobe_bin=ffprobe_bin)
    target_duration = min(max(audio_duration, style.min_duration_sec), style.max_duration_sec)
    segment_sec = target_duration / len(image_paths)
    filter_complex, mapped_stream = _build_filter_complex(
        image_count=len(image_paths),
        segment_sec=segment_sec,
        fps=style.fps,
        srt_path=srt_path,
        style=style,
    )

    cmd: list[str] = [ffmpeg_bin, "-y"]
    for image in image_paths:
        cmd.extend(["-loop", "1", "-t", f"{segment_sec:.3f}", "-i", str(image)])
    cmd.extend(["-i", str(audio_path)])
    cmd.extend(
        [
            "-filter_complex",
            filter_complex,
            "-map",
            f"[{mapped_stream}]",
            "-map",
            f"{len(image_paths)}:a",
            "-t",
            f"{target_duration:.3f}",
            "-r",
            str(style.fps),
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-b:v",
            style.bitrate,
            "-c:a",
            "aac",
            "-b:a",
            "128k",
            "-af",
            "loudnorm=I=-16:TP=-1.5:LRA=11",
            "-movflags",
            "+faststart",
            "-shortest",
            str(output_path),
        ]
    )

    LOGGER.info("FFmpeg command: %s", " ".join(cmd))
    try:
        subprocess.run(cmd, check=True, capture_output=True, text=True)
        return output_path
    except subprocess.CalledProcessError as exc:
        if srt_path is not None:
            LOGGER.warning(
                "Render with subtitles failed, retrying without subtitles. stderr=%s",
                exc.stderr[-2000:],
            )
            return render_video(
                image_paths=image_paths,
                audio_path=audio_path,
                output_path=output_path,
                style=style,
                ffmpeg_bin=ffmpeg_bin,
                ffprobe_bin=ffprobe_bin,
                srt_path=None,
            )
        raise RuntimeError(f"ffmpeg render failed: {exc.stderr[-2000:]}") from exc
