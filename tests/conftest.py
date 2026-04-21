"""
tests/conftest.py — Shared pytest fixtures
"""
import os
import pytest

# Point ALL db operations at an in-memory SQLite before any imports
os.environ["DATABASE_URI"] = "sqlite:///:memory:"


@pytest.fixture(scope="session")
def app():
    from database.db import configure_db, init_db
    configure_db("sqlite:///:memory:")
    init_db()
    from app.app import create_app
    flask_app = create_app({"TESTING": True, "SECRET_KEY": "test-key"})
    yield flask_app


@pytest.fixture(autouse=True)
def reset_db(app):
    """
    Before every test: drop all tables, recreate them, seed the 4 test users.
    This gives every test a clean, predictable state.
    The seeded users match the session IDs injected by the role fixtures below.
    """
    import bcrypt
    from database.db import engine, db_session
    from database.models import Base, UserModel

    with app.app_context():
        Base.metadata.drop_all(bind=engine)
        Base.metadata.create_all(bind=engine)

        pw = bcrypt.hashpw(b"testpass", bcrypt.gensalt()).decode()
        with db_session() as session:
            for uid, uname, role in [
                (1, "alice", "researcher"),
                (2, "bob",   "technician"),
                (3, "carol", "admin"),
                (4, "dave",  "viewer"),
            ]:
                session.add(UserModel(
                    user_id=uid,
                    username=uname,
                    email=f"{uname}@lab.ch",
                    password_hash=pw,
                    role=role,
                    is_active=True,
                ))
    yield


# ── HTTP client fixtures ──────────────────────────────────────────────────────

@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def researcher_client(app):
    c = app.test_client()
    with c.session_transaction() as sess:
        sess["user_id"] = 1; sess["user_role"] = "researcher"; sess["username"] = "alice"
    return c


@pytest.fixture
def technician_client(app):
    c = app.test_client()
    with c.session_transaction() as sess:
        sess["user_id"] = 2; sess["user_role"] = "technician"; sess["username"] = "bob"
    return c


@pytest.fixture
def admin_client(app):
    c = app.test_client()
    with c.session_transaction() as sess:
        sess["user_id"] = 3; sess["user_role"] = "admin"; sess["username"] = "carol"
    return c


@pytest.fixture
def viewer_client(app):
    c = app.test_client()
    with c.session_transaction() as sess:
        sess["user_id"] = 4; sess["user_role"] = "viewer"; sess["username"] = "dave"
    return c


# ── Reusable test data ────────────────────────────────────────────────────────

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

INVALID_CSV_MISSING_COL = "sample_type,collection_date\nblood,2025-03-01\n"
