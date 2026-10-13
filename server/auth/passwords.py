"""密码哈希（bcrypt）。"""
from __future__ import annotations

import bcrypt

_MIN_PASSWORD_LEN = 8
_MAX_PASSWORD_LEN = 128


def validate_password_strength(password: str) -> None:
    if len(password) < _MIN_PASSWORD_LEN:
        raise ValueError(f"密码至少 {_MIN_PASSWORD_LEN} 位")
    if len(password) > _MAX_PASSWORD_LEN:
        raise ValueError("密码过长")


def hash_password(password: str) -> str:
    validate_password_strength(password)
    salt = bcrypt.gensalt(rounds=12)
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(
            password.encode("utf-8"),
            password_hash.encode("utf-8"),
        )
    except (ValueError, TypeError):
        return False
