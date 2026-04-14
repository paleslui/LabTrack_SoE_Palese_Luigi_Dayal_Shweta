"""
app/app.py
==========
Flask Application Factory
"""

from flask import Flask, jsonify
from .routes.auth_routes   import auth_bp
from .routes.sample_routes import sample_bp
from .routes.user_routes   import user_bp


def create_app(config: dict | None = None) -> Flask:
    app = Flask(__name__)

    app.config.update(
        SECRET_KEY="change-me-in-production",
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        DATABASE_URI="sqlite:///labtrack.db",
        MAX_CONTENT_LENGTH=5 * 1024 * 1024,
    )

    if config:
        app.config.update(config)

    app.register_blueprint(auth_bp,   url_prefix="/api/auth")
    app.register_blueprint(sample_bp, url_prefix="/api/samples")
    app.register_blueprint(user_bp,   url_prefix="/api/users")

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
