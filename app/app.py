"""
app/app.py
==========
Flask Application Factory
--------------------------
ARCHITECTURE NOTE (Stage 6)
----------------------------
This module is the entry point for LabTrack's Presentation Layer.
It implements the Application Factory pattern, which allows multiple
app instances to be created (e.g., one for production, one for testing)
without sharing global state.

Architecture style: Three-Tier Layered + Client-Server
- This file lives at the boundary of the Client-Server split:
  it starts the server that browsers (clients) connect to.
- Inside the server, it wires together the three tiers:
    Presentation  →  app/routes/  (Flask Blueprints)
    Application   →  services/, patterns/
    Data          →  repositories/ (Singleton instances)
"""

from flask import Flask, jsonify
from app.routes.auth_routes   import auth_bp
from app.routes.sample_routes import sample_bp
from app.routes.user_routes   import user_bp


def create_app(config: dict | None = None) -> Flask:
    """
    Create and configure a Flask application instance.

    Parameters
    ----------
    config : dict, optional
        Override default configuration values. Useful for testing
        (e.g., pass {"TESTING": True} to disable error handling).

    Returns
    -------
    Flask — the configured application object.
    """
    app = Flask(__name__)

    # ── Default configuration ─────────────────────────────────────────────
    app.config.update(
        SECRET_KEY="change-me-in-production",   # Session signing key
        SESSION_COOKIE_HTTPONLY=True,            # Prevent JS access to cookie
        SESSION_COOKIE_SAMESITE="Lax",           # CSRF mitigation
        DATABASE_URI="sqlite:///labtrack.db",    # Swappable via config (NFR-11)
        MAX_CONTENT_LENGTH=5 * 1024 * 1024,     # 5 MB upload limit for CSV
    )

    if config:
        app.config.update(config)

    # ── Register Blueprints (Presentation Layer) ──────────────────────────
    # Each Blueprint corresponds to one component in the architecture diagram.
    # URL prefixes are the API base paths defined in the API requirements table.
    app.register_blueprint(auth_bp,   url_prefix="/api/auth")
    app.register_blueprint(sample_bp, url_prefix="/api/samples")
    app.register_blueprint(user_bp,   url_prefix="/api/users")

    # ── Global error handlers ─────────────────────────────────────────────
    @app.errorhandler(400)
    def bad_request(e):
        return jsonify({"error": "Bad request", "detail": str(e)}), 400

    @app.errorhandler(401)
    def unauthorised(e):
        return jsonify({"error": "Authentication required"}), 401

    @app.errorhandler(403)
    def forbidden(e):
        return jsonify({"error": "Insufficient permissions"}), 403

    @app.errorhandler(404)
    def not_found(e):
        return jsonify({"error": "Resource not found"}), 404

    @app.errorhandler(500)
    def internal_error(e):
        return jsonify({"error": "Internal server error"}), 500

    return app


# ── Development entry point ───────────────────────────────────────────────────
if __name__ == "__main__":
    app = create_app()
    # NOTE: Use a production WSGI server (gunicorn, waitress) in deployment.
    app.run(host="0.0.0.0", port=5000, debug=True)
