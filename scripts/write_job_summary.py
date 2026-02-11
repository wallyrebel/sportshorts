from __future__ import annotations

import json
import sys
from pathlib import Path


def main() -> int:
    if len(sys.argv) != 3:
        print("Usage: python scripts/write_job_summary.py <run_summary.json> <output_md_path>")
        return 2

    run_summary_path = Path(sys.argv[1])
    output_path = Path(sys.argv[2])

    if not run_summary_path.exists():
        output_path.write_text("run_summary.json was not found.\n", encoding="utf-8")
        return 0

    data = json.loads(run_summary_path.read_text(encoding="utf-8"))
    stats = data.get("stats", {})
    created = data.get("created", [])

    lines: list[str] = []
    lines.append("## AutoSportsVideo Run Summary")
    lines.append("")
    lines.append(f"- Dry run: `{data.get('dry_run')}`")
    lines.append(f"- Created clips: `{data.get('created_count', 0)}`")
    lines.append(f"- Entries seen: `{stats.get('entries_seen', 0)}`")
    lines.append(f"- Skipped no image: `{stats.get('skipped_no_image', 0)}`")
    lines.append(f"- Skipped duplicate: `{stats.get('skipped_duplicate', 0)}`")
    lines.append(f"- Errors: `{stats.get('errors', 0)}`")
    lines.append("")

    if created:
        lines.append("### Presigned Links")
        lines.append("")
        for idx, item in enumerate(created, start=1):
            title = str(item.get("title", "clip"))
            url = str(item.get("presigned_url", ""))
            lines.append(f"{idx}. [{title}]({url})")
    else:
        lines.append("No clips created in this run.")

    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

