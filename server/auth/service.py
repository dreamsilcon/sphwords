"""注册 / 登录 / 找回密码业务逻辑。"""
from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone
from pathlib import Path

from server import config
from server.auth.captcha import verify_captcha
from server.auth.email_rules import is_valid_email, normalize_email
from server.auth.mailer import (
    build_reset_link,
    build_verify_link,
    send_reset_email,
    send_verification_email,
)
from server.auth.passwords import hash_password, validate_password_strength, verify_password
from server.auth.rate_limit import RateLimitExceeded, enforce_and_hit
from server.auth.repository import (
    consume_email_token,
    create_email_token,
    create_session,
    create_user,
    delete_session,
    get_session,
    get_user_by_email,
    get_user_by_id,
    invalidate_tokens,
    mark_user_verified,
    purge_expired,
    set_user_password,
)


class AuthError(Exception):
    pass


def _expires(hours: float) -> str:
    return (
        datetime.now(timezone.utc).astimezone() + timedelta(hours=hours)
    ).isoformat()


def register_user(
    *,
    email: str,
    password: str,
    captcha_id: str,
    captcha_answer: str,
    client_ip: str,
    db_path: Path | None = None,
) -> dict:
    purge_expired(db_path)
    normalized = normalize_email(email)
    if not is_valid_email(normalized):
        raise AuthError("请输入有效的邮箱地址")

    try:
        validate_password_strength(password)
    except ValueError as exc:
        raise AuthError(str(exc)) from exc

    try:
        enforce_and_hit(
            f"register:ip:{client_ip}",
            max_count=config.AUTH_REGISTER_PER_IP_PER_HOUR,
            window_seconds=3600,
            db_path=db_path,
        )
        enforce_and_hit(
            f"register:email:{normalized}",
            max_count=config.AUTH_REGISTER_PER_EMAIL_PER_DAY,
            window_seconds=86400,
            db_path=db_path,
        )
    except RateLimitExceeded as exc:
        raise AuthError(str(exc)) from exc

    if not verify_captcha(captcha_id, captcha_answer, client_ip, db_path):
        raise AuthError("验证码错误或已过期，请刷新后重试")

    existing = get_user_by_email(normalized, db_path)
    if existing:
        if existing["is_verified"]:
            raise AuthError("该邮箱已注册，请直接登录")
        raise AuthError("该邮箱已提交注册，请查收验证邮件或稍后再试")

    password_hash = hash_password(password)
    user_id = create_user(normalized, password_hash, db_path)
    token = secrets.token_urlsafe(32)
    invalidate_tokens(user_id, "verify", db_path)
    create_email_token(
        user_id,
        token,
        "verify",
        _expires(config.AUTH_EMAIL_VERIFY_TTL_HOURS),
        db_path,
    )

    try:
        send_verification_email(normalized, token)
    except Exception as exc:
        raise AuthError(str(exc)) from exc

    verify_link = build_verify_link(token)
    if config.AUTH_USE_SMTP:
        message = "注册成功，验证邮件已发送，请查收邮箱并点击链接完成验证"
    else:
        message = (
            "注册成功。当前为开发模式，不会发送真实邮件，"
            "请直接点击下方验证链接完成邮箱验证"
        )

    result = {
        "email": normalized,
        "message": message,
        "dev_mode": not config.AUTH_USE_SMTP,
    }
    if not config.AUTH_USE_SMTP:
        result["verify_link"] = verify_link
    return result


def verify_email_token(token: str, *, client_ip: str, db_path: Path | None = None) -> dict:
    if not token or len(token) < 20:
        raise AuthError("无效的验证链接")
    try:
        enforce_and_hit(
            f"verify:ip:{client_ip}",
            max_count=config.AUTH_VERIFY_PER_IP_PER_HOUR,
            window_seconds=3600,
            db_path=db_path,
        )
    except RateLimitExceeded as exc:
        raise AuthError(str(exc)) from exc

    row = consume_email_token(token.strip(), "verify", db_path)
    if not row:
        raise AuthError("验证链接无效或已过期")

    user_id = int(row["user_id"])
    mark_user_verified(user_id, db_path)
    user = get_user_by_id(user_id, db_path)
    email = user["email"] if user else ""
    return {"email": email, "message": "邮箱验证成功，可以登录使用"}


def login_user(
    *,
    email: str,
    password: str,
    client_ip: str,
    db_path: Path | None = None,
) -> dict:
    purge_expired(db_path)
    normalized = normalize_email(email)
    if not is_valid_email(normalized):
        raise AuthError("邮箱或密码错误")

    try:
        enforce_and_hit(
            f"login:ip:{client_ip}",
            max_count=config.AUTH_LOGIN_PER_IP_PER_HOUR,
            window_seconds=3600,
            db_path=db_path,
        )
    except RateLimitExceeded as exc:
        raise AuthError(str(exc)) from exc

    user = get_user_by_email(normalized, db_path)
    if not user or not verify_password(password, user["password_hash"]):
        raise AuthError("邮箱或密码错误")
    if not user["is_verified"]:
        raise AuthError("请先完成邮箱验证后再登录")

    session_id = secrets.token_urlsafe(32)
    create_session(
        session_id,
        int(user["id"]),
        _expires(config.AUTH_SESSION_TTL_HOURS),
        client_ip,
        db_path,
    )
    return {"session_id": session_id, "email": normalized}


def logout_user(session_id: str, db_path: Path | None = None) -> None:
    if session_id:
        delete_session(session_id, db_path)


def resolve_session(session_id: str, db_path: Path | None = None) -> dict | None:
    if not session_id:
        return None
    purge_expired(db_path)
    row = get_session(session_id, db_path)
    if not row:
        return None
    user = get_user_by_id(int(row["user_id"]), db_path)
    if not user or not user["is_verified"]:
        return None
    return {"id": int(user["id"]), "email": user["email"]}


def request_password_reset(
    *,
    email: str,
    captcha_id: str,
    captcha_answer: str,
    client_ip: str,
    db_path: Path | None = None,
) -> dict:
    """始终返回成功文案，避免枚举邮箱。"""
    purge_expired(db_path)
    normalized = normalize_email(email)

    if not verify_captcha(captcha_id, captcha_answer, client_ip, db_path):
        raise AuthError("验证码错误或已过期，请刷新后重试")

    generic = {
        "message": "如果该邮箱已注册，我们已发送重置链接（请查收邮件或开发模式日志）",
        "dev_mode": not config.AUTH_USE_SMTP,
    }

    if not is_valid_email(normalized):
        return generic

    try:
        enforce_and_hit(
            f"forgot:email:{normalized}",
            max_count=config.AUTH_FORGOT_PER_EMAIL_PER_HOUR,
            window_seconds=3600,
            db_path=db_path,
        )
        enforce_and_hit(
            f"forgot:ip:{client_ip}",
            max_count=20,
            window_seconds=3600,
            db_path=db_path,
        )
    except RateLimitExceeded as exc:
        raise AuthError(str(exc)) from exc

    user = get_user_by_email(normalized, db_path)
    if not user or not user["is_verified"]:
        return generic

    token = secrets.token_urlsafe(32)
    invalidate_tokens(int(user["id"]), "reset", db_path)
    create_email_token(
        int(user["id"]),
        token,
        "reset",
        _expires(config.AUTH_RESET_TTL_HOURS),
        db_path,
    )
    try:
        send_reset_email(normalized, token)
    except Exception as exc:
        raise AuthError(str(exc)) from exc

    if not config.AUTH_USE_SMTP:
        generic["reset_link"] = build_reset_link(token)
    return generic


def change_password(
    *,
    user_id: int,
    current_password: str,
    new_password: str,
    client_ip: str,
    db_path: Path | None = None,
) -> dict:
    try:
        validate_password_strength(new_password)
    except ValueError as exc:
        raise AuthError(str(exc)) from exc

    try:
        enforce_and_hit(
            f"changepw:ip:{client_ip}",
            max_count=20,
            window_seconds=3600,
            db_path=db_path,
        )
    except RateLimitExceeded as exc:
        raise AuthError(str(exc)) from exc

    user = get_user_by_id(user_id, db_path)
    if not user or not verify_password(current_password, user["password_hash"]):
        raise AuthError("当前密码不正确")
    if current_password == new_password:
        raise AuthError("新密码不能与当前密码相同")

    set_user_password(user_id, hash_password(new_password), db_path)
    return {"message": "密码已更新"}


def reset_password(
    *,
    token: str,
    password: str,
    client_ip: str,
    db_path: Path | None = None,
) -> dict:
    if not token or len(token) < 20:
        raise AuthError("无效的重置链接")
    try:
        validate_password_strength(password)
    except ValueError as exc:
        raise AuthError(str(exc)) from exc

    try:
        enforce_and_hit(
            f"reset:ip:{client_ip}",
            max_count=30,
            window_seconds=3600,
            db_path=db_path,
        )
    except RateLimitExceeded as exc:
        raise AuthError(str(exc)) from exc

    row = consume_email_token(token.strip(), "reset", db_path)
    if not row:
        raise AuthError("重置链接无效或已过期")

    user_id = int(row["user_id"])
    set_user_password(user_id, hash_password(password), db_path)
    invalidate_tokens(user_id, "reset", db_path)
    return {"message": "密码已更新，请使用新密码登录"}
