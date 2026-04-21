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
        demos = [
            ('blood',   'Homo sapiens',    date(2025, 1, 10), 'Freezer-A1', 'Stored',     'Morning venipuncture'),
            ('DNA',     'Mus musculus',    date(2025, 2, 3),  'Fridge-B2',  'Processing', 'Extracted from tail biopsy'),
            ('tissue',  'Homo sapiens',    date(2025, 3, 15), 'Shelf-C3',   'Collected',  'Post-op biopsy sample'),
            ('plasma',  'Rattus norveg.',  date(2025, 3, 22), 'Freezer-A3', 'Stored',     ''),
            ('RNA',     'Homo sapiens',    date(2025, 4, 1),  'Fridge-C2',  'Processing', 'Batch 3 — RIN > 8'),
            ('serum',   'Mus musculus',    date(2025, 4, 5),  'Freezer-A2', 'Collected',  ''),
        ]
        for i, (stype, org, col_date, loc, status, notes) in enumerate(demos, start=1):
            year = col_date.year
            session.add(SampleModel(
                sample_id=f'LT-{year}-{i:04d}',
                sample_type=stype,
                source_organism=org,
                collection_date=col_date,
                storage_location=loc,
                status=status,
                notes=notes,
                created_by=uid,
            ))
        print('✓ Demo samples seeded (6 samples)')
