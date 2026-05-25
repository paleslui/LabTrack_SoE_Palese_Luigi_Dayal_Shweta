"""
app/routes/sample_routes.py — Full REST API for samples, wired to SampleService
"""

# Architecture note:
# Core operations (register, update_status) flow through SampleService as per
# the three-tier layered design. Extended operations added in v11.0 (bulk ops,
# edit, reservations, attachments) access the repository via the service instance
# (_get_service()._sample_repo) as a pragmatic shortcut — these do not require
# business rule validation beyond what the DB constraints enforce.
# The Strategy pattern (search_strategy.py) is applied here rather than inside
# SampleService because search is a presentation-layer concern: it depends on
# HTTP query parameters which SampleService deliberately has no knowledge of.

from flask import Blueprint, request, jsonify, abort, g, Response, session
from datetime import datetime
import io, csv

from .auth_routes import login_required, require_role
from database.db import log_activity

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
    if request.args.get("date_from") and request.args.get("date_to"):
        filters["date_range"] = f"{request.args['date_from']},{request.args['date_to']}"
    # Filter by submitter username — resolve to user_id first
    if request.args.get("submitted_by"):
        from repositories.user_repository import UserRepository
        u = UserRepository().get_by_username(request.args["submitted_by"].strip())
        if u:
            filters["user"] = str(u.get_user_id())

    results = all_samples
    if filters:
        ctx = SampleSearchContext(SearchByType())
        results = ctx.multi_search(all_samples, filters)

    # Location search — matches across all structured + legacy location fields
    if request.args.get("location"):
        loc = request.args["location"].lower()
        results = [s for s in results if
            loc in (s.get_storage_location() or "").lower() or
            loc in (s.get_location_building() or "").lower() or
            loc in (s.get_location_room() or "").lower() or
            loc in (s.get_location_equipment() or "").lower() or
            loc in (s.get_location_position() or "").lower()]

    # Parent sample filter — lineage
    if request.args.get("parent_id"):
        pid = request.args["parent_id"]
        results = [s for s in results if s.get_parent_sample_id() == pid]

    # Project filter
    if request.args.get("project_id"):
        try:
            proj_id = int(request.args["project_id"])
            results = [s for s in results if s.get_project_id() == proj_id]
        except ValueError:
            pass

    # Reserved-only filter — active reservations whose expiry is still in the future
    if request.args.get("reserved_only") in ("1", "true", "yes"):
        now = datetime.utcnow()
        results = [s for s in results
                   if s.get_reserved_by() is not None
                   and s.get_reserved_until() is not None
                   and s.get_reserved_until() > now]

    page     = max(1, int(request.args.get("page", 1)))
    per_page = min(500, max(1, int(request.args.get("per_page", 50))))
    total    = len(results)
    start    = (page - 1) * per_page
    paged    = results[start:start + per_page]

    from repositories.user_repository import UserRepository
    user_repo = UserRepository()
    user_cache: dict[int, str] = {}
    def _uname(uid: int) -> str:
        if uid not in user_cache:
            u = user_repo.get_by_id(uid)
            user_cache[uid] = u.get_username() if u else str(uid)
        return user_cache[uid]

    sample_dicts = []
    for s in paged:
        d = s.to_dict()
        d["created_by_username"] = _uname(s.get_created_by_id())
        if s.get_reserved_by() is not None:
            d["reserved_by_username"] = _uname(s.get_reserved_by())
        sample_dicts.append(d)

    return jsonify({
        "samples": sample_dicts,
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

    # Parse optional expiry_date
    expiry_date = None
    if data.get("expiry_date"):
        try:
            expiry_date = datetime.strptime(data["expiry_date"], "%Y-%m-%d").date()
        except ValueError:
            return jsonify({"error": "expiry_date must be YYYY-MM-DD", "field": "expiry_date"}), 400

    # Parse optional quantity
    quantity = None
    if data.get("quantity") is not None and data.get("quantity") != "":
        try:
            quantity = float(data["quantity"])
        except (ValueError, TypeError):
            return jsonify({"error": "quantity must be a number", "field": "quantity"}), 400

    try:
        service = _get_service()
        sample = service.register_sample(
            requesting_user_id=g.current_user_id,
            sample_type=data["sample_type"],
            source_organism=data["source_organism"],
            collection_date=collection_date,
            storage_location=data["storage_location"],
            notes=data.get("notes", ""),
            expiry_date=expiry_date,
            quantity=quantity,
            quantity_unit=data.get("quantity_unit") or None,
            location_building=data.get("location_building") or None,
            location_room=data.get("location_room") or None,
            location_equipment=data.get("location_equipment") or None,
            location_position=data.get("location_position") or None,
            parent_sample_id=data.get("parent_sample_id") or None,
            project_id=int(data["project_id"]) if data.get("project_id") else None,
        )
        log_activity(g.current_user_id, session.get("username", "?"),
                     "register_sample", sample.get_sample_id(), ip=request.remote_addr)
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


@sample_bp.get("/audit-export")
@login_required
def export_full_audit():
    """
    GET /api/samples/audit-export
    Export the complete audit log for ALL samples as CSV.
    Useful for regulatory compliance (GLP, ISO 15189).
    Optional query param: sample_id — export audit for one specific sample.
    """
    import csv as csvmod
    from repositories.user_repository import UserRepository
    from repositories.sample_repository import SampleRepository
    sample_repo = SampleRepository()
    user_repo   = UserRepository()

    filter_id = request.args.get("sample_id")

    output  = io.StringIO()
    writer  = csvmod.writer(output)
    writer.writerow(["sample_id", "sample_type", "timestamp",
                     "old_status", "new_status", "changed_by"])

    user_cache = {}
    def uname(uid):
        if uid not in user_cache:
            u = user_repo.get_by_id(uid)
            user_cache[uid] = u.get_username() if u else str(uid)
        return user_cache[uid]

    samples = ([sample_repo.get_by_id(filter_id)] if filter_id
               else sample_repo.get_all())
    samples = [s for s in samples if s is not None]

    for sample in samples:
        for entry in sample.get_audit_log():
            writer.writerow([
                sample.get_sample_id(),
                sample.get_sample_type(),
                str(entry.get_timestamp())[:19],
                entry.get_old_status().value,
                entry.get_new_status().value,
                uname(entry.get_changed_by_id()),
            ])

    fname = f"audit_{filter_id}.csv" if filter_id else "audit_full.csv"
    return Response(
        output.getvalue(), mimetype="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{fname}"'}
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
    if sample.get_reserved_by() is not None:
        result["reserved_by_username"] = _get_username(sample.get_reserved_by())
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
        log_activity(g.current_user_id, session.get("username", "?"),
                     "update_status", f"{sample_id} → {new_status_str}",
                     ip=request.remote_addr)
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
    repo     = service._sample_repo

    # Pre-load existing sample types+organism+date combos to detect duplicates
    existing = repo.get_all()
    existing_keys = set()
    for s in existing:
        key = (
            s.get_sample_type().lower().strip(),
            s.get_source_organism().lower().strip(),
            s.get_collection_date().strftime("%Y-%m-%d"),
            s.get_storage_location().lower().strip(),
        )
        existing_keys.add(key)

    imported, duplicates = 0, []
    for i, row in enumerate(valid_rows, start=2):  # row 2 = first data row (row 1 = header)
        key = (
            row["sample_type"].lower().strip(),
            row["source_organism"].lower().strip(),
            row["collection_date"].strftime("%Y-%m-%d"),
            row["storage_location"].lower().strip(),
        )
        if key in existing_keys:
            duplicates.append(
                f"Row {i}: duplicate — a sample with the same type, organism, "
                f"date and location already exists in the database."
            )
            continue
        try:
            service.register_sample(
                requesting_user_id=g.current_user_id,
                sample_type=row["sample_type"],
                source_organism=row["source_organism"],
                collection_date=row["collection_date"],
                storage_location=row["storage_location"],
                notes=row.get("notes", ""),
            )
            existing_keys.add(key)  # prevent intra-file duplicates too
            imported += 1
        except Exception as e:
            errors.append(f"Row {i}: {e}")

    all_errors = errors + duplicates
    if imported:
        log_activity(g.current_user_id, session.get("username", "?"),
                     "import_csv", f"{imported} samples", ip=request.remote_addr)
    return jsonify({
        "imported":   imported,
        "duplicates": len(duplicates),
        "errors":     all_errors,
    }), 200


@sample_bp.put("/bulk-status")
@login_required
@require_role("researcher", "technician", "admin")
def bulk_update_status():
    """
    PUT /api/samples/bulk-status
    Body: { "sample_ids": [...], "status": "Processing" }
    """
    data = request.get_json(silent=True) or {}
    sample_ids = data.get("sample_ids", [])
    new_status_str = data.get("status", "").strip()

    if not sample_ids or not new_status_str:
        return jsonify({"error": "sample_ids and status are required"}), 400

    from models.sample import SampleStatus
    try:
        new_status = SampleStatus(new_status_str)
    except ValueError:
        return jsonify({"error": f"Invalid status: {new_status_str}"}), 400

    svc = _get_service()
    updated, failed = 0, []
    for sid in sample_ids:
        try:
            svc.update_sample_status(g.current_user_id, sid, new_status)
            updated += 1
        except Exception as e:
            failed.append({"sample_id": sid, "error": str(e)})

    return jsonify({"updated": updated, "failed": failed}), 200


@sample_bp.post("/bulk-export")
@login_required
def bulk_export():
    """
    POST /api/samples/bulk-export
    Body: { "sample_ids": [...] }
    """
    data = request.get_json(silent=True) or {}
    sample_ids = set(data.get("sample_ids", []))
    if not sample_ids:
        return jsonify({"error": "sample_ids required"}), 400

    repo = _get_service()._sample_repo
    samples = [s for s in repo.get_all() if s.get_sample_id() in sample_ids]

    output = io.StringIO()
    w = csv.DictWriter(output, fieldnames=[
        "sample_id", "sample_type", "source_organism",
        "collection_date", "storage_location", "status", "notes",
    ])
    w.writeheader()
    for s in samples:
        d = s.to_dict()
        w.writerow({k: d[k] for k in w.fieldnames})

    return Response(
        output.getvalue(), mimetype="text/csv",
        headers={"Content-Disposition": 'attachment; filename="labtrack_bulk_export.csv"'}
    )


@sample_bp.put("/<string:sample_id>")
@login_required
@require_role("researcher", "technician", "admin")
def update_sample(sample_id: str):
    """
    PUT /api/samples/<id>
    Update any sample field except sample_id.
    Body: { sample_type, source_organism, collection_date, storage_location,
            notes, expiry_date, quantity, quantity_unit,
            location_building, location_room, location_equipment, location_position,
            parent_sample_id }
    All fields optional — only provided fields are updated.
    """
    data = request.get_json(silent=True) or {}
    repo = _get_service()._sample_repo
    sample = repo.get_by_id(sample_id)
    if not sample:
        return jsonify({"error": "Sample not found"}), 404

    # Update each field if provided
    if "sample_type" in data and data["sample_type"].strip():
        sample._sample_type = data["sample_type"].strip()
    if "source_organism" in data and data["source_organism"].strip():
        sample._source_organism = data["source_organism"].strip()
    if "collection_date" in data and data["collection_date"]:
        try:
            sample._collection_date = datetime.strptime(data["collection_date"], "%Y-%m-%d")
        except ValueError:
            return jsonify({"error": "collection_date must be YYYY-MM-DD"}), 400
    if "storage_location" in data and data["storage_location"].strip():
        sample._storage_location = data["storage_location"].strip()
    if "notes" in data:
        sample._notes = data["notes"]
    if "expiry_date" in data:
        if data["expiry_date"]:
            try:
                sample._expiry_date = datetime.strptime(data["expiry_date"], "%Y-%m-%d").date()
            except ValueError:
                return jsonify({"error": "expiry_date must be YYYY-MM-DD"}), 400
        else:
            sample._expiry_date = None
    if "quantity" in data:
        sample._quantity = float(data["quantity"]) if data["quantity"] not in (None, "") else None
    if "quantity_unit" in data:
        sample._quantity_unit = data["quantity_unit"] or None
    if "location_building" in data:
        sample._location_building = data["location_building"] or None
    if "location_room" in data:
        sample._location_room = data["location_room"] or None
    if "location_equipment" in data:
        sample._location_equipment = data["location_equipment"] or None
    if "location_position" in data:
        sample._location_position = data["location_position"] or None
    if "parent_sample_id" in data:
        sample._parent_sample_id = data["parent_sample_id"] or None
    if "project_id" in data:
        pid = data["project_id"]
        sample._project_id = int(pid) if pid not in (None, "", 0, "0") else None

    sample._updated_at = datetime.utcnow()
    repo.update(sample)
    log_activity(g.current_user_id, session.get("username", "?"),
                 "update_sample", sample_id, ip=request.remote_addr)
    return jsonify(sample.to_dict()), 200


@sample_bp.delete("/<string:sample_id>")
@login_required
@require_role("researcher", "technician", "admin")
def delete_sample(sample_id: str):
    repo = _get_service()._sample_repo
    sample = repo.get_by_id(sample_id)
    if not sample:
        return jsonify({"error": "Sample not found"}), 404
    try:
        repo.delete(sample_id)
        log_activity(g.current_user_id, session.get("username", "?"),
                     "delete_sample", sample_id, ip=request.remote_addr)
        return jsonify({"message": f"Sample {sample_id} deleted"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@sample_bp.delete("/bulk-delete")
@login_required
@require_role("researcher", "technician", "admin")
def bulk_delete():
    """
    DELETE /api/samples/bulk-delete
    Body: { "sample_ids": [...] }
    """
    data = request.get_json(silent=True) or {}
    sample_ids = data.get("sample_ids", [])
    if not sample_ids:
        return jsonify({"error": "sample_ids required"}), 400

    repo = _get_service()._sample_repo
    deleted, failed = 0, []
    for sid in sample_ids:
        try:
            repo.delete(sid)
            deleted += 1
        except KeyError as e:
            failed.append({"sample_id": sid, "error": str(e)})

    if deleted:
        log_activity(g.current_user_id, session.get("username", "?"),
                     "bulk_delete", f"{deleted} samples", ip=request.remote_addr)
    return jsonify({"deleted": deleted, "failed": failed}), 200


@sample_bp.patch("/<string:sample_id>/notes")
@login_required
@require_role("researcher", "technician", "admin")
def update_notes(sample_id: str):
    """
    PATCH /api/samples/<id>/notes
    Body: { "notes": str }
    """
    data = request.get_json(silent=True) or {}
    notes = data.get("notes", "")
    from repositories.sample_repository import SampleRepository
    repo = SampleRepository()
    sample = repo.get_by_id(sample_id)
    if not sample:
        return jsonify({"error": "Sample not found"}), 404
    sample.set_notes(notes)
    repo.update(sample)
    return jsonify({"message": "Notes updated", "notes": notes}), 200


@sample_bp.get("/<string:sample_id>/children")
@login_required
def get_children(sample_id: str):
    """GET /api/samples/<id>/children — returns all samples derived from this one."""
    repo = _get_service()._sample_repo
    all_samples = repo.get_all()
    children = [s.to_dict() for s in all_samples if s.get_parent_sample_id() == sample_id]
    return jsonify({"children": children, "total": len(children)}), 200


def _build_label_image(sample, width: int = 400, height: int = 200, host: str = "localhost:5001"):
    """Render a single PNG label (QR on left, metadata on right). Returns a PIL Image.
    
    The QR code encodes a live URL (http://<host>/view/<sample_id>) rather than
    static sample data. When scanned, it fetches the current state from the server —
    so status changes, quantity updates, and notes edits are always reflected.
    The physical printed label never needs to change.
    """
    import qrcode
    from PIL import Image, ImageDraw

    # Encode live URL — the QR code is permanent but the page it points to is always current
    live_url = f"http://{host}/view/{sample.get_sample_id()}"
    qr = qrcode.QRCode(version=2, box_size=6, border=2,
                       error_correction=qrcode.constants.ERROR_CORRECT_M)
    qr.add_data(live_url)
    qr.make(fit=True)
    qr_img = qr.make_image(fill_color="black", back_color="white")

    label = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(label)
    qr_size = 160
    label.paste(qr_img.resize((qr_size, qr_size)), (10, 20))

    x = qr_size + 20
    draw.text((x, 20),  sample.get_sample_id(),       fill="black")
    draw.text((x, 44),  sample.get_sample_type(),      fill="#444")
    draw.text((x, 62),  sample.get_source_organism(),  fill="#444")
    loc = sample.get_full_location() or sample.get_storage_location() or ""
    draw.text((x, 80),  loc[:28],                      fill="#444")
    draw.text((x, 98),  sample.get_status().value,     fill="#2E75B6")
    if sample.get_expiry_date():
        draw.text((x, 116), f"Exp: {sample.get_expiry_date()}", fill="#842029")
    if sample.get_quantity():
        qty_text = f"Qty: {sample.get_quantity()} {sample.get_quantity_unit() or ''}"
        draw.text((x, 134), qty_text, fill="#444")

    draw.rectangle([0, 0, width - 1, height - 1], outline="#CCCCCC", width=1)
    return label


@sample_bp.get("/<string:sample_id>/label")
@login_required
def get_label(sample_id: str):
    """GET /api/samples/<id>/label — returns a PNG label with QR code."""
    from io import BytesIO
    from flask import send_file

    repo = _get_service()._sample_repo
    sample = repo.get_by_id(sample_id)
    if not sample:
        return jsonify({"error": "Sample not found"}), 404

    label = _build_label_image(sample, host=request.host)
    buf = BytesIO()
    label.save(buf, format="PNG")
    buf.seek(0)
    return send_file(buf, mimetype="image/png",
                     download_name=f"{sample_id}_label.png")


@sample_bp.post("/bulk-labels")
@login_required
def bulk_labels():
    """POST /api/samples/bulk-labels — returns a PNG with labels in a 3-column grid."""
    from io import BytesIO
    from flask import send_file
    from PIL import Image

    data = request.get_json(silent=True) or {}
    sample_ids = set(data.get("sample_ids", []))
    if not sample_ids:
        return jsonify({"error": "sample_ids required"}), 400

    repo = _get_service()._sample_repo
    samples = [s for s in repo.get_all() if s.get_sample_id() in sample_ids]
    if not samples:
        return jsonify({"error": "No matching samples"}), 404

    LABEL_W, LABEL_H = 400, 200
    COLS = 3
    rows = -(-len(samples) // COLS)
    sheet = Image.new("RGB", (LABEL_W * COLS, LABEL_H * rows), "white")
    for i, s in enumerate(samples):
        label = _build_label_image(s, LABEL_W, LABEL_H)
        sheet.paste(label, ((i % COLS) * LABEL_W, (i // COLS) * LABEL_H))

    buf = BytesIO()
    sheet.save(buf, format="PNG")
    buf.seek(0)
    return send_file(buf, mimetype="image/png", download_name="labtrack_labels.png")


# ══════════════════════════════════════════════════════════════════════════════
# RESERVATION — place a soft lock on a sample
# ══════════════════════════════════════════════════════════════════════════════

@sample_bp.post("/<string:sample_id>/reserve")
@login_required
@require_role("researcher", "technician", "admin")
def reserve_sample(sample_id: str):
    """
    POST /api/samples/<id>/reserve
    Body: { "until": "YYYY-MM-DD", "note": str (optional) }
    """
    data = request.get_json(silent=True) or {}
    until_str = (data.get("until") or "").strip()
    if not until_str:
        return jsonify({"error": "until (YYYY-MM-DD) is required"}), 400
    try:
        until_dt = datetime.strptime(until_str, "%Y-%m-%d")
    except ValueError:
        return jsonify({"error": "until must be YYYY-MM-DD"}), 400
    if until_dt <= datetime.utcnow():
        return jsonify({"error": "Reservation 'until' must be in the future"}), 400

    repo = _get_service()._sample_repo
    sample = repo.get_by_id(sample_id)
    if not sample:
        return jsonify({"error": "Sample not found"}), 404

    sample._reserved_by      = g.current_user_id
    sample._reserved_until   = until_dt
    sample._reservation_note = (data.get("note") or "").strip() or None
    sample._updated_at       = datetime.utcnow()
    repo.update(sample)

    log_activity(g.current_user_id, session.get("username", "?"),
                 "reserve_sample", f"{sample_id} until {until_str}",
                 ip=request.remote_addr)

    result = sample.to_dict()
    result["reserved_by_username"] = _get_username(g.current_user_id)
    return jsonify(result), 200


@sample_bp.delete("/<string:sample_id>/reserve")
@login_required
def cancel_reservation(sample_id: str):
    """DELETE /api/samples/<id>/reserve — only reserver or admin can cancel."""
    repo = _get_service()._sample_repo
    sample = repo.get_by_id(sample_id)
    if not sample:
        return jsonify({"error": "Sample not found"}), 404
    if sample.get_reserved_by() is None:
        return jsonify({"error": "Sample is not reserved"}), 400

    is_admin = session.get("user_role") == "admin"
    if sample.get_reserved_by() != g.current_user_id and not is_admin:
        return jsonify({"error": "Only the reserver or an admin can lift this reservation"}), 403

    sample._reserved_by      = None
    sample._reserved_until   = None
    sample._reservation_note = None
    sample._updated_at       = datetime.utcnow()
    repo.update(sample)

    log_activity(g.current_user_id, session.get("username", "?"),
                 "cancel_reservation", sample_id, ip=request.remote_addr)

    return jsonify({"message": f"Reservation on {sample_id} lifted"}), 200


# ══════════════════════════════════════════════════════════════════════════════
# ATTACHMENTS — file uploads tied to a sample
# ══════════════════════════════════════════════════════════════════════════════

_ALLOWED_EXTENSIONS = {"pdf", "png", "jpg", "jpeg", "gif", "doc", "docx", "xlsx", "csv", "txt"}

def _check_mime(file_bytes: bytes, extension: str) -> bool:
    """
    Verify that the actual file content matches the claimed extension.
    Returns True if the file looks safe, False if it looks like a disguised file.
    We only reject files whose magic bytes clearly indicate a dangerous type
    (e.g. ELF executable, PE executable, shell script).
    """
    DANGEROUS_SIGS = [
        b"\x7fELF",        # Linux ELF executable
        b"MZ",              # Windows PE executable
        b"#!/",             # Shell script
        b"#!",              # Shebang
        b"<script",         # HTML/JS
        b"<?php",           # PHP
    ]
    for sig in DANGEROUS_SIGS:
        if file_bytes[:len(sig)].lower() == sig.lower():
            return False
    return True


def _uploads_dir() -> str:
    import os
    here = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(here, "..", "static", "uploads")


def _ext_ok(filename: str) -> bool:
    if "." not in filename:
        return False
    return filename.rsplit(".", 1)[1].lower() in _ALLOWED_EXTENSIONS


@sample_bp.post("/<string:sample_id>/attachments")
@login_required
@require_role("researcher", "technician", "admin")
def upload_attachment(sample_id: str):
    """POST multipart/form-data with field 'file'. Saves to disk, records in DB."""
    import os, uuid
    from werkzeug.utils import secure_filename
    from database.db import db_session
    from database.models import AttachmentModel, SampleModel

    if "file" not in request.files:
        return jsonify({"error": "No file uploaded (multipart field 'file')"}), 400
    file = request.files["file"]
    if not file.filename:
        return jsonify({"error": "No file selected"}), 400
    if not _ext_ok(file.filename):
        return jsonify({"error": f"Extension not allowed. Accepted: {sorted(_ALLOWED_EXTENSIONS)}"}), 400
    ext = file.filename.rsplit(".", 1)[1].lower()

    # Read file content for MIME validation
    file_bytes = file.read(512)
    file.seek(0)  # Reset stream so we can save the full file later

    if not _check_mime(file_bytes, ext):
        return jsonify({"error": "File content does not match its extension. Upload rejected."}), 400

    # Confirm sample exists
    with db_session() as s:
        if not s.query(SampleModel).filter_by(sample_id=sample_id).first():
            return jsonify({"error": "Sample not found"}), 404

    safe_name = secure_filename(file.filename) or "upload"
    stored_name = f"{uuid.uuid4().hex}_{safe_name}"
    sample_dir = os.path.abspath(os.path.join(_uploads_dir(), sample_id))
    os.makedirs(sample_dir, exist_ok=True)
    disk_path = os.path.join(sample_dir, stored_name)
    file.save(disk_path)
    file_size = os.path.getsize(disk_path)

    with db_session() as s:
        orm = AttachmentModel(
            sample_id=sample_id,
            filename=stored_name,
            original_name=safe_name,
            file_size=file_size,
            mime_type=(file.mimetype or None),
            uploaded_by=g.current_user_id,
        )
        s.add(orm)
        s.flush()
        attachment_id = orm.attachment_id

    log_activity(g.current_user_id, session.get("username", "?"),
                 "upload_attachment", f"{sample_id}: {safe_name}",
                 ip=request.remote_addr)

    return jsonify({
        "attachment_id": attachment_id,
        "original_name": safe_name,
        "file_size": file_size,
    }), 201


@sample_bp.get("/<string:sample_id>/attachments")
@login_required
def list_attachments(sample_id: str):
    from database.db import db_session
    from database.models import AttachmentModel
    with db_session() as s:
        rows = (s.query(AttachmentModel)
                 .filter_by(sample_id=sample_id)
                 .order_by(AttachmentModel.uploaded_at.desc())
                 .all())
        out = []
        for r in rows:
            out.append({
                "attachment_id": r.attachment_id,
                "original_name": r.original_name,
                "file_size":     r.file_size,
                "mime_type":     r.mime_type,
                "uploaded_by_username": _get_username(r.uploaded_by),
                "uploaded_at":   r.uploaded_at.isoformat() if r.uploaded_at else None,
            })
    return jsonify({"attachments": out}), 200


@sample_bp.get("/<string:sample_id>/attachments/<int:attachment_id>")
@login_required
def download_attachment(sample_id: str, attachment_id: int):
    import os
    from flask import send_file
    from database.db import db_session
    from database.models import AttachmentModel
    with db_session() as s:
        r = s.query(AttachmentModel).filter_by(
            attachment_id=attachment_id, sample_id=sample_id).first()
        if not r:
            return jsonify({"error": "Attachment not found"}), 404
        disk_path = os.path.abspath(os.path.join(_uploads_dir(), sample_id, r.filename))
        original = r.original_name
        mime = r.mime_type
    if not os.path.exists(disk_path):
        return jsonify({"error": "File missing on disk"}), 404
    return send_file(disk_path, mimetype=mime or "application/octet-stream",
                     as_attachment=True, download_name=original)


@sample_bp.delete("/<string:sample_id>/attachments/<int:attachment_id>")
@login_required
@require_role("researcher", "technician", "admin")
def delete_attachment(sample_id: str, attachment_id: int):
    import os
    from database.db import db_session
    from database.models import AttachmentModel
    with db_session() as s:
        r = s.query(AttachmentModel).filter_by(
            attachment_id=attachment_id, sample_id=sample_id).first()
        if not r:
            return jsonify({"error": "Attachment not found"}), 404
        disk_path = os.path.abspath(os.path.join(_uploads_dir(), sample_id, r.filename))
        original = r.original_name
        s.delete(r)
    try:
        if os.path.exists(disk_path):
            os.remove(disk_path)
    except OSError:
        pass

    log_activity(g.current_user_id, session.get("username", "?"),
                 "delete_attachment", f"{sample_id}: {original}",
                 ip=request.remote_addr)

    return jsonify({"message": "Attachment deleted"}), 200
