"""
app/routes/auth_routes.py — Authentication endpoints + decorators
"""

import bcrypt
from flask import Blueprint, request, jsonify, session, abort, g
from functools import wraps

auth_bp = Blueprint("auth", __name__)


def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        user_id = session.get("user_id")
        if not user_id:
            abort(401)
        g.current_user_id = user_id
        return f(*args, **kwargs)
    return decorated


def require_role(*roles):
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            if session.get("user_role", "") not in roles:
                abort(403)
            return f(*args, **kwargs)
        return decorated
    return decorator


@auth_bp.post("/login")
def login():
    data = request.get_json(silent=True) or {}
    username = data.get("username", "").strip()
    password = data.get("password", "")

    if not username or not password:
        return jsonify({"error": "username and password are required"}), 400

    from repositories.user_repository import UserRepository
    repo = UserRepository()

    user = repo.get_by_username(username)
    if user is None or not user.is_active():
        return jsonify({"error": "Invalid credentials"}), 401

    stored_hash = repo.get_password_hash(username)
    if not bcrypt.checkpw(password.encode(), stored_hash.encode()):
        return jsonify({"error": "Invalid credentials"}), 401

    session["user_id"]   = user.get_user_id()
    session["user_role"] = user.get_role()
    session["username"]  = user.get_username()

    return jsonify({
        "user_id":  user.get_user_id(),
        "username": user.get_username(),
        "role":     user.get_role(),
    }), 200


@auth_bp.post("/logout")
@login_required
def logout():
    session.clear()
    return jsonify({"message": "Logged out successfully"}), 200


@auth_bp.get("/me")
@login_required
def me():
    return jsonify({
        "user_id":  g.current_user_id,
        "username": session.get("username"),
        "role":     session.get("user_role"),
    }), 200
