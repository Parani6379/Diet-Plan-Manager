"""
MealMatrix – Database Models

Improvements applied:
  - datetime.now(timezone.utc) replaces deprecated datetime.utcnow()
  - Composite index on OTPRecord for fast lookup queries
  - Consistent cascade deletes
"""
from datetime import datetime, timezone
from extensions import db
from werkzeug.security import generate_password_hash, check_password_hash


def _now():
    """
    Returns the current UTC time as a NAIVE datetime (no tzinfo).
    SQLite stores and retrieves DateTime columns without timezone info,
    so we must keep everything naive-UTC for comparison to work correctly.
    """
    return datetime.now(timezone.utc).replace(tzinfo=None)


class User(db.Model):
    """
    Core user record.
    A user registers with EITHER email OR phone.
    The account becomes active only after OTP verification.
    """
    __tablename__ = "users"

    id             = db.Column(db.Integer, primary_key=True)
    username       = db.Column(db.String(120), nullable=True)
    email          = db.Column(db.String(180), unique=True, nullable=True, index=True)
    phone          = db.Column(db.String(30),  unique=True, nullable=True, index=True)
    password_hash  = db.Column(db.String(256), nullable=False)
    email_verified = db.Column(db.Boolean, default=False, nullable=False)
    phone_verified = db.Column(db.Boolean, default=False, nullable=False)
    is_active      = db.Column(db.Boolean, default=False, nullable=False)
    created_at     = db.Column(db.DateTime(timezone=True), default=_now)
    updated_at     = db.Column(db.DateTime(timezone=True), default=_now, onupdate=_now)

    # Cascade delete OTP records when user is deleted
    otp_records = db.relationship(
        "OTPRecord", backref="user", lazy=True, cascade="all, delete-orphan"
    )
    profile = db.relationship(
        "UserProfile", backref="user", lazy=True, cascade="all, delete-orphan", uselist=False
    )
    weekly_plan = db.relationship(
        "WeeklyPlan", backref="user", lazy=True, cascade="all, delete-orphan", uselist=False
    )

    # ── Password helpers ──────────────────────────────────────────────────────
    def set_password(self, password: str):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)

    def to_dict(self) -> dict:
        return {
            "id":             self.id,
            "username":       self.username,
            "email":          self.email,
            "phone":          self.phone,
            "email_verified": self.email_verified,
            "phone_verified": self.phone_verified,
            "is_active":      self.is_active,
        }

    def __repr__(self):
        return f"<User id={self.id} email={self.email} phone={self.phone}>"


class OTPRecord(db.Model):
    """
    Stores short-lived OTP codes for email and phone verification.
    Indexed on (user_id, otp_type, used) for fast lookup.
    """
    __tablename__ = "otp_records"
    __table_args__ = (
        # ✅ Composite index — speeds up create_otp_record and verify_otp queries
        db.Index("idx_otp_lookup", "user_id", "otp_type", "used"),
    )

    id         = db.Column(db.Integer, primary_key=True)
    user_id    = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    otp_type   = db.Column(db.String(10), nullable=False)   # 'email' or 'phone'
    code       = db.Column(db.String(6),  nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=_now)
    expires_at = db.Column(db.DateTime(timezone=True), nullable=False)
    used       = db.Column(db.Boolean, default=False, nullable=False)

    def is_valid(self) -> bool:
        """Returns True only if not yet used AND not expired.
        Strips tzinfo from expires_at before comparing — SQLite returns
        naive datetimes even when stored with timezone=True.
        """
        expires = self.expires_at
        if expires is None:
            return False   # no expiry set — treat as invalid
        if expires.tzinfo is not None:
            expires = expires.replace(tzinfo=None)  # normalize to naive UTC
        return not self.used and (_now() <= expires)

    def __repr__(self):
        return (
            f"<OTPRecord user={self.user_id} type={self.otp_type} "
            f"code=[REDACTED] valid={self.is_valid()}>"
        )


class UserProfile(db.Model):
    """
    Extended profile info submitted on the Create Profile page.
    Stores physical stats and calculated daily nutrition targets.
    """
    __tablename__ = "user_profiles"

    id         = db.Column(db.Integer, primary_key=True)
    user_id    = db.Column(db.Integer, db.ForeignKey("users.id"), unique=True, nullable=False, index=True)
    name       = db.Column(db.String(120), nullable=True)
    age        = db.Column(db.Integer, nullable=True)
    gender     = db.Column(db.String(20), nullable=True)
    weight_kg  = db.Column(db.Float, nullable=True)
    height_cm  = db.Column(db.Float, nullable=True)
    diet_type  = db.Column(db.String(50), nullable=True)
    # Calculated targets
    kcal       = db.Column(db.Integer, nullable=True)
    protein_g  = db.Column(db.Integer, nullable=True)
    carbs_g    = db.Column(db.Integer, nullable=True)
    fat_g      = db.Column(db.Integer, nullable=True)
    # Meal preferences (comma-separated IDs)
    meal_prefs = db.Column(db.Text, nullable=True)
    updated_at = db.Column(db.DateTime(timezone=True), default=_now, onupdate=_now)

    def to_dict(self) -> dict:
        return {
            "name":      self.name,
            "age":       self.age,
            "gender":    self.gender,
            "weight_kg": self.weight_kg,
            "height_cm": self.height_cm,
            "diet_type": self.diet_type,
            "kcal":      self.kcal,
            "protein_g": self.protein_g,
            "carbs_g":   self.carbs_g,
            "fat_g":     self.fat_g,
        }

    def __repr__(self):
        return f"<UserProfile user={self.user_id} diet={self.diet_type}>"


class WeeklyPlan(db.Model):
    """
    Stores a user's weekly meal plan progress as a JSON blob.
    """
    __tablename__ = "weekly_plans"

    id         = db.Column(db.Integer, primary_key=True)
    user_id    = db.Column(db.Integer, db.ForeignKey("users.id"), unique=True, nullable=False, index=True)
    plan_json  = db.Column(db.Text, nullable=True)   # JSON string
    updated_at = db.Column(db.DateTime(timezone=True), default=_now, onupdate=_now)

    def __repr__(self):
        return f"<WeeklyPlan user={self.user_id}>"
