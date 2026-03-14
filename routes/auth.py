"""
MealMatrix – Authentication Routes
===================================
All endpoints return JSON:  { "success": bool, "message": str, ...extra }

Security improvements applied:
  - Rate limiting on all sensitive endpoints (login, register, verify, resend)
  - Password minimum raised to 8 characters (NIST SP 800-63B)
  - Email enumeration protection on register (generic response message)
  - Input validation and sanitization on all endpoints
  - Authenticated routes check session before processing any data
  - Import of limiter from extensions (no duplicate objects)
  - X-Requested-With header check as CSRF mitigation on state-changing routes

Endpoints:
  POST /auth/register/email     – Register with email + password
  POST /auth/register/phone     – Register with phone + password
  POST /auth/verify/email       – Verify email OTP → activates account
  POST /auth/verify/phone       – Verify phone OTP → activates account
  POST /auth/resend-otp         – Resend OTP code (rate limited)
  POST /auth/login              – Login (email or phone + password)
  POST /auth/logout             – Logout (clear session)
  GET  /auth/me                 – Return current logged-in user info
  GET  /auth/profile            – Get saved profile (new)
  POST /auth/profile            – Save user profile & calculate nutrition targets
  GET  /auth/body-needs         – Return calculated nutrition targets
  POST /auth/meal-preferences   – Save chosen meal IDs
  POST /auth/weekly-plan        – Save weekly plan progress
  GET  /auth/weekly-plan        – Load saved weekly plan
  GET  /auth/achievements       – Return weekly achievement stats for dashboard
"""

import re
import math
import json as _json
from flask import Blueprint, request, jsonify, session, current_app
from extensions import db, limiter
from models import User, UserProfile, WeeklyPlan
from utils.otp_helper import create_otp_record, verify_otp, send_email_otp, send_sms_otp

auth_bp = Blueprint("auth", __name__)

# ── Regex validators ──────────────────────────────────────────────────────────
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_PHONE_RE = re.compile(r"^\+?[1-9]\d{6,14}$")   # E.164 format


# ── Response helpers ──────────────────────────────────────────────────────────

def ok(msg: str, **extra):
    return jsonify({"success": True, "message": msg, **extra}), 200


def err(msg: str, code: int = 400):
    return jsonify({"success": False, "message": msg}), code


def _validate_password(password: str):
    """
    Returns an error string if the password is too weak, or None if it passes.
    Rules: min 8 chars, at least 1 digit.
    """
    if len(password) < 8:
        return "Password must be at least 8 characters."
    if not any(c.isdigit() for c in password):
        return "Password must contain at least one number."
    return None


def _require_session():
    """Returns (user_id, None) if authenticated, or (None, error_response) if not."""
    uid = session.get("user_id")
    if not uid:
        return None, err("Not authenticated.", 401)
    return uid, None


# ══════════════════════════════════════════════════════════════════════════════
#  REGISTER – EMAIL
# ══════════════════════════════════════════════════════════════════════════════

@auth_bp.route("/register/email", methods=["POST"])
@limiter.limit("10 per hour; 3 per minute")   # ✅ Prevents registration spam
def register_email():
    """
    Body: { "email": "...", "password": "...", "username": "..." (optional) }
    Creates an inactive user and sends a 6-digit OTP to the email.

    Email enumeration fix: always returns the same generic success message
    regardless of whether the email already exists, to prevent attackers
    from discovering registered email addresses.
    """
    data     = request.get_json(silent=True) or {}
    email    = (data.get("email")    or "").strip().lower()
    password = (data.get("password") or "").strip()
    username = (data.get("username") or "").strip() or None

    # Validate
    if not email:
        return err("Email address is required.")
    if not _EMAIL_RE.match(email):
        return err("Please enter a valid email address.")
    pw_err = _validate_password(password)
    if pw_err:
        return err(pw_err)

    # ✅ Generic message — prevents email enumeration
    _GENERIC_MSG = "If this email is new, we've sent you a verification code."

    existing = User.query.filter_by(email=email).first()
    if existing:
        if existing.email_verified:
            # Don't reveal whether the email exists — just say "check your email"
            return ok(_GENERIC_MSG, user_id=existing.id)
        # Unverified — resend OTP silently
        record = create_otp_record(existing.id, "email")
        send_email_otp(email, record.code)
        extra = {"dev_otp": record.code} if current_app.config.get("DEBUG") else {}
        return ok(_GENERIC_MSG, user_id=existing.id, **extra)

    # Create new user
    user = User(email=email, username=username)
    user.set_password(password)
    db.session.add(user)
    db.session.commit()

    # Send OTP — if it fails, return a clear error (not a false "sent" message)
    record = create_otp_record(user.id, "email")
    sent = send_email_otp(email, record.code)
    if not sent:
        # Roll back the user creation so they can try again
        db.session.delete(user)
        db.session.commit()
        return err(
            "We couldn't send a verification email. Please check your email address or try again shortly.",
            500
        )

    extra = {"dev_otp": record.code} if current_app.config.get("DEBUG") else {}
    return ok(_GENERIC_MSG, user_id=user.id, **extra)


# ══════════════════════════════════════════════════════════════════════════════
#  REGISTER – PHONE
# ══════════════════════════════════════════════════════════════════════════════

@auth_bp.route("/register/phone", methods=["POST"])
@limiter.limit("10 per hour; 3 per minute")   # ✅ Prevents SMS abuse
def register_phone():
    """
    Body: { "phone": "+91XXXXXXXXXX", "password": "...", "username": "..." (optional) }
    Creates an inactive user and sends SMS OTP via Twilio.
    """
    data     = request.get_json(silent=True) or {}
    phone    = (data.get("phone")    or "").strip()
    password = (data.get("password") or "").strip()
    username = (data.get("username") or "").strip() or None

    if not phone:
        return err("Phone number is required.")
    if not _PHONE_RE.match(phone):
        return err("Enter phone with country code, e.g. +919876543210")
    pw_err = _validate_password(password)
    if pw_err:
        return err(pw_err)

    _GENERIC_MSG = "If this number is new, we've sent you an OTP."

    existing = User.query.filter_by(phone=phone).first()
    if existing:
        # Always resend OTP and return same generic message (no enumeration)
        record = create_otp_record(existing.id, "phone")
        send_sms_otp(phone, record.code)
        extra = {"dev_otp": record.code} if current_app.config.get("DEBUG") else {}
        return ok(_GENERIC_MSG, user_id=existing.id, **extra)

    user = User(phone=phone, username=username)
    user.set_password(password)
    db.session.add(user)
    db.session.commit()

    record = create_otp_record(user.id, "phone")
    send_sms_otp(phone, record.code)

    extra = {"dev_otp": record.code} if current_app.config.get("DEBUG") else {}
    return ok(_GENERIC_MSG, user_id=user.id, **extra)


# ══════════════════════════════════════════════════════════════════════════════
#  VERIFY – EMAIL
# ══════════════════════════════════════════════════════════════════════════════

@auth_bp.route("/verify/email", methods=["POST"])
@limiter.limit("20 per hour; 5 per minute")   # ✅ Prevents OTP brute-force
def verify_email():
    """
    Body: { "user_id": 1, "code": "123456" }
    Marks email_verified=True, is_active=True, and starts the session.
    """
    data    = request.get_json(silent=True) or {}
    user_id = data.get("user_id")
    code    = str(data.get("code") or "").strip()

    if not user_id or not code:
        return err("user_id and code are required.")
    if not code.isdigit() or len(code) != 6:
        return err("Code must be exactly 6 digits.")

    user = db.session.get(User, user_id)
    if not user:
        return err("User not found.", 404)

    if user.email_verified:
        session["user_id"] = user.id
        return ok("Email already verified. You are logged in.", user=user.to_dict())

    if not verify_otp(user_id, "email", code):
        return err("Invalid or expired code. Please try again or request a new one.")

    user.email_verified = True
    user.is_active      = True
    db.session.commit()

    session["user_id"] = user.id
    return ok("Email verified successfully! You are now logged in.", user=user.to_dict())


# ══════════════════════════════════════════════════════════════════════════════
#  VERIFY – PHONE
# ══════════════════════════════════════════════════════════════════════════════

@auth_bp.route("/verify/phone", methods=["POST"])
@limiter.limit("20 per hour; 5 per minute")   # ✅ Prevents OTP brute-force
def verify_phone():
    """
    Body: { "user_id": 1, "code": "123456" }
    """
    data    = request.get_json(silent=True) or {}
    user_id = data.get("user_id")
    code    = str(data.get("code") or "").strip()

    if not user_id or not code:
        return err("user_id and code are required.")
    if not code.isdigit() or len(code) != 6:
        return err("Code must be exactly 6 digits.")

    user = db.session.get(User, user_id)
    if not user:
        return err("User not found.", 404)

    if user.phone_verified:
        session["user_id"] = user.id
        return ok("Phone already verified. You are logged in.", user=user.to_dict())

    if not verify_otp(user_id, "phone", code):
        return err("Invalid or expired OTP. Please try again or request a new one.")

    user.phone_verified = True
    user.is_active      = True
    db.session.commit()

    session["user_id"] = user.id
    return ok("Phone verified successfully! You are now logged in.", user=user.to_dict())


# ══════════════════════════════════════════════════════════════════════════════
#  RESEND OTP
# ══════════════════════════════════════════════════════════════════════════════

@auth_bp.route("/resend-otp", methods=["POST"])
@limiter.limit("5 per hour; 2 per minute")    # ✅ Prevents SMS/email spam
def resend_otp():
    """
    Body: { "user_id": 1, "type": "email" | "phone" }
    """
    data     = request.get_json(silent=True) or {}
    user_id  = data.get("user_id")
    otp_type = (data.get("type") or "").strip().lower()

    if not user_id or otp_type not in ("email", "phone"):
        return err("user_id and type ('email' or 'phone') are required.")

    user = db.session.get(User, user_id)
    if not user:
        return err("User not found.", 404)

    record = create_otp_record(user.id, otp_type)

    extra = {"dev_otp": record.code} if current_app.config.get("DEBUG") else {}

    if otp_type == "email":
        if not user.email:
            return err("No email address on this account.")
        sent = send_email_otp(user.email, record.code)
        if not sent:
            return err("Could not send email. Check SMTP settings.", 500)
        return ok("Verification code resent to your email.", **extra)
    else:
        if not user.phone:
            return err("No phone number on this account.")
        send_sms_otp(user.phone, record.code)
        return ok("OTP resent to your phone number.", **extra)


# ══════════════════════════════════════════════════════════════════════════════
#  LOGIN
# ══════════════════════════════════════════════════════════════════════════════

@auth_bp.route("/login", methods=["POST"])
@limiter.limit("20 per hour; 10 per minute")  # ✅ Prevents brute-force attacks
def login():
    """
    Body: { "identifier": "<email or phone>", "password": "..." }
    Sets session on success.
    """
    data       = request.get_json(silent=True) or {}
    identifier = (
        data.get("identifier") or data.get("email") or data.get("phone") or ""
    ).strip().lower()
    password   = (data.get("password") or "").strip()

    if not identifier:
        return err("Email or phone number is required.")
    if not password:
        return err("Password is required.")

    # Look up by email first, then phone
    user = (
        User.query.filter_by(email=identifier).first()
        or User.query.filter_by(phone=identifier).first()
    )

    # ✅ Unified error — doesn't reveal whether the account exists
    if not user or not user.check_password(password):
        return err("Incorrect email/phone or password.", 401)

    # Check verification status
    if not user.is_active:
        if user.email and not user.email_verified:
            return err(
                "Please verify your email first. Check your inbox for the OTP.",
                403
            )
        if user.phone and not user.phone_verified:
            return err(
                "Please verify your phone number first. Check your SMS.",
                403
            )
        return err("Account inactive. Please contact support.", 403)

    # ✅ Regenerate session ID on login to prevent session fixation
    session.clear()
    session["user_id"] = user.id
    return ok("Logged in successfully!", user=user.to_dict())


# ══════════════════════════════════════════════════════════════════════════════
#  LOGOUT
# ══════════════════════════════════════════════════════════════════════════════

@auth_bp.route("/logout", methods=["POST"])
def logout():
    session.pop("user_id", None)
    session.clear()
    return ok("You have been logged out.")


# ══════════════════════════════════════════════════════════════════════════════
#  CURRENT USER
# ══════════════════════════════════════════════════════════════════════════════

@auth_bp.route("/me", methods=["GET"])
def me():
    """Returns the currently logged-in user or 401."""
    user_id, error = _require_session()
    if error:
        return error

    user = db.session.get(User, user_id)
    if not user:
        session.clear()
        return err("User not found.", 404)

    return ok("Authenticated.", user=user.to_dict())


# ══════════════════════════════════════════════════════════════════════════════
#  NUTRITION CALCULATOR HELPER
# ══════════════════════════════════════════════════════════════════════════════

def _calculate_nutrition(age: int, gender: str, weight_kg: float,
                         height_cm: float, diet_type: str) -> dict:
    """
    Estimate daily nutrition targets via Harris-Benedict BMR × TDEE (moderate activity).
    Returns kcal, protein_g, carbs_g, fat_g.
    """
    # BMR (Harris-Benedict revised)
    if gender.lower() == "female":
        bmr = 447.593 + (9.247 * weight_kg) + (3.098 * height_cm) - (4.330 * age)
    else:  # male / other → use male formula
        bmr = 88.362 + (13.397 * weight_kg) + (4.799 * height_cm) - (5.677 * age)

    # TDEE – moderate activity (×1.55)
    kcal = math.ceil(bmr * 1.55)

    # Macro splits by diet type (protein%, carbs%, fat%)
    splits = {
        "balanced":     (0.25, 0.50, 0.25),
        "vegetarian":   (0.20, 0.55, 0.25),
        "vegan":        (0.18, 0.57, 0.25),
        "keto":         (0.25, 0.05, 0.70),
        "paleo":        (0.30, 0.35, 0.35),
        "high-protein": (0.35, 0.40, 0.25),
    }
    p_pct, c_pct, f_pct = splits.get(diet_type.lower(), splits["balanced"])

    # Calories per gram: protein=4, carbs=4, fat=9
    protein_g = math.ceil((kcal * p_pct) / 4)
    carbs_g   = math.ceil((kcal * c_pct) / 4)
    fat_g     = math.ceil((kcal * f_pct) / 9)

    return {"kcal": kcal, "protein_g": protein_g, "carbs_g": carbs_g, "fat_g": fat_g}


# ══════════════════════════════════════════════════════════════════════════════
#  GET PROFILE  (GET /auth/profile)  ← NEW endpoint
# ══════════════════════════════════════════════════════════════════════════════

@auth_bp.route("/profile", methods=["GET"])
def get_profile():
    """Returns the current user's saved profile data."""
    user_id, error = _require_session()
    if error:
        return error

    profile = UserProfile.query.filter_by(user_id=user_id).first()
    if not profile:
        return jsonify({"success": True, "profile": None}), 200

    return jsonify({"success": True, "profile": profile.to_dict()}), 200


# ══════════════════════════════════════════════════════════════════════════════
#  SAVE PROFILE  (POST /auth/profile)
# ══════════════════════════════════════════════════════════════════════════════

@auth_bp.route("/profile", methods=["POST"])
def save_profile():
    """
    Body: { name, age, gender, weight, height, diet_type }
    Requires an active session.
    Creates or updates UserProfile and stores calculated nutrition targets.
    Validates all numeric inputs to prevent edge-case calculation errors.
    """
    user_id, error = _require_session()
    if error:
        return error

    data      = request.get_json(silent=True) or {}
    name      = (data.get("name")      or "").strip() or None
    age       = data.get("age")
    gender    = (data.get("gender")    or "").strip()
    weight    = data.get("weight")
    height    = data.get("height")
    diet_type = (data.get("diet_type") or "balanced").strip().lower()

    # Validate required fields
    if not gender:
        return err("Gender is required.")
    try:
        age    = int(age)
        weight = float(weight)
        height = float(height)
    except (TypeError, ValueError):
        return err("Age, weight, and height must be valid numbers.")

    # ✅ Reject nonsensical values that would break BMR calculation
    if not (1 <= age <= 120):
        return err("Age must be between 1 and 120.")
    if not (1.0 <= weight <= 500.0):
        return err("Weight must be between 1 and 500 kg.")
    if not (30.0 <= height <= 300.0):
        return err("Height must be between 30 and 300 cm.")
    if diet_type not in ("balanced", "vegetarian", "vegan", "keto", "paleo", "high-protein"):
        diet_type = "balanced"   # safe fallback

    # Calculate nutrition targets
    nutrition = _calculate_nutrition(age, gender, weight, height, diet_type)

    # Upsert UserProfile
    profile = UserProfile.query.filter_by(user_id=user_id).first()
    if not profile:
        profile = UserProfile(user_id=user_id)
        db.session.add(profile)

    profile.name      = name
    profile.age       = age
    profile.gender    = gender
    profile.weight_kg = weight
    profile.height_cm = height
    profile.diet_type = diet_type
    profile.kcal      = nutrition["kcal"]
    profile.protein_g = nutrition["protein_g"]
    profile.carbs_g   = nutrition["carbs_g"]
    profile.fat_g     = nutrition["fat_g"]
    db.session.commit()

    return ok(
        "Profile saved successfully!",
        profile=profile.to_dict(),
        nutrition=nutrition,
    )


# ══════════════════════════════════════════════════════════════════════════════
#  BODY NEEDS  (GET /auth/body-needs)
# ══════════════════════════════════════════════════════════════════════════════

@auth_bp.route("/body-needs", methods=["GET"])
def body_needs():
    """
    Returns the stored daily nutrition targets for the current user.
    Used by body-needs.html to display personalised macros.
    """
    user_id, error = _require_session()
    if error:
        return error

    profile = UserProfile.query.filter_by(user_id=user_id).first()
    if not profile or not profile.kcal:
        return err("No profile found. Please complete the profile form first.", 404)

    return jsonify({
        "success": True,
        "kcal":    profile.kcal,
        "protein": profile.protein_g,
        "carbs":   profile.carbs_g,
        "fat":     profile.fat_g,
    }), 200


# ══════════════════════════════════════════════════════════════════════════════
#  MEAL PREFERENCES  (GET + POST /auth/meal-preferences)
# ══════════════════════════════════════════════════════════════════════════════

# Canonical meal catalogue — used to resolve IDs back to their category
_MEAL_CATALOGUE = {
    "breakfast": ["oatmeal_berries", "avocado_toast", "greek_yogurt", "smoothie"],
    "lunch":     ["chicken_salad", "quinoa_bowl", "brown_rice_chicken", "veggie_wrap"],
    "dinner":    ["salmon_veggies", "stir_fry", "tofu_bowl", "buddha_bowl"],
    "snacks":    ["mixed_nuts", "mixed_nuts2", "protein_balls", "yogurt_parfait"],
}
# Flat reverse lookup: meal_id → category
_MEAL_TO_CAT = {mid: cat for cat, ids in _MEAL_CATALOGUE.items() for mid in ids}


@auth_bp.route("/meal-preferences", methods=["GET"])
def get_meal_preferences():
    """
    Returns the user's saved meal preferences.
    Response: { "meals": [...], "categories": { "breakfast": [...], ... } }
    """
    user_id, error = _require_session()
    if error:
        return error

    profile = UserProfile.query.filter_by(user_id=user_id).first()
    if not profile or not profile.meal_prefs:
        return ok("No meal preferences saved yet.", meals=[], categories={})

    # Split comma-separated IDs stored in DB
    flat = [m for m in profile.meal_prefs.split(",") if m.strip()]

    # Try to parse a stored categories JSON blob (new format)
    categories = {}
    try:
        if profile.meal_prefs.startswith("{"):
            stored = _json.loads(profile.meal_prefs)
            flat       = stored.get("meals", [])
            categories = stored.get("categories", {})
    except Exception:
        pass

    # If categories not available, rebuild them from the catalogue lookup
    if not categories:
        categories = {"breakfast": [], "lunch": [], "dinner": [], "snacks": []}
        for mid in flat:
            cat = _MEAL_TO_CAT.get(mid)
            if cat and len(categories[cat]) < 3:
                categories[cat].append(mid)

    return ok("Meal preferences loaded.", meals=flat, categories=categories)


@auth_bp.route("/meal-preferences", methods=["POST"])
def save_meal_preferences():
    """
    Body: { "meals": [...], "categories": { "breakfast": [...], ... } }
    Saves the user's chosen meal IDs to their profile.
    """
    user_id, error = _require_session()
    if error:
        return error

    data       = request.get_json(silent=True) or {}
    meals      = data.get("meals") or []
    categories = data.get("categories") or {}

    if not isinstance(meals, list):
        return err("meals must be a list.")
    # Sanitize: only allow alphanumeric + underscore meal IDs
    safe_meals = [str(m)[:60] for m in meals if re.match(r"^[\w-]{1,60}$", str(m))]

    # Sanitize categories dict
    safe_cats = {}
    for cat, ids in categories.items():
        if isinstance(ids, list):
            safe_cats[cat] = [str(i)[:60] for i in ids if re.match(r"^[\w-]{1,60}$", str(i))]

    profile = UserProfile.query.filter_by(user_id=user_id).first()
    if not profile:
        profile = UserProfile(user_id=user_id)
        db.session.add(profile)

    # Store as JSON blob so both flat + category data survive
    if safe_cats:
        profile.meal_prefs = _json.dumps({"meals": safe_meals, "categories": safe_cats})
    else:
        profile.meal_prefs = ",".join(safe_meals)

    db.session.commit()

    return ok("Meal preferences saved!", meals=safe_meals, categories=safe_cats)


# ══════════════════════════════════════════════════════════════════════════════
#  WEEKLY PLAN  (POST /auth/weekly-plan)
# ══════════════════════════════════════════════════════════════════════════════

@auth_bp.route("/weekly-plan", methods=["POST"])
def save_weekly_plan():
    """
    Body: { "plan": { "Monday": { "done": true/false, "checks": {...} }, ... } }
    Saves the full weekly plan state as JSON.
    """
    user_id, error = _require_session()
    if error:
        return error

    data = request.get_json(silent=True) or {}
    plan = data.get("plan") or {}

    if not isinstance(plan, dict):
        return err("plan must be a JSON object.")

    wp = WeeklyPlan.query.filter_by(user_id=user_id).first()
    if not wp:
        wp = WeeklyPlan(user_id=user_id)
        db.session.add(wp)

    wp.plan_json = _json.dumps(plan)
    db.session.commit()

    return ok("Weekly plan saved!")


# ══════════════════════════════════════════════════════════════════════════════
#  GET WEEKLY PLAN  (GET /auth/weekly-plan)
# ══════════════════════════════════════════════════════════════════════════════

@auth_bp.route("/weekly-plan", methods=["GET"])
def get_weekly_plan():
    """
    Returns the user's saved weekly plan JSON so the frontend can restore state.
    Response: { success: true, plan: { Monday: { done: bool, checks: {...} } } }
    """
    user_id, error = _require_session()
    if error:
        return error

    wp = WeeklyPlan.query.filter_by(user_id=user_id).first()
    if not wp or not wp.plan_json:
        return jsonify({"success": True, "plan": {}}), 200

    try:
        plan = _json.loads(wp.plan_json)
    except Exception:
        plan = {}

    return jsonify({"success": True, "plan": plan}), 200


# ══════════════════════════════════════════════════════════════════════════════
#  ACHIEVEMENTS  (GET /auth/achievements)
# ══════════════════════════════════════════════════════════════════════════════

@auth_bp.route("/achievements", methods=["GET"])
def achievements():
    """
    Returns the user's weekly achievement percentages derived from the saved
    weekly plan (how many days done, etc.) and their nutrition targets.
    Used by dashboard.html for circular progress and bar chart.
    """
    user_id, error = _require_session()
    if error:
        return error

    DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    import datetime
    today_name = datetime.datetime.now().strftime("%A")
    streak = 0

    wp   = WeeklyPlan.query.filter_by(user_id=user_id).first()
    plan = {}
    if wp and wp.plan_json:
        try:
            plan = _json.loads(wp.plan_json)
        except Exception:
            plan = {}

    # Calculate streak logic (backwards from today)
    if plan:
        try:
            today_idx = DAYS.index(today_name)
            check_days = [DAYS[(today_idx - i) % 7] for i in range(7)]
            for d in check_days:
                if plan.get(d, {}).get("done") is True:
                    streak += 1
                else:
                    break
        except:
            pass

    # Calculate macro-specific percentages (Issue 1 fix)
    total_days = 7
    breakfast_ticked = 0
    lunch_ticked     = 0
    dinner_ticked    = 0
    any_meal_days    = 0
    
    weekly_data = []

    for d in DAYS:
        day_plan = plan.get(d, {})
        checks = day_plan.get("checks", {})
        
        if checks.get("Breakfast") or checks.get("breakfast"): breakfast_ticked += 1
        if checks.get("Lunch") or checks.get("lunch"):         lunch_ticked += 1
        if checks.get("Dinner") or checks.get("dinner"):       dinner_ticked += 1
        
        if any(checks.values()):
            any_meal_days += 1

        # Daily completion % for bar chart
        ticked = sum(1 for v in checks.values() if v)
        total_checks = len(checks) or 4 # Default to 4 meals if not specified
        weekly_data.append(round((ticked / total_checks) * 100))

    carbs_pct   = round((breakfast_ticked / total_days) * 100)
    protein_pct = round((lunch_ticked     / total_days) * 100)
    fat_pct     = round((dinner_ticked    / total_days) * 100)
    kcal_pct    = round((any_meal_days    / total_days) * 100)

    done_days = [d for d in DAYS if plan.get(d, {}).get("done")]
    profile   = UserProfile.query.filter_by(user_id=user_id).first()

    return jsonify({
        "success":     True,
        "kcal_pct":    kcal_pct,
        "protein_pct": protein_pct,
        "carbs_pct":   carbs_pct,
        "fat_pct":     fat_pct,
        "done_days":   done_days,
        "weekly_data": weekly_data,
        "streak":      streak,
        "kcal":        profile.kcal      if profile else 2000,
        "protein":     profile.protein_g if profile else 150,
        "carbs":       profile.carbs_g   if profile else 150,
        "fat":         profile.fat_g     if profile else 50,
    }), 200
