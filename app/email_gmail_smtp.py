from __future__ import annotations

import logging
import smtplib
from datetime import UTC, datetime
from email.message import EmailMessage

from app.models import VideoResult

LOGGER = logging.getLogger(__name__)


class GmailSender:
    def __init__(
        self,
        host: str,
        port: int,
        user: str,
        password: str,
        to_address: str,
        mode: str = "digest",
    ) -> None:
        self.host = host
        self.port = port
        self.user = user
        self.password = password
        self.to_address = to_address
        self.mode = mode

    def send(self, videos: list[VideoResult], always_email: bool = False) -> int:
        if not videos and not always_email:
            LOGGER.info("No clips created; email suppressed because ALWAYS_EMAIL=false.")
            return 0

        if self.mode == "per_clip":
            return self._send_per_clip(videos=videos, always_email=always_email)
        return self._send_digest(videos=videos, always_email=always_email)

    def _send_digest(self, videos: list[VideoResult], always_email: bool) -> int:
        now = datetime.now(tz=UTC).strftime("%Y-%m-%d %H:%M UTC")
        subject = f"AutoSportsVideo digest - {len(videos)} new clip(s) - {now}"
        lines: list[str] = [f"AutoSportsVideo run at {now}", ""]
        if videos:
            for idx, item in enumerate(videos, start=1):
                lines.extend(
                    [
                        f"{idx}. {item.title}",
                        f"   Feed: {item.feed_name}",
                        f"   Published: {item.published or 'unknown'}",
                        f"   Source: {item.source_link or 'N/A'}",
                        f"   Presigned URL: {item.presigned_url}",
                        "",
                    ]
                )
        else:
            lines.append("No new clips were created in this run.")
            lines.append("")
            if always_email:
                lines.append("ALWAYS_EMAIL=true forced this notification.")
                lines.append("")

        body = "\n".join(lines)
        self._send_email(subject=subject, body=body)
        return 1

    def _send_per_clip(self, videos: list[VideoResult], always_email: bool) -> int:
        if not videos:
            if always_email:
                self._send_email(
                    subject="AutoSportsVideo - no new clips",
                    body="No new clips were created in this run.",
                )
                return 1
            return 0
        count = 0
        for item in videos:
            body = "\n".join(
                [
                    f"Title: {item.title}",
                    f"Feed: {item.feed_name}",
                    f"Published: {item.published or 'unknown'}",
                    f"Source: {item.source_link or 'N/A'}",
                    f"Presigned URL: {item.presigned_url}",
                ]
            )
            self._send_email(
                subject=f"AutoSportsVideo clip: {item.title[:90]}",
                body=body,
            )
            count += 1
        return count

    def _send_email(self, subject: str, body: str) -> None:
        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = self.user
        msg["To"] = self.to_address
        msg.set_content(body)

        with smtplib.SMTP(self.host, self.port, timeout=30) as server:
            server.ehlo()
            server.starttls()
            server.ehlo()
            server.login(self.user, self.password)
            server.send_message(msg)
        LOGGER.info("Email sent to %s with subject '%s'", self.to_address, subject)

