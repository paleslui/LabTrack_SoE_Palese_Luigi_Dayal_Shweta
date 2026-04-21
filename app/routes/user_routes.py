"""
app/routes/user_routes.py — Admin-only user management, wired to UserRepository
"""

import bcrypt
from flask import Blueprint, request, jsonify
from .auth_routes import login_required, require_role

user_bp = Blueprint("users", __name__)


def _repo():
    from repositories.user_repository import UserRepository
    return UserRepository()


def _user_to_dict(user) -> dict:
    return {
        "user_id":    user.get_user_id(),
        "username":   user.get_username(),
        "email":      user.get_email(),
        "role":       user.get_role(),
        "is_active":  user.is_active(),
        "created_at": user.get_created_at().isoformat(),
    }


@user_bp.get("/")
@login_required
@require_role("admin")
def list_users():
    users = _repo().get_all()
    return jsonify({"users": [_user_to_dict(u) for u in users]}), 200


@user_bp.post("/")
@login_required
@require_role("admin")
def create_user():
    data = request.get_json(silent=True) or {}
    for field in ("username", "email", "password", "role"):
        if not data.get(field):
            return jsonify({"error": f"{field} is required"}), 400
    if len(data["password"]) < 8:
        return jsonify({"error": "password must be at least 8 characters"}), 400

    from patterns.user_factory import UserFactory
    repo = _repo()
    new_id = repo.count() + 1
    pw_hash = bcrypt.hashpw(data["password"].encode(), bcrypt.gensalt()).decode()
    try:
        user = UserFactory.create(new_id, data["username"], data["email"], pw_hash, data["role"])
        repo.add(user)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    return jsonify(_user_to_dict(user)), 201


@user_bp.get("/<int:user_id>")
@login_required
@require_role("admin")
def get_user(user_id: int):
    user = _repo().get_by_id(user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404
    return jsonify(_user_to_dict(user)), 200


@user_bp.put("/<int:user_id>")
@login_required
@require_role("admin")
def update_user(user_id: int):
    data = request.get_json(silent=True) or {}
    if not any(k in data for k in ("email", "role", "is_active")):
        return jsonify({"error": "Provide at least one of: email, role, is_active"}), 400

    repo = _repo()
    user = repo.get_by_id(user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404

    if "email" in data:
        user.set_email(data["email"])
    if "is_active" in data:
        user.set_active(bool(data["is_active"]))
    if "role" in data:
        from patterns.user_factory import UserFactory
        # Recreate with new role using factory
        new_user = UserFactory.create(
            user.get_user_id(), user.get_username(),
            user.get_email(), user._password_hash, data["role"]
        )
        new_user._is_active = user.is_active()
        user = new_user

    repo.update(user)
    return jsonify(_user_to_dict(user)), 200


@user_bp.delete("/<int:user_id>")
@login_required
@require_role("admin")
def deactivate_user(user_id: int):
    repo = _repo()
    user = repo.get_by_id(user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404
    user.set_active(False)
    repo.update(user)
    return jsonify({"message": f"User {user.get_username()!r} deactivated"}), 200
