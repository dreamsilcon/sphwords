"""SPHWords server config (WSL / local first)."""
from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.environ.get("SPHWORDS_DATA_DIR", ROOT / "data"))
LOG_DIR = Path(os.environ.get("SPHWORDS_LOG_DIR", ROOT / "logs"))
DB_PATH = Path(os.environ.get("SPHWORDS_DB_PATH", DATA_DIR / "sphwords.db"))

AUTH_BASE_URL = os.environ.get("SPHWORDS_BASE_URL", "http://127.0.0.1:8787").rstrip("/")
# Cookie path follows URL prefix, e.g. http://host/sphwords → /sphwords
try:
    from urllib.parse import urlparse

    _path = urlparse(AUTH_BASE_URL).path.rstrip("/")
    AUTH_COOKIE_PATH = _path if _path else "/"
except Exception:
    AUTH_COOKIE_PATH = "/"
# Public URL prefix for links in emails / server-rendered HTML, e.g. "/sphwords"
AUTH_URL_PREFIX = "" if AUTH_COOKIE_PATH == "/" else AUTH_COOKIE_PATH
AUTH_SESSION_COOKIE_NAME = "sphwords_session"
AUTH_SESSION_TTL_HOURS = int(os.environ.get("SPHWORDS_SESSION_TTL_HOURS", "720"))
AUTH_EMAIL_VERIFY_TTL_HOURS = 24
AUTH_RESET_TTL_HOURS = 2
AUTH_CAPTCHA_TTL_SECONDS = 300

AUTH_REGISTER_PER_IP_PER_HOUR = 10
AUTH_REGISTER_PER_EMAIL_PER_DAY = 5
AUTH_LOGIN_PER_IP_PER_HOUR = 60
AUTH_VERIFY_PER_IP_PER_HOUR = 40
AUTH_FORGOT_PER_EMAIL_PER_HOUR = 5

AUTH_USE_SMTP = os.environ.get("SPHWORDS_USE_SMTP", "").lower() in ("1", "true", "yes")
AUTH_SMTP_HOST = os.environ.get("SPHWORDS_SMTP_HOST", "smtp.gmail.com")
AUTH_SMTP_PORT = int(os.environ.get("SPHWORDS_SMTP_PORT", "587"))
AUTH_SMTP_USER = os.environ.get("SPHWORDS_SMTP_USER", "")
AUTH_SMTP_PASSWORD = os.environ.get("SPHWORDS_SMTP_PASSWORD", "")
AUTH_FROM_EMAIL = os.environ.get("SPHWORDS_FROM_EMAIL", AUTH_SMTP_USER or "noreply@sphwords.local")
AUTH_DEV_EMAIL_LOG = LOG_DIR / "auth_emails.log"

AUTH_COOKIE_SECURE = os.environ.get("SPHWORDS_COOKIE_SECURE", "").lower() in ("1", "true", "yes")

STATIC_ROOT = ROOT
