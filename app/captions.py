from __future__ import annotations

import math
import re
from pathlib import Path


def _fmt_srt_time(seconds: float) -> str:
    ms = int(round(seconds * 1000))
    hours = ms // 3_600_000
    ms -= hours * 3_600_000
    minutes = ms // 60_000
    ms -= minutes * 60_000
    secs = ms // 1000
    ms -= secs * 1000
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{ms:03d}"


def _chunk_words(text: str, target_chunks: int) -> list[str]:
    words = [w for w in re.split(r"\s+", text.strip()) if w]
    if not words:
        return []
    target_chunks = max(1, target_chunks)
    chunk_size = max(3, math.ceil(len(words) / target_chunks))
    chunks: list[str] = []
    for idx in range(0, len(words), chunk_size):
        chunks.append(" ".join(words[idx : idx + chunk_size]))
    return chunks


def generate_srt(narration_text: str, duration_sec: float, output_path: Path) -> Path:
    chunks = _chunk_words(narration_text, target_chunks=max(3, int(duration_sec // 2)))
    if not chunks:
        chunks = [narration_text.strip()]
    step = duration_sec / max(len(chunks), 1)

    lines: list[str] = []
    for idx, chunk in enumerate(chunks, start=1):
        start = (idx - 1) * step
        end = idx * step
        lines.append(str(idx))
        lines.append(f"{_fmt_srt_time(start)} --> {_fmt_srt_time(end)}")
        lines.append(chunk)
        lines.append("")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines), encoding="utf-8")
    return output_path

