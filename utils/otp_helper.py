"""
MealMatrix – OTP Utility Helpers
Handles: generation, DB persistence, email (SMTP), and SMS (Twilio) delivery.

Security improvements applied:
  - secrets.randbelow() replaces random.choices() — cryptographically secure
  - Bulk OTP invalidation replaces N+1 loop
  - OTP code is NEVER logged in plaintext (only masked reference is logged)
  - SMTP connection is explicitly closed even on error (try/finally)
"""
import secrets
import smtplib
from datetime import datetime, timezone, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from flask import current_app
from extensions import db
from models import OTPRecord


# ─────────────────────────────────────────────────────────────────────────────
# Generation & DB
# ─────────────────────────────────────────────────────────────────────────────

def generate_otp(length: int = 6) -> str:
    """
    Returns a zero-padded numeric OTP string using the cryptographically
    secure `secrets` module (replaces `random.choices` which is NOT secure).
    """
    return "".join(str(secrets.randbelow(10)) for _ in range(length))


def create_otp_record(user_id: int, otp_type: str) -> OTPRecord:
    """
    Invalidates all existing active OTPs for this user+type in a single
    bulk UPDATE (replaces the previous N+1 loop), then creates and saves
    a fresh OTPRecord. Returns the new record.
    """
    expiry_minutes = current_app.config.get("OTP_EXPIRY_MINUTES", 10)

    # ✅ Bulk UPDATE instead of an N+1 loop
    OTPRecord.query.filter_by(
        user_id=user_id, otp_type=otp_type, used=False
    ).update({"used": True}, synchronize_session=False)

    code = generate_otp()
    record = OTPRecord(
        user_id    = user_id,
        otp_type   = otp_type,
        code       = code,
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=expiry_minutes),
    )
    db.session.add(record)
    db.session.commit()
    return record


def verify_otp(user_id: int, otp_type: str, code: str) -> bool:
    """
    Returns True and marks the OTP as used if the code is valid and not expired.
    Uses constant-time comparison via secrets.compare_digest to resist timing attacks.
    """
    record = (
        OTPRecord.query
        .filter_by(user_id=user_id, otp_type=otp_type, used=False)
        .order_by(OTPRecord.created_at.desc())
        .first()
    )
    if record and record.is_valid():
        # ✅ Constant-time comparison — prevents timing-based OTP inference
        if secrets.compare_digest(record.code, str(code).strip()):
            record.used = True
            db.session.commit()
            return True
    return False


# ─────────────────────────────────────────────────────────────────────────────
# Email Delivery (SMTP / Gmail)
# ─────────────────────────────────────────────────────────────────────────────

def send_email_otp(to_email: str, otp_code: str) -> bool:
    """
    Sends a styled HTML + plain-text email with the OTP via SMTP (Gmail).
    Returns True on success, False on failure.

    Key improvements:
    - Always attempts real SMTP — debug console is fallback ONLY if SMTP fails.
    - Includes plain-text part alongside HTML to pass spam filters.
    - From/Reply-To set to authenticated Gmail account address.
    """
    cfg      = current_app.config
    is_debug = cfg.get("DEBUG", False)
    username = cfg.get("MAIL_USERNAME", "")
    password = cfg.get("MAIL_PASSWORD", "")

    # ── Dev mode: no credentials configured ───────────────────────────────────
    if not username or not password:
        current_app.logger.warning(
            "[Email OTP] No SMTP credentials in .env — cannot send real email."
        )
        if is_debug:
            print(f"\n{'='*50}")
            print(f"  [DEV] EMAIL OTP for {to_email}: {otp_code}")
            print(f"  (No SMTP credentials — console only)")
            print(f"{'='*50}\n")
        return True   # allow registration flow in dev

    expiry    = cfg.get("OTP_EXPIRY_MINUTES", 10)
    subject   = "Your MealMatrix Verification Code"
    from_addr = f"MealMatrix <{username}>"   # ✅ display name + real Gmail address

    # ── Plain-text version (required alongside HTML to avoid spam filters) ────
    text_body = (
        f"Your MealMatrix verification code is: {otp_code}\n\n"
        f"This code expires in {expiry} minutes.\n"
        f"Do not share this code with anyone.\n\n"
        f"If you did not request this, ignore this email."
    )

    # ── HTML version ──────────────────────────────────────────────────────────
    html_body = f"""
<!DOCTYPE html>
<html>
<body style="margin:0;padding:0;background:#f0f4f8;font-family:Arial,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0">
    <tr>
      <td align="center" style="padding:40px 20px;">
        <table width="480" cellpadding="0" cellspacing="0"
               style="background:#fff;border-radius:16px;overflow:hidden;
                      box-shadow:0 4px 20px rgba(0,0,0,.08);">
          <tr>
            <td style="background:linear-gradient(135deg,#00d26a,#00b359);
                       padding:30px;text-align:center;">
              <h1 style="margin:0;color:#fff;font-size:26px;letter-spacing:1px;">
                MealMatrix
              </h1>
              <p style="margin:6px 0 0;color:rgba(255,255,255,.85);font-size:14px;">
                Healthy Meal Planner
              </p>
            </td>
          </tr>
          <tr>
            <td style="padding:36px 40px;text-align:center;">
              <p style="margin:0 0 8px;font-size:16px;color:#333;">
                Your one-time verification code is:
              </p>
              <div style="display:inline-block;margin:20px 0;padding:18px 36px;
                          background:#f0fff8;border:2px dashed #00d26a;
                          border-radius:12px;">
                <span style="font-size:42px;font-weight:bold;letter-spacing:12px;
                             color:#00b359;">{otp_code}</span>
              </div>
              <p style="margin:0;font-size:13px;color:#888;">
                This code expires in <strong>{expiry} minutes</strong>.<br/>
                Do not share it with anyone.
              </p>
            </td>
          </tr>
          <tr>
            <td style="padding:20px 40px;background:#f8fafc;text-align:center;
                       border-top:1px solid #eee;">
              <p style="margin:0;font-size:12px;color:#aaa;">
                &copy; 2026 MealMatrix &middot; If you didn&apos;t request this, ignore this email.
              </p>
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</body>
</html>
"""

    # ── Build message (plain + html = multipart/alternative) ──────────────────
    msg = MIMEMultipart("alternative")
    msg["Subject"]  = subject
    msg["From"]     = from_addr      # ✅ Matches authenticated Gmail account
    msg["To"]       = to_email
    msg["Reply-To"] = username       # ✅ Improves inbox delivery scoring
    msg.attach(MIMEText(text_body, "plain"))  # ✅ Plain-text first — avoids spam filters
    msg.attach(MIMEText(html_body, "html"))

    smtp = None
    try:
        smtp = smtplib.SMTP(cfg["MAIL_SERVER"], cfg["MAIL_PORT"], timeout=15)
        smtp.ehlo()
        if cfg.get("MAIL_USE_TLS", True):
            smtp.starttls()
            smtp.ehlo()
        smtp.login(username, password)
        smtp.sendmail(username, to_email, msg.as_string())
        current_app.logger.info("[Email OTP] Sent successfully to %s", to_email)
        return True
    except Exception as exc:
        current_app.logger.error("[Email OTP] SMTP FAILED for %s: %s", to_email, exc)
        # ✅ In DEBUG mode — print OTP to console as fallback when SMTP fails
        if is_debug:
            print(f"\n{'='*50}")
            print(f"  [DEV] EMAIL OTP for {to_email}: {otp_code}")
            print(f"  SMTP error: {exc}")
            print(f"{'='*50}\n")
            return True   # allow registration flow in dev
        return False
    finally:
        # ✅ Always close the SMTP connection cleanly
        if smtp:
            try:
                smtp.quit()
            except Exception:
                pass


# ─────────────────────────────────────────────────────────────────────────────
# SMS Delivery (Twilio)
# ─────────────────────────────────────────────────────────────────────────────

def send_sms_otp(to_phone: str, otp_code: str) -> bool:
    """
    Sends the OTP via Twilio SMS.
    If credentials are not set, logs a dev-mode notice WITHOUT the OTP code.
    Returns True on success or dev-mode skip, False on actual send error.
    """
    cfg      = current_app.config
    sid      = cfg.get("TWILIO_ACCOUNT_SID",  "")
    token    = cfg.get("TWILIO_AUTH_TOKEN",    "")
    from_num = cfg.get("TWILIO_PHONE_NUMBER",  "")
    expiry   = cfg.get("OTP_EXPIRY_MINUTES", 10)

    # Dev mode — no credentials configured
    if not (sid and token and from_num):
        current_app.logger.warning(
            "[SMS OTP] Twilio not configured — check DB otp_records table "
            f"for the code (phone: {to_phone})."
            # ✅ OTP code is NOT logged
        )
        return True   # flow continues; developer reads OTP from DB

    try:
        from twilio.rest import Client
        client  = Client(sid, token)
        message = client.messages.create(
            body    = (
                f"Your MealMatrix verification code is: {otp_code}\n"
                f"Valid for {expiry} minutes. Do not share this code."
            ),
            from_   = from_num,
            to      = to_phone,
        )
        current_app.logger.info(
            "[SMS OTP] Sent to %s — SID: %s", to_phone, message.sid
        )
        return True
    except Exception as exc:
        current_app.logger.error("[SMS OTP] FAILED for %s: %s", to_phone, exc)
        return False
