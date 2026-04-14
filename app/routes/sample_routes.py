"""
app/routes/sample_routes.py  (fixed imports)
"""

from flask import Blueprint, request, jsonify, abort
from datetime import datetime
import io, csv

from .auth_routes import login_required, require_role   # <-- relative import

sample_bp = Blueprint("samples", __name__)


def _get_service():
    return None  # stub — wire real service in Stage 7


@sample_bp.get("/")
@login_required
def list_samples():
    filters = {}
    if request.args.get("type"):     filters["type"]     = request.args["type"]
    if request.args.get("status"):   filters["status"]   = request.args["status"]
    if request.args.get("location"): filters["location"] = request.args["location"]
    if request.args.get("user_id"):  filters["user"]     = request.args["user_id"]
    if request.args.get("date_from") and request.args.get("date_to"):
        filters["date_range"] = f"{request.args['date_from']},{request.args['date_to']}"

    page     = max(1, int(request.args.get("page", 1)))
    per_page = min(100, max(1, int(request.args.get("per_page", 20))))

    return jsonify({"samples": [], "total": 0, "page": page, "pages": 0}), 200


@sample_bp.post("/")
@login_required
@require_role("researcher", "admin")
def register_sample():
    data = request.get_json(silent=True) or {}

    required = ["sample_type", "source_organism", "collection_date", "storage_location"]
    for field in required:
        if not data.get(field):
            return jsonify({"error": f"{field} is required", "field": field}), 400

    try:
        datetime.strptime(data["collection_date"], "%Y-%m-%d")
    except ValueError:
        return jsonify({"error": "collection_date must be YYYY-MM-DD", "field": "collection_date"}), 400

    return jsonify({"message": "sample registered (stub)", "sample_id": "LT-2025-0001"}), 201


@sample_bp.get("/<string:sample_id>")
@login_required
def get_sample(sample_id: str):
    return jsonify({"error": "Sample not found (stub)"}), 404


@sample_bp.put("/<string:sample_id>/status")
@login_required
@require_role("researcher", "technician", "admin")
def update_status(sample_id: str):
    data = request.get_json(silent=True) or {}
    if not data.get("status", "").strip():
        return jsonify({"error": "status is required"}), 400
    return jsonify({"message": "status updated (stub)", "sample_id": sample_id}), 200


@sample_bp.post("/import")
@login_required
@require_role("researcher", "admin")
def import_csv():
    if "file" not in request.files:
        return jsonify({"error": "No file uploaded. Provide a multipart field named 'file'."}), 400
    file = request.files["file"]
    if not file.filename.endswith(".csv"):
        return jsonify({"error": "Only .csv files are accepted."}), 400
    return jsonify({"imported": 0, "errors": ["CSV import stub — not yet wired to DB"]}), 200


@sample_bp.get("/export")
@login_required
def export_csv():
    from flask import Response
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=[
        "sample_id", "sample_type", "source_organism",
        "collection_date", "storage_location", "status", "notes"
    ])
    writer.writeheader()
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": 'attachment; filename="labtrack_export.csv"'}
    )
