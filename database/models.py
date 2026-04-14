"""
database/models.py
==================
STAGE 7: Data Storage Solution
--------------------------------
SQLAlchemy ORM models for LabTrack.

These classes define the relational schema and replace the in-memory
dictionaries used in Stages 3–6. Each ORM class maps directly to one
table in the ER diagram (see SRS Stage 7, Figure 6).

DB CHOICE: SQLite (dev/test) with SQLAlchemy ORM
-------------------------------------------------
- SQLite is file-based, requiring no separate server process —
  ideal for a student project and lab intranet deployment (NFR-10).
- SQLAlchemy ORM provides database-engine independence: switching to
  PostgreSQL for a production deployment requires only a one-line
  change to DATABASE_URI (NFR-11).
- SQLite's ACID compliance satisfies NFR-07 (atomic writes, no
  inconsistent records after partial failure).

SCHEMA OVERVIEW (matches ER diagram)
-------------------------------------
  USER        — accounts, roles, credentials
  SAMPLE      — biological samples and their lifecycle status
  AUDIT_ENTRY — immutable record of every status change (audit trail)

RELATIONSHIPS
-------------
  USER  1:M  SAMPLE      (a user registers many samples)
  SAMPLE 1:M AUDIT_ENTRY (a sample has many status-change records)
  USER  1:M  AUDIT_ENTRY (a user is responsible for many status changes)
"""

from datetime import datetime, date
from sqlalchemy import (
    Column, Integer, String, Boolean, DateTime, Date, Text,
    ForeignKey, CheckConstraint, Index, create_engine
)
from sqlalchemy.orm import declarative_base, relationship, validates

Base = declarative_base()

# Valid lifecycle statuses (mirrors SampleStatus enum in models/sample.py)
VALID_STATUSES = ("Collected", "Processing", "Stored", "Consumed", "Discarded")

# Valid user roles (mirrors UserFactory._ROLE_MAP keys)
VALID_ROLES = ("researcher", "technician", "admin", "viewer")


# ══════════════════════════════════════════════════════════════════════════════
# TABLE: users
# ══════════════════════════════════════════════════════════════════════════════

class UserModel(Base):
    """
    Persistent representation of a LabTrack user account.

    Corresponds to the USER entity in the ER diagram.
    Maps to the User domain class hierarchy (Researcher, LabTechnician,
    Administrator, Viewer) via UserFactory.create(role=self.role).

    Security note: password_hash stores a bcrypt hash only.
    Plain-text passwords are NEVER persisted (NFR-02).
    """

    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint(f"role IN {VALID_ROLES}", name="ck_users_role"),
        {"comment": "LabTrack user accounts and RBAC roles"},
    )

    # ── Primary key ──────────────────────────────────────────────────────
    user_id: int = Column(
        Integer, primary_key=True, autoincrement=True,
        comment="Auto-incremented surrogate key"
    )

    # ── Identity fields ───────────────────────────────────────────────────
    username: str = Column(
        String(100), unique=True, nullable=False, index=True,
        comment="Login username — must be unique across all accounts"
    )
    email: str = Column(
        String(255), unique=True, nullable=False,
        comment="Contact email — used for password recovery"
    )
    password_hash: str = Column(
        String(255), nullable=False,
        comment="bcrypt hash of the user's password — NEVER store plaintext"
    )

    # ── Role-based access control ─────────────────────────────────────────
    role: str = Column(
        String(50), nullable=False,
        comment="RBAC role: researcher | technician | admin | viewer"
    )

    # ── Account state ─────────────────────────────────────────────────────
    is_active: bool = Column(
        Boolean, nullable=False, default=True,
        comment="False = soft-deleted account (retained for audit trail)"
    )
    created_at: datetime = Column(
        DateTime, nullable=False, default=datetime.utcnow,
        comment="UTC timestamp of account creation"
    )

    # ── Relationships ─────────────────────────────────────────────────────
    samples = relationship(
        "SampleModel",
        back_populates="creator",
        foreign_keys="SampleModel.created_by",
        lazy="select",
        doc="Samples registered by this user"
    )
    audit_entries = relationship(
        "AuditEntryModel",
        back_populates="changer",
        foreign_keys="AuditEntryModel.changed_by",
        lazy="select",
        doc="Status changes performed by this user"
    )

    # ── Validation ────────────────────────────────────────────────────────
    @validates("role")
    def validate_role(self, key, value):
        if value not in VALID_ROLES:
            raise ValueError(f"Invalid role {value!r}. Must be one of {VALID_ROLES}.")
        return value

    @validates("email")
    def validate_email(self, key, value):
        if "@" not in value:
            raise ValueError(f"Invalid email address: {value!r}")
        return value.lower().strip()

    def __repr__(self) -> str:
        return f"<UserModel user_id={self.user_id} username={self.username!r} role={self.role!r}>"


# ══════════════════════════════════════════════════════════════════════════════
# TABLE: samples
# ══════════════════════════════════════════════════════════════════════════════

class SampleModel(Base):
    """
    Persistent representation of a biological sample.

    Corresponds to the SAMPLE entity in the ER diagram.
    The sample_id column uses the human-readable format LT-YYYY-NNNN
    (generated by SampleRepository) rather than a surrogate integer key,
    making sample IDs meaningful in external reports and CSV exports.

    The status column is constrained to the five lifecycle states.
    Transition validation (e.g., cannot jump from Collected to Stored)
    is enforced in the domain model (Sample.update_status) and in
    SampleService, not in the database layer.
    """

    __tablename__ = "samples"
    __table_args__ = (
        CheckConstraint(f"status IN {VALID_STATUSES}", name="ck_samples_status"),
        Index("ix_samples_status", "status"),
        Index("ix_samples_created_by", "created_by"),
        Index("ix_samples_collection_date", "collection_date"),
        {"comment": "Biological samples tracked through their lifecycle"},
    )

    # ── Primary key ──────────────────────────────────────────────────────
    sample_id: str = Column(
        String(20), primary_key=True,
        comment="Human-readable ID in format LT-YYYY-NNNN (generated by SampleRepository)"
    )

    # ── Sample metadata ───────────────────────────────────────────────────
    sample_type: str = Column(
        String(100), nullable=False,
        comment="Type of biological material (e.g., blood, tissue, DNA)"
    )
    source_organism: str = Column(
        String(200), nullable=False,
        comment="Organism of origin (e.g., Homo sapiens, Mus musculus)"
    )
    collection_date: date = Column(
        Date, nullable=False,
        comment="Date the sample was physically collected from the source"
    )
    storage_location: str = Column(
        String(200), nullable=False,
        comment="Physical or logical storage location (e.g., Freezer-A3, Shelf-B2)"
    )
    notes: str = Column(
        Text, nullable=True,
        comment="Optional free-text notes about the sample"
    )

    # ── Lifecycle state ───────────────────────────────────────────────────
    status: str = Column(
        String(50), nullable=False, default="Collected",
        comment="Current lifecycle state: Collected | Processing | Stored | Consumed | Discarded"
    )

    # ── Audit fields ──────────────────────────────────────────────────────
    created_by: int = Column(
        Integer, ForeignKey("users.user_id"), nullable=False,
        comment="FK → users.user_id — the researcher who registered this sample"
    )
    created_at: datetime = Column(
        DateTime, nullable=False, default=datetime.utcnow,
        comment="UTC timestamp of initial registration"
    )
    updated_at: datetime = Column(
        DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow,
        comment="UTC timestamp of the most recent modification"
    )

    # ── Relationships ─────────────────────────────────────────────────────
    creator = relationship(
        "UserModel",
        back_populates="samples",
        foreign_keys=[created_by],
        doc="The user who registered this sample"
    )
    audit_entries = relationship(
        "AuditEntryModel",
        back_populates="sample",
        cascade="all, delete-orphan",
        order_by="AuditEntryModel.timestamp",
        lazy="select",
        doc="Ordered list of status changes for this sample"
    )

    # ── Validation ────────────────────────────────────────────────────────
    @validates("status")
    def validate_status(self, key, value):
        if value not in VALID_STATUSES:
            raise ValueError(f"Invalid status {value!r}. Must be one of {VALID_STATUSES}.")
        return value

    @validates("sample_id")
    def validate_sample_id(self, key, value):
        import re
        if not re.match(r"^LT-\d{4}-\d{4}$", value):
            raise ValueError(f"sample_id must match LT-YYYY-NNNN, got {value!r}.")
        return value

    def __repr__(self) -> str:
        return (
            f"<SampleModel sample_id={self.sample_id!r} "
            f"type={self.sample_type!r} status={self.status!r}>"
        )


# ══════════════════════════════════════════════════════════════════════════════
# TABLE: audit_entries
# ══════════════════════════════════════════════════════════════════════════════

class AuditEntryModel(Base):
    """
    Immutable record of a single lifecycle status change.

    Corresponds to the AUDIT_ENTRY entity in the ER diagram.
    Once written, rows in this table are NEVER updated or deleted —
    they form a permanent, chronologically ordered audit trail (FR-12).

    The SQLAlchemy cascade="all, delete-orphan" on SampleModel ensures
    that if a sample is ever removed, its audit entries are also removed.
    In normal operation, samples are soft-deleted via status=Discarded,
    so this cascade is a safety net only.
    """

    __tablename__ = "audit_entries"
    __table_args__ = (
        CheckConstraint(f"old_status IN {VALID_STATUSES}", name="ck_audit_old_status"),
        CheckConstraint(f"new_status IN {VALID_STATUSES}", name="ck_audit_new_status"),
        Index("ix_audit_sample_id", "sample_id"),
        Index("ix_audit_changed_by", "changed_by"),
        Index("ix_audit_timestamp", "timestamp"),
        {"comment": "Append-only log of all sample lifecycle status changes"},
    )

    # ── Primary key ──────────────────────────────────────────────────────
    entry_id: int = Column(
        Integer, primary_key=True, autoincrement=True,
        comment="Auto-incremented surrogate key"
    )

    # ── Foreign keys ──────────────────────────────────────────────────────
    sample_id: str = Column(
        String(20), ForeignKey("samples.sample_id"), nullable=False,
        comment="FK → samples.sample_id — the sample whose status changed"
    )
    changed_by: int = Column(
        Integer, ForeignKey("users.user_id"), nullable=False,
        comment="FK → users.user_id — the user who performed the status change"
    )

    # ── Transition record ─────────────────────────────────────────────────
    old_status: str = Column(
        String(50), nullable=False,
        comment="Lifecycle status before this transition"
    )
    new_status: str = Column(
        String(50), nullable=False,
        comment="Lifecycle status after this transition"
    )
    timestamp: datetime = Column(
        DateTime, nullable=False, default=datetime.utcnow,
        comment="UTC timestamp of the status change"
    )

    # ── Relationships ─────────────────────────────────────────────────────
    sample = relationship(
        "SampleModel",
        back_populates="audit_entries",
        doc="The sample this entry belongs to"
    )
    changer = relationship(
        "UserModel",
        back_populates="audit_entries",
        foreign_keys=[changed_by],
        doc="The user who performed the status change"
    )

    def __repr__(self) -> str:
        return (
            f"<AuditEntryModel entry_id={self.entry_id} "
            f"sample={self.sample_id!r} "
            f"{self.old_status!r} → {self.new_status!r} "
            f"by user {self.changed_by}>"
        )
