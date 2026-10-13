"""SQLite schema and helpers."""
from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from server import config


def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def connect(db_path: Path | None = None) -> sqlite3.Connection:
    path = Path(db_path or config.DB_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


@contextmanager
def db_session(db_path: Path | None = None) -> Iterator[sqlite3.Connection]:
    conn = connect(db_path)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db(db_path: Path | None = None) -> None:
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    config.LOG_DIR.mkdir(parents=True, exist_ok=True)
    with db_session(db_path) as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              email TEXT NOT NULL UNIQUE,
              password_hash TEXT NOT NULL,
              is_verified INTEGER NOT NULL DEFAULT 0,
              created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS sessions (
              session_id TEXT PRIMARY KEY,
              user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
              expires_at TEXT NOT NULL,
              client_ip TEXT,
              created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS email_tokens (
              token TEXT PRIMARY KEY,
              user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
              purpose TEXT NOT NULL,
              expires_at TEXT NOT NULL,
              created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS captcha_challenges (
              captcha_id TEXT PRIMARY KEY,
              answer_hash TEXT NOT NULL,
              expires_at TEXT NOT NULL,
              client_ip TEXT,
              created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS rate_limits (
              bucket TEXT PRIMARY KEY,
              count INTEGER NOT NULL,
              window_start TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS drill_state (
              user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
              payload_json TEXT NOT NULL,
              updated_at TEXT NOT NULL
            );
            """
        )


def row_to_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    if row is None:
        return None
    return dict(row)


def now_iso() -> str:
    return _now_iso()


def default_drill_payload() -> dict[str, Any]:
    return {
        "source": "chapter",
        "lists": [{"id": "default", "name": "默认不熟", "ids": []}],
        "activeListId": "default",
        "viewListId": "default",
        "sourceListId": "default",
        "updatedAt": now_iso(),
    }


def dumps_payload(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def loads_payload(raw: str) -> dict[str, Any]:
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise ValueError("invalid payload")
    return data
