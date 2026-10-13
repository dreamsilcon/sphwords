"""Auth + drill persistence."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from server.db import (
    db_session,
    default_drill_payload,
    dumps_payload,
    loads_payload,
    now_iso,
    row_to_dict,
)


def create_user(email: str, password_hash: str, db_path: Path | None = None) -> int:
    with db_session(db_path) as conn:
        cur = conn.execute(
            "INSERT INTO users(email, password_hash, is_verified, created_at) VALUES (?,?,0,?)",
            (email, password_hash, now_iso()),
        )
        return int(cur.lastrowid)


def get_user_by_email(email: str, db_path: Path | None = None) -> dict[str, Any] | None:
    with db_session(db_path) as conn:
        row = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        return row_to_dict(row)


def get_user_by_id(user_id: int, db_path: Path | None = None) -> dict[str, Any] | None:
    with db_session(db_path) as conn:
        row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        return row_to_dict(row)


def mark_user_verified(user_id: int, db_path: Path | None = None) -> None:
    with db_session(db_path) as conn:
        conn.execute("UPDATE users SET is_verified = 1 WHERE id = ?", (user_id,))


def set_user_password(user_id: int, password_hash: str, db_path: Path | None = None) -> None:
    with db_session(db_path) as conn:
        conn.execute(
            "UPDATE users SET password_hash = ? WHERE id = ?",
            (password_hash, user_id),
        )


def invalidate_tokens(user_id: int, purpose: str | None = None, db_path: Path | None = None) -> None:
    with db_session(db_path) as conn:
        if purpose:
            conn.execute(
                "DELETE FROM email_tokens WHERE user_id = ? AND purpose = ?",
                (user_id, purpose),
            )
        else:
            conn.execute("DELETE FROM email_tokens WHERE user_id = ?", (user_id,))


def create_email_token(
    user_id: int,
    token: str,
    purpose: str,
    expires_at: str,
    db_path: Path | None = None,
) -> None:
    with db_session(db_path) as conn:
        conn.execute(
            "INSERT INTO email_tokens(token, user_id, purpose, expires_at, created_at) VALUES (?,?,?,?,?)",
            (token, user_id, purpose, expires_at, now_iso()),
        )


def consume_email_token(
    token: str,
    purpose: str,
    db_path: Path | None = None,
) -> dict[str, Any] | None:
    with db_session(db_path) as conn:
        row = conn.execute(
            "SELECT * FROM email_tokens WHERE token = ? AND purpose = ?",
            (token, purpose),
        ).fetchone()
        if not row:
            return None
        data = row_to_dict(row)
        assert data is not None
        conn.execute("DELETE FROM email_tokens WHERE token = ?", (token,))
        # expire check
        try:
            from datetime import datetime

            if datetime.fromisoformat(data["expires_at"]) < datetime.now().astimezone():
                return None
        except ValueError:
            return None
        return data


def create_session(
    session_id: str,
    user_id: int,
    expires_at: str,
    client_ip: str,
    db_path: Path | None = None,
) -> None:
    with db_session(db_path) as conn:
        conn.execute(
            "INSERT INTO sessions(session_id, user_id, expires_at, client_ip, created_at) VALUES (?,?,?,?,?)",
            (session_id, user_id, expires_at, client_ip, now_iso()),
        )


def delete_session(session_id: str, db_path: Path | None = None) -> None:
    with db_session(db_path) as conn:
        conn.execute("DELETE FROM sessions WHERE session_id = ?", (session_id,))


def get_session(session_id: str, db_path: Path | None = None) -> dict[str, Any] | None:
    with db_session(db_path) as conn:
        row = conn.execute(
            "SELECT * FROM sessions WHERE session_id = ?",
            (session_id,),
        ).fetchone()
        if not row:
            return None
        data = row_to_dict(row)
        assert data is not None
        try:
            from datetime import datetime

            if datetime.fromisoformat(data["expires_at"]) < datetime.now().astimezone():
                conn.execute("DELETE FROM sessions WHERE session_id = ?", (session_id,))
                return None
        except ValueError:
            return None
        return data


def create_captcha_challenge(
    captcha_id: str,
    answer_hash: str,
    expires_at: str,
    client_ip: str,
    db_path: Path | None = None,
) -> None:
    with db_session(db_path) as conn:
        conn.execute(
            "INSERT INTO captcha_challenges(captcha_id, answer_hash, expires_at, client_ip, created_at) VALUES (?,?,?,?,?)",
            (captcha_id, answer_hash, expires_at, client_ip, now_iso()),
        )


def consume_captcha(
    captcha_id: str,
    expected_hash: str,
    client_ip: str,
    db_path: Path | None = None,
) -> bool:
    with db_session(db_path) as conn:
        row = conn.execute(
            "SELECT * FROM captcha_challenges WHERE captcha_id = ?",
            (captcha_id,),
        ).fetchone()
        if not row:
            return False
        conn.execute("DELETE FROM captcha_challenges WHERE captcha_id = ?", (captcha_id,))
        try:
            from datetime import datetime

            if datetime.fromisoformat(row["expires_at"]) < datetime.now().astimezone():
                return False
        except ValueError:
            return False
        if row["answer_hash"] != expected_hash:
            return False
        # IP soft-check: allow if missing
        if row["client_ip"] and client_ip and row["client_ip"] != client_ip:
            # still accept — mobile proxies change IP; hash match is enough
            pass
        return True


def purge_expired(db_path: Path | None = None) -> None:
    with db_session(db_path) as conn:
        now = now_iso()
        conn.execute("DELETE FROM sessions WHERE expires_at < ?", (now,))
        conn.execute("DELETE FROM email_tokens WHERE expires_at < ?", (now,))
        conn.execute("DELETE FROM captcha_challenges WHERE expires_at < ?", (now,))


def get_drill_state(user_id: int, db_path: Path | None = None) -> dict[str, Any]:
    with db_session(db_path) as conn:
        row = conn.execute(
            "SELECT payload_json FROM drill_state WHERE user_id = ?",
            (user_id,),
        ).fetchone()
        if not row:
            payload = default_drill_payload()
            conn.execute(
                "INSERT INTO drill_state(user_id, payload_json, updated_at) VALUES (?,?,?)",
                (user_id, dumps_payload(payload), now_iso()),
            )
            return payload
        try:
            return loads_payload(row["payload_json"])
        except (ValueError, TypeError, json.JSONDecodeError):
            return default_drill_payload()


def save_drill_state(user_id: int, payload: dict[str, Any], db_path: Path | None = None) -> dict[str, Any]:
    payload = dict(payload)
    payload["updatedAt"] = now_iso()
    with db_session(db_path) as conn:
        conn.execute(
            """
            INSERT INTO drill_state(user_id, payload_json, updated_at) VALUES (?,?,?)
            ON CONFLICT(user_id) DO UPDATE SET
              payload_json = excluded.payload_json,
              updated_at = excluded.updated_at
            """,
            (user_id, dumps_payload(payload), payload["updatedAt"]),
        )
    return payload
