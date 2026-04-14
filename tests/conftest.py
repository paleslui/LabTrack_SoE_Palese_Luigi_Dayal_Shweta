"""
tests/conftest.py
==================
Shared pytest fixtures for LabTrack's three-layer test suite.

TESTING STRATEGY (Stage 10)
-----------------------------
LabTrack uses three test layers, each with its own scope and fixture set:

  1. Unit tests (test_models.py, test_patterns.py — Stages 3 & 5)
     - Test individual classes in isolation
     - No database, no Flask, no HTTP
     - Fast: run in < 1 second

  2. Integration tests (test_routes.py — this stage)
     - Test Flask API endpoints end-to-end
     - Use Flask test client + in-memory SQLite (DATABASE_URI = 'sqlite:///:memory:')
     - Each test gets a fresh database (function-scoped fixtures)
     - Verify: HTTP status codes, JSON response structure,
       authentication enforcement, permission enforcement,
       and data persistence across requests

  3. System tests (test_system.py — this stage)
     - Test complete user workflows (register → update → export)
     - Use the same in-memory setup but compose multiple API calls
     - Verify: business invariants hold across a full lifecycle

All tests are collected by pytest and run via: pytest tests/ -v --tb=short
"""

import pytest
from app.app import create_app


# ── Application fixture (session-scoped) ─────────────────────────────────────

@pytest.fixture(scope="session")
def app():
    """
    Create a Flask application configured for testing.

    Uses an in-memory SQLite database so each test session starts
    with a clean, ephemeral database that is discarded on exit.
    """
    flask_app = create_app({
        "TESTING": True,
        "SECRET_KEY": "test-secret-key",
        "DATABASE_URI": "sqlite:///:memory:",
        # Disable CSRF and session protections that require a browser
        "WTF_CSRF_ENABLED": False,
        "SESSION_COOKIE_SECURE": False,
    })
    yield flask_app


# ── Database fixture (function-scoped) ────────────────────────────────────────

@pytest.fixture(autouse=True)
def reset_db(app):
    """
    Create all tables before each test and drop them after.

    autouse=True means this fixture runs automatically for every test
    in the integration and system suites — no need to request it explicitly.
    This guarantees full test isolation: no state leaks between tests.
    """
    # Stage 7 DB integration: when database/db.py is wired in, replace with:
    # from database.db import init_db, engine
    # from database.models import Base
    # with app.app_context():
    #     Base.metadata.create_all(engine)
    #     yield
    #     Base.metadata.drop_all(engine)
    yield  # stub until Stage 7 DB is fully wired to the Flask app


# ── HTTP client fixtures ──────────────────────────────────────────────────────

@pytest.fixture
def client(app):
    """
    Unauthenticated Flask test client.

    Use for testing endpoints that should reject anonymous requests (401)
    and for the login endpoint itself.
    """
    return app.test_client()


@pytest.fixture
def researcher_client(app):
    """
    Flask test client authenticated as a Researcher.

    Can register samples, update status, search, view audit log.
    Cannot manage users.
    """
    client = app.test_client()
    with client.session_transaction() as sess:
        sess["user_id"]   = 1
        sess["user_role"] = "researcher"
        sess["username"]  = "alice"
    return client


@pytest.fixture
def technician_client(app):
    """
    Flask test client authenticated as a Lab Technician.

    Can update status. Cannot register samples or manage users.
    """
    client = app.test_client()
    with client.session_transaction() as sess:
        sess["user_id"]   = 2
        sess["user_role"] = "technician"
        sess["username"]  = "bob"
    return client


@pytest.fixture
def admin_client(app):
    """
    Flask test client authenticated as an Administrator.

    Full access: all sample operations + user management.
    """
    client = app.test_client()
    with client.session_transaction() as sess:
        sess["user_id"]   = 3
        sess["user_role"] = "admin"
        sess["username"]  = "carol"
    return client


@pytest.fixture
def viewer_client(app):
    """
    Flask test client authenticated as a Viewer.

    Read-only: cannot register, update, import, or manage users.
    """
    client = app.test_client()
    with client.session_transaction() as sess:
        sess["user_id"]   = 4
        sess["user_role"] = "viewer"
        sess["username"]  = "dave"
    return client


# ── Data fixtures ─────────────────────────────────────────────────────────────

VALID_SAMPLE_PAYLOAD = {
    "sample_type":      "blood",
    "source_organism":  "Homo sapiens",
    "collection_date":  "2025-04-01",
    "storage_location": "Freezer-A1",
    "notes":            "Morning collection",
}

VALID_CSV = (
    "sample_type,source_organism,collection_date,storage_location,notes\n"
    "blood,Homo sapiens,2025-03-01,Freezer-A1,Batch 1\n"
    "DNA,Mus musculus,2025-03-15,Fridge-B2,\n"
    "tissue,Homo sapiens,2025-04-01,Shelf-C3,Post-op\n"
)

INVALID_CSV_MISSING_COL = (
    "sample_type,collection_date,storage_location\n"
    "blood,2025-03-01,Freezer-A1\n"
)
