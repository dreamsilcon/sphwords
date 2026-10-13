"""简单 SQLite 限流。"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from server.db import db_session, now_iso


class RateLimitExceeded(Exception):
    def __init__(self, message: str, retry_after_seconds: int = 60):
        super().__init__(message)
        self.retry_after_seconds = retry_after_seconds


def enforce_and_hit(
    bucket: str,
    *,
    max_count: int,
    window_seconds: int,
    db_path: Path | None = None,
) -> None:
    now = datetime.now(timezone.utc).astimezone()
    with db_session(db_path) as conn:
        row = conn.execute(
            "SELECT count, window_start FROM rate_limits WHERE bucket = ?",
            (bucket,),
        ).fetchone()
        if row is None:
            conn.execute(
                "INSERT INTO rate_limits(bucket, count, window_start) VALUES (?,?,?)",
                (bucket, 1, now_iso()),
            )
            return
        try:
            start = datetime.fromisoformat(row["window_start"])
        except ValueError:
            start = now
        if now - start > timedelta(seconds=window_seconds):
            conn.execute(
                "UPDATE rate_limits SET count = 1, window_start = ? WHERE bucket = ?",
                (now_iso(), bucket),
            )
            return
        if int(row["count"]) >= max_count:
            retry = window_seconds - int((now - start).total_seconds())
            raise RateLimitExceeded(
                "操作过于频繁，请稍后再试",
                retry_after_seconds=max(1, retry),
            )
        conn.execute(
            "UPDATE rate_limits SET count = count + 1 WHERE bucket = ?",
            (bucket,),
        )
