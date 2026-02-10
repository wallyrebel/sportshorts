from __future__ import annotations

import json
import logging
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import boto3
from botocore.client import Config
from botocore.exceptions import ClientError

LOGGER = logging.getLogger(__name__)

R2_ENDPOINT_DEFAULT = "https://8da6aa93ea04160c27bb21557c54e2b0.r2.cloudflarestorage.com"


class R2Storage:
    def __init__(
        self,
        access_key_id: str,
        secret_access_key: str,
        bucket: str,
        endpoint_url: str = R2_ENDPOINT_DEFAULT,
    ) -> None:
        self.bucket = bucket
        self.endpoint_url = endpoint_url
        self.s3 = boto3.client(
            "s3",
            endpoint_url=endpoint_url,
            aws_access_key_id=access_key_id,
            aws_secret_access_key=secret_access_key,
            region_name="auto",
            config=Config(signature_version="s3v4"),
        )

    def upload_file(self, local_path: Path, key: str, content_type: str = "video/mp4") -> None:
        self.s3.upload_file(
            Filename=str(local_path),
            Bucket=self.bucket,
            Key=key,
            ExtraArgs={"ContentType": content_type},
        )
        LOGGER.info("Uploaded %s to r2://%s/%s", local_path, self.bucket, key)

    def upload_json(self, key: str, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
        self.s3.put_object(
            Bucket=self.bucket,
            Key=key,
            Body=body,
            ContentType="application/json",
        )

    def download_json(self, key: str, default: dict[str, Any]) -> dict[str, Any]:
        try:
            resp = self.s3.get_object(Bucket=self.bucket, Key=key)
        except ClientError as exc:
            code = str(exc.response.get("Error", {}).get("Code", ""))
            if code in {"NoSuchKey", "404"}:
                return default
            raise
        raw = resp["Body"].read()
        return json.loads(raw.decode("utf-8"))

    def presign_get_url(self, key: str, expires_seconds: int = 604800) -> str:
        return self.s3.generate_presigned_url(
            ClientMethod="get_object",
            Params={"Bucket": self.bucket, "Key": key},
            ExpiresIn=expires_seconds,
        )

    def list_objects(self, prefix: str) -> list[dict[str, Any]]:
        paginator = self.s3.get_paginator("list_objects_v2")
        results: list[dict[str, Any]] = []
        for page in paginator.paginate(Bucket=self.bucket, Prefix=prefix):
            for obj in page.get("Contents", []):
                results.append(obj)
        return results

    def delete_objects(self, keys: list[str]) -> int:
        if not keys:
            return 0
        total = 0
        chunk_size = 1000
        for idx in range(0, len(keys), chunk_size):
            part = keys[idx : idx + chunk_size]
            payload = {"Objects": [{"Key": key} for key in part], "Quiet": True}
            resp = self.s3.delete_objects(Bucket=self.bucket, Delete=payload)
            total += len(resp.get("Deleted", []))
        return total

    def delete_videos_older_than(self, retention_days: int, now: datetime | None = None) -> int:
        if retention_days <= 0:
            return 0
        now = now or datetime.now(tz=UTC)
        cutoff = now - timedelta(days=retention_days)
        old_keys: list[str] = []
        for obj in self.list_objects(prefix="videos/"):
            last_modified = obj["LastModified"].astimezone(UTC)
            if last_modified < cutoff:
                old_keys.append(str(obj["Key"]))
        deleted = self.delete_objects(old_keys)
        if deleted:
            LOGGER.info("Deleted %s old R2 objects older than %s days", deleted, retention_days)
        return deleted

