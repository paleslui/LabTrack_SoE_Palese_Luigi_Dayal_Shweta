"""
app/routes/sample_routes.py — Full REST API for samples, wired to SampleService
"""

from flask import Blueprint, request, jsonify, abort, g, Response
from datetime import datetime
import io, csv

from .auth_routes import login_required, require_role

sample_bp = Blueprint("samples", __name__)


def _get_service():
    from repositories.sample_repository import SampleRepository
    from repositories.user_repository import UserRepository
    from services.sample_service import SampleService
    return SampleService(SampleRepository(), UserRepository())


def _get_username(user_id: int) -> str:
    from repositories.user_repository import UserRepository
    u = UserRepository().get_by_id(user_id)
    return u.get_username() if u else str(user_id)


@sample_bp.get("/")
@login_required
def list_samples():
    service = _get_service()
    from models.sample import SampleStatus
    from patterns.search_strategy import SampleSearchContext, SearchByType, SearchByStatus, SearchByLocation, SearchByDateRange

    all_samples = service._sample_repo.get_all()

    # Apply filters via Strategy pattern
    filters = {}
    if request.args.get("type"):     filters["type"]     = request.args["type"]
    if request.args.get("status"):   filters["status"]   = request.args["status"]
    if request.args.get("location"): filters["location"] = request.args["location"]
    if request.args.get("date_from") and request.args.get("date_to"):
        filters["date_range"] = f"{request.args['date_from']},{request.args['date_to']}"

    results = all_samples
    if filters:
        ctx = SampleSearchContext(SearchByType())
        results = ctx.multi_search(all_samples, filters)

    page     = max(1, int(request.args.get("page", 1)))
    per_page = min(100, max(1, int(request.args.get("per_page", 50))))
    total    = len(results)
    start    = (page - 1) * per_page
    paged    = results[start:start + per_page]

    return jsonify({
        "samples": [s.to_dict() for s in paged],
        "total":   total,
        "page":    page,
        "pages":   (total + per_page - 1) // per_page if per_page else 1,
    }), 200


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
        collection_date = datetime.strptime(data["collection_date"], "%Y-%m-%d")
    except ValueError:
        return jsonify({"error": "collection_date must be YYYY-MM-DD", "field": "collection_date"}), 400

    try:
        service = _get_service()
        sample = service.register_sample(
            requesting_user_id=g.current_user_id,
            sample_type=data["sample_type"],
            source_organism=data["source_organism"],
            collection_date=collection_date,
            storage_location=data["storage_location"],
            notes=data.get("notes", ""),
        )
        return jsonify(sample.to_dict()), 201
    except PermissionError as e:
        return jsonify({"error": str(e)}), 403
    except ValueError as e:
        return jsonify({"error": str(e)}), 400


@sample_bp.get("/export")
@login_required
def export_csv():
    service = _get_service()
    all_samples = service._sample_repo.get_all()

    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=[
        "sample_id", "sample_type", "source_organism",
        "collection_date", "storage_location", "status", "notes"
    ])
    writer.writeheader()
    for s in all_samples:
        d = s.to_dict()
        writer.writerow({k: d[k] for k in writer.fieldnames})

    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": 'attachment; filename="labtrack_export.csv"'}
    )


@sample_bp.get("/<string:sample_id>")
@login_required
def get_sample(sample_id: str):
    service = _get_service()
    try:
        sample = service.get_sample(sample_id)
    except KeyError:
        return jsonify({"error": "Sample not found"}), 404

    result = sample.to_dict()
    result["created_by_username"] = _get_username(sample.get_created_by_id())
    result["audit_log"] = []
    for entry in sample.get_audit_log():
        e = entry.to_dict()
        e["changed_by_username"] = _get_username(entry.get_changed_by_id())
        result["audit_log"].append(e)

    return jsonify(result), 200


@sample_bp.put("/<string:sample_id>/status")
@login_required
@require_role("researcher", "technician", "admin")
def update_status(sample_id: str):
    data = request.get_json(silent=True) or {}
    new_status_str = data.get("status", "").strip()
    if not new_status_str:
        return jsonify({"error": "status is required"}), 400

    from models.sample import SampleStatus
    try:
        new_status = SampleStatus(new_status_str)
    except ValueError:
        valid = [s.value for s in SampleStatus]
        return jsonify({"error": f"Invalid status. Valid values: {valid}"}), 400

    try:
        service = _get_service()
        sample  = service.update_sample_status(g.current_user_id, sample_id, new_status)
        result  = sample.to_dict()
        result["audit_log"] = [e.to_dict() for e in sample.get_audit_log()]
        return jsonify(result), 200
    except PermissionError as e:
        return jsonify({"error": str(e)}), 403
    except KeyError:
        return jsonify({"error": "Sample not found"}), 404
    except ValueError as e:
        return jsonify({"error": str(e)}), 400


@sample_bp.post("/import")
@login_required
@require_role("researcher", "admin")
def import_csv():
    if "file" not in request.files:
        return jsonify({"error": "No file uploaded. Provide a multipart field named 'file'."}), 400
    file = request.files["file"]
    if not file.filename.endswith(".csv"):
        return jsonify({"error": "Only .csv files are accepted."}), 400

    from patterns.csv_adapter import CsvImportAdapter
    csv_text = file.read().decode("utf-8", errors="replace")
    adapter  = CsvImportAdapter(csv_text)
    valid_rows, errors = adapter.parse()

    service  = _get_service()
    imported = 0
    for row in valid_rows:
        try:
            service.register_sample(
                requesting_user_id=g.current_user_id,
                sample_type=row["sample_type"],
                source_organism=row["source_organism"],
                collection_date=datetime.strptime(row["collection_date"], "%Y-%m-%d"),
                storage_location=row["storage_location"],
                notes=row.get("notes", ""),
            )
            imported += 1
        except Exception as e:
            errors.append(str(e))

    return jsonify({"imported": imported, "errors": errors}), 200
