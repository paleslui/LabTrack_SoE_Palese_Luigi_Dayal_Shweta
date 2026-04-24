"""
database/db.py — Engine, session factory, init_db(), seed_default_users().
"""

import os
from contextlib import contextmanager
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, Session
from database.models import Base

DATABASE_URI = os.environ.get("DATABASE_URI", "sqlite:///labtrack.db")

engine = create_engine(DATABASE_URI, echo=False, connect_args={"check_same_thread": False})

@event.listens_for(engine, "connect")
def _set_sqlite_pragma(dbapi_conn, connection_record):
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA foreign_keys = ON")
    cursor.close()

SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


def configure_db(uri: str) -> None:
    """Reconfigure the engine — used by tests to point at sqlite:///:memory:"""
    global engine, SessionLocal
    engine = create_engine(uri, echo=False, connect_args={"check_same_thread": False})
    SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


def init_db() -> None:
    Base.metadata.create_all(bind=engine)
    # Ensure uploads directory for file attachments exists
    uploads_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                               "app", "static", "uploads")
    os.makedirs(uploads_dir, exist_ok=True)


def migrate_db() -> None:
    """
    Add new columns to existing SQLite DB without data loss.
    Safe to call on every startup — skips columns that already exist.
    """
    from sqlalchemy import text, inspect
    with engine.connect() as conn:
        inspector = inspect(engine)
        existing = [c['name'] for c in inspector.get_columns('samples')]
        migrations = [
            ("expiry_date",         "DATE"),
            ("quantity",            "FLOAT"),
            ("quantity_unit",       "VARCHAR(20)"),
            ("location_building",   "VARCHAR(100)"),
            ("location_room",       "VARCHAR(100)"),
            ("location_equipment",  "VARCHAR(100)"),
            ("location_position",   "VARCHAR(50)"),
            ("parent_sample_id",    "VARCHAR(20)"),
            ("project_id",          "INTEGER"),
            ("reserved_by",         "INTEGER"),
            ("reserved_until",      "DATETIME"),
            ("reservation_note",    "VARCHAR(200)"),
        ]
        for col, col_type in migrations:
            if col not in existing:
                conn.execute(text(f"ALTER TABLE samples ADD COLUMN {col} {col_type}"))
                print(f"✓ Migrated: added samples.{col}")
        conn.commit()


def get_session() -> Session:
    return SessionLocal()


@contextmanager
def db_session():
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def log_activity(user_id, username: str, action: str, detail: str = "", ip: str = "") -> None:
    """Record a user action in the activity log. Never raises — logging must not break requests."""
    try:
        from database.models import ActivityLogModel
        with db_session() as session:
            session.add(ActivityLogModel(
                user_id=user_id if isinstance(user_id, int) else None,
                username=str(username) if username else None,
                action=action,
                detail=detail or None,
                ip_address=ip or None,
            ))
    except Exception:
        pass


def seed_default_users() -> None:
    """Create the four default demo users if the users table is empty."""
    import bcrypt
    from database.models import UserModel
    with db_session() as session:
        if session.query(UserModel).count() > 0:
            return
        defaults = [
            ("alice", "alice@lab.ch",  "alice123",  "researcher"),
            ("bob",   "bob@lab.ch",    "bob123",    "technician"),
            ("carol", "carol@lab.ch",  "carol123",  "admin"),
            ("dave",  "dave@lab.ch",   "dave123",   "viewer"),
        ]
        for username, email, password, role in defaults:
            pw_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
            session.add(UserModel(username=username, email=email,
                                  password_hash=pw_hash, role=role, is_active=True))
        print("✓ Default users seeded: alice / bob / carol / dave")


def seed_demo_samples() -> None:
    """Insert a handful of realistic samples if the samples table is empty."""
    from database.models import SampleModel, UserModel
    from datetime import date
    with db_session() as session:
        if session.query(SampleModel).count() > 0:
            return
        # Get alice's user_id (researcher who registers the samples)
        alice = session.query(UserModel).filter_by(username='alice').first()
        if not alice:
            return
        uid = alice.user_id
        # (type, organism, collect_date, location, status, notes, expiry_date, qty, unit)
        demos = [
            ('blood',   'Homo sapiens',   date(2025, 1, 10), 'Freezer-A1', 'Stored',     'Morning venipuncture',      date(2025, 7, 10),  5.0,  'ml'),
            ('DNA',     'Mus musculus',   date(2025, 2, 3),  'Fridge-B2',  'Processing', 'Extracted from tail biopsy', date(2026, 2, 3),   12.5, 'ug'),
            ('tissue',  'Homo sapiens',   date(2025, 3, 15), 'Shelf-C3',   'Collected',  'Post-op biopsy sample',     date(2025, 9, 15),  2.0,  'mg'),
            ('plasma',  'Rattus norveg.', date(2025, 3, 22), 'Freezer-A3', 'Stored',     '',                           date(2026, 3, 22),  8.0,  'ml'),
            ('RNA',     'Homo sapiens',   date(2025, 4, 1),  'Fridge-C2',  'Processing', 'Batch 3 — RIN > 8',         date(2025, 10, 1),  3.5,  'ug'),
            ('serum',   'Mus musculus',   date(2025, 4, 5),  'Freezer-A2', 'Collected',  '',                           date(2026, 4, 5),   6.0,  'ml'),
        ]
        for i, (stype, org, col_date, loc, status, notes, exp_date, qty, unit) in enumerate(demos, start=1):
            year = col_date.year
            session.add(SampleModel(
                sample_id=f'LT-{year}-{i:04d}',
                sample_type=stype,
                source_organism=org,
                collection_date=col_date,
                storage_location=loc,
                status=status,
                notes=notes,
                expiry_date=exp_date,
                quantity=qty,
                quantity_unit=unit,
                created_by=uid,
            ))
        print('✓ Demo samples seeded (6 samples)')
