from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.state import load_state, mark_processed, prune_state_by_retention, save_state


class FakeR2:
    def __init__(self, initial: dict | None = None) -> None:
        self.initial = initial
        self.uploaded: dict | None = None

    def download_json(self, key: str, default: dict) -> dict:
        return self.initial if self.initial is not None else default

    def upload_json(self, key: str, payload: dict) -> None:
        self.uploaded = {"key": key, "payload": payload}


def test_state_load_and_save_mocked() -> None:
    fake = FakeR2()
    state = load_state(fake)
    mark_processed(state, "item-1", "2026-01-01T00:00:00+00:00")
    save_state(fake, state)
    assert fake.uploaded is not None
    assert fake.uploaded["key"] == "state/processed.json"
    assert "item-1" in fake.uploaded["payload"]["processed"]


def test_prune_state_by_retention() -> None:
    now = datetime(2026, 2, 10, tzinfo=UTC)
    old_ts = (now - timedelta(days=31)).isoformat()
    new_ts = (now - timedelta(days=5)).isoformat()
    state = {"processed": {"old": old_ts, "new": new_ts}}
    pruned = prune_state_by_retention(state, retention_days=30, now=now)
    assert pruned == 1
    assert "old" not in state["processed"]
    assert "new" in state["processed"]

