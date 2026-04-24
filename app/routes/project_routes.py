"""
app/routes/project_routes.py — CRUD for sample project groupings.
"""

from flask import Blueprint, request, jsonify, g, session
from .auth_routes import login_required, require_role

project_bp = Blueprint("projects", __name__)


def _repo():
    from repositories.project_repository import ProjectRepository
    return ProjectRepository()


@project_bp.get("/")
@login_required
def list_projects():
    return jsonify({"projects": _repo().get_all()}), 200


@project_bp.post("/")
@login_required
@require_role("researcher", "admin")
def create_project():
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    if not name:
        return jsonify({"error": "Project name is required"}), 400
    try:
        proj = _repo().create(
            name=name,
            description=data.get("description", ""),
            created_by_id=g.current_user_id,
        )
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    from database.db import log_activity
    log_activity(g.current_user_id, session.get("username", "?"),
                 "create_project", proj["name"], ip=request.remote_addr)

    return jsonify(proj), 201


@project_bp.delete("/<int:project_id>")
@login_required
@require_role("admin")
def delete_project(project_id: int):
    try:
        _repo().delete(project_id)
    except KeyError:
        return jsonify({"error": "Project not found"}), 404

    from database.db import log_activity
    log_activity(g.current_user_id, session.get("username", "?"),
                 "delete_project", str(project_id), ip=request.remote_addr)

    return jsonify({"message": f"Project {project_id} deleted"}), 200
