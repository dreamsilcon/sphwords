"""发送验证 / 重置邮件（开发模式写日志）。"""
from __future__ import annotations

import logging
import smtplib
from email.message import EmailMessage

from server import config

logger = logging.getLogger(__name__)


def build_verify_link(token: str) -> str:
    return f"{config.AUTH_BASE_URL}/auth/verify-email?token={token}"


def build_reset_link(token: str) -> str:
    return f"{config.AUTH_BASE_URL}/reset.html?token={token}"


def send_verification_email(to_email: str, token: str) -> None:
    link = build_verify_link(token)
    subject = "SPHWords 邮箱验证"
    body = (
        "你好，\n\n"
        "感谢注册 SPHWords 单词笔记。\n"
        "请点击以下链接完成邮箱验证（24 小时内有效）：\n\n"
        f"{link}\n\n"
        "如非本人操作，请忽略此邮件。\n"
    )
    _send(to_email, subject, body, link)


def send_reset_email(to_email: str, token: str) -> None:
    link = build_reset_link(token)
    subject = "SPHWords 重置密码"
    body = (
        "你好，\n\n"
        "我们收到了重置 SPHWords 密码的请求。\n"
        "请点击以下链接设置新密码（2 小时内有效）：\n\n"
        f"{link}\n\n"
        "如非本人操作，请忽略此邮件。\n"
    )
    _send(to_email, subject, body, link)


def _send(to_email: str, subject: str, body: str, link: str) -> None:
    if not config.AUTH_USE_SMTP:
        _log_dev_email(to_email, subject, body, link)
        return

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = config.AUTH_FROM_EMAIL
    msg["To"] = to_email
    msg.set_content(body)

    try:
        with smtplib.SMTP(
            config.AUTH_SMTP_HOST,
            config.AUTH_SMTP_PORT,
            timeout=30,
        ) as smtp:
            smtp.starttls()
            smtp.login(config.AUTH_SMTP_USER, config.AUTH_SMTP_PASSWORD)
            smtp.send_message(msg)
    except Exception as exc:
        logger.exception("SMTP 发送失败: %s", exc)
        raise RuntimeError("邮件发送失败，请稍后重试") from exc


def _log_dev_email(to_email: str, subject: str, body: str, link: str) -> None:
    log_path = config.AUTH_DEV_EMAIL_LOG
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as f:
        f.write(f"\n--- {subject} -> {to_email} ---\n{body}\n")
    logger.info("DEV 模式链接已写入 %s : %s", log_path, link)
