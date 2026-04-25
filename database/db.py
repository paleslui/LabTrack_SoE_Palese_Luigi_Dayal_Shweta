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

        # User table lockout columns
        user_cols = [c["name"] for c in inspector.get_columns("users")]
        for col, col_type in [("failed_login_attempts","INTEGER DEFAULT 0"),("locked_until","DATETIME")]:
            if col not in user_cols:
                conn.execute(text(f"ALTER TABLE users ADD COLUMN {col} {col_type}"))
                print(f"✓ Migrated: added users.{col}")

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


def send_email(app_config, to: str, subject: str, body: str) -> bool:
    """
    Send a plain-text email via SMTP.
    Only sends if MAIL_ENABLED is True in app config. Returns True on success.
    Errors are swallowed — failed email must never break the calling request/job.
    """
    if not app_config.get("MAIL_ENABLED"):
        return False
    if not to:
        return False
    import smtplib
    from email.mime.text import MIMEText
    try:
        msg = MIMEText(body, "plain")
        msg["Subject"] = subject
        msg["From"]    = app_config["MAIL_FROM"]
        msg["To"]      = to
        with smtplib.SMTP(app_config["MAIL_SERVER"], app_config["MAIL_PORT"]) as server:
            if app_config.get("MAIL_USE_TLS"):
                server.starttls()
            if app_config.get("MAIL_USERNAME"):
                server.login(app_config["MAIL_USERNAME"], app_config["MAIL_PASSWORD"])
            server.sendmail(app_config["MAIL_FROM"], [to], msg.as_string())
        return True
    except Exception as e:
        print(f"[LabTrack] Email error: {e}")
        return False


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


def seed_demo_projects() -> None:
    """Insert a few demo projects if the projects table is empty."""
    from database.models import ProjectModel, UserModel
    with db_session() as session:
        if session.query(ProjectModel).count() > 0:
            return
        carol = session.query(UserModel).filter_by(username='carol').first()
        alice = session.query(UserModel).filter_by(username='alice').first()
        if not (carol and alice):
            return
        projects = [
            ("COVID-19 Cohort A", "Plasma + serum samples from 24 donors, longitudinal study", carol.user_id),
            ("Mouse Knockout B6", "Tissue and DNA extracts from B6 knockout colony", alice.user_id),
            ("Microbiome Pilot",  "Stool and saliva samples for 16S rRNA sequencing",         alice.user_id),
        ]
        for name, desc, uid in projects:
            session.add(ProjectModel(name=name, description=desc, created_by=uid))
        print('✓ Demo projects seeded (3 projects)')


def seed_demo_samples() -> None:
    """
    Insert a rich, varied set of demo samples if the samples table is empty.

    Designed to exercise every feature in the UI:
      - Mixed projects (assigned + unassigned)
      - Expiry states: expired, expiring within 7 days, fresh, none
      - Active reservations (alice + bob)
      - Parent → child lineage chain
      - Structured location hierarchy on some samples, legacy field on others
      - All five lifecycle statuses represented
      - Multiple organisms / sample types
    """
    from database.models import SampleModel, UserModel, ProjectModel
    from datetime import date, datetime, timedelta
    with db_session() as session:
        if session.query(SampleModel).count() > 0:
            return

        users = {u.username: u.user_id for u in session.query(UserModel).all()}
        if 'alice' not in users:
            return
        alice = users['alice']
        bob   = users.get('bob', alice)
        carol = users.get('carol', alice)

        projects = {p.name: p.project_id for p in session.query(ProjectModel).all()}
        cohort_a   = projects.get("COVID-19 Cohort A")
        knockout   = projects.get("Mouse Knockout B6")
        microbiome = projects.get("Microbiome Pilot")

        today  = date.today()
        now    = datetime.utcnow()
        expired   = today - timedelta(days=5)
        soon      = today + timedelta(days=7)        # exact match for warning email
        fresh     = today + timedelta(days=180)
        long_term = today + timedelta(days=365)

        # ----- Sample dictionaries (kw-arg style for clarity) -----
        demos = [
            # 1: COVID cohort — Stored, expiring soon, structured location, reserved by alice
            dict(idx=1, year=2025,
                 sample_type='plasma', source_organism='Homo sapiens',
                 collection_date=date(2025, 2, 15), storage_location='Freezer-A1',
                 location_building='Building A', location_room='Cold Room 1',
                 location_equipment='Freezer-A', location_position='Shelf 1, Box 3, A1',
                 status='Stored', notes='Donor #007, T0 baseline', expiry_date=soon,
                 quantity=2.5, quantity_unit='ml',
                 project_id=cohort_a, created_by=alice,
                 reserved_by=alice, reserved_until=now + timedelta(days=2),
                 reservation_note="Running ELISA Thursday"),

            # 2: COVID cohort — Stored, fresh expiry
            dict(idx=2, year=2025,
                 sample_type='serum', source_organism='Homo sapiens',
                 collection_date=date(2025, 3, 1), storage_location='Freezer-A1',
                 location_building='Building A', location_room='Cold Room 1',
                 location_equipment='Freezer-A', location_position='Shelf 1, Box 3, B2',
                 status='Stored', notes='Donor #008, T0 baseline', expiry_date=fresh,
                 quantity=1.8, quantity_unit='ml',
                 project_id=cohort_a, created_by=alice),

            # 3: COVID cohort — EXPIRED, Discarded
            dict(idx=3, year=2024,
                 sample_type='plasma', source_organism='Homo sapiens',
                 collection_date=date(2024, 11, 5), storage_location='Freezer-A1',
                 status='Discarded', notes='Donor #003, exceeded shelf-life',
                 expiry_date=expired, quantity=0.0, quantity_unit='ml',
                 project_id=cohort_a, created_by=alice),

            # 4: Mouse KO — tissue, Collected, structured loc
            dict(idx=4, year=2025,
                 sample_type='tissue', source_organism='Mus musculus',
                 collection_date=date(2025, 4, 2), storage_location='Shelf-C3',
                 location_building='Building B', location_room='Tissue Lab',
                 location_equipment='Shelf-C', location_position='Bin 3',
                 status='Collected', notes='B6-KO mouse #14, liver',
                 expiry_date=long_term, quantity=120.0, quantity_unit='mg',
                 project_id=knockout, created_by=alice),

            # 5: Mouse KO — DNA EXTRACT (child of #4)
            dict(idx=5, year=2025,
                 sample_type='DNA', source_organism='Mus musculus',
                 collection_date=date(2025, 4, 4), storage_location='Fridge-B2',
                 status='Processing', notes='Extracted from tissue (parent LT-2025-0004)',
                 expiry_date=long_term, quantity=42.0, quantity_unit='ug',
                 project_id=knockout, created_by=alice,
                 parent_sample_id='LT-2025-0004'),

            # 6: Mouse KO — RNA EXTRACT (also child of #4)
            dict(idx=6, year=2025,
                 sample_type='RNA', source_organism='Mus musculus',
                 collection_date=date(2025, 4, 4), storage_location='Fridge-B2',
                 status='Processing', notes='RIN 9.2, batch 7',
                 expiry_date=today + timedelta(days=30), quantity=15.0, quantity_unit='ug',
                 project_id=knockout, created_by=alice,
                 parent_sample_id='LT-2025-0004'),

            # 7: Microbiome — saliva, Collected, no expiry, reserved by bob
            dict(idx=7, year=2025,
                 sample_type='saliva', source_organism='Homo sapiens',
                 collection_date=date(2025, 4, 10), storage_location='Freezer-A2',
                 status='Collected', notes='Subject S-12, fasted 8h',
                 quantity=2.0, quantity_unit='ml',
                 project_id=microbiome, created_by=bob,
                 reserved_by=bob, reserved_until=now + timedelta(days=5),
                 reservation_note="Pending DNA extraction next week"),

            # 8: Microbiome — stool sample
            dict(idx=8, year=2025,
                 sample_type='stool', source_organism='Homo sapiens',
                 collection_date=date(2025, 4, 12), storage_location='Freezer-A3',
                 status='Stored', notes='Subject S-12',
                 expiry_date=today + timedelta(days=90),
                 quantity=500.0, quantity_unit='mg',
                 project_id=microbiome, created_by=bob),

            # 9: Unassigned project — old blood, Consumed
            dict(idx=9, year=2024,
                 sample_type='blood', source_organism='Homo sapiens',
                 collection_date=date(2024, 12, 1), storage_location='Freezer-A1',
                 status='Consumed', notes='Used for protocol calibration',
                 expiry_date=date(2025, 6, 1), quantity=0.0, quantity_unit='ml',
                 project_id=None, created_by=alice),

            # 10: Unassigned — fresh tissue, Collected
            dict(idx=10, year=2025,
                 sample_type='tissue', source_organism='Rattus norvegicus',
                 collection_date=date(2025, 4, 18), storage_location='Shelf-C3',
                 status='Collected', notes='', expiry_date=long_term,
                 quantity=80.0, quantity_unit='mg',
                 project_id=None, created_by=alice),

            # 11: Unassigned — bacterial culture, Processing
            dict(idx=11, year=2025,
                 sample_type='culture', source_organism='Escherichia coli',
                 collection_date=date(2025, 4, 19), storage_location='Incubator-1',
                 location_building='Building A', location_room='Microbiology',
                 location_equipment='Incubator-1', location_position='Rack 2',
                 status='Processing', notes='K-12 strain, OD600=0.6',
                 quantity=10.0, quantity_unit='ml',
                 project_id=None, created_by=bob),

            # 12: Reserved by alice, expiring TODAY → triggers expiry email
            dict(idx=12, year=2025,
                 sample_type='plasma', source_organism='Homo sapiens',
                 collection_date=date(2024, 10, 20), storage_location='Freezer-A1',
                 status='Stored', notes='Donor #001, last archive vial',
                 expiry_date=today, quantity=1.0, quantity_unit='ml',
                 project_id=cohort_a, created_by=alice),
        ]

        for d in demos:
            sid = f"LT-{d['year']}-{d['idx']:04d}"
            kwargs = {k: v for k, v in d.items() if k not in ('idx', 'year')}
            session.add(SampleModel(sample_id=sid, **kwargs))

        print(f"✓ Demo samples seeded ({len(demos)} samples — projects, expiries, reservations, lineage)")
