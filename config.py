"""
MealMatrix – Configuration
All secrets are loaded from .env via python-dotenv

Security hardening applied:
  - SECRET_KEY warns loudly if missing (never silently falls back)
  - DEBUG defaults to False (must be explicitly set true in .env)
  - SESSION_COOKIE_SECURE is True when FLASK_ENV=production
  - SESSION_COOKIE_SAMESITE Lax — blocks cross-site POST (basic CSRF mitigation)
  - Safe int parsing for MAIL_PORT and OTP_EXPIRY_MINUTES
"""
import os
import warnings
from datetime import timedelta
from dotenv import load_dotenv

# Load .env from the same directory as this file
load_dotenv(os.path.join(os.path.abspath(os.path.dirname(__file__)), ".env"))


def _parse_int(value: str, name: str, default: int) -> int:
    """Safely parse an integer env var with a clear warning on failure."""
    try:
        return int(value)
    except (ValueError, TypeError):
        warnings.warn(
            f"[MealMatrix] {name}='{value}' is not a valid integer — "
            f"falling back to default: {default}",
            stacklevel=2,
        )
        return default


class Config:
    # ── Core ────────────────────────────────────────────────────────────────
    _secret = os.getenv("SECRET_KEY", "")
    if not _secret:
        warnings.warn(
            "\n⚠️  [MealMatrix] SECRET_KEY is not set in .env — "
            "using an insecure development fallback.\n"
            "   Generate a real key with:  python -c \"import secrets; print(secrets.token_hex(32))\"\n"
            "   and add it to your .env before any public deployment!\n",
            stacklevel=2,
        )
        _secret = "mm-dev-fallback-key-DO-NOT-USE-IN-PROD-" + "x" * 20
    SECRET_KEY = _secret

    # ── Environment ──────────────────────────────────────────────────────────
    FLASK_ENV = os.getenv("FLASK_ENV", "development")
    # ✅  Secure default: DEBUG = False (was previously defaulting to True)
    DEBUG     = os.getenv("FLASK_DEBUG", "false").lower() == "true"

    # ── Database ─────────────────────────────────────────────────────────────
    BASE_DIR = os.path.abspath(os.path.dirname(__file__))
    SQLALCHEMY_DATABASE_URI = (
        os.getenv("DATABASE_URL")
        or f"sqlite:///{os.path.join(BASE_DIR, 'instance', 'mealmatrix.db')}"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_pre_ping": True,   # detect and drop stale connections
        "pool_recycle":  300,    # recycle connections every 5 minutes
    }

    # ── Server-Side Session (filesystem) ────────────────────────────────────
    SESSION_TYPE               = "filesystem"
    SESSION_FILE_DIR           = os.path.join(BASE_DIR, "flask_session")
    SESSION_FILE_THRESHOLD     = 500          # purge oldest files when count exceeds this
    SESSION_PERMANENT          = True
    PERMANENT_SESSION_LIFETIME = timedelta(days=7)
    SESSION_COOKIE_HTTPONLY    = True
    SESSION_COOKIE_SAMESITE    = "Lax"        # ✅ blocks cross-site POST requests (CSRF mitigation)
    # ✅ Secure=True in production (HTTPS only); False in development (HTTP localhost)
    SESSION_COOKIE_SECURE      = os.getenv("FLASK_ENV", "development") == "production"
    SESSION_COOKIE_NAME        = "mm_session"  # unique name avoids collisions

    # ── Rate Limiting (flask-limiter) ────────────────────────────────────────
    # Storage: memory:// for dev; swap to redis://host:port/0 in production
    RATELIMIT_STORAGE_URL     = os.getenv("REDIS_URL", "memory://")
    RATELIMIT_DEFAULT         = "500 per day;100 per hour"
    RATELIMIT_HEADERS_ENABLED = True   # exposes X-RateLimit-* headers

    # ── Twilio (Phone OTP) ───────────────────────────────────────────────────
    TWILIO_ACCOUNT_SID  = os.getenv("TWILIO_ACCOUNT_SID", "")
    TWILIO_AUTH_TOKEN   = os.getenv("TWILIO_AUTH_TOKEN", "")
    TWILIO_PHONE_NUMBER = os.getenv("TWILIO_PHONE_NUMBER", "")

    # ── Email / SMTP ─────────────────────────────────────────────────────────
    MAIL_SERVER         = os.getenv("MAIL_SERVER",  "smtp.gmail.com")
    MAIL_PORT           = _parse_int(os.getenv("MAIL_PORT", "587"), "MAIL_PORT", 587)
    MAIL_USE_TLS        = os.getenv("MAIL_USE_TLS", "true").lower() == "true"
    MAIL_USERNAME       = os.getenv("MAIL_USERNAME", "")
    MAIL_PASSWORD       = os.getenv("MAIL_PASSWORD", "")
    MAIL_DEFAULT_SENDER = os.getenv("MAIL_DEFAULT_SENDER", os.getenv("MAIL_USERNAME", ""))

    # ── OTP Settings ─────────────────────────────────────────────────────────
    OTP_EXPIRY_MINUTES = _parse_int(os.getenv("OTP_EXPIRY_MINUTES", "10"), "OTP_EXPIRY_MINUTES", 10)
