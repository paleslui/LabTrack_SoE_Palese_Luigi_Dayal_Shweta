"""
app/routes/sample_routes.py
============================
ARCHITECTURE LAYER: Presentation (Flask Blueprint)
----------------------------------------------------
REST API for biological sample management.
All requests pass through authentication before reaching business logic.

API Endpoints
-------------
GET    /api/samples/           — List samples (with optional filters)
POST   /api/samples/           — Register a new sample        [FR-06, FR-07]
GET    /api/samples/<id>       — Get sample detail by ID
PUT    /api/samples/<id>/status — Update lifecycle status     [FR-10, FR-11]
POST   /api/samples/import     — Bulk CSV import              [FR-12, FR-13]
GET    /api/samples/export     — Export filtered list as CSV  [FR-13]

Communication flow (Architecture Stage 6):
  Browser → HTTP request → [sample_routes]
         → SampleService (Application layer)
         → SampleRepository / UserRepository (Data layer, Singleton)
         → SQLite via SQLAlchemy
         ← JSON response ← Browser
"""

from flask import Blueprint, request, jsonify, abort
from datetime import datetime
import io, csv

from app.routes.auth_routes import login_required, require_role

sample_bp = Blueprint("samples", __name__)

# ── Lazy imports (Stage 7 will wire real DB; stubs used now) ──────────────────
def _get_service():
    """
    Return the SampleService instance.
    Wrapped in a function to allow easy swap to real service in Stage 7.
    """
    # Real implementation (Stage 7):
    # from patterns.singleton_meta import SampleRepository, UserRepository
    # from services.sample_service import SampleService
    # return SampleService(SampleRepository(), UserRepository())
    return None  # Stub


# ---------------------------------------------------------------------------
# LIST — GET /api/samples/
# ---------------------------------------------------------------------------

@sample_bp.get("/")
@login_required
def list_samples():
    """
    GET /api/samples/
    -----------------
    Return a filtered, paginated list of samples.

    Query parameters:
        type        : str   — filter by sample_type (partial match)
        status      : str   — filter by lifecycle status (exact)
        location    : str   — filter by storage_location (partial)
        user_id     : int   — filter by registering user
        date_from   : str   — collection_date ≥ YYYY-MM-DD
        date_to     : str   — collection_date ≤ YYYY-MM-DD
        page        : int   — page number (default 1)
        per_page    : int   — items per page (default 20, max 100)

    Response (200 OK):
        {
          "samples": [ { sample dict }, ... ],
          "total":   int,
          "page":    int,
          "pages":   int
        }

    Pattern used: Strategy (SampleSearchContext selects the filter algorithm
    based on which query parameters are present).
    """
    filters = {}
    if request.args.get("type"):     filters["type"]     = request.args["type"]
    if request.args.get("status"):   filters["status"]   = request.args["status"]
    if request.args.get("location"): filters["location"] = request.args["location"]
    if request.args.get("user_id"):  filters["user"]     = request.args["user_id"]
    if request.args.get("date_from") and request.args.get("date_to"):
        filters["date_range"] = f"{request.args['date_from']},{request.args['date_to']}"

    page     = max(1, int(request.args.get("page", 1)))
    per_page = min(100, max(1, int(request.args.get("per_page", 20))))

    # Stage 7: replace with real service call
    # service = _get_service()
    # from patterns.search_strategy import SampleSearchContext, SearchByType
    # ctx = SampleSearchContext(SearchByType())
    # all_samples = ctx.multi_search(service._sample_repo.get_all(), filters)
    # paginated   = all_samples[(page-1)*per_page : page*per_page]
    # return jsonify({ "samples": [s.to_dict() for s in paginated], ... })

    return jsonify({"samples": [], "total": 0, "page": page, "pages": 0}), 200


# ---------------------------------------------------------------------------
# CREATE — POST /api/samples/
# ---------------------------------------------------------------------------

@sample_bp.post("/")
@login_required
def register_sample():
    """
    POST /api/samples/
    ------------------
    Register a new biological sample (FR-06, FR-07).

    Request body (JSON):
        {
          "sample_type":      str  (required),
          "source_organism":  str  (required),
          "collection_date":  str  "YYYY-MM-DD" (required),
          "storage_location": str  (required),
          "notes":            str  (optional)
        }

    Response (201 Created):
        { sample dict }   — includes auto-generated LT-YYYY-NNNN sample_id

    Response (400 Bad Request):
        { "error": "...", "field": "..." }

    Response (403 Forbidden):
        { "error": "Insufficient permissions" }

    Pattern used: Factory (UserFactory reconstructs the User from session to
    check can_register_sample() permission before delegating to repository).
    """
    data = request.get_json(silent=True) or {}

    required = ["sample_type", "source_organism", "collection_date", "storage_location"]
    for field in required:
        if not data.get(field):
            return jsonify({"error": f"{field} is required", "field": field}), 400

    try:
        collection_date = datetime.strptime(data["collection_date"], "%Y-%m-%d")
    except ValueError:
        return jsonify({
            "error": "collection_date must be in YYYY-MM-DD format",
            "field": "collection_date"
        }), 400

    # Stage 7: replace with real service call
    # from app.routes.auth_routes import g
    # service = _get_service()
    # sample = service.register_sample(
    #     requesting_user_id=g.current_user_id,
    #     sample_type=data["sample_type"],
    #     source_organism=data["source_organism"],
    #     collection_date=collection_date,
    #     storage_location=data["storage_location"],
    #     notes=data.get("notes", "")
    # )
    # return jsonify(sample.to_dict()), 201

    return jsonify({"message": "sample registered (stub)", "sample_id": "LT-2025-0001"}), 201


# ---------------------------------------------------------------------------
# READ — GET /api/samples/<sample_id>
# ---------------------------------------------------------------------------

@sample_bp.get("/<string:sample_id>")
@login_required
def get_sample(sample_id: str):
    """
    GET /api/samples/<sample_id>
    ----------------------------
    Return full detail for a single sample, including its audit log.

    Response (200 OK):
        {
          ...sample fields...,
          "audit_log": [ { audit entry dict }, ... ]
        }

    Response (404 Not Found):
        { "error": "Sample not found" }
    """
    # Stage 7: replace with real service call
    # service = _get_service()
    # try:
    #     sample = service.get_sample(sample_id)
    # except KeyError:
    #     return jsonify({"error": "Sample not found"}), 404
    # result = sample.to_dict()
    # result["audit_log"] = [e.to_dict() for e in sample.get_audit_log()]
    # return jsonify(result), 200

    return jsonify({"error": "Sample not found (stub)"}), 404


# ---------------------------------------------------------------------------
# UPDATE STATUS — PUT /api/samples/<sample_id>/status
# ---------------------------------------------------------------------------

@sample_bp.put("/<string:sample_id>/status")
@login_required
def update_status(sample_id: str):
    """
    PUT /api/samples/<sample_id>/status
    ------------------------------------
    Transition a sample to a new lifecycle status (FR-10, FR-11).

    Request body (JSON):
        { "status": "Processing" | "Stored" | "Consumed" | "Discarded" }

    Response (200 OK):
        { ...updated sample dict... }

    Response (400 Bad Request):
        { "error": "Invalid transition: Collected → Stored" }

    Response (403 Forbidden):
        { "error": "Insufficient permissions" }

    Pattern used: The lifecycle transition rules enforced by Sample.update_status()
    implement a State-like validation. Permission check uses polymorphism
    (user.can_update_status()).
    """
    data = request.get_json(silent=True) or {}
    new_status_str = data.get("status", "").strip()

    if not new_status_str:
        return jsonify({"error": "status is required"}), 400

    # Stage 7: replace with real service call
    # from models.sample import SampleStatus
    # from app.routes.auth_routes import g
    # try:
    #     new_status = SampleStatus(new_status_str)
    # except ValueError:
    #     valid = [s.value for s in SampleStatus]
    #     return jsonify({"error": f"Invalid status. Valid: {valid}"}), 400
    # service = _get_service()
    # try:
    #     updated = service.update_sample_status(g.current_user_id, sample_id, new_status)
    # except PermissionError as e:
    #     return jsonify({"error": str(e)}), 403
    # except KeyError:
    #     return jsonify({"error": "Sample not found"}), 404
    # except ValueError as e:
    #     return jsonify({"error": str(e)}), 400
    # return jsonify(updated.to_dict()), 200

    return jsonify({"message": "status updated (stub)", "sample_id": sample_id}), 200


# ---------------------------------------------------------------------------
# CSV IMPORT — POST /api/samples/import
# ---------------------------------------------------------------------------

@sample_bp.post("/import")
@login_required
@require_role("researcher", "admin")
def import_csv():
    """
    POST /api/samples/import
    ------------------------
    Bulk-import samples from an uploaded CSV file (FR-12).

    Request: multipart/form-data with field "file" containing a CSV.

    CSV required columns:
        sample_type, source_organism, collection_date (YYYY-MM-DD),
        storage_location

    CSV optional columns:
        notes

    Response (200 OK):
        {
          "imported": int,   — number of rows successfully registered
          "errors":   [ "Row 3: collection_date must be YYYY-MM-DD", ... ]
        }

    Pattern used: Adapter (CsvImportAdapter translates the raw CSV into the
    dict interface expected by SampleService.register_sample()).
    """
    if "file" not in request.files:
        return jsonify({"error": "No file uploaded. Provide a multipart field named 'file'."}), 400

    file = request.files["file"]
    if not file.filename.endswith(".csv"):
        return jsonify({"error": "Only .csv files are accepted."}), 400

    csv_content = file.read().decode("utf-8", errors="replace")

    # Stage 7: replace with real service + adapter call
    # from patterns.csv_adapter import CsvImportAdapter
    # from app.routes.auth_routes import g
    # adapter = CsvImportAdapter(csv_content)
    # valid_rows, errors = adapter.parse()
    # service = _get_service()
    # imported = 0
    # for row in valid_rows:
    #     try:
    #         service.register_sample(requesting_user_id=g.current_user_id, **row)
    #         imported += 1
    #     except Exception as e:
    #         errors.append(str(e))
    # return jsonify({"imported": imported, "errors": errors}), 200

    return jsonify({"imported": 0, "errors": ["CSV import stub — not yet wired to DB"]}), 200


# ---------------------------------------------------------------------------
# CSV EXPORT — GET /api/samples/export
# ---------------------------------------------------------------------------

@sample_bp.get("/export")
@login_required
def export_csv():
    """
    GET /api/samples/export
    -----------------------
    Export the current sample list (with active filters) as a downloadable CSV.
    Accepts the same query parameters as GET /api/samples/.

    Response (200 OK):
        Content-Type: text/csv
        Content-Disposition: attachment; filename="labtrack_export.csv"
        [CSV rows]
    """
    from flask import Response

    # Stage 7: apply filters via SampleSearchContext and stream CSV
    # (same filter logic as list_samples endpoint)
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=[
        "sample_id", "sample_type", "source_organism",
        "collection_date", "storage_location", "status", "notes"
    ])
    writer.writeheader()
    # writer.writerows([s.to_dict() for s in filtered_samples])

    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": 'attachment; filename="labtrack_export.csv"'}
    )
