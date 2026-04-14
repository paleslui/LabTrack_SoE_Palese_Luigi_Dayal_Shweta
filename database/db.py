"""
database/db.py
===============
Database engine setup and session management.

STAGE 7: wires the Singleton repositories (Stage 5) to the real
SQLAlchemy session, replacing the in-memory dictionaries used in Stages 3–6.

Usage
-----
    from database.db import init_db, get_session
    init_db()                       # call once at app startup
    session = get_session()         # use inside a request context
    session.add(model_instance)
    session.commit()
    session.close()

Or use the context-manager form:
    with db_session() as session:
        session.add(model_instance)
        # session.commit() called automatically on clean exit
"""

from contextlib import contextmanager
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, Session
from database.models import Base

# ---------------------------------------------------------------------------
# Engine configuration
# ---------------------------------------------------------------------------

DATABASE_URI = "sqlite:///labtrack.db"

engine = create_engine(
    DATABASE_URI,
    echo=False,            # set to True to log all SQL to stdout for debugging
    connect_args={
        "check_same_thread": False,  # required for SQLite in multi-threaded Flask
    },
)

# Enable SQLite foreign-key enforcement (disabled by default in SQLite)
@event.listens_for(engine, "connect")
def _set_sqlite_pragma(dbapi_conn, connection_record):
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA foreign_keys = ON")
    cursor.close()

# ---------------------------------------------------------------------------
# Session factory
# ---------------------------------------------------------------------------

SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,   # we manage transactions explicitly
    autoflush=False,    # flush only when we call session.commit() or explicitly
)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def init_db() -> None:
    """
    Create all tables defined in database/models.py if they do not exist.

    Call once at application startup (in app.py create_app()).
    Safe to call multiple times — SQLAlchemy uses CREATE TABLE IF NOT EXISTS.
    """
    Base.metadata.create_all(bind=engine)


def get_session() -> Session:
    """
    Return a new SQLAlchemy session.

    The caller is responsible for calling session.commit() and session.close().
    Prefer the context-manager form (db_session) for automatic cleanup.
    """
    return SessionLocal()


@contextmanager
def db_session():
    """
    Context manager that provides a session with automatic commit/rollback.

    Usage:
        with db_session() as session:
            session.add(some_model)
        # session is committed and closed on exit

    On exception: rolls back and re-raises.
    """
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


# ---------------------------------------------------------------------------
# Convenience query helpers
# ---------------------------------------------------------------------------

def get_user_by_username(session: Session, username: str):
    """Return the UserModel with the given username, or None."""
    from database.models import UserModel
    return session.query(UserModel).filter_by(username=username).first()


def get_sample_by_id(session: Session, sample_id: str):
    """Return the SampleModel with the given ID, or None."""
    from database.models import SampleModel
    return session.query(SampleModel).filter_by(sample_id=sample_id).first()


def get_audit_log(session: Session, sample_id: str):
    """Return all AuditEntryModel rows for the given sample, oldest first."""
    from database.models import AuditEntryModel
    return (session.query(AuditEntryModel)
            .filter_by(sample_id=sample_id)
            .order_by(AuditEntryModel.timestamp)
            .all())
