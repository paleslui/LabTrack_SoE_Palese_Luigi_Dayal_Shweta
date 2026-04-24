"""
app/routes/user_routes.py — Admin-only user management, wired to UserRepository
"""

import bcrypt
from flask import Blueprint, request, jsonify, session, g, Response
from .auth_routes import login_required, require_role
from database.db import log_activity

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

    log_activity(g.current_user_id, session.get("username", "?"),
                 "create_user", data["username"], ip=request.remote_addr)
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
    log_activity(g.current_user_id, session.get("username", "?"),
                 "deactivate_user", user.get_username(), ip=request.remote_addr)
    return jsonify({"message": f"User {user.get_username()!r} deactivated"}), 200


# ══════════════════════════════════════════════════════════════════════════════
# ACTIVITY LOG — admin-only system-level audit trail
# ══════════════════════════════════════════════════════════════════════════════

@user_bp.get("/activity-log")
@login_required
@require_role("admin")
def get_activity_log():
    """
    GET /api/users/activity-log
    Query params: limit (default 100, max 500), username, action.
    """
    from database.models import ActivityLogModel
    from database.db import db_session
    limit = min(500, max(1, int(request.args.get("limit", 100))))
    with db_session() as s:
        q = s.query(ActivityLogModel).order_by(ActivityLogModel.timestamp.desc())
        if request.args.get("username"):
            q = q.filter(ActivityLogModel.username == request.args["username"])
        if request.args.get("action"):
            q = q.filter(ActivityLogModel.action == request.args["action"])
        rows = q.limit(limit).all()
        return jsonify({"logs": [{
            "log_id":    r.log_id,
            "username":  r.username,
            "action":    r.action,
            "detail":    r.detail,
            "ip":        r.ip_address,
            "timestamp": str(r.timestamp)[:19] if r.timestamp else None,
        } for r in rows]}), 200


@user_bp.get("/activity-log/export")
@login_required
@require_role("admin")
def export_activity_log():
    """GET /api/users/activity-log/export — full activity log as CSV."""
    import io, csv as csvmod
    from database.models import ActivityLogModel
    from database.db import db_session
    output = io.StringIO()
    w = csvmod.writer(output)
    w.writerow(["timestamp", "username", "action", "detail", "ip"])
    with db_session() as s:
        rows = s.query(ActivityLogModel).order_by(ActivityLogModel.timestamp.desc()).all()
        for r in rows:
            w.writerow([str(r.timestamp)[:19] if r.timestamp else "",
                        r.username or "", r.action, r.detail or "", r.ip_address or ""])
    return Response(output.getvalue(), mimetype="text/csv",
                    headers={"Content-Disposition": 'attachment; filename="activity_log.csv"'})
