"""
tests/test_routes.py
=====================
STAGE 10: Integration tests for all Flask API endpoints.

Tests exercise the full HTTP stack — request parsing, authentication
enforcement, permission checks, business logic delegation, and JSON
response structure — using the Flask test client with an in-memory
SQLite database.

Coverage targets:
  - Every endpoint in auth_routes, sample_routes, user_routes
  - Every HTTP method per endpoint (GET, POST, PUT, DELETE)
  - Authentication enforcement (401 for unauthenticated requests)
  - Role enforcement (403 for insufficient permission)
  - Input validation (400 for missing/invalid fields)
  - Happy-path responses (correct status code + JSON structure)
"""

import io
import pytest
from tests.conftest import VALID_SAMPLE_PAYLOAD, VALID_CSV, INVALID_CSV_MISSING_COL


# ══════════════════════════════════════════════════════════════════════════════
# AUTH ROUTES  /api/auth/
# ══════════════════════════════════════════════════════════════════════════════

class TestAuthRoutes:

    # ── POST /api/auth/login ──────────────────────────────────────────────

    def test_login_missing_username_returns_400(self, client):
        resp = client.post("/api/auth/login", json={"password": "secret"})
        assert resp.status_code == 400
        assert "username" in resp.get_json()["error"].lower() \
            or resp.get_json().get("error") is not None

    def test_login_missing_password_returns_400(self, client):
        resp = client.post("/api/auth/login", json={"username": "alice"})
        assert resp.status_code == 400

    def test_login_empty_body_returns_400(self, client):
        resp = client.post("/api/auth/login", json={})
        assert resp.status_code == 400

    def test_login_success_returns_200_with_user_data(self, client):
        resp = client.post("/api/auth/login",
                           json={"username": "alice", "password": "anypass"})
        # Stage 6 routes use a stub that accepts any credentials.
        # Stage 7 will replace the stub with bcrypt verification.
        assert resp.status_code == 200
        data = resp.get_json()
        assert "user_id" in data
        assert "username" in data
        assert "role" in data

    def test_login_sets_session(self, client):
        client.post("/api/auth/login",
                    json={"username": "alice", "password": "pass"})
        # After login, /api/auth/me should succeed
        resp = client.get("/api/auth/me")
        assert resp.status_code == 200

    # ── POST /api/auth/logout ─────────────────────────────────────────────

    def test_logout_unauthenticated_returns_401(self, client):
        resp = client.post("/api/auth/logout")
        assert resp.status_code == 401

    def test_logout_authenticated_returns_200(self, researcher_client):
        resp = researcher_client.post("/api/auth/logout")
        assert resp.status_code == 200

    def test_logout_clears_session(self, researcher_client):
        researcher_client.post("/api/auth/logout")
        resp = researcher_client.get("/api/auth/me")
        assert resp.status_code == 401

    # ── GET /api/auth/me ──────────────────────────────────────────────────

    def test_me_unauthenticated_returns_401(self, client):
        resp = client.get("/api/auth/me")
        assert resp.status_code == 401

    def test_me_authenticated_returns_profile(self, researcher_client):
        resp = researcher_client.get("/api/auth/me")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["username"] == "alice"
        assert data["role"] == "researcher"


# ══════════════════════════════════════════════════════════════════════════════
# SAMPLE ROUTES  /api/samples/
# ══════════════════════════════════════════════════════════════════════════════

class TestSampleRoutes:

    # ── GET /api/samples/ ─────────────────────────────────────────────────

    def test_list_unauthenticated_returns_401(self, client):
        resp = client.get("/api/samples/")
        assert resp.status_code == 401

    def test_list_authenticated_returns_200(self, researcher_client):
        resp = researcher_client.get("/api/samples/")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "samples" in data
        assert "total" in data
        assert "page" in data

    def test_list_viewer_can_access(self, viewer_client):
        resp = viewer_client.get("/api/samples/")
        assert resp.status_code == 200

    def test_list_filters_accepted(self, researcher_client):
        resp = researcher_client.get(
            "/api/samples/?type=blood&status=Collected&page=1&per_page=10"
        )
        assert resp.status_code == 200

    # ── POST /api/samples/ ────────────────────────────────────────────────

    def test_register_unauthenticated_returns_401(self, client):
        resp = client.post("/api/samples/", json=VALID_SAMPLE_PAYLOAD)
        assert resp.status_code == 401

    def test_register_researcher_can_register(self, researcher_client):
        resp = researcher_client.post("/api/samples/", json=VALID_SAMPLE_PAYLOAD)
        assert resp.status_code == 201

    def test_register_admin_can_register(self, admin_client):
        resp = admin_client.post("/api/samples/", json=VALID_SAMPLE_PAYLOAD)
        assert resp.status_code == 201

    def test_register_viewer_returns_403(self, viewer_client):
        resp = viewer_client.post("/api/samples/", json=VALID_SAMPLE_PAYLOAD)
        assert resp.status_code == 403

    def test_register_technician_returns_403(self, technician_client):
        resp = technician_client.post("/api/samples/", json=VALID_SAMPLE_PAYLOAD)
        assert resp.status_code == 403

    def test_register_missing_sample_type_returns_400(self, researcher_client):
        payload = {k: v for k, v in VALID_SAMPLE_PAYLOAD.items()
                   if k != "sample_type"}
        resp = researcher_client.post("/api/samples/", json=payload)
        assert resp.status_code == 400
        assert resp.get_json().get("field") == "sample_type"

    def test_register_invalid_date_returns_400(self, researcher_client):
        payload = {**VALID_SAMPLE_PAYLOAD, "collection_date": "01/04/2025"}
        resp = researcher_client.post("/api/samples/", json=payload)
        assert resp.status_code == 400
        assert resp.get_json().get("field") == "collection_date"

    def test_register_missing_location_returns_400(self, researcher_client):
        payload = {k: v for k, v in VALID_SAMPLE_PAYLOAD.items()
                   if k != "storage_location"}
        resp = researcher_client.post("/api/samples/", json=payload)
        assert resp.status_code == 400

    # ── GET /api/samples/<id> ─────────────────────────────────────────────

    def test_get_sample_unauthenticated_returns_401(self, client):
        resp = client.get("/api/samples/LT-2025-0001")
        assert resp.status_code == 401

    def test_get_sample_not_found_returns_404(self, researcher_client):
        resp = researcher_client.get("/api/samples/LT-9999-9999")
        assert resp.status_code == 404

    # ── PUT /api/samples/<id>/status ─────────────────────────────────────

    def test_update_status_unauthenticated_returns_401(self, client):
        resp = client.put("/api/samples/LT-2025-0001/status",
                          json={"status": "Processing"})
        assert resp.status_code == 401

    def test_update_status_missing_body_returns_400(self, researcher_client):
        resp = researcher_client.put("/api/samples/LT-2025-0001/status", json={})
        assert resp.status_code == 400

    def test_update_status_viewer_returns_403(self, viewer_client):
        resp = viewer_client.put("/api/samples/LT-2025-0001/status",
                                 json={"status": "Processing"})
        assert resp.status_code == 403

    # ── POST /api/samples/import ──────────────────────────────────────────

    def test_import_unauthenticated_returns_401(self, client):
        data = {"file": (io.BytesIO(VALID_CSV.encode()), "samples.csv")}
        resp = client.post("/api/samples/import",
                           data=data, content_type="multipart/form-data")
        assert resp.status_code == 401

    def test_import_viewer_returns_403(self, viewer_client):
        data = {"file": (io.BytesIO(VALID_CSV.encode()), "samples.csv")}
        resp = viewer_client.post("/api/samples/import",
                                  data=data, content_type="multipart/form-data")
        assert resp.status_code == 403

    def test_import_no_file_returns_400(self, researcher_client):
        resp = researcher_client.post("/api/samples/import",
                                      data={}, content_type="multipart/form-data")
        assert resp.status_code == 400

    def test_import_valid_csv_returns_200(self, researcher_client):
        data = {"file": (io.BytesIO(VALID_CSV.encode()), "samples.csv")}
        resp = researcher_client.post("/api/samples/import",
                                      data=data, content_type="multipart/form-data")
        assert resp.status_code == 200
        result = resp.get_json()
        assert "imported" in result
        assert "errors" in result

    # ── GET /api/samples/export ───────────────────────────────────────────

    def test_export_unauthenticated_returns_401(self, client):
        resp = client.get("/api/samples/export")
        assert resp.status_code == 401

    def test_export_authenticated_returns_csv(self, researcher_client):
        resp = researcher_client.get("/api/samples/export")
        assert resp.status_code == 200
        assert "text/csv" in resp.content_type


# ══════════════════════════════════════════════════════════════════════════════
# USER ROUTES  /api/users/
# ══════════════════════════════════════════════════════════════════════════════

class TestUserRoutes:

    # ── GET /api/users/ ───────────────────────────────────────────────────

    def test_list_users_unauthenticated_returns_401(self, client):
        resp = client.get("/api/users/")
        assert resp.status_code == 401

    def test_list_users_researcher_returns_403(self, researcher_client):
        resp = researcher_client.get("/api/users/")
        assert resp.status_code == 403

    def test_list_users_admin_returns_200(self, admin_client):
        resp = admin_client.get("/api/users/")
        assert resp.status_code == 200
        assert "users" in resp.get_json()

    # ── POST /api/users/ ──────────────────────────────────────────────────

    def test_create_user_non_admin_returns_403(self, researcher_client):
        resp = researcher_client.post("/api/users/", json={
            "username": "new", "email": "new@lab.ch",
            "password": "password123", "role": "viewer"
        })
        assert resp.status_code == 403

    def test_create_user_missing_role_returns_400(self, admin_client):
        resp = admin_client.post("/api/users/", json={
            "username": "new", "email": "new@lab.ch", "password": "password123"
        })
        assert resp.status_code == 400

    def test_create_user_short_password_returns_400(self, admin_client):
        resp = admin_client.post("/api/users/", json={
            "username": "new", "email": "new@lab.ch",
            "password": "short", "role": "viewer"
        })
        assert resp.status_code == 400

    def test_create_user_admin_succeeds(self, admin_client):
        resp = admin_client.post("/api/users/", json={
            "username": "newuser", "email": "new@lab.ch",
            "password": "password123", "role": "researcher"
        })
        assert resp.status_code == 201

    # ── PUT /api/users/<id> ───────────────────────────────────────────────

    def test_update_user_non_admin_returns_403(self, researcher_client):
        resp = researcher_client.put("/api/users/1", json={"role": "admin"})
        assert resp.status_code == 403

    def test_update_user_no_fields_returns_400(self, admin_client):
        resp = admin_client.put("/api/users/1", json={})
        assert resp.status_code == 400

    # ── DELETE /api/users/<id> ────────────────────────────────────────────

    def test_deactivate_user_non_admin_returns_403(self, researcher_client):
        resp = researcher_client.delete("/api/users/5")
        assert resp.status_code == 403

    def test_deactivate_user_admin_returns_200(self, admin_client):
        resp = admin_client.delete("/api/users/5")
        assert resp.status_code == 200
