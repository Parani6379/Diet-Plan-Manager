"""
MealMatrix – Shared Flask Extensions
Defined here to avoid circular imports between app.py and other modules.

flask-limiter is loaded optionally — if not yet installed, a no-op shim is
used so the server still boots. Install later with:
    pip install flask-limiter
"""
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

# ── Rate Limiter (optional until flask-limiter is installed) ──────────────────
try:
    from flask_limiter import Limiter
    from flask_limiter.util import get_remote_address

    limiter = Limiter(
        key_func=get_remote_address,
        default_limits=["500 per day", "100 per hour"],
        headers_enabled=True,
    )
    LIMITER_AVAILABLE = True

except ImportError:
    # No-op shim: limiter.limit() becomes a pass-through decorator
    import warnings
    warnings.warn(
        "\n[MealMatrix] flask-limiter is not installed — rate limiting is DISABLED.\n"
        "Install it with:  pip install flask-limiter\n",
        stacklevel=2,
    )

    class _NoOpLimiter:
        """Minimal stub that satisfies @limiter.limit(...) decorators."""
        def limit(self, *args, **kwargs):
            def decorator(f):
                return f
            return decorator

        def init_app(self, app):
            pass   # nothing to initialise

    limiter = _NoOpLimiter()
    LIMITER_AVAILABLE = False
