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

    from database.db import log_activity
    log_activity(user.get_user_id(), user.get_username(), "login",
                 ip=request.remote_addr)

    return jsonify({
        "user_id":  user.get_user_id(),
        "username": user.get_username(),
        "role":     user.get_role(),
    }), 200


@auth_bp.post("/logout")
@login_required
def logout():
    from database.db import log_activity
    log_activity(session.get("user_id"), session.get("username", "?"),
                 "logout", ip=request.remote_addr)
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


@auth_bp.put("/profile")
@login_required
def update_profile():
    """
    PUT /api/auth/profile
    Any logged-in user can update their own email and/or password.
    Body: { "email": str (optional), "current_password": str, "new_password": str (optional) }
    """
    data = request.get_json(silent=True) or {}
    from repositories.user_repository import UserRepository
    repo = UserRepository()
    user = repo.get_by_id(g.current_user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404

    current_pw = data.get("current_password", "")
    stored_hash = repo.get_password_hash(user.get_username())
    if not stored_hash or not bcrypt.checkpw(current_pw.encode(), stored_hash.encode()):
        return jsonify({"error": "Current password is incorrect"}), 403

    if data.get("email"):
        try:
            user.set_email(data["email"])
        except ValueError as e:
            return jsonify({"error": str(e)}), 400

    if data.get("new_password"):
        if len(data["new_password"]) < 8:
            return jsonify({"error": "New password must be at least 8 characters"}), 400
        new_hash = bcrypt.hashpw(data["new_password"].encode(), bcrypt.gensalt()).decode()
        repo.update_password(g.current_user_id, new_hash)

    repo.update(user)
    return jsonify({
        "message": "Profile updated successfully",
        "username": user.get_username(),
        "email": user.get_email(),
    }), 200
