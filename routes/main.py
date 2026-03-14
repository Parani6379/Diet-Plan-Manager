"""
MealMatrix – Main / General Routes
====================================
Serves the static frontend and provides general API endpoints.
Access at: http://127.0.0.1:5000

Security improvements:
  - Path traversal protection on /pages/ and /src/ routes
  - Improved newsletter email validation (regex-based)
  - Rate limit on newsletter subscription to prevent spam
"""
import os
import re
from functools import wraps
from flask import (
    Blueprint, send_from_directory,
    session, jsonify, request, current_app, abort,
)
from extensions import db, limiter
from models import WeeklyPlan, UserProfile
import datetime
import json

main_bp = Blueprint("main", __name__)

# Absolute path to the frontend root (one level above /backend)
FRONTEND_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

_EMAIL_RE = re.compile(r"^[^@\s]{1,64}@[^@\s]{1,255}\.[^@\s]{1,64}$")


# ── Auth guard ────────────────────────────────────────────────────────────────

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("user_id"):
            return jsonify({"success": False, "message": "Login required."}), 401
        return f(*args, **kwargs)
    return decorated


# ── Safe file sender (prevents path traversal) ────────────────────────────────

def _safe_send(directory: str, filename: str):
    """
    Safely serve a file from `directory`, rejecting any path that contains
    '..' or tries to escape the target directory (path traversal protection).
    """
    # Resolve the absolute path and ensure it stays within the intended directory
    safe_dir  = os.path.realpath(directory)
    full_path = os.path.realpath(os.path.join(directory, filename))
    if not full_path.startswith(safe_dir + os.sep) and full_path != safe_dir:
        abort(403)    # Forbidden — path traversal attempt
    if not os.path.isfile(full_path):
        abort(404)
    return send_from_directory(directory, filename)


# ── Frontend page routes ──────────────────────────────────────────────────────

@main_bp.route("/")
@main_bp.route("/index.html")
def home():
    return send_from_directory(FRONTEND_ROOT, "index.html")


@main_bp.route("/pages/<path:filename>")
def pages(filename):
    pages_dir = os.path.join(FRONTEND_ROOT, "pages")
    return _safe_send(pages_dir, filename)   # ✅ Path traversal protected


@main_bp.route("/src/<path:filename>")
def src_files(filename):
    src_dir = os.path.join(FRONTEND_ROOT, "src")
    return _safe_send(src_dir, filename)     # ✅ Path traversal protected


@main_bp.route("/docs/<path:filename>")
def docs(filename):
    docs_dir = os.path.join(FRONTEND_ROOT, "docs")
    return _safe_send(docs_dir, filename)    # ✅ Path traversal protected


# ── Protected API endpoints ───────────────────────────────────────────────────

@main_bp.route("/api/dashboard", methods=["GET"])
@login_required
def dashboard():
    user_id = session.get("user_id")
    
    # 1. Fetch Weekly Plan
    wp = WeeklyPlan.query.filter_by(user_id=user_id).first()
    plan_data = {}
    if wp and wp.plan_json:
        try:
            plan_data = json.loads(wp.plan_json)
        except:
            plan_data = {}

    # 2. Calculate Streak
    streak = 0
    if plan_data:
        DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        today_name = datetime.datetime.now().strftime("%A")
        
        try:
            today_idx = DAYS.index(today_name)
            # Reorder days to start from today and go backwards
            # e.g. if today is Wed (2): [Wed, Tue, Mon, Sun, Sat, Fri, Thu]
            check_days = [DAYS[(today_idx - i) % 7] for i in range(7)]
            
            for day in check_days:
                if plan_data.get(day, {}).get("done") is True:
                    streak += 1
                else:
                    break
        except ValueError:
            pass

    return jsonify({
        "success": True,
        "message": "Welcome to your MealMatrix dashboard!",
        "data": {
            "plans":  plan_data,
            "streak": streak,
            "tip":    "Keep up the great work and stay consistent!",
        },
    })


@main_bp.route("/api/subscribe-newsletter", methods=["POST"])
@limiter.limit("5 per hour")    # ✅ Prevents newsletter spam
def subscribe_newsletter():
    data  = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    # ✅ Proper regex validation (replaces the weak "@ not in email" check)
    if not email or not _EMAIL_RE.match(email):
        return jsonify({"success": False, "message": "A valid email address is required."}), 400
    current_app.logger.info("[Newsletter] New subscriber: %s", email)
    return jsonify({"success": True, "message": "Subscribed successfully!"}), 200


@main_bp.route("/api/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "app": "MealMatrix"}), 200
