"""
MealMatrix – Flask Backend Entry Point
Run with:  python app.py
Access at: http://127.0.0.1:5000
"""
import os
from flask import Flask
from flask_session import Session
from flask_cors import CORS
from config import Config
from extensions import db, limiter
from routes.auth import auth_bp
from routes.main import main_bp


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    # ── Required folders (created automatically) ──────────────────────────────
    os.makedirs(os.path.join(app.config["BASE_DIR"], "instance"),      exist_ok=True)
    os.makedirs(os.path.join(app.config["BASE_DIR"], "flask_session"), exist_ok=True)

    # ── CORS ──────────────────────────────────────────────────────────────────
    # Restrict to known origins only. "null" is kept for local file:// development.
    CORS(
        app,
        supports_credentials=True,
        origins=["http://127.0.0.1:5000", "http://localhost:5000", "null"],
        allow_headers=["Content-Type", "Authorization", "X-Requested-With"],
        methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    )

    # ── Extensions ────────────────────────────────────────────────────────────
    db.init_app(app)
    Session(app)
    limiter.init_app(app)   # ✅ Rate limiting enabled

    # ── Blueprints ────────────────────────────────────────────────────────────
    app.register_blueprint(auth_bp, url_prefix="/auth")
    app.register_blueprint(main_bp, url_prefix="/")

    # ── DB Tables (create on first run) ───────────────────────────────────────
    with app.app_context():
        db.create_all()
        app.logger.info("Database ready at: %s", app.config["SQLALCHEMY_DATABASE_URI"])

    # ── Global error handlers ─────────────────────────────────────────────────
    @app.errorhandler(429)
    def rate_limit_exceeded(e):
        from flask import jsonify
        return jsonify({
            "success": False,
            "message": "Too many requests. Please wait a moment and try again.",
        }), 429

    @app.errorhandler(404)
    def not_found(e):
        from flask import jsonify, request
        if request.path.startswith("/auth") or request.path.startswith("/api"):
            return jsonify({"success": False, "message": "Endpoint not found."}), 404
        return e  # let Flask handle non-API 404s normally

    return app


if __name__ == "__main__":
    application = create_app()
    print("\n" + "=" * 50)
    print("  MealMatrix backend is running!")
    print("  Open your browser at: http://127.0.0.1:5000")
    print(f"  Debug mode: {application.config['DEBUG']}")
    print("=" * 50 + "\n")
    application.run(debug=application.config["DEBUG"], host="127.0.0.1", port=5000)
