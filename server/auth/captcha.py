"""图形验证码（SVG）。"""
from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from pathlib import Path

from server import config
from server.auth.repository import consume_captcha, create_captcha_challenge

_CHARS = "23456789ABCDEFGHJKMNPQRSTUVWXYZ"


def _hash_answer(captcha_id: str, answer: str) -> str:
    normalized = answer.strip().upper()
    payload = f"{captcha_id}:{normalized}".encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def issue_captcha(client_ip: str, db_path: Path | None = None) -> tuple[str, str]:
    text = "".join(secrets.choice(_CHARS) for _ in range(5))
    captcha_id = secrets.token_urlsafe(18)
    answer_hash = _hash_answer(captcha_id, text)
    expires = (
        datetime.now(timezone.utc).astimezone()
        + timedelta(seconds=config.AUTH_CAPTCHA_TTL_SECONDS)
    ).isoformat()
    create_captcha_challenge(captcha_id, answer_hash, expires, client_ip, db_path)
    return captcha_id, render_svg_captcha(text)


def verify_captcha(
    captcha_id: str,
    answer: str,
    client_ip: str,
    db_path: Path | None = None,
) -> bool:
    if not captcha_id or not answer:
        return False
    expected_hash = _hash_answer(captcha_id, answer)
    return consume_captcha(captcha_id, expected_hash, client_ip, db_path)


def render_svg_captcha(text: str) -> str:
    w, h = 160, 52
    lines = []
    rng = secrets.SystemRandom()
    for _ in range(6):
        x1, y1 = rng.randint(0, w), rng.randint(0, h)
        x2, y2 = rng.randint(0, w), rng.randint(0, h)
        color = f"#{rng.randint(80, 180):02x}{rng.randint(80, 180):02x}{rng.randint(80, 180):02x}"
        lines.append(
            f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{color}" stroke-width="1.2"/>'
        )
    chars = []
    for i, ch in enumerate(text):
        x = 18 + i * 26
        y = 34 + rng.randint(-4, 4)
        rotate = rng.randint(-18, 18)
        fill = f"#{rng.randint(20, 80):02x}{rng.randint(20, 80):02x}{rng.randint(20, 80):02x}"
        chars.append(
            f'<text x="{x}" y="{y}" fill="{fill}" font-size="26" font-family="monospace" '
            f'font-weight="700" transform="rotate({rotate} {x} {y})">{ch}</text>'
        )
    noise = []
    for _ in range(40):
        cx, cy = rng.randint(0, w), rng.randint(0, h)
        noise.append(f'<circle cx="{cx}" cy="{cy}" r="1" fill="#999"/>')
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">'
        f'<rect width="100%" height="100%" fill="#f4f4f5"/>'
        + "".join(lines)
        + "".join(noise)
        + "".join(chars)
        + "</svg>"
    )
