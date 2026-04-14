"""
app/routes/user_routes.py
==========================
ARCHITECTURE LAYER: Presentation (Flask Blueprint)
----------------------------------------------------
REST API for user account management (admin-only operations).

API Endpoints
-------------
GET    /api/users/         — List all users          [admin only]
POST   /api/users/         — Create new user account [admin only, FR-04]
GET    /api/users/<id>     — Get user detail          [admin only]
PUT    /api/users/<id>     — Update user (role/email) [admin only]
DELETE /api/users/<id>     — Deactivate user account  [admin only]

Pattern used: Factory (UserFactory creates the correct User subclass from
the role string supplied in the request body).
"""

from flask import Blueprint, request, jsonify
from app.routes.auth_routes import login_required, require_role

user_bp = Blueprint("users", __name__)


@user_bp.get("/")
@login_required
@require_role("admin")
def list_users():
    """
    GET /api/users/
    ---------------
    Return all registered user accounts.

    Response (200 OK):
        { "users": [ { user_id, username, email, role, is_active }, ... ] }
    """
    # Stage 7:
    # from patterns.singleton_meta import UserRepository
    # users = UserRepository().get_all()
    # return jsonify({"users": [
    #     {"user_id": u.get_user_id(), "username": u.get_username(),
    #      "email": u.get_email(), "role": u.get_role(),
    #      "is_active": u.is_active()} for u in users
    # ]}), 200
    return jsonify({"users": []}), 200


@user_bp.post("/")
@login_required
@require_role("admin")
def create_user():
    """
    POST /api/users/
    ----------------
    Create a new user account (FR-04).

    Request body (JSON):
        {
          "username":  str (required, unique),
          "email":     str (required),
          "password":  str (required, min 8 chars),
          "role":      str (required: researcher|technician|admin|viewer)
        }

    Response (201 Created):
        { user_id, username, email, role }

    Pattern used: Factory — UserFactory.create() is called with the 'role'
    field to produce the correct User subclass. This means the Presentation
    Layer never imports any User subclass directly, keeping it decoupled.
    """
    data = request.get_json(silent=True) or {}

    for field in ("username", "email", "password", "role"):
        if not data.get(field):
            return jsonify({"error": f"{field} is required"}), 400

    if len(data["password"]) < 8:
        return jsonify({"error": "password must be at least 8 characters"}), 400

    # Stage 7:
    # import bcrypt
    # from patterns.user_factory    import UserFactory
    # from patterns.singleton_meta  import UserRepository
    # password_hash = bcrypt.hashpw(data["password"].encode(), bcrypt.gensalt()).decode()
    # try:
    #     repo = UserRepository()
    #     new_id = repo.count() + 1
    #     user = UserFactory.create(new_id, data["username"], data["email"],
    #                               password_hash, data["role"])
    #     repo.add(user)
    # except ValueError as e:   # unknown role
    #     return jsonify({"error": str(e)}), 400
    # return jsonify({"user_id": user.get_user_id(), "username": user.get_username(),
    #                 "email": user.get_email(), "role": user.get_role()}), 201

    return jsonify({"message": "user created (stub)", "username": data["username"]}), 201


@user_bp.get("/<int:user_id>")
@login_required
@require_role("admin")
def get_user(user_id: int):
    """
    GET /api/users/<user_id>
    ------------------------
    Return the profile of a specific user.

    Response (200 OK):
        { user_id, username, email, role, is_active }

    Response (404 Not Found):
        { "error": "User not found" }
    """
    # Stage 7:
    # from patterns.singleton_meta import UserRepository
    # user = UserRepository().get_by_id(user_id)
    # if not user:
    #     return jsonify({"error": "User not found"}), 404
    # return jsonify({ ... }), 200
    return jsonify({"error": "User not found (stub)"}), 404


@user_bp.put("/<int:user_id>")
@login_required
@require_role("admin")
def update_user(user_id: int):
    """
    PUT /api/users/<user_id>
    ------------------------
    Update a user's email or role.

    Request body (JSON):
        { "email": str (optional), "role": str (optional), "is_active": bool (optional) }

    Response (200 OK):
        { ...updated user dict... }
    """
    data = request.get_json(silent=True) or {}

    if not any(k in data for k in ("email", "role", "is_active")):
        return jsonify({"error": "Provide at least one of: email, role, is_active"}), 400

    # Stage 7: fetch user, apply changes, call repo.update()
    return jsonify({"message": "user updated (stub)", "user_id": user_id}), 200


@user_bp.delete("/<int:user_id>")
@login_required
@require_role("admin")
def deactivate_user(user_id: int):
    """
    DELETE /api/users/<user_id>
    ---------------------------
    Deactivate (soft-delete) a user account.
    The record is retained in the database for audit purposes.

    Response (200 OK):
        { "message": "User deactivated" }
    """
    # Stage 7:
    # from patterns.singleton_meta import UserRepository
    # user = UserRepository().get_by_id(user_id)
    # if not user:
    #     return jsonify({"error": "User not found"}), 404
    # user.set_active(False)
    # UserRepository().update(user)
    # return jsonify({"message": "User deactivated"}), 200
    return jsonify({"message": "user deactivated (stub)", "user_id": user_id}), 200
