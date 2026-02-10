from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.utils import iso_utc, parse_iso_utc

STATE_KEY = "state/processed.json"


def load_state(r2) -> dict:
    default = {"version": 1, "processed": {}}
    state = r2.download_json(STATE_KEY, default=default)
    if "processed" not in state or not isinstance(state["processed"], dict):
        state["processed"] = {}
    return state


def save_state(r2, state: dict) -> None:
    r2.upload_json(STATE_KEY, payload=state)


def is_processed(state: dict, item_id: str) -> bool:
    return item_id in state.get("processed", {})


def mark_processed(state: dict, item_id: str, timestamp: str | None = None) -> None:
    state.setdefault("processed", {})
    state["processed"][item_id] = timestamp or iso_utc()


def prune_state_by_retention(
    state: dict,
    retention_days: int,
    now: datetime | None = None,
) -> int:
    if retention_days <= 0:
        return 0
    now = now or datetime.now(tz=UTC)
    cutoff = now - timedelta(days=retention_days)
    processed: dict = state.get("processed", {})
    to_delete: list[str] = []
    for item_id, ts in processed.items():
        try:
            parsed = parse_iso_utc(str(ts))
        except Exception:
            to_delete.append(item_id)
            continue
        if parsed < cutoff:
            to_delete.append(item_id)
    for item_id in to_delete:
        processed.pop(item_id, None)
    return len(to_delete)

