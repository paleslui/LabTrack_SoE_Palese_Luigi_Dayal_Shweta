"""
repositories/sample_repository.py
----------------------------------
SQLAlchemy-backed data access layer for Sample objects.
"""

from datetime import datetime
from typing import Optional
from models.sample import Sample, SampleStatus, AuditEntry
from database.db import db_session
from database.models import SampleModel, AuditEntryModel


class SampleRepository:

    # ── ID generation ──────────────────────────────────────────────────────
    def _next_id(self) -> str:
        """Generate next LT-YYYY-NNNN ID using DB count."""
        with db_session() as session:
            count = session.query(SampleModel).count() + 1
            year = datetime.utcnow().year
            return f"LT-{year}-{count:04d}"

    # ── ORM ↔ Domain conversion ────────────────────────────────────────────
    @staticmethod
    def _to_domain(orm: SampleModel, audit_rows: list) -> Sample:
        """Convert a SampleModel + its AuditEntryModel rows into a Sample domain object."""
        col_date = orm.collection_date
        if not isinstance(col_date, datetime):
            col_date = datetime(col_date.year, col_date.month, col_date.day)

        sample = Sample(
            sample_id=orm.sample_id,
            sample_type=orm.sample_type,
            source_organism=orm.source_organism,
            collection_date=col_date,
            storage_location=orm.storage_location,
            created_by_id=orm.created_by,
            notes=orm.notes or "",
            expiry_date=orm.expiry_date,
            quantity=orm.quantity,
            quantity_unit=orm.quantity_unit,
            location_building=orm.location_building,
            location_room=orm.location_room,
            location_equipment=orm.location_equipment,
            location_position=orm.location_position,
            parent_sample_id=orm.parent_sample_id,
            project_id=orm.project_id,
            reserved_by=orm.reserved_by,
            reserved_until=orm.reserved_until,
            reservation_note=orm.reservation_note,
        )
        # Restore persisted state (bypass __init__ defaults)
        sample._status     = SampleStatus(orm.status)
        sample._created_at = orm.created_at
        sample._updated_at = orm.updated_at

        # Restore audit log
        for ae in audit_rows:
            entry = AuditEntry(
                sample_id=ae.sample_id,
                old_status=SampleStatus(ae.old_status),
                new_status=SampleStatus(ae.new_status),
                changed_by_id=ae.changed_by,
            )
            entry._timestamp = ae.timestamp
            sample._audit_log.append(entry)

        return sample

    # ── Create ─────────────────────────────────────────────────────────────
    def create(self, sample_type: str, source_organism: str,
               collection_date: datetime, storage_location: str,
               created_by_id: int, notes: str = "",
               expiry_date=None, quantity=None, quantity_unit=None,
               location_building=None, location_room=None,
               location_equipment=None, location_position=None,
               parent_sample_id=None, project_id=None) -> Sample:
        """Generate an ID, persist the sample, return the domain object."""
        with db_session() as session:
            year = datetime.utcnow().year
            count = session.query(SampleModel).count() + 1
            new_id = f"LT-{year}-{count:04d}"
            orm = SampleModel(
                sample_id=new_id,
                sample_type=sample_type,
                source_organism=source_organism,
                collection_date=collection_date,
                storage_location=storage_location,
                status="Collected",
                notes=notes,
                created_by=created_by_id,
                expiry_date=expiry_date,
                quantity=quantity,
                quantity_unit=quantity_unit,
                location_building=location_building,
                location_room=location_room,
                location_equipment=location_equipment,
                location_position=location_position,
                parent_sample_id=parent_sample_id,
                project_id=project_id,
            )
            session.add(orm)

        return Sample(
            sample_id=new_id,
            sample_type=sample_type,
            source_organism=source_organism,
            collection_date=collection_date,
            storage_location=storage_location,
            created_by_id=created_by_id,
            notes=notes,
            expiry_date=expiry_date,
            quantity=quantity,
            quantity_unit=quantity_unit,
            location_building=location_building,
            location_room=location_room,
            location_equipment=location_equipment,
            location_position=location_position,
            parent_sample_id=parent_sample_id,
            project_id=project_id,
        )

    def add(self, sample: Sample) -> None:
        """Persist an already-constructed Sample domain object."""
        with db_session() as session:
            if session.query(SampleModel).filter_by(sample_id=sample.get_sample_id()).first():
                raise ValueError(f"Sample {sample.get_sample_id()!r} already exists.")
            orm = SampleModel(
                sample_id=sample.get_sample_id(),
                sample_type=sample.get_sample_type(),
                source_organism=sample.get_source_organism(),
                collection_date=sample.get_collection_date(),
                storage_location=sample.get_storage_location(),
                status=sample.get_status().value,
                notes=sample.get_notes(),
                created_by=sample.get_created_by_id(),
            )
            session.add(orm)

    # ── Read ───────────────────────────────────────────────────────────────
    def get_by_id(self, sample_id: str) -> Optional[Sample]:
        with db_session() as session:
            orm = session.query(SampleModel).filter_by(sample_id=sample_id).first()
            if orm is None:
                return None
            audit_rows = (session.query(AuditEntryModel)
                          .filter_by(sample_id=sample_id)
                          .order_by(AuditEntryModel.timestamp)
                          .all())
            return self._to_domain(orm, audit_rows)

    def get_all(self) -> list[Sample]:
        with db_session() as session:
            rows = session.query(SampleModel).order_by(SampleModel.created_at.desc()).all()
            result = []
            for orm in rows:
                audit_rows = (session.query(AuditEntryModel)
                              .filter_by(sample_id=orm.sample_id)
                              .order_by(AuditEntryModel.timestamp)
                              .all())
                result.append(self._to_domain(orm, audit_rows))
            return result

    def find_by_status(self, status: SampleStatus) -> list[Sample]:
        with db_session() as session:
            rows = session.query(SampleModel).filter_by(status=status.value).all()
            return [self._to_domain(r, []) for r in rows]

    def find_by_type(self, sample_type: str) -> list[Sample]:
        with db_session() as session:
            rows = session.query(SampleModel).filter(
                SampleModel.sample_type.ilike(f"%{sample_type}%")
            ).all()
            return [self._to_domain(r, []) for r in rows]

    def find_by_user(self, user_id: int) -> list[Sample]:
        with db_session() as session:
            rows = session.query(SampleModel).filter_by(created_by=user_id).all()
            return [self._to_domain(r, []) for r in rows]

    # ── Update ─────────────────────────────────────────────────────────────
    def update(self, sample: Sample) -> None:
        """
        Persist status change and any new audit entries.
        Compares existing DB audit count vs domain object to save only new entries.
        """
        with db_session() as session:
            orm = session.query(SampleModel).filter_by(
                sample_id=sample.get_sample_id()
            ).first()
            if orm is None:
                raise KeyError(f"Sample {sample.get_sample_id()!r} not found.")

            orm.sample_type        = sample.get_sample_type()
            orm.source_organism    = sample.get_source_organism()
            orm.collection_date    = sample.get_collection_date()
            orm.status             = sample.get_status().value
            orm.storage_location   = sample.get_storage_location()
            orm.notes              = sample.get_notes()
            orm.expiry_date        = sample.get_expiry_date()
            orm.quantity           = sample.get_quantity()
            orm.quantity_unit      = sample.get_quantity_unit()
            orm.location_building  = sample.get_location_building()
            orm.location_room      = sample.get_location_room()
            orm.location_equipment = sample.get_location_equipment()
            orm.location_position  = sample.get_location_position()
            orm.parent_sample_id   = sample.get_parent_sample_id()
            orm.project_id         = sample.get_project_id()
            orm.reserved_by        = sample.get_reserved_by()
            orm.reserved_until     = sample.get_reserved_until()
            orm.reservation_note   = sample.get_reservation_note()
            orm.updated_at         = sample.get_updated_at()

            # Save new audit entries (those beyond what's already in DB)
            existing = (session.query(AuditEntryModel)
                        .filter_by(sample_id=sample.get_sample_id())
                        .count())
            domain_log = sample.get_audit_log()
            for entry in domain_log[existing:]:
                ae = AuditEntryModel(
                    sample_id=entry.get_sample_id(),
                    old_status=entry.get_old_status().value,
                    new_status=entry.get_new_status().value,
                    changed_by=entry.get_changed_by_id(),
                    timestamp=entry.get_timestamp(),
                )
                session.add(ae)

    # ── Delete ─────────────────────────────────────────────────────────────
    def delete(self, sample_id: str) -> None:
        with db_session() as session:
            orm = session.query(SampleModel).filter_by(sample_id=sample_id).first()
            if orm is None:
                raise KeyError(f"Sample {sample_id!r} not found.")
            session.delete(orm)

    def count(self) -> int:
        with db_session() as session:
            return session.query(SampleModel).count()

    def __repr__(self) -> str:
        return f"<SampleRepository samples={self.count()}>"
