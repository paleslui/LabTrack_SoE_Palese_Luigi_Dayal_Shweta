"""
app/routes/user_routes.py  (fixed imports)
"""

from flask import Blueprint, request, jsonify
from .auth_routes import login_required, require_role   # <-- relative import

user_bp = Blueprint("users", __name__)


@user_bp.get("/")
@login_required
@require_role("admin")
def list_users():
    return jsonify({"users": []}), 200


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
    return jsonify({"message": "user created (stub)", "username": data["username"]}), 201


@user_bp.get("/<int:user_id>")
@login_required
@require_role("admin")
def get_user(user_id: int):
    return jsonify({"error": "User not found (stub)"}), 404


@user_bp.put("/<int:user_id>")
@login_required
@require_role("admin")
def update_user(user_id: int):
    data = request.get_json(silent=True) or {}
    if not any(k in data for k in ("email", "role", "is_active")):
        return jsonify({"error": "Provide at least one of: email, role, is_active"}), 400
    return jsonify({"message": "user updated (stub)", "user_id": user_id}), 200


@user_bp.delete("/<int:user_id>")
@login_required
@require_role("admin")
def deactivate_user(user_id: int):
    return jsonify({"message": "user deactivated (stub)", "user_id": user_id}), 200
