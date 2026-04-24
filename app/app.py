"""
app/app.py — Flask Application Factory
"""

from flask import Flask, jsonify, render_template
from .routes.auth_routes    import auth_bp
from .routes.sample_routes  import sample_bp
from .routes.user_routes    import user_bp
from .routes.project_routes import project_bp


def create_app(config: dict | None = None) -> Flask:
    app = Flask(__name__)

    app.config.update(
        SECRET_KEY="labtrack-dev-secret-change-in-production",
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        DATABASE_URI="sqlite:///labtrack.db",
        MAX_CONTENT_LENGTH=5 * 1024 * 1024,
    )

    if config:
        app.config.update(config)

    # ── Initialise DB and seed default users ──────────────────────────────
    if not config or not config.get("TESTING"):
        from database.db import init_db, migrate_db, seed_default_users, seed_demo_samples
        init_db()
        migrate_db()
        seed_default_users()
        seed_demo_samples()

    # ── Register Blueprints ───────────────────────────────────────────────
    app.register_blueprint(auth_bp,    url_prefix="/api/auth")
    app.register_blueprint(sample_bp,  url_prefix="/api/samples")
    app.register_blueprint(user_bp,    url_prefix="/api/users")
    app.register_blueprint(project_bp, url_prefix="/api/projects")

    # ── Serve the HTML frontend ───────────────────────────────────────────
    @app.route("/")
    def index():
        resp = app.make_response(render_template("index.html"))
        # Single-file template inlined with JS — force browsers to re-fetch on
        # every reload so a stale cached copy never shadows new frontend code.
        resp.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        resp.headers["Pragma"] = "no-cache"
        resp.headers["Expires"] = "0"
        return resp


    @app.route("/view/<sample_id>")
    def sample_view(sample_id):
        """Public live sample view linked from QR codes on printed labels."""
        from flask import request
        from repositories.sample_repository import SampleRepository
        from repositories.user_repository import UserRepository
        from datetime import date as date_type
        repo = SampleRepository()
        sample = repo.get_by_id(sample_id)
        if sample is None:
            return f"""<!DOCTYPE html><html><head><meta charset="UTF-8">
            <meta name="viewport" content="width=device-width,initial-scale=1">
            <title>Not found</title>
            <style>body{{font-family:Arial,sans-serif;display:flex;align-items:center;
            justify-content:center;min-height:100vh;margin:0;background:#F0F2F5}}
            .box{{background:#fff;padding:32px;border-radius:8px;text-align:center}}</style>
            </head><body><div class="box"><p style="font-size:48px">?</p>
            <h2 style="color:#1F3864">Sample not found</h2>
            <p style="color:#888">{sample_id}</p></div></body></html>""", 404

        user_repo = UserRepository()
        creator = user_repo.get_by_id(sample.get_created_by_id())
        creator_name = creator.get_username() if creator else str(sample.get_created_by_id())

        expiry_html = ""
        if sample.get_expiry_date():
            days = (sample.get_expiry_date() - date_type.today()).days
            if days < 0:
                expiry_html = f'<span style="background:#F8D7DA;color:#842029;padding:3px 10px;border-radius:12px;font-size:13px;font-weight:bold">Expired {abs(days)}d ago</span>'
            elif days <= 30:
                expiry_html = f'<span style="background:#FFF3CD;color:#856404;padding:3px 10px;border-radius:12px;font-size:13px;font-weight:bold">Expires in {days}d ({sample.get_expiry_date()})</span>'
            else:
                expiry_html = f'<span style="background:#D1E7DD;color:#0F5132;padding:3px 10px;border-radius:12px;font-size:13px">{sample.get_expiry_date()}</span>'

        status_colors = {"Collected":"#1D9E75","Processing":"#BA7517","Stored":"#2E75B6","Consumed":"#666","Discarded":"#842029"}
        status_color = status_colors.get(sample.get_status().value, "#333")

        parts = []
        for getter in ["get_location_building","get_location_room","get_location_equipment","get_location_position"]:
            if hasattr(sample, getter):
                v = getattr(sample, getter)()
                if v: parts.append(v)
        location_display = " > ".join(parts) or sample.get_storage_location() or "Not set"

        audit_rows = ""
        for entry in reversed(sample.get_audit_log()[-5:]):
            changer = user_repo.get_by_id(entry.get_changed_by_id())
            changer_name = changer.get_username() if changer else str(entry.get_changed_by_id())
            c = status_colors.get(entry.get_new_status().value, "#333")
            audit_rows += f"<tr><td>{str(entry.get_timestamp())[:16]}</td><td>{entry.get_old_status().value}</td><td style='color:{c};font-weight:bold'>{entry.get_new_status().value}</td><td>{changer_name}</td></tr>"

        qty_str = ""
        if sample.get_quantity() is not None:
            qty_str = f"{sample.get_quantity()} {sample.get_quantity_unit() or ''}".strip()

        rows = [
            ("Type", sample.get_sample_type()),
            ("Organism", sample.get_source_organism()),
            ("Collected", sample.get_collection_date().strftime("%Y-%m-%d")),
            ("Location", location_display),
        ]
        if qty_str:       rows.append(("Quantity", qty_str))
        if expiry_html:   rows.append(("Expiry", expiry_html))
        if sample.get_notes(): rows.append(("Notes", sample.get_notes()))
        rows.append(("Registered by", creator_name))

        rows_html = "".join(
            f'<div class="row"><span class="lbl">{k}</span><span class="val">{v}</span></div>'
            for k, v in rows
        )

        audit_section = ""
        if audit_rows:
            audit_section = f"""<div class="card">
  <div class="card-title">Recent status changes</div>
  <table><thead><tr><th>When</th><th>From</th><th>To</th><th>By</th></tr></thead>
  <tbody>{audit_rows}</tbody></table></div>"""

        return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="refresh" content="60">
<title>{sample.get_sample_id()} - LabTrack</title>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:Arial,sans-serif;background:#F0F2F5;color:#333;padding:16px;max-width:480px;margin:0 auto}}
.header{{background:#1F3864;color:#fff;padding:14px 16px;border-radius:8px;margin-bottom:12px;display:flex;align-items:center;justify-content:space-between}}
.header h1{{font-size:16px;font-weight:bold;font-family:monospace}}
.header .sub{{font-size:11px;color:#B0C4DE;margin-top:2px}}
.card{{background:#fff;border-radius:8px;border:1px solid #DDD;padding:16px;margin-bottom:12px}}
.card-title{{font-size:11px;font-weight:bold;color:#1F3864;margin-bottom:10px;text-transform:uppercase;letter-spacing:.5px}}
.row{{display:flex;padding:6px 0;border-bottom:1px solid #F5F5F5;font-size:14px}}
.row:last-child{{border-bottom:none}}
.lbl{{color:#888;width:100px;flex-shrink:0;font-size:13px}}
.val{{flex:1;font-weight:500}}
.badge{{display:inline-block;padding:5px 14px;border-radius:14px;font-size:14px;font-weight:bold;color:#fff;background:{status_color}}}
table{{width:100%;border-collapse:collapse;font-size:12px}}
th{{background:#F8F8F8;text-align:left;padding:6px 8px;color:#666;border-bottom:1px solid #EEE}}
td{{padding:6px 8px;border-bottom:1px solid #F5F5F5}}
.footer{{text-align:center;font-size:11px;color:#BBB;margin-top:12px;line-height:1.8}}
</style>
</head>
<body>
<div class="header">
  <div>
    <div class="sub">LabTrack - scanned label</div>
    <h1>{sample.get_sample_id()}</h1>
  </div>
  <span class="badge">{sample.get_status().value}</span>
</div>
<div class="card">
  <div class="card-title">Sample information</div>
  {rows_html}
</div>
{audit_section}
<div class="footer">
  Live data - auto-refreshes every 60s<br>
  Last updated: {str(sample.get_updated_at())[:16]} UTC<br>
  {request.host}
</div>
</body>
</html>"""


    # ── Error handlers ────────────────────────────────────────────────────
    @app.errorhandler(400)
    def bad_request(e):
        return jsonify({"error": "Bad request", "detail": str(e)}), 400

    @app.errorhandler(401)
    def unauthorised(e):
        return jsonify({"error": "Authentication required"}), 401

    @app.errorhandler(403)
    def forbidden(e):
        return jsonify({"error": "Insufficient permissions"}), 403

    @app.errorhandler(404)
    def not_found(e):
        return jsonify({"error": "Resource not found"}), 404

    @app.errorhandler(500)
    def internal_error(e):
        return jsonify({"error": "Internal server error"}), 500

    return app
