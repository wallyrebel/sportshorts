from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.r2_storage import R2Storage


class FakeS3Presign:
    def __init__(self) -> None:
        self.args = None

    def generate_presigned_url(self, ClientMethod: str, Params: dict, ExpiresIn: int) -> str:
        self.args = (ClientMethod, Params, ExpiresIn)
        return "https://presigned.example.com/file.mp4"


def test_presigned_url_generation_mocked() -> None:
    store = object.__new__(R2Storage)
    store.bucket = "videoshorts"
    store.s3 = FakeS3Presign()
    url = store.presign_get_url("videos/2026/02/10/test.mp4", expires_seconds=123)
    assert url == "https://presigned.example.com/file.mp4"
    method, params, expiry = store.s3.args
    assert method == "get_object"
    assert params["Bucket"] == "videoshorts"
    assert params["Key"] == "videos/2026/02/10/test.mp4"
    assert expiry == 123


def test_delete_videos_older_than_mocked() -> None:
    now = datetime(2026, 2, 10, tzinfo=UTC)
    old = now - timedelta(days=45)
    new = now - timedelta(days=5)
    store = object.__new__(R2Storage)
    store.list_objects = lambda prefix: [  # type: ignore[method-assign]
        {"Key": "videos/old.mp4", "LastModified": old},
        {"Key": "videos/new.mp4", "LastModified": new},
    ]
    deleted_keys: list[str] = []

    def fake_delete(keys: list[str]) -> int:
        deleted_keys.extend(keys)
        return len(keys)

    store.delete_objects = fake_delete  # type: ignore[method-assign]
    removed = store.delete_videos_older_than(retention_days=30, now=now)
    assert removed == 1
    assert deleted_keys == ["videos/old.mp4"]

