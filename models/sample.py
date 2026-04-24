"""
models/sample.py
----------------
Defines the Sample class — the central entity of LabTrack.

Relationships:
  - Sample is composed of one AuditLog list (composition: logs cannot
    exist independently of the sample they belong to)
  - Sample has an association with User (created_by, updated_by)

Design note (Stage 5):
  The Strategy pattern will be applied to the search/filter logic
  that operates on collections of Sample objects.
"""

from datetime import datetime
from enum import Enum
from typing import Optional


class SampleStatus(Enum):
    """
    Enumeration of the valid lifecycle states for a sample.
    Transitions must follow the defined order (enforced by Sample).
    """
    COLLECTED  = "Collected"
    PROCESSING = "Processing"
    STORED     = "Stored"
    CONSUMED   = "Consumed"
    DISCARDED  = "Discarded"


# Valid forward transitions — a sample may only move to one of these next states
# All statuses are fully reversible — any status can move to any other.
# This allows correction of mistakes, including accidental Consumed or Discarded.
# The audit log records every change, so corrections are always traceable.
_ALL = [
    SampleStatus.COLLECTED,
    SampleStatus.PROCESSING,
    SampleStatus.STORED,
    SampleStatus.CONSUMED,
    SampleStatus.DISCARDED,
]

ALLOWED_TRANSITIONS: dict[SampleStatus, list[SampleStatus]] = {
    s: [t for t in _ALL if t != s]
    for s in _ALL
}


class Sample:
    """
    Represents a biological sample tracked through its full lifecycle.

    Attributes
    ----------
    _sample_id        : str      — unique ID in format LT-YYYY-NNNN
    _sample_type      : str      — type of biological material (e.g., "blood", "DNA")
    _source_organism  : str      — organism of origin (e.g., "Homo sapiens")
    _collection_date  : datetime — date the sample was physically collected
    _storage_location : str      — physical or logical storage location code
    _status           : SampleStatus — current lifecycle state
    _notes            : str      — optional free-text notes
    _created_by_id    : int      — user_id of the registering researcher
    _created_at       : datetime — database insertion timestamp
    _updated_at       : datetime — timestamp of last modification
    _audit_log        : list     — ordered list of AuditEntry objects (composition)
    """

    def __init__(
        self,
        sample_id: str,
        sample_type: str,
        source_organism: str,
        collection_date: datetime,
        storage_location: str,
        created_by_id: int,
        notes: str = "",
        expiry_date=None,
        quantity: float | None = None,
        quantity_unit: str | None = None,
        location_building: str | None = None,
        location_room: str | None = None,
        location_equipment: str | None = None,
        location_position: str | None = None,
        parent_sample_id: str | None = None,
        project_id: int | None = None,
        reserved_by: int | None = None,
        reserved_until=None,
        reservation_note: str | None = None,
    ):
        self._sample_id: str = sample_id
        self._sample_type: str = sample_type
        self._source_organism: str = source_organism
        self._collection_date: datetime = collection_date
        self._storage_location: str = storage_location
        self._status: SampleStatus = SampleStatus.COLLECTED
        self._notes: str = notes
        self._expiry_date = expiry_date           # date | None
        self._quantity: float | None = quantity
        self._quantity_unit: str | None = quantity_unit
        self._location_building: str | None = location_building
        self._location_room: str | None = location_room
        self._location_equipment: str | None = location_equipment
        self._location_position: str | None = location_position
        self._parent_sample_id: str | None = parent_sample_id
        self._project_id: int | None = project_id
        self._reserved_by: int | None = reserved_by
        self._reserved_until = reserved_until
        self._reservation_note: str | None = reservation_note
        self._created_by_id: int = created_by_id
        self._created_at: datetime = datetime.utcnow()
        self._updated_at: datetime = datetime.utcnow()
        self._audit_log: list["AuditEntry"] = []   # composition

    # ── Getters ────────────────────────────────────────────────────────────
    def get_sample_id(self) -> str:
        return self._sample_id

    def get_sample_type(self) -> str:
        return self._sample_type

    def get_source_organism(self) -> str:
        return self._source_organism

    def get_collection_date(self) -> datetime:
        return self._collection_date

    def get_storage_location(self) -> str:
        return self._storage_location

    def get_status(self) -> SampleStatus:
        return self._status

    def get_expiry_date(self):
        return self._expiry_date

    def get_quantity(self) -> float | None:
        return self._quantity

    def get_quantity_unit(self) -> str | None:
        return self._quantity_unit

    def get_location_building(self) -> str | None:
        return self._location_building

    def get_location_room(self) -> str | None:
        return self._location_room

    def get_location_equipment(self) -> str | None:
        return self._location_equipment

    def get_location_position(self) -> str | None:
        return self._location_position

    def get_full_location(self) -> str:
        """Return ' › '-joined structured location, or fall back to storage_location."""
        parts = [self._location_building, self._location_room,
                 self._location_equipment, self._location_position]
        structured = " › ".join(p for p in parts if p)
        return structured or self._storage_location or ""

    def get_parent_sample_id(self) -> str | None:
        return self._parent_sample_id

    def get_project_id(self) -> int | None:
        return self._project_id

    def get_reserved_by(self) -> int | None:
        return self._reserved_by

    def get_reserved_until(self):
        return self._reserved_until

    def get_reservation_note(self) -> str | None:
        return self._reservation_note

    def get_notes(self) -> str:
        return self._notes

    def get_created_by_id(self) -> int:
        return self._created_by_id

    def get_created_at(self) -> datetime:
        return self._created_at

    def get_updated_at(self) -> datetime:
        return self._updated_at

    def get_audit_log(self) -> list["AuditEntry"]:
        """Return a copy of the audit log to prevent external mutation."""
        return list(self._audit_log)

    # ── Setters ────────────────────────────────────────────────────────────
    def set_storage_location(self, location: str) -> None:
        """Update the physical or logical storage location."""
        self._storage_location = location
        self._updated_at = datetime.utcnow()

    def set_notes(self, notes: str) -> None:
        """Replace the free-text notes field."""
        self._notes = notes
        self._updated_at = datetime.utcnow()

    # ── Business logic ────────────────────────────────────────────────────
    def update_status(self, new_status: SampleStatus, changed_by_id: int) -> None:
        """
        Transition the sample to a new lifecycle status.

        Only allows transitions defined in ALLOWED_TRANSITIONS.
        Appends an AuditEntry to the internal audit log on success.

        Parameters
        ----------
        new_status    : SampleStatus — the target lifecycle state
        changed_by_id : int          — user_id of the user making the change

        Raises
        ------
        ValueError — if the transition is not permitted
        """
        allowed = ALLOWED_TRANSITIONS.get(self._status, [])
        if new_status not in allowed:
            raise ValueError(
                f"Invalid transition: {self._status.value} → {new_status.value}. "
                f"Allowed: {[s.value for s in allowed]}"
            )

        entry = AuditEntry(
            sample_id=self._sample_id,
            old_status=self._status,
            new_status=new_status,
            changed_by_id=changed_by_id,
        )
        self._audit_log.append(entry)
        self._status = new_status
        self._updated_at = datetime.utcnow()

    def is_terminal(self) -> bool:
        """Return True if the sample has reached a terminal state."""
        return self._status in (SampleStatus.CONSUMED, SampleStatus.DISCARDED)

    def to_dict(self) -> dict:
        """Serialize the sample to a plain dictionary (for API responses)."""
        return {
            "sample_id":        self._sample_id,
            "sample_type":      self._sample_type,
            "source_organism":  self._source_organism,
            "collection_date":  self._collection_date.strftime("%Y-%m-%d"),
            "storage_location": self._storage_location,
            "status":           self._status.value,
            "notes":            self._notes,
            "expiry_date":      self._expiry_date.strftime("%Y-%m-%d") if self._expiry_date else None,
            "quantity":         self._quantity,
            "quantity_unit":    self._quantity_unit,
            "location_building":  self._location_building,
            "location_room":      self._location_room,
            "location_equipment": self._location_equipment,
            "location_position":  self._location_position,
            "parent_sample_id":   self._parent_sample_id,
            "project_id":         self._project_id,
            "reserved_by":        self._reserved_by,
            "reserved_until":     self._reserved_until.isoformat() if self._reserved_until else None,
            "reservation_note":   self._reservation_note,
            "created_by_id":    self._created_by_id,
            "created_at":       self._created_at.isoformat(),
            "updated_at":       self._updated_at.isoformat(),
        }

    def __repr__(self) -> str:
        return (
            f"<Sample id={self._sample_id!r} type={self._sample_type!r} "
            f"status={self._status.value!r}>"
        )


# ══════════════════════════════════════════════════════════════════════════════
# AuditEntry — composed by Sample (cannot exist without a parent Sample)
# ══════════════════════════════════════════════════════════════════════════════

class AuditEntry:
    """
    Records a single lifecycle status change for a sample.

    Relationship: Composition with Sample.
    An AuditEntry is created inside Sample.update_status() and is never
    instantiated independently in the application layer.

    Attributes
    ----------
    _sample_id    : str          — FK reference to the parent sample
    _old_status   : SampleStatus — status before the transition
    _new_status   : SampleStatus — status after the transition
    _changed_by_id: int          — user_id of the actor
    _timestamp    : datetime     — UTC time of the transition
    """

    def __init__(
        self,
        sample_id: str,
        old_status: SampleStatus,
        new_status: SampleStatus,
        changed_by_id: int,
    ):
        self._sample_id: str = sample_id
        self._old_status: SampleStatus = old_status
        self._new_status: SampleStatus = new_status
        self._changed_by_id: int = changed_by_id
        self._timestamp: datetime = datetime.utcnow()

    def get_sample_id(self) -> str:
        return self._sample_id

    def get_old_status(self) -> SampleStatus:
        return self._old_status

    def get_new_status(self) -> SampleStatus:
        return self._new_status

    def get_changed_by_id(self) -> int:
        return self._changed_by_id

    def get_timestamp(self) -> datetime:
        return self._timestamp

    def to_dict(self) -> dict:
        return {
            "sample_id":     self._sample_id,
            "old_status":    self._old_status.value,
            "new_status":    self._new_status.value,
            "changed_by_id": self._changed_by_id,
            "timestamp":     self._timestamp.isoformat(),
        }

    def __repr__(self) -> str:
        return (
            f"<AuditEntry sample={self._sample_id!r} "
            f"{self._old_status.value} → {self._new_status.value} "
            f"by user {self._changed_by_id}>"
        )
