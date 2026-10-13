"""邮箱格式校验：任意合法邮箱（不限 Gmail）。"""
from __future__ import annotations

import re

# Practical email check: local@domain with a dot in domain. Not full RFC 5322.
_EMAIL_RE = re.compile(
    r"^[a-z0-9](?:[a-z0-9._%+\-]{0,62}[a-z0-9])?"
    r"@"
    r"[a-z0-9](?:[a-z0-9\-]{0,61}[a-z0-9])?"
    r"(?:\.[a-z0-9](?:[a-z0-9\-]{0,61}[a-z0-9])?)+$"
)


def normalize_email(email: str) -> str:
    return email.strip().lower()


def is_valid_email(email: str) -> bool:
    normalized = normalize_email(email)
    if len(normalized) < 5 or len(normalized) > 254:
        return False
    if ".." in normalized or normalized.startswith(".") or normalized.endswith("."):
        return False
    return bool(_EMAIL_RE.match(normalized))
